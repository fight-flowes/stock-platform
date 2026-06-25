from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stockrag.config import Settings
from stockrag.event_kb.config import EventKBSettings
from stockrag.event_kb.extractors import normalize_simple_events
from stockrag.event_kb.pipeline.extract_simple_report import build_simple_report_bundle
from stockrag.event_kb.schemas import SimpleAffectedStock, SimpleEventCandidate, SimpleReportSummary


class EventNormalizerTests(unittest.TestCase):
    def test_normalize_events_merges_variant_wording_to_same_canonical_key(self) -> None:
        blocks = [
            {
                "block_id": "block-pmma",
                "section_path": "上涨核心逻辑",
                "block_type": "paragraph",
                "content_text": "生意社数据显示，PMMA价格90天上涨4.43%至15700元/吨，产业链景气度回升。",
            }
        ]
        common_stocks = [SimpleAffectedStock(stock_code="002395", stock_name="双象股份")]
        first = SimpleEventCandidate(
            event_name="数据显示 PMMA价格90天上涨4.43%至15700元/吨",
            event_time_text="2026年6月4日",
            event_content="数据显示，PMMA价格90天上涨4.43%至15700元/吨。",
            event_scope="industry",
            affected_stocks=common_stocks,
            affected_industries=["PMMA"],
            affected_themes=["PMMA涨价"],
        )
        second = SimpleEventCandidate(
            event_name="PMMA价格持续上涨，90日涨幅4.43%",
            event_time_text="6月4日",
            event_content="生意社数据显示 PMMA 90天涨4.43% 至15700元/吨。",
            event_scope="industry",
            affected_stocks=common_stocks,
            affected_industries=["PMMA"],
            affected_themes=["PMMA涨价"],
            evidence_text="生意社数据显示，PMMA价格90天上涨4.43%至15700元/吨，产业链景气度回升。",
        )

        normalized = normalize_simple_events([first, second], blocks=blocks, report_date="2026-06-04")

        self.assertEqual(normalized[0].anchor_block_id, "block-pmma")
        self.assertEqual(normalized[1].anchor_block_id, "block-pmma")
        self.assertEqual(normalized[0].event_time_normalized, "2026-06-04")
        self.assertEqual(normalized[1].event_time_normalized, "2026-06-04")
        self.assertEqual(normalized[0].canonical_event_key, normalized[1].canonical_event_key)
        self.assertEqual(normalized[0].event_type, "industry")
        self.assertEqual(normalized[1].event_type, "industry")

    def test_build_bundle_uses_canonical_key_for_stable_event_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "002395_双象股份.md"
            report_path.write_text(
                "# 双象股份(002395)上涨分析报告（2026-06-04）\n\n## 上涨核心逻辑\nPMMA价格上涨。\n",
                encoding="utf-8",
            )
            settings = Settings(root_dir=Path(tmpdir), data_dir=Path(tmpdir))
            kb_settings = EventKBSettings(
                duckdb_path=Path(tmpdir) / "stockkb.duckdb",
                llm_extract_enabled=False,
                llm_extract_base_url="",
                llm_extract_model="",
                llm_extract_api_key="",
                llm_extract_temperature=0.0,
                llm_extract_timeout=30,
                llm_extract_max_blocks=24,
                llm_merge_enabled=False,
                llm_merge_base_url="",
                llm_merge_model="",
                llm_merge_api_key="",
                llm_merge_temperature=0.0,
                llm_merge_timeout=30,
                llm_merge_confidence_threshold=0.8,
                llm_merge_max_judges=20,
                llm_merge_prompt_version="v1",
            )
            first_event = SimpleEventCandidate(
                event_name="PMMA价格90天上涨4.43%至15700元/吨",
                event_time_text="2026-06-04",
                event_content="PMMA产业链价格走强。",
                canonical_event_key="canonical-pmma-event",
                event_time_normalized="2026-06-04",
                event_scope="industry",
            )
            second_event = SimpleEventCandidate(
                event_name="PMMA价格持续上涨，90日涨幅4.43%",
                event_time_text="2026年6月4日",
                event_content="生意社数据显示PMMA价格继续走强。",
                canonical_event_key="canonical-pmma-event",
                event_time_normalized="2026-06-04",
                event_scope="industry",
            )

            with patch(
                "stockrag.event_kb.pipeline.extract_simple_report.extract_simple_events_and_risk",
                return_value=([first_event], SimpleReportSummary()),
            ):
                first_bundle = build_simple_report_bundle(report_path, settings, kb_settings=kb_settings)
            with patch(
                "stockrag.event_kb.pipeline.extract_simple_report.extract_simple_events_and_risk",
                return_value=([second_event], SimpleReportSummary()),
            ):
                second_bundle = build_simple_report_bundle(report_path, settings, kb_settings=kb_settings)

            self.assertEqual(first_bundle.events[0].event_id, second_bundle.events[0].event_id)

    def test_build_bundle_prefers_llm_core_logic_and_falls_back_when_summary_is_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "002068_黑猫股份.md"
            report_path.write_text(
                (
                    "# 黑猫股份(002068)上涨分析报告（2026-06-18）\n\n"
                    "## 上涨核心逻辑\n"
                    "驱动类型：板块驱动型\n"
                ),
                encoding="utf-8",
            )
            settings = Settings(root_dir=Path(tmpdir), data_dir=Path(tmpdir))
            kb_settings = EventKBSettings(
                duckdb_path=Path(tmpdir) / "stockkb.duckdb",
                llm_extract_enabled=False,
                llm_extract_base_url="",
                llm_extract_model="",
                llm_extract_api_key="",
                llm_extract_temperature=0.0,
                llm_extract_timeout=30,
                llm_extract_max_blocks=24,
                llm_merge_enabled=False,
                llm_merge_base_url="",
                llm_merge_model="",
                llm_merge_api_key="",
                llm_merge_temperature=0.0,
                llm_merge_timeout=30,
                llm_merge_confidence_threshold=0.8,
                llm_merge_max_judges=20,
                llm_merge_prompt_version="v1",
            )
            events = [
                SimpleEventCandidate(
                    event_name="超级电容板块走强",
                    event_time_text="2026-06-18",
                    event_content="超级电容板块全天强势，AI电源需求预期带动产业链走强。",
                    event_scope="industry",
                ),
                SimpleEventCandidate(
                    event_name="黑猫股份中试送样",
                    event_time_text="2026-06-09",
                    event_content="黑猫股份介孔炭中试完成并向客户送样，强化了公司在超级电容材料方向的兑现预期。",
                    event_scope="stock",
                ),
            ]

            with patch(
                "stockrag.event_kb.pipeline.extract_simple_report.extract_simple_events_and_risk",
                return_value=(
                    events,
                    SimpleReportSummary(
                        core_logic="驱动类型：板块驱动型",
                        risk_summary="下游需求兑现和公司产能释放节奏仍存在不确定性。",
                    ),
                ),
            ):
                bundle = build_simple_report_bundle(report_path, settings, kb_settings=kb_settings)

            self.assertIn("超级电容板块全天强势", bundle.report.core_logic)
            self.assertIn("中试完成并向客户送样", bundle.report.core_logic)
            self.assertEqual(bundle.report.risk_summary, "下游需求兑现和公司产能释放节奏仍存在不确定性。")


if __name__ == "__main__":
    unittest.main()
