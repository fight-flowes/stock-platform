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
from ..schemas import SimpleEventRecord, SimpleReportBundle, SimpleReportRecord


_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


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
    core_logic = extract_core_logic(document)
    report_id = stable_id(metadata["source_path"])
    now = datetime.now(timezone.utc).isoformat()
    simple_events, risk_summary = extract_simple_events_and_risk(
        document,
        str(metadata.get("report_date", "")),
        kb_settings,
        primary_stock_code=str(metadata.get("stock_code", "")),
        primary_stock_name=str(metadata.get("stock_name", "")),
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
        risk_summary=risk_summary.summary_text,
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
