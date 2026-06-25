from __future__ import annotations

import re

from ..schemas import MarkdownDocument


_STAR_COUNT_RE = re.compile(r"⭐")
_CLEAN_MARK_RE = re.compile(r"[✅⚠️⚠]")
_STOCK_CODE_RE = re.compile(r"\d{6}(?:\.(?:SZ|SH|BJ))?", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def extract_basic_info_fields(document: MarkdownDocument) -> dict[str, str]:
    extracted: dict[str, str] = {}
    metadata_fields = document.metadata_fields

    if "涨停日期" in metadata_fields:
        extracted["report_date"] = _normalize_iso_date(metadata_fields["涨停日期"])
    if "报告生成时间" in metadata_fields:
        extracted["report_generated_at"] = metadata_fields["报告生成时间"]

    for block in document.blocks:
        if block.block_type != "table":
            continue
        if "基本信息" not in block.section_path:
            continue
        for row in block.table_rows:
            item_name = (row.get("项目") or row.get("字段") or "").strip()
            data = (
                row.get("数据")
                or row.get("值")
                or row.get("内容")
                or row.get("结果")
                or ""
            ).strip()
            if not item_name or not data:
                continue

            if item_name == "股票代码":
                extracted["stock_code"] = _normalize_stock_code(_strip_marks(data))
            elif item_name == "股票名称":
                extracted["stock_name"] = _strip_marks(data)
            elif item_name == "所属行业":
                extracted["industry"] = _strip_marks(data)
            elif item_name == "所属板块":
                extracted["concept_tags"] = _strip_marks(data)
            elif item_name == "市场类型":
                extracted["market_type"] = _strip_marks(data)
            elif item_name == "流通市值":
                extracted["float_market_cap"] = _strip_marks(data)
            elif item_name == "总市值":
                extracted["total_market_cap"] = _strip_marks(data)
            elif item_name == "最新价格":
                extracted["latest_price"] = _strip_marks(data)
            elif item_name == "涨跌幅":
                extracted["change_pct"] = _strip_marks(data)
            elif item_name == "换手率":
                extracted["turnover_rate"] = _strip_marks(data)
            elif item_name == "涨停日期":
                normalized = _normalize_iso_date(_strip_marks(data))
                if normalized:
                    extracted["report_date"] = normalized
    return extracted


def extract_credibility_level(text: str) -> int | None:
    count = len(_STAR_COUNT_RE.findall(text))
    return count or None


def _strip_marks(text: str) -> str:
    cleaned = _CLEAN_MARK_RE.sub("", text)
    return cleaned.replace("**", "").strip()


def _normalize_stock_code(text: str) -> str:
    """Pick the first ``NNNNNN`` / ``NNNNNN.SZ|SH|BJ`` token in ``text``.

    Markdown reports occasionally append free-form suffixes such as
    ``002910.SZ（深交所主板）``; downstream callers compare ``stock_code``
    with ``=`` so the suffix has to be peeled off here, otherwise the
    record becomes unreachable from the calenderapp ``事件`` button.
    Returns the original ``text`` (post-strip) when no canonical token is
    found, so handcrafted codes are still preserved verbatim.
    """
    if not text:
        return text
    match = _STOCK_CODE_RE.search(text)
    return match.group(0).upper() if match else text.strip()


def _normalize_iso_date(text: str) -> str:
    """Pick the first ``YYYY-MM-DD`` token in ``text``.

    Reports sometimes write ``2026-06-16（周二）`` in the basic-info
    table — same severity as the stock-code suffix above, so we strip it
    here. Falls back to the original (stripped) text when nothing
    matches so non-ISO inputs are not silently dropped.
    """
    if not text:
        return text
    match = _ISO_DATE_RE.search(text)
    return match.group(0) if match else text.strip()
