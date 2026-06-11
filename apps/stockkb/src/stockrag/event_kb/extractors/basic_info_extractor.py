from __future__ import annotations

import re

from ..schemas import MarkdownDocument


_STAR_COUNT_RE = re.compile(r"⭐")
_CLEAN_MARK_RE = re.compile(r"[✅⚠️⚠]")


def extract_basic_info_fields(document: MarkdownDocument) -> dict[str, str]:
    extracted: dict[str, str] = {}
    metadata_fields = document.metadata_fields

    if "涨停日期" in metadata_fields:
        extracted["report_date"] = metadata_fields["涨停日期"]
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
                extracted["stock_code"] = _strip_marks(data)
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
    return extracted


def extract_credibility_level(text: str) -> int | None:
    count = len(_STAR_COUNT_RE.findall(text))
    return count or None


def _strip_marks(text: str) -> str:
    cleaned = _CLEAN_MARK_RE.sub("", text)
    return cleaned.replace("**", "").strip()
