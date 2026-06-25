from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ...config import Settings
from ...metadata import extract_report_metadata
from ...text_normalizer import normalize_text_for_retrieval
from ..config import EventKBSettings
from ..extractors import extract_basic_info_fields, extract_core_logic, extract_simple_events_and_risk
from ..ids import stable_id
from ..parsers import parse_markdown_document
from ..schemas import SimpleEventCandidate, SimpleEventRecord, SimpleReportBundle, SimpleReportRecord, SimpleReportSummary


_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_LOW_SIGNAL_CORE_LOGIC_RE = re.compile(
    r"^(?:驱动类型\s*[:：]\s*)?(?:板块|事件|情绪|资金|消息|个股|题材)(?:驱动)?型?$"
)


def build_simple_report_bundle(
    report_path: Path,
    settings: Settings,
    *,
    kb_settings: EventKBSettings,
    source_path: str | None = None,
    source_name: str | None = None,
    parent_name: str | None = None,
) -> SimpleReportBundle:
    raw_text = report_path.read_text(encoding="utf-8")
    normalized_text, _ = normalize_text_for_retrieval(raw_text)
    metadata = extract_report_metadata(
        report_path,
        raw_text,
        source_path=source_path,
        source_name=source_name,
        parent_name=parent_name,
    )
    document = parse_markdown_document(normalized_text)
    metadata.update(
        {
            key: value
            for key, value in extract_basic_info_fields(document).items()
            if value
        }
    )
    rule_core_logic = extract_core_logic(document)
    report_id = stable_id(metadata["source_path"])
    now = datetime.now(timezone.utc).isoformat()
    simple_events, report_summary = extract_simple_events_and_risk(
        document,
        str(metadata.get("report_date", "")),
        kb_settings,
        primary_stock_code=str(metadata.get("stock_code", "")),
        primary_stock_name=str(metadata.get("stock_name", "")),
    )
    core_logic = _resolve_core_logic(
        llm_core_logic=report_summary.core_logic,
        rule_core_logic=rule_core_logic,
        events=simple_events,
    )
    report = SimpleReportRecord(
        report_id=report_id,
        source_path=str(metadata["source_path"]),
        source_name=str(metadata["source_name"]),
        report_title=str(metadata["report_title"]),
        stock_code=str(metadata.get("stock_code", "")),
        stock_name=str(metadata.get("stock_name", "")),
        report_date=str(metadata.get("report_date", "")),
        core_logic=core_logic,
        risk_summary=report_summary.risk_summary,
        created_at=now,
        updated_at=now,
    )
    events = [
        SimpleEventRecord(
            event_id=stable_id(
                report_id,
                item.canonical_event_key or item.event_name,
            ),
            report_id=report_id,
            event_name=item.event_name,
            event_time_text=item.event_time_text,
            event_time_normalized=item.event_time_normalized or _normalize_date_text(item.event_time_text),
            event_content=item.event_content,
            canonical_event_key=item.canonical_event_key,
            event_type=item.event_type,
            event_scope=item.event_scope,
            scope_reason=item.scope_reason,
            source_name=item.source_name,
            source_url=item.source_url,
            affected_stock_codes_json=json.dumps(
                [
                    {"stock_code": stock.stock_code, "stock_name": stock.stock_name}
                    for stock in item.affected_stocks
                ],
                ensure_ascii=False,
            ),
            affected_industries_json=json.dumps(item.affected_industries, ensure_ascii=False),
            affected_themes_json=json.dumps(item.affected_themes, ensure_ascii=False),
            anchor_block_id=item.anchor_block_id,
            evidence_text=item.evidence_text,
            created_at=now,
            updated_at=now,
        )
        for item in simple_events
    ]
    return SimpleReportBundle(report=report, events=events)


def _normalize_date_text(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    match = _DATE_RE.search(cleaned)
    if match:
        return match.group(1)
    return ""


def _resolve_core_logic(
    *,
    llm_core_logic: str,
    rule_core_logic: str,
    events: list[SimpleEventCandidate],
) -> str:
    llm_core_logic = (llm_core_logic or "").strip()
    if not _is_low_signal_core_logic(llm_core_logic):
        return llm_core_logic

    rule_core_logic = (rule_core_logic or "").strip()
    if not _is_low_signal_core_logic(rule_core_logic):
        return rule_core_logic

    return _build_core_logic_from_events(events)


def _is_low_signal_core_logic(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "")).strip()
    if not normalized:
        return True
    if len(normalized) < 12:
        return True
    if _LOW_SIGNAL_CORE_LOGIC_RE.match(normalized):
        return True
    if normalized.startswith("驱动类型") and len(normalized) <= 24:
        return True
    return False


def _build_core_logic_from_events(events: list[SimpleEventCandidate]) -> str:
    if not events:
        return ""

    ordered = sorted(
        events,
        key=lambda item: (
            0 if item.event_scope in {"industry", "mixed", "macro"} else 1,
            0 if item.affected_themes else 1,
            0 if item.affected_industries else 1,
            -len(item.event_content or ""),
        ),
    )
    selected_texts: list[str] = []
    seen: set[str] = set()
    for event in ordered:
        text = _normalize_summary_sentence(event.event_content or event.event_name)
        if not text:
            continue
        key = re.sub(r"\s+", "", text)
        if key in seen:
            continue
        selected_texts.append(text)
        seen.add(key)
        if len(selected_texts) >= 3:
            break
    return " ".join(selected_texts).strip()


def _normalize_summary_sentence(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return ""
    if normalized[-1] not in "。！？!?":
        normalized += "。"
    return normalized
