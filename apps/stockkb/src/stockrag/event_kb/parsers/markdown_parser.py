from __future__ import annotations

import re

from ..ids import stable_id
from ..schemas import MarkdownBlock, MarkdownDocument


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_META_FIELD_RE = re.compile(r"^\*\*(.+?)\*\*[：:]\s*(.+?)\s*$")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+\.\s+)(.+?)\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$")


def parse_markdown_document(text: str) -> MarkdownDocument:
    lines = text.split("\n")
    heading_stack: list[tuple[int, str]] = []
    blocks: list[MarkdownBlock] = []
    metadata_fields: dict[str, str] = {}
    paragraph_lines: list[str] = []
    paragraph_start = 0
    line_index = 0

    def current_section() -> tuple[str, int]:
        if not heading_stack:
            return "root", 0
        return " / ".join(title for _, title in heading_stack), heading_stack[-1][0]

    def flush_paragraph(end_index: int) -> None:
        nonlocal paragraph_start
        content = "\n".join(paragraph_lines).strip()
        if not content:
            paragraph_lines.clear()
            return
        section_path, section_level = current_section()
        blocks.append(
            MarkdownBlock(
                block_id=stable_id(section_path, "paragraph", paragraph_start, end_index, content),
                section_path=section_path,
                section_level=section_level,
                block_type="paragraph",
                content_text=content,
                source_line_start=paragraph_start,
                source_line_end=end_index,
            )
        )
        paragraph_lines.clear()

    while line_index < len(lines):
        line = lines[line_index]
        stripped = line.strip()
        meta_match = _META_FIELD_RE.match(stripped)
        heading_match = _HEADING_RE.match(stripped)

        if heading_match:
            flush_paragraph(line_index)
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_stack[:] = [item for item in heading_stack if item[0] < level]
            heading_stack.append((level, title))
            section_path, section_level = current_section()
            blocks.append(
                MarkdownBlock(
                    block_id=stable_id(section_path, "heading", line_index),
                    section_path=section_path,
                    section_level=section_level,
                    block_type="heading",
                    content_text=title,
                    source_line_start=line_index + 1,
                    source_line_end=line_index + 1,
                )
            )
            line_index += 1
            continue

        if meta_match:
            metadata_fields[meta_match.group(1).strip()] = meta_match.group(2).strip()

        if _is_table_start(lines, line_index):
            flush_paragraph(line_index)
            block, consumed = _parse_table(lines, line_index, current_section())
            blocks.append(block)
            line_index = consumed
            continue

        list_match = _LIST_ITEM_RE.match(stripped)
        if list_match:
            flush_paragraph(line_index)
            section_path, section_level = current_section()
            blocks.append(
                MarkdownBlock(
                    block_id=stable_id(section_path, "list_item", line_index, list_match.group(1)),
                    section_path=section_path,
                    section_level=section_level,
                    block_type="list_item",
                    content_text=list_match.group(1).strip(),
                    source_line_start=line_index + 1,
                    source_line_end=line_index + 1,
                )
            )
            line_index += 1
            continue

        if not stripped:
            flush_paragraph(line_index)
            line_index += 1
            continue

        if not paragraph_lines:
            paragraph_start = line_index + 1
        paragraph_lines.append(line.rstrip())
        line_index += 1

    flush_paragraph(len(lines))
    return MarkdownDocument(text=text, metadata_fields=metadata_fields, blocks=blocks)


def _is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    return "|" in lines[index] and _TABLE_SEPARATOR_RE.match(lines[index + 1].strip()) is not None


def _parse_table(
    lines: list[str],
    start_index: int,
    current_section: tuple[str, int],
) -> tuple[MarkdownBlock, int]:
    headers = _split_table_row(lines[start_index])
    section_path, section_level = current_section
    row_index = start_index + 2
    rows: list[dict[str, str]] = []

    while row_index < len(lines):
        raw = lines[row_index]
        if not raw.strip() or "|" not in raw:
            break
        values = _split_table_row(raw)
        if len(values) != len(headers):
            break
        rows.append(dict(zip(headers, values, strict=True)))
        row_index += 1

    block = MarkdownBlock(
        block_id=stable_id(section_path, "table", start_index, row_index),
        section_path=section_path,
        section_level=section_level,
        block_type="table",
        content_text="\n".join(lines[start_index:row_index]).strip(),
        source_line_start=start_index + 1,
        source_line_end=row_index,
        table_headers=headers,
        table_rows=rows,
    )
    return block, row_index


def _split_table_row(row: str) -> list[str]:
    stripped = row.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]
