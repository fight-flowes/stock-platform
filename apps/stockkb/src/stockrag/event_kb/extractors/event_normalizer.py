from __future__ import annotations

import re
from typing import Any

from ..ids import stable_id
from ..schemas import SimpleEventCandidate


_LEADING_CONTEXT_RE = re.compile(
    r"^(?:据(?:悉|报道|公告|统计|披露)|报道称|公告称|消息面上|资料显示|数据显示|报告显示|研报指出|机构指出|券商指出|公司公告显示)[：:，,\s]*"
)
_TRAILING_PUNCT_RE = re.compile(r"[。；;，,、:：\s]+$")
_SPACE_RE = re.compile(r"\s+")
_DATE_RE = re.compile(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})日?")
_MONTH_DAY_RE = re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})日")
_RELATIVE_TIME_RE = re.compile(r"(近\d+日|近\d+天|\d+日内|\d+天|\d+个月|\d+周|近日|近期|当日|当天)")
_STOPWORD_RE = re.compile(r"(据悉|报道称|公告称|消息面上|资料显示|数据显示|报告显示|研报指出|机构指出|券商指出)")
_NON_WORD_RE = re.compile(r"[\s\u3000\"'“”‘’（）()，,。:：;；、】【\\/-]+")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?")


def normalize_simple_events(
    events: list[SimpleEventCandidate],
    *,
    blocks: list[dict[str, str]],
    report_date: str,
) -> list[SimpleEventCandidate]:
    block_map = {
        str(block.get("block_id") or "").strip(): block
        for block in blocks
        if str(block.get("block_id") or "").strip()
    }
    return [
        _normalize_simple_event(
            event,
            blocks=blocks,
            block_map=block_map,
            report_date=report_date,
        )
        for event in events
    ]


def _normalize_simple_event(
    event: SimpleEventCandidate,
    *,
    blocks: list[dict[str, str]],
    block_map: dict[str, dict[str, str]],
    report_date: str,
) -> SimpleEventCandidate:
    event_name = _normalize_event_name(event.event_name)
    event_content = _normalize_sentence(event.event_content)
    evidence_text = _normalize_sentence(event.evidence_text or event.event_content)
    anchor_block_id = _resolve_anchor_block_id(
        event.anchor_block_id,
        evidence_text=evidence_text,
        event_content=event_content,
        event_name=event_name,
        blocks=blocks,
        block_map=block_map,
    )
    if anchor_block_id and not evidence_text:
        evidence_text = _normalize_sentence(str(block_map[anchor_block_id].get("content_text") or ""))
    event_time_text = _normalize_sentence(event.event_time_text)
    event_time_normalized = _normalize_date_text(event_time_text, report_date)
    canonical_event_key = _build_canonical_event_key(
        anchor_block_id=anchor_block_id,
        evidence_text=evidence_text,
        event_name=event_name,
        event_content=event_content,
        event_time_text=event_time_text,
        event_time_normalized=event_time_normalized,
        event_scope=event.event_scope,
        affected_stocks=event.affected_stocks,
        affected_industries=event.affected_industries,
        affected_themes=event.affected_themes,
    )
    event_type = infer_market_event_type(
        event_scope=event.event_scope,
        affected_stocks=event.affected_stocks,
        affected_industries=event.affected_industries,
        affected_themes=event.affected_themes,
    )
    return SimpleEventCandidate(
        event_name=event_name,
        event_time_text=event_time_text,
        event_content=event_content,
        canonical_event_key=canonical_event_key,
        event_time_normalized=event_time_normalized,
        event_type=event_type,
        event_scope=event.event_scope,
        scope_reason=_normalize_sentence(event.scope_reason),
        source_name=_normalize_sentence(event.source_name),
        source_url=_normalize_url(event.source_url),
        affected_stocks=event.affected_stocks,
        affected_industries=event.affected_industries,
        affected_themes=event.affected_themes,
        anchor_block_id=anchor_block_id,
        evidence_text=evidence_text,
        confidence_score=event.confidence_score,
        needs_review=event.needs_review,
        review_reason=_normalize_sentence(event.review_reason),
    )


def infer_market_event_type(
    *,
    event_scope: str,
    affected_stocks: list[Any],
    affected_industries: list[str],
    affected_themes: list[str],
) -> str:
    normalized_scope = _normalize_sentence(event_scope).lower()
    if normalized_scope in {"industry", "macro", "mixed"}:
        return "industry"
    if normalized_scope == "stock":
        return "stock"
    if affected_industries or affected_themes:
        return "industry"
    if len([item for item in affected_stocks if getattr(item, "stock_code", "") or getattr(item, "stock_name", "")]) > 1:
        return "industry"
    return "stock"


def _resolve_anchor_block_id(
    raw_anchor_block_id: str,
    *,
    evidence_text: str,
    event_content: str,
    event_name: str,
    blocks: list[dict[str, str]],
    block_map: dict[str, dict[str, str]],
) -> str:
    anchor_block_id = str(raw_anchor_block_id or "").strip()
    if anchor_block_id and anchor_block_id in block_map:
        return anchor_block_id

    for candidate_text in (evidence_text, event_content, event_name):
        matched = _match_block_id(candidate_text, blocks)
        if matched:
            return matched
    return ""


def _match_block_id(text: str, blocks: list[dict[str, str]]) -> str:
    normalized_target = _normalize_compare_text(text)
    if len(normalized_target) < 6:
        return ""
    best_block_id = ""
    best_score = 0
    for block in blocks:
        block_id = str(block.get("block_id") or "").strip()
        if not block_id:
            continue
        normalized_block = _normalize_compare_text(str(block.get("content_text") or ""))
        if not normalized_block:
            continue
        score = 0
        if normalized_target in normalized_block:
            score = min(len(normalized_target), 200)
        elif normalized_block in normalized_target:
            score = min(len(normalized_block), 200)
        else:
            shared_numbers = _shared_number_score(normalized_target, normalized_block)
            if shared_numbers:
                score = shared_numbers
        if score > best_score:
            best_block_id = block_id
            best_score = score
    return best_block_id if best_score >= 10 else ""


def _shared_number_score(left: str, right: str) -> int:
    left_numbers = set(_NUMBER_RE.findall(left))
    if not left_numbers:
        return 0
    right_numbers = set(_NUMBER_RE.findall(right))
    overlap = left_numbers & right_numbers
    if not overlap:
        return 0
    return len(overlap) * 10


def _build_canonical_event_key(
    *,
    anchor_block_id: str,
    evidence_text: str,
    event_name: str,
    event_content: str,
    event_time_text: str,
    event_time_normalized: str,
    event_scope: str,
    affected_stocks: list[Any],
    affected_industries: list[str],
    affected_themes: list[str],
) -> str:
    subject_key = _build_subject_key(affected_stocks, affected_industries, affected_themes)
    numbers_key = ",".join(
        sorted(
            set(
                _NUMBER_RE.findall(
                    f"{event_name} {_normalize_compare_text(evidence_text)} {_normalize_compare_text(event_content)}"
                )
            )
        )
    )
    time_key = event_time_normalized or _normalize_relative_time(event_time_text)
    anchor_key = anchor_block_id or stable_id(_normalize_compare_text(evidence_text or event_content or event_name))
    return stable_id(anchor_key, time_key, event_scope or "", subject_key, numbers_key)


def _build_subject_key(
    affected_stocks: list[Any],
    affected_industries: list[str],
    affected_themes: list[str],
) -> str:
    stock_codes = sorted({str(item.stock_code or "").strip() for item in affected_stocks if getattr(item, "stock_code", "")})
    industries = sorted({_normalize_compare_text(item) for item in affected_industries if item})
    themes = sorted({_normalize_compare_text(item) for item in affected_themes if item})
    if stock_codes or industries or themes:
        return "|".join([",".join(stock_codes), ",".join(industries), ",".join(themes)])
    return ""


def _normalize_event_name(text: str) -> str:
    cleaned = _normalize_sentence(text)
    cleaned = _LEADING_CONTEXT_RE.sub("", cleaned)
    cleaned = _TRAILING_PUNCT_RE.sub("", cleaned)
    return cleaned


def _normalize_sentence(text: str) -> str:
    cleaned = (text or "").replace("**", " ").replace("__", " ")
    cleaned = cleaned.replace("％", "%").replace("／", "/")
    cleaned = _SPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


def _normalize_url(text: str) -> str:
    cleaned = _normalize_sentence(text)
    return cleaned.rstrip(").,，。；;】】")


def _normalize_date_text(text: str, report_date: str) -> str:
    cleaned = _normalize_sentence(text)
    if not cleaned:
        return ""
    match = _DATE_RE.search(cleaned)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    month_day = _MONTH_DAY_RE.search(cleaned)
    if month_day:
        report_year = _extract_report_year(report_date)
        if report_year:
            month, day = month_day.groups()
            return f"{report_year:04d}-{int(month):02d}-{int(day):02d}"
    return ""


def _extract_report_year(report_date: str) -> int | None:
    match = re.search(r"(20\d{2})", str(report_date or ""))
    if not match:
        return None
    return int(match.group(1))


def _normalize_relative_time(text: str) -> str:
    cleaned = _normalize_sentence(text)
    match = _RELATIVE_TIME_RE.search(cleaned)
    return match.group(1) if match else _normalize_compare_text(cleaned)[:32]


def _normalize_compare_text(text: str) -> str:
    cleaned = _normalize_sentence(text).lower()
    cleaned = _STOPWORD_RE.sub("", cleaned)
    return _NON_WORD_RE.sub("", cleaned)
