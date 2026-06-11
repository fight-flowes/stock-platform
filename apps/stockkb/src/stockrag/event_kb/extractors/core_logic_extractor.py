from __future__ import annotations

import re

from ..schemas import MarkdownBlock, MarkdownDocument


_PRIMARY_SECTION_TOKENS = (
    "上涨核心逻辑",
    "涨停核心逻辑",
    "核心上涨逻辑",
)
_SECONDARY_SECTION_TOKENS = (
    "上涨逻辑",
    "涨停逻辑",
    "核心逻辑",
)
_EXCLUDED_SECTION_TOKENS = (
    "风险",
    "来源",
    "验证",
    "免责声明",
    "搜索记录",
    "数据来源说明",
)
_MARK_RE = re.compile(r"\*\*|__|`+")
_SPACE_RE = re.compile(r"\s+")


def extract_core_logic(document: MarkdownDocument) -> str:
    section_path = _find_best_core_logic_section(document)
    if not section_path:
        return ""

    paragraphs: list[str] = []
    list_items: list[str] = []
    for block in document.blocks:
        if not block.section_path.startswith(section_path):
            continue
        if block.block_type == "paragraph":
            cleaned = _clean_text(block.content_text)
            if cleaned:
                paragraphs.append(cleaned)
        elif block.block_type == "list_item":
            cleaned = _clean_text(block.content_text)
            if cleaned:
                list_items.append(cleaned)

    if paragraphs:
        return paragraphs[0]
    if list_items:
        return "；".join(list_items[:3])
    return ""


def _find_best_core_logic_section(document: MarkdownDocument) -> str:
    best_score = -1
    best_section = ""
    for block in document.blocks:
        if block.block_type != "heading":
            continue
        score = _score_heading_block(block)
        if score > best_score:
            best_score = score
            best_section = block.section_path
    return best_section if best_score > 0 else ""


def _score_heading_block(block: MarkdownBlock) -> int:
    section_path = str(block.section_path or "").strip()
    if not section_path:
        return 0
    last_title = section_path.split(" / ")[-1].strip()
    if any(token in last_title for token in _EXCLUDED_SECTION_TOKENS):
        return 0

    score = 0
    for token in _PRIMARY_SECTION_TOKENS:
        if token in last_title:
            score = max(score, 100)
        elif token in section_path:
            score = max(score, 80)
    for token in _SECONDARY_SECTION_TOKENS:
        if token in last_title:
            score = max(score, 60)
        elif token in section_path:
            score = max(score, 40)
    return score


def _clean_text(text: str) -> str:
    cleaned = _MARK_RE.sub("", str(text or ""))
    cleaned = cleaned.replace("\n", " ").strip()
    return _SPACE_RE.sub(" ", cleaned)
