from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class SimpleAffectedStock:
    stock_code: str
    stock_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SimpleEventCandidate:
    event_name: str
    event_time_text: str
    event_content: str
    canonical_event_key: str = ""
    event_time_normalized: str = ""
    event_type: str = ""
    event_scope: str = ""
    scope_reason: str = ""
    source_name: str = ""
    source_url: str = ""
    affected_stocks: list[SimpleAffectedStock] = field(default_factory=list)
    affected_industries: list[str] = field(default_factory=list)
    affected_themes: list[str] = field(default_factory=list)
    anchor_block_id: str = ""
    evidence_text: str = ""
    confidence_score: float | None = None
    needs_review: bool = False
    review_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["affected_stocks"] = [item.to_dict() for item in self.affected_stocks]
        return payload


@dataclass(slots=True)
class SimpleRiskSummary:
    summary_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SimpleReportRecord:
    report_id: str
    source_path: str
    source_name: str
    report_title: str
    stock_code: str
    stock_name: str
    report_date: str
    core_logic: str = ""
    risk_summary: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SimpleEventRecord:
    event_id: str
    report_id: str
    event_name: str
    event_time_text: str
    event_time_normalized: str = ""
    event_content: str = ""
    canonical_event_key: str = ""
    event_type: str = ""
    event_scope: str = ""
    scope_reason: str = ""
    source_name: str = ""
    source_url: str = ""
    affected_stock_codes_json: str = "[]"
    affected_industries_json: str = "[]"
    affected_themes_json: str = "[]"
    anchor_block_id: str = ""
    evidence_text: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SimpleReportBundle:
    report: SimpleReportRecord
    events: list[SimpleEventRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report": self.report.to_dict(),
            "events": [item.to_dict() for item in self.events],
        }
