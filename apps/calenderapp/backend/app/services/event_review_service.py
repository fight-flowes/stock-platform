from __future__ import annotations

import json
import logging
import re
import threading
from typing import Any

from app.services.stockkb_proxy_service import StockkbProxyService
from app.services.vibe_trading_proxy_service import VibeTradingProxyError, VibeTradingProxyService


class EventReviewServiceError(RuntimeError):
    pass


logger = logging.getLogger(__name__)


class EventReviewService:
    _active_jobs_lock = threading.Lock()
    _active_jobs: dict[str, threading.Thread] = {}

    @classmethod
    def get_review(cls, event_key: str) -> dict[str, Any]:
        return StockkbProxyService.get_market_event_review(event_key)

    @classmethod
    def run_review(cls, event_key: str, *, force: bool = False) -> dict[str, Any]:
        existing = StockkbProxyService.get_market_event_review(event_key)
        if (
            not force
            and existing.get("found", False)
            and isinstance(existing.get("review"), dict)
            and str(existing["review"].get("review_status") or "") == "completed"
        ):
            existing["source"] = "cache"
            return existing

        pending = StockkbProxyService.run_market_event_review(event_key)
        if not pending.get("found", False):
            raise EventReviewServiceError(f"市场事件不存在: {event_key}")

        event = pending.get("event")
        if not isinstance(event, dict):
            detail = StockkbProxyService.get_market_event_detail(event_key)
            if not detail.get("found", False):
                raise EventReviewServiceError(f"加载市场事件详情失败: {event_key}")
            event = detail.get("event") or {}

        prompt = cls._build_review_prompt(event)
        session_id = cls._acquire_session_id(event_key, existing)

        StockkbProxyService.put_market_event_review(
            event_key,
            {
                "review_status": "pending",
                "review_version": "event-review-mcp.v1",
                "review_source": "vibe-trading:event-review-mcp",
                "source_snapshot": event,
                "vibe_session_id": session_id,
            },
        )

        started = cls._enqueue_review_job(
            event_key=event_key,
            event_snapshot=event,
            prompt=prompt,
            session_id=session_id,
        )
        stored = StockkbProxyService.get_market_event_review(event_key)
        stored["event"] = event
        stored["source"] = "queued" if started else "running"
        stored["session_id"] = session_id
        return stored

    @classmethod
    def _acquire_session_id(cls, event_key: str, existing: dict[str, Any]) -> str:
        """Reuse the Vibe-Trading session previously bound to this event when
        possible; create a new one only when there is none or the upstream
        session has been garbage-collected. This keeps ``Event Review *``
        sessions at most 1-per-event instead of 1-per-attempt.
        """
        existing_review = existing.get("review") if isinstance(existing.get("review"), dict) else {}
        previous_session_id = str(existing_review.get("vibe_session_id") or "").strip()

        if previous_session_id:
            try:
                if VibeTradingProxyService.get_session(session_id=previous_session_id) is not None:
                    return previous_session_id
            except VibeTradingProxyError:
                # Probe failed for a non-404 reason — fall through to creating a
                # fresh session rather than aborting the whole review.
                pass

        session = VibeTradingProxyService.create_session(title=f"Event Review {event_key}")
        session_id = str(session.get("session_id") or "").strip()
        if not session_id:
            raise EventReviewServiceError("Vibe-Trading 未返回有效 session_id")
        return session_id

    @classmethod
    def _enqueue_review_job(
        cls,
        *,
        event_key: str,
        event_snapshot: dict[str, Any],
        prompt: str,
        session_id: str,
    ) -> bool:
        with cls._active_jobs_lock:
            existing_thread = cls._active_jobs.get(event_key)
            if existing_thread is not None and existing_thread.is_alive():
                return False

            thread = threading.Thread(
                target=cls._run_review_job,
                kwargs={
                    "event_key": event_key,
                    "event_snapshot": event_snapshot,
                    "prompt": prompt,
                    "session_id": session_id,
                },
                name=f"event-review-{event_key}",
                daemon=True,
            )
            cls._active_jobs[event_key] = thread
            thread.start()
            return True

    @classmethod
    def _run_review_job(
        cls,
        *,
        event_key: str,
        event_snapshot: dict[str, Any],
        prompt: str,
        session_id: str,
    ) -> None:
        try:
            logger.info("event review job started: event_key=%s session_id=%s", event_key, session_id)
            cls._execute_review_job(
                event_key=event_key,
                event_snapshot=event_snapshot,
                prompt=prompt,
                session_id=session_id,
            )
            logger.info("event review job finished: event_key=%s session_id=%s", event_key, session_id)
        except Exception as exc:  # pragma: no cover - safety net
            error_text = str(exc).strip() or "事件核查执行失败"
            logger.exception(
                "event review job crashed: event_key=%s session_id=%s",
                event_key,
                session_id,
            )
            try:
                cls._save_failed_review(
                    event_key,
                    event_snapshot,
                    error_text,
                    session_id=session_id,
                )
            except Exception:  # pragma: no cover - safety net
                logger.exception(
                    "event review failure could not be persisted: event_key=%s session_id=%s",
                    event_key,
                    session_id,
                )
        finally:
            with cls._active_jobs_lock:
                cls._active_jobs.pop(event_key, None)

    @classmethod
    def _execute_review_job(
        cls,
        *,
        event_key: str,
        event_snapshot: dict[str, Any],
        prompt: str,
        session_id: str,
    ) -> None:
        VibeTradingProxyService.send_message(session_id=session_id, content=prompt)
        completion = VibeTradingProxyService.wait_for_completion(session_id=session_id, timeout_seconds=90)
        if not completion.get("completed", False):
            error_text = str(completion.get("payload", {}).get("error") or "事件核查执行失败").strip()
            cls._save_failed_review(event_key, event_snapshot, error_text, session_id=session_id)
            return

        messages = VibeTradingProxyService.get_messages(session_id=session_id)
        review_payload = cls._extract_review_json(messages)
        normalized_payload = cls._normalize_review_payload(review_payload)
        cls._save_completed_review(event_key, event_snapshot, normalized_payload, session_id=session_id)

    @classmethod
    def _build_review_prompt(cls, event: dict[str, Any]) -> str:
        source_reports = event.get("source_reports") if isinstance(event.get("source_reports"), list) else []
        primary_source = source_reports[0] if source_reports and isinstance(source_reports[0], dict) else {}

        payload = {
            "event_name": str(event.get("event_name") or ""),
            "event_time_text": str(event.get("event_time_text") or ""),
            "event_content": str(event.get("event_content") or ""),
            "source_name": str(primary_source.get("source_name") or ""),
            "source_url": str(primary_source.get("source_url") or ""),
        }
        payload_text = json.dumps(payload, ensure_ascii=False)
        return (
            "请调用 mcp_event_review_verify_event，对下面的事件做真实性与时间核查。\n"
            "要求：\n"
            "1. 优先调用 mcp_event_review_verify_event。\n"
            "2. 最终回复只能返回该工具输出的 JSON 对象本身。\n"
            "3. 不要输出 Markdown，不要补充解释，不要扩写无证据支持的内容。\n"
            f"事件输入：{payload_text}"
        )

    @classmethod
    def _extract_review_json(cls, messages: list[dict[str, Any]]) -> dict[str, Any]:
        assistant_messages = [
            item for item in messages
            if str(item.get("role") or "").strip().lower() == "assistant" and str(item.get("content") or "").strip()
        ]
        for item in reversed(assistant_messages):
            parsed = cls._extract_json_object(str(item.get("content") or ""))
            if parsed and isinstance(parsed.get("review"), dict):
                return parsed
            data = parsed.get("data") if isinstance(parsed, dict) else None
            if isinstance(data, dict) and isinstance(data.get("review"), dict):
                return data
        raise EventReviewServiceError("未能从 Vibe-Trading 返回中提取核查 JSON")

    @classmethod
    def _extract_json_object(cls, text: str) -> dict[str, Any] | None:
        raw = (text or "").strip()
        if not raw:
            return None

        candidates = [raw]
        fence_match = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.S)
        candidates.extend(fence_match)

        if "{" in raw and "}" in raw:
            start = raw.find("{")
            end = raw.rfind("}")
            if end > start:
                candidates.append(raw[start:end + 1])

        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload

        # Repair-and-retry. The LLM that forwards the MCP tool output to the
        # caller occasionally rewrites Chinese full-width quotes (e.g. ‘“’/‘”’)
        # back into ASCII double quotes. When the original payload contained
        # those characters inside string values (typical Brave headlines like
        # ``"再涨20%！覆铜板龙头\"建滔集团\"发布..."``), the rewrite produces
        # bare ASCII ``"`` *inside* a JSON string value — collapsing the JSON
        # at the first such position and triggering ``Expecting ',' delimiter``
        # in the loop above.
        #
        # The repair is a state-machine pass over each candidate: we track
        # whether we are inside a JSON string and, on encountering a ``"``,
        # peek ahead for the next non-whitespace character. If it isn't one of
        # ``,]}:``, the quote is treated as a stray inner quote and escaped to
        # ``\"`` before re-parsing. False positives would only happen on
        # legitimate JSON whose string values end immediately before another
        # string value with no separator, which is malformed anyway.
        for candidate in candidates:
            repaired = cls._repair_jsonish_inner_quotes(candidate)
            if repaired is None or repaired == candidate:
                continue
            try:
                payload = json.loads(repaired)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return None

    @classmethod
    def _repair_jsonish_inner_quotes(cls, raw: str) -> str | None:
        """Escape stray ASCII ``"`` characters that appear *inside* JSON
        string values. Returns the repaired string, or ``None`` when the
        input is too short to be worth scanning.

        The state machine is intentionally conservative — it never inserts,
        moves or deletes anything other than a single backslash before a
        suspect ``"``. Inputs that are already valid JSON pass through with
        zero edits (and the caller can detect that via ``repaired == raw``).
        """
        if not raw or len(raw) < 2:
            return None

        out: list[str] = []
        in_string = False
        i = 0
        n = len(raw)
        while i < n:
            ch = raw[i]
            if not in_string:
                out.append(ch)
                if ch == '"':
                    in_string = True
                i += 1
                continue

            # Inside a string.
            if ch == "\\":
                # Preserve the escape sequence verbatim (\", \\, \n, \uXXXX, ...)
                out.append(ch)
                if i + 1 < n:
                    out.append(raw[i + 1])
                    i += 2
                else:
                    i += 1
                continue

            if ch != '"':
                out.append(ch)
                i += 1
                continue

            # ch is an unescaped ``"`` while we believe we're inside a string.
            # Peek the next non-whitespace character to decide whether this is
            # a real string terminator or a stray inner quote.
            j = i + 1
            while j < n and raw[j] in " \t\r\n":
                j += 1
            next_ch = raw[j] if j < n else ""
            if next_ch in {",", "]", "}", ":"} or j == n:
                # Real terminator.
                out.append(ch)
                in_string = False
                i += 1
            else:
                # Stray inner quote — escape it.
                out.append("\\")
                out.append(ch)
                i += 1

        return "".join(out)

    @classmethod
    def _normalize_review_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
        next_action = payload.get("next_action") if isinstance(payload.get("next_action"), list) else []
        debug = payload.get("debug") if isinstance(payload.get("debug"), dict) else {}
        supporting = evidence.get("supporting") if isinstance(evidence.get("supporting"), list) else []
        key_items = evidence.get("key_items") if isinstance(evidence.get("key_items"), list) else []
        missing = evidence.get("missing") if isinstance(evidence.get("missing"), list) else []
        if supporting and not key_items:
            key_items = list(supporting)
        return {
            "status": str(payload.get("status") or "ok"),
            "review": {
                "event_truth": str(review.get("event_truth") or "unverified"),
                "time_truth": str(review.get("time_truth") or "time_unknown"),
                "content_truth": str(review.get("content_truth") or "unsupported"),
                "disposition": str(review.get("disposition") or "needs_review"),
                "confidence": float(review.get("confidence") or 0.0),
                "headline": str(review.get("headline") or ""),
                "summary": str(review.get("summary") or ""),
            },
            "evidence": {
                "supporting": supporting,
                "key_items": key_items,
                "missing": missing,
            },
            "next_action": [str(item) for item in next_action if str(item).strip()],
            "debug": debug,
        }

    @classmethod
    def _save_completed_review(
        cls,
        event_key: str,
        event_snapshot: dict[str, Any],
        review_payload: dict[str, Any],
        *,
        session_id: str = "",
    ) -> dict[str, Any]:
        review = review_payload.get("review") if isinstance(review_payload.get("review"), dict) else {}
        return StockkbProxyService.put_market_event_review(
            event_key,
            {
                "review_status": "completed",
                "review_version": "event-review-mcp.v1",
                "review_source": "vibe-trading:event-review-mcp",
                "event_truth": str(review.get("event_truth") or ""),
                "time_truth": str(review.get("time_truth") or ""),
                "content_truth": str(review.get("content_truth") or ""),
                "disposition": str(review.get("disposition") or ""),
                "confidence": float(review.get("confidence") or 0.0),
                "headline": str(review.get("headline") or ""),
                "summary": str(review.get("summary") or ""),
                "review_payload": review_payload,
                "source_snapshot": event_snapshot,
                "vibe_session_id": session_id,
                "error_message": "",
            },
        )

    @classmethod
    def _save_failed_review(
        cls,
        event_key: str,
        event_snapshot: dict[str, Any],
        error_message: str,
        *,
        session_id: str = "",
    ) -> dict[str, Any]:
        return StockkbProxyService.put_market_event_review(
            event_key,
            {
                "review_status": "failed",
                "review_version": "event-review-mcp.v1",
                "review_source": "vibe-trading:event-review-mcp",
                "event_truth": "",
                "time_truth": "",
                "content_truth": "",
                "disposition": "needs_review",
                "confidence": 0.0,
                "headline": "",
                "summary": "",
                "review_payload": {},
                "source_snapshot": event_snapshot,
                "vibe_session_id": session_id,
                "error_message": error_message,
            },
        )
