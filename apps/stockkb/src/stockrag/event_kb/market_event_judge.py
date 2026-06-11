from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

import requests

from .config import EventKBSettings
from .ids import stable_id


_SYSTEM_PROMPT = """你是A股市场事件归并仲裁器。
你的任务是判断两个事件是否描述的是同一个底层市场事件。

判断原则：
1. 只有在两个事件描述的是同一个底层事实、同一个来源事实或同一个市场催化时，才返回 same_event=true
2. 如果只是主题相似、行业相近、同一天但事实不同，必须返回 same_event=false
3. 对个股事件要非常谨慎，不同公司的不同公告/订单/项目，通常不是同一个事件
4. 对行业事件，如果来源、关键数值、日期、证据事实一致，即使表述不同，也可以视为同一事件

输出 JSON：
{
  "same_event": true,
  "confidence": 0.0,
  "reason": "一句话说明判断依据"
}

只能返回 JSON，不要解释。"""


@dataclass(slots=True)
class MarketEventJudgeDecision:
    same_event: bool
    confidence: float
    reason: str
    merge_method: str


class MarketEventJudge:
    def __init__(
        self,
        kb_settings: EventKBSettings,
        *,
        load_cache: Callable[[str], dict[str, Any] | None],
        save_cache: Callable[[dict[str, Any]], None],
    ) -> None:
        self.kb_settings = kb_settings
        self._load_cache = load_cache
        self._save_cache = save_cache
        self._judge_count = 0

    def judge(self, left: dict[str, Any], right: dict[str, Any]) -> MarketEventJudgeDecision | None:
        if not self._is_enabled():
            return None
        if self._judge_count >= self.kb_settings.llm_merge_max_judges:
            return None
        pair_key = self._pair_key(left, right)
        cached = self._load_cache(pair_key)
        if cached is not None:
            return MarketEventJudgeDecision(
                same_event=bool(cached.get("same_event", False)),
                confidence=float(cached.get("confidence") or 0.0),
                reason=str(cached.get("reason") or ""),
                merge_method="llm",
            )

        payload = self._build_payload(left, right)
        parsed = self._call_llm(payload)
        confidence = self._coerce_confidence(parsed.get("confidence"))
        decision = MarketEventJudgeDecision(
            same_event=bool(parsed.get("same_event", False)) and confidence >= self.kb_settings.llm_merge_confidence_threshold,
            confidence=confidence,
            reason=str(parsed.get("reason") or ""),
            merge_method="llm",
        )
        self._save_cache(
            {
                "pair_key": pair_key,
                "left_event_id": str(left.get("event_id") or ""),
                "right_event_id": str(right.get("event_id") or ""),
                "same_event": decision.same_event,
                "confidence": decision.confidence,
                "reason": decision.reason,
                "model": self.kb_settings.llm_merge_model,
                "prompt_version": self.kb_settings.llm_merge_prompt_version,
            }
        )
        self._judge_count += 1
        return decision

    def _is_enabled(self) -> bool:
        return bool(
            self.kb_settings.llm_merge_enabled
            and self.kb_settings.llm_merge_base_url
            and self.kb_settings.llm_merge_model
        )

    def _pair_key(self, left: dict[str, Any], right: dict[str, Any]) -> str:
        event_ids = sorted(
            [
                str(left.get("event_id") or ""),
                str(right.get("event_id") or ""),
            ]
        )
        return stable_id(
            "market-judge",
            event_ids[0],
            event_ids[1],
            self.kb_settings.llm_merge_model,
            self.kb_settings.llm_merge_prompt_version,
        )

    def _build_payload(self, left: dict[str, Any], right: dict[str, Any]) -> str:
        return json.dumps(
            {
                "left_event": self._event_payload(left),
                "right_event": self._event_payload(right),
            },
            ensure_ascii=False,
            indent=2,
        )

    def _event_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": str(row.get("event_id") or ""),
            "event_type": str(row.get("event_type") or ""),
            "event_scope": str(row.get("event_scope") or ""),
            "event_name": str(row.get("event_name") or ""),
            "event_time_text": str(row.get("event_time_text") or ""),
            "event_time_normalized": str(row.get("event_time_normalized") or ""),
            "event_content": str(row.get("event_content") or ""),
            "source_name": str(row.get("source_name") or ""),
            "source_url": str(row.get("source_url") or ""),
            "stock_code": str(row.get("stock_code") or ""),
            "stock_name": str(row.get("stock_name") or ""),
            "affected_stocks": row.get("affected_stocks") or [],
            "affected_industries": row.get("affected_industries") or [],
            "affected_themes": row.get("affected_themes") or [],
            "evidence_text": str(row.get("evidence_text") or ""),
            "report_title": str(row.get("report_title") or ""),
            "report_date": str(row.get("report_date") or ""),
        }

    def _call_llm(self, payload: str) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.kb_settings.llm_merge_api_key:
            headers["Authorization"] = f"Bearer {self.kb_settings.llm_merge_api_key}"
        response = requests.post(
            self.kb_settings.llm_merge_base_url.rstrip("/") + "/chat/completions",
            headers=headers,
            json={
                "model": self.kb_settings.llm_merge_model,
                "temperature": self.kb_settings.llm_merge_temperature,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": payload},
                ],
            },
            timeout=self.kb_settings.llm_merge_timeout,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content.strip())
        return parsed if isinstance(parsed, dict) else {}

    def _coerce_confidence(self, value: Any) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, numeric))
