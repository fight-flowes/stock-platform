from __future__ import annotations

import json
import time
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.settings import (
    VIBE_TRADING_API_BASE_URL,
    VIBE_TRADING_API_KEY,
    VIBE_TRADING_API_TIMEOUT,
)


class VibeTradingProxyError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int = 502,
        upstream_status: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.upstream_status = upstream_status


class VibeTradingProxyService:
    @classmethod
    def create_session(cls, *, title: str = "Vibe-Trading") -> Dict[str, Any]:
        clean_title = (title or "").strip() or "Vibe-Trading"
        payload = cls._request_json(
            "POST",
            "/sessions",
            {"title": clean_title},
        )
        return {
            "session_id": str(payload.get("session_id") or ""),
            "title": str(payload.get("title") or clean_title),
            "status": str(payload.get("status") or "idle"),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
        }

    @classmethod
    def list_sessions(cls, *, limit: int = 50) -> list[dict[str, Any]]:
        payload = cls._request_json(
            "GET",
            "/sessions",
            query={"limit": max(1, min(int(limit or 50), 200))},
        )
        if not isinstance(payload, list):
            raise VibeTradingProxyError("上游会话列表格式异常", http_status=502)

        items: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            items.append(
                {
                    "session_id": str(item.get("session_id") or ""),
                    "title": str(item.get("title") or ""),
                    "status": str(item.get("status") or "idle"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                    "last_attempt_id": item.get("last_attempt_id"),
                }
            )
        return items

    @classmethod
    def get_session(cls, *, session_id: str) -> Optional[Dict[str, Any]]:
        """Probe whether a session still exists upstream.

        Returns the session metadata dict on 200, or ``None`` on 404 (so the
        caller can fall back to creating a new one). Other HTTP errors propagate
        as ``VibeTradingProxyError`` so genuine outages are not silently masked.
        """
        clean_session_id = cls._require_session_id(session_id)
        try:
            payload = cls._request_json("GET", f"/sessions/{clean_session_id}")
        except VibeTradingProxyError as exc:
            if exc.upstream_status == 404:
                return None
            raise
        if not isinstance(payload, dict):
            return None
        return payload

    @classmethod
    def delete_session(cls, *, session_id: str) -> bool:
        """Delete a session upstream. Returns True if the upstream removed it
        (or it was already gone), False only on transient failures the caller
        may want to log and retry."""
        clean_session_id = cls._require_session_id(session_id)
        try:
            cls._request_json("DELETE", f"/sessions/{clean_session_id}")
            return True
        except VibeTradingProxyError as exc:
            if exc.upstream_status == 404:
                return True
            raise

    @classmethod
    def get_messages(cls, *, session_id: str) -> list[dict[str, Any]]:
        clean_session_id = cls._require_session_id(session_id)
        payload = cls._request_json(
            "GET",
            f"/sessions/{clean_session_id}/messages",
        )
        if not isinstance(payload, list):
            raise VibeTradingProxyError("上游消息格式异常", http_status=502)
        return [item for item in payload if isinstance(item, dict)]

    @classmethod
    def send_message(cls, *, session_id: str, content: str) -> Dict[str, Any]:
        clean_session_id = cls._require_session_id(session_id)
        clean_content = (content or "").strip()
        if not clean_content:
            raise ValueError("content 不能为空")

        payload = cls._request_json(
            "POST",
            f"/sessions/{clean_session_id}/messages",
            {"content": clean_content},
        )
        if not isinstance(payload, dict):
            raise VibeTradingProxyError("上游响应格式异常", http_status=502)
        return payload

    @classmethod
    def cancel_session(cls, *, session_id: str) -> Dict[str, Any]:
        clean_session_id = cls._require_session_id(session_id)
        payload = cls._request_json(
            "POST",
            f"/sessions/{clean_session_id}/cancel",
        )
        if not isinstance(payload, dict):
            raise VibeTradingProxyError("上游取消响应格式异常", http_status=502)
        return payload

    @classmethod
    def stream_events(cls, *, session_id: str) -> Iterable[str]:
        clean_session_id = cls._require_session_id(session_id)
        req = cls._build_request(
            "GET",
            f"/sessions/{clean_session_id}/events",
            accept="text/event-stream",
        )

        try:
            with urlopen(req, timeout=VIBE_TRADING_API_TIMEOUT) as resp:
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    yield line.decode("utf-8", errors="replace")
        except HTTPError as exc:
            detail = cls._read_error_body(exc)
            raise VibeTradingProxyError(
                detail or f"Vibe-Trading SSE 请求失败: HTTP {exc.code}",
                http_status=502,
                upstream_status=exc.code,
            ) from exc
        except URLError as exc:
            raise VibeTradingProxyError(
                f"无法连接到 Vibe-Trading: {exc.reason}",
                http_status=502,
            ) from exc
        except TimeoutError as exc:
            raise VibeTradingProxyError(
                "连接 Vibe-Trading SSE 超时",
                http_status=504,
            ) from exc
        except Exception as exc:  # pragma: no cover - network edge path
            raise VibeTradingProxyError(
                f"Vibe-Trading SSE 代理异常: {exc}",
                http_status=502,
            ) from exc

    @classmethod
    def wait_for_completion(cls, *, session_id: str, timeout_seconds: int = 90) -> Dict[str, Any]:
        deadline = time.monotonic() + max(1, int(timeout_seconds or 90))
        current_event = ""
        data_lines: list[str] = []

        for raw_line in cls.stream_events(session_id=session_id):
            if time.monotonic() > deadline:
                raise VibeTradingProxyError("等待 Vibe-Trading 执行完成超时", http_status=504)

            line = raw_line.rstrip("\r\n")
            if not line:
                if current_event in {"attempt.completed", "attempt.failed"}:
                    payload = cls._parse_sse_data(data_lines)
                    return {
                        "event": current_event,
                        "payload": payload,
                        "completed": current_event == "attempt.completed",
                    }
                current_event = ""
                data_lines = []
                continue

            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue
            if line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].lstrip())

        raise VibeTradingProxyError("Vibe-Trading 事件流已结束，但未收到完成信号", http_status=502)

    @classmethod
    def _request_json(
        cls,
        method: str,
        path: str,
        body: Optional[dict[str, Any]] = None,
        *,
        query: Optional[dict[str, Any]] = None,
    ) -> Any:
        req = cls._build_request(
            method,
            path,
            body=body,
            query=query,
            accept="application/json",
        )

        try:
            with urlopen(req, timeout=VIBE_TRADING_API_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", errors="replace").strip()
        except HTTPError as exc:
            detail = cls._read_error_body(exc)
            raise VibeTradingProxyError(
                detail or f"Vibe-Trading 请求失败: HTTP {exc.code}",
                http_status=502,
                upstream_status=exc.code,
            ) from exc
        except URLError as exc:
            raise VibeTradingProxyError(
                f"无法连接到 Vibe-Trading: {exc.reason}",
                http_status=502,
            ) from exc
        except TimeoutError as exc:
            raise VibeTradingProxyError(
                "请求 Vibe-Trading 超时",
                http_status=504,
            ) from exc

        if not raw:
            return {}

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VibeTradingProxyError(
                "Vibe-Trading 返回了无法解析的 JSON",
                http_status=502,
            ) from exc

    @classmethod
    def _build_request(
        cls,
        method: str,
        path: str,
        *,
        body: Optional[dict[str, Any]] = None,
        query: Optional[dict[str, Any]] = None,
        accept: str = "application/json",
    ) -> Request:
        url = cls._build_url(path, query=query)
        headers = {"Accept": accept}
        data = None

        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")

        api_key = (VIBE_TRADING_API_KEY or "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        return Request(url, data=data, headers=headers, method=method)

    @classmethod
    def _build_url(
        cls,
        path: str,
        *,
        query: Optional[dict[str, Any]] = None,
    ) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        url = f"{VIBE_TRADING_API_BASE_URL}{clean_path}"
        clean_query = {
            str(k): str(v)
            for k, v in (query or {}).items()
            if v is not None and str(v).strip() != ""
        }
        if clean_query:
            url = f"{url}?{urlencode(clean_query)}"
        return url

    @classmethod
    def _read_error_body(cls, exc: HTTPError) -> str:
        try:
            raw = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            return ""

        if not raw:
            return ""

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return raw

        if isinstance(payload, dict):
            return str(payload.get("detail") or payload.get("message") or raw)
        return raw

    @staticmethod
    def _parse_sse_data(lines: list[str]) -> Dict[str, Any]:
        if not lines:
            return {}
        raw = "\n".join(lines).strip()
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
        return payload if isinstance(payload, dict) else {"raw": raw}

    @staticmethod
    def _require_session_id(session_id: str) -> str:
        clean_session_id = (session_id or "").strip()
        if not clean_session_id:
            raise ValueError("session_id 不能为空")
        return clean_session_id
