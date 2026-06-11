from __future__ import annotations

import hashlib
import re
from pathlib import Path


_FILENAME_RE = re.compile(r"(?P<code>\d{6})_(?P<name>.+)\.md$", re.IGNORECASE)
_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_DATE_RE = re.compile(r"涨停日期\**[：:]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})")
_BOARD_ROW_RE = re.compile(r"\|\s*所属板块\s*\|\s*([^|]+?)\s*\|")
_COMPACT_DATE_RE = re.compile(r"(?<!\d)(\d{8})(?!\d)")
_HIERARCHICAL_DATE_RE = re.compile(r"(?<!\d)(\d{4})/(\d{2})/(\d{2})(?!\d)")


def make_doc_id(source_path: str) -> str:
    return hashlib.sha1(source_path.encode("utf-8")).hexdigest()


def compact_date(date_str: str) -> str:
    return date_str.replace("-", "") if date_str else ""


def _normalize_compact_date(compact: str) -> str:
    return f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"


def _infer_report_date(*candidates: str) -> str:
    for candidate in candidates:
        if not candidate:
            continue

        hierarchical_match = _HIERARCHICAL_DATE_RE.search(candidate)
        if hierarchical_match:
            year, month, day = hierarchical_match.groups()
            return f"{year}-{month}-{day}"

        compact_match = _COMPACT_DATE_RE.search(candidate)
        if compact_match:
            return _normalize_compact_date(compact_match.group(1))

    return ""


def extract_report_metadata(
    path: Path,
    text: str,
    *,
    source_path: str | None = None,
    source_name: str | None = None,
    parent_name: str | None = None,
) -> dict[str, str | list[str]]:
    stock_code = ""
    stock_name = ""
    resolved_source_name = source_name or path.name

    match = _FILENAME_RE.search(resolved_source_name)
    if match:
        stock_code = match.group("code")
        stock_name = match.group("name")

    title_match = _TITLE_RE.search(text)
    report_title = title_match.group(1).strip() if title_match else Path(resolved_source_name).stem

    resolved_parent_name = parent_name if parent_name is not None else path.parent.name
    resolved_source_path = source_path or str(path.resolve())
    report_date = _infer_report_date(resolved_parent_name, resolved_source_path, str(path))

    body_date_match = _DATE_RE.search(text)
    if body_date_match:
        report_date = body_date_match.group(1)

    tags: list[str] = []
    board_match = _BOARD_ROW_RE.search(text)
    if board_match:
        raw_tags = board_match.group(1)
        tags = [item.strip() for item in re.split(r"[／/、]", raw_tags) if item.strip()]

    return {
        "doc_id": make_doc_id(resolved_source_path),
        "source_path": resolved_source_path,
        "source_name": resolved_source_name,
        "report_title": report_title,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "report_date": report_date,
        "report_date_compact": compact_date(report_date),
        "tags": tags,
    }
