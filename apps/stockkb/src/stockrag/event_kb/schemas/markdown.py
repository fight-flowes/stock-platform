from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MarkdownBlock:
    block_id: str
    section_path: str
    section_level: int
    block_type: str
    content_text: str
    source_line_start: int
    source_line_end: int
    table_headers: list[str] = field(default_factory=list)
    table_rows: list[dict[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class MarkdownDocument:
    text: str
    metadata_fields: dict[str, str]
    blocks: list[MarkdownBlock]
