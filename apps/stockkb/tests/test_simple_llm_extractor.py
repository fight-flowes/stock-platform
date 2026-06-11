from __future__ import annotations

import unittest

from stockrag.event_kb.extractors.simple_llm_extractor import (
    _backfill_source_metadata,
    _build_event_section_bundles,
    _collect_blocks,
)
from stockrag.event_kb.parsers import parse_markdown_document
from stockrag.event_kb.schemas import SimpleEventCandidate


class SimpleLLMExtractorTests(unittest.TestCase):
    def test_build_event_section_bundles_supports_titles_with_slash(self) -> None:
        document = parse_markdown_document(
            """
# 测试报告

## 核心事件展开

##### 事件9：8万吨/年电子级环氧树脂扩建项目获注册批复，已进入土建招标阶段

事件日期：2026-06-09

事件内容：项目获批并进入土建招标阶段。

来源：同花顺财经

URL：https://m.10jqka.com.cn/example
""".strip()
        )

        bundles = _build_event_section_bundles(document)

        self.assertEqual(len(bundles), 1)
        self.assertIn("事件9：8万吨/年电子级环氧树脂扩建项目获注册批复", bundles[0]["section_path"])
        self.assertEqual(bundles[0]["source_name"], "同花顺财经")
        self.assertEqual(bundles[0]["source_url"], "https://m.10jqka.com.cn/example")

    def test_collect_blocks_backfills_adjacent_source_metadata(self) -> None:
        document = parse_markdown_document(
            """
# 测试报告

## 事件线索

公司控股子公司完成客户验证并开始小批量供货。

来源：东方财富

URL：https://caifuhao.eastmoney.com/news/example
""".strip()
        )

        blocks = _collect_blocks(document, max_blocks=4)
        paragraph_block = next(item for item in blocks if item["block_type"] == "paragraph")

        self.assertEqual(paragraph_block["source_name"], "东方财富")
        self.assertEqual(paragraph_block["source_url"], "https://caifuhao.eastmoney.com/news/example")

    def test_backfill_source_metadata_uses_selected_block_source_fields(self) -> None:
        event = SimpleEventCandidate(
            event_name="BMI树脂通过客户验证并供货",
            event_time_text="2026-06-10",
            event_content="公司控股子公司完成客户验证并开始小批量供货。",
            source_name="",
            source_url="",
            anchor_block_id="block-1",
        )
        blocks = [
            {
                "block_id": "block-1",
                "section_path": "事件线索",
                "block_type": "paragraph",
                "content_text": "公司控股子公司完成客户验证并开始小批量供货。",
                "source_name": "东方财富",
                "source_url": "https://caifuhao.eastmoney.com/news/example",
            }
        ]

        updated = _backfill_source_metadata([event], blocks=blocks)

        self.assertEqual(updated[0].source_name, "东方财富")
        self.assertEqual(updated[0].source_url, "https://caifuhao.eastmoney.com/news/example")


if __name__ == "__main__":
    unittest.main()
