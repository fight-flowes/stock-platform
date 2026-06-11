from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from stockrag.event_kb.config import EventKBSettings
from stockrag.event_kb.schemas import SimpleEventRecord, SimpleReportBundle, SimpleReportRecord
from stockrag.event_kb.storage import DuckDBBackend


class MarketEventBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import duckdb  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest(f"duckdb is not installed: {exc}") from exc

    def test_rule_builder_dedupes_same_industry_event_across_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stockkb.duckdb"
            backend = DuckDBBackend(db_path)
            created_at = datetime.now(timezone.utc).isoformat()

            first_bundle = SimpleReportBundle(
                report=SimpleReportRecord(
                    report_id="report-a",
                    source_path="minio://stockinfo/2026/06/04/002395_双象股份.md",
                    source_name="002395_双象股份.md",
                    report_title="双象股份(002395)上涨分析报告（2026-06-04）",
                    stock_code="002395",
                    stock_name="双象股份",
                    report_date="2026-06-04",
                    created_at=created_at,
                    updated_at=created_at,
                ),
                events=[
                    SimpleEventRecord(
                        event_id="event-a",
                        report_id="report-a",
                        event_name="PMMA价格90天上涨4.43%至15700元/吨",
                        event_time_text="2026-06-04",
                        event_time_normalized="2026-06-04",
                        event_content="生意社数据显示 PMMA 价格上涨。",
                        event_type="industry",
                        event_scope="industry",
                        scope_reason="行业价格数据催化。",
                        source_name="生意社",
                        source_url="https://example.com/pmma-price",
                        affected_stock_codes_json='[{"stock_code":"002395","stock_name":"双象股份"}]',
                        affected_industries_json='["PMMA"]',
                        affected_themes_json='["PMMA涨价"]',
                        evidence_text="生意社数据显示，PMMA价格90天上涨4.43%至15700元/吨。",
                        created_at=created_at,
                        updated_at=created_at,
                    ),
                ],
            )
            second_bundle = SimpleReportBundle(
                report=SimpleReportRecord(
                    report_id="report-b",
                    source_path="minio://stockinfo/2026/06/04/300221_银禧科技.md",
                    source_name="300221_银禧科技.md",
                    report_title="银禧科技(300221)上涨分析报告（2026-06-04）",
                    stock_code="300221",
                    stock_name="银禧科技",
                    report_date="2026-06-04",
                    created_at=created_at,
                    updated_at=created_at,
                ),
                events=[
                    SimpleEventRecord(
                        event_id="event-b",
                        report_id="report-b",
                        event_name="PMMA价格持续上涨，90日涨幅4.43%",
                        event_time_text="2026年6月4日",
                        event_time_normalized="2026-06-04",
                        event_content="同一份生意社价格数据被报告引用。",
                        event_type="industry",
                        event_scope="industry",
                        scope_reason="行业价格数据催化。",
                        source_name="生意社",
                        source_url="https://example.com/pmma-price",
                        affected_stock_codes_json='[{"stock_code":"300221","stock_name":"银禧科技"}]',
                        affected_industries_json='["PMMA"]',
                        affected_themes_json='["PMMA涨价"]',
                        evidence_text="生意社数据显示，PMMA价格90天上涨4.43%至15700元/吨。",
                        created_at=created_at,
                        updated_at=created_at,
                    ),
                ],
            )

            backend.upsert_simple_bundle(first_bundle)
            backend.upsert_simple_bundle(second_bundle)

            query_result = backend.query_market_events(filters={"event_type": "industry"}, page=1, page_size=20)

            self.assertEqual(query_result["total_count"], 1)
            item = query_result["items"][0]
            self.assertEqual(item["event_type"], "industry")
            self.assertEqual(item["source_report_count"], 2)
            self.assertEqual(item["affected_stock_count"], 2)

            detail_result = backend.query_market_event_detail(item["event_key"])
            self.assertTrue(detail_result["found"])
            self.assertEqual(detail_result["event"]["event_type"], "industry")
            self.assertEqual(len(detail_result["event"]["source_reports"]), 2)
            self.assertEqual(sorted(detail_result["event"]["source_event_ids"]), ["event-a", "event-b"])

    def test_rule_builder_keeps_stock_event_separate_from_industry_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stockkb.duckdb"
            backend = DuckDBBackend(db_path)
            created_at = datetime.now(timezone.utc).isoformat()
            bundle = SimpleReportBundle(
                report=SimpleReportRecord(
                    report_id="report-c",
                    source_path="minio://stockinfo/2026/06/05/603890_春秋电子.md",
                    source_name="603890_春秋电子.md",
                    report_title="春秋电子(603890)上涨分析报告（2026-06-05）",
                    stock_code="603890",
                    stock_name="春秋电子",
                    report_date="2026-06-05",
                    created_at=created_at,
                    updated_at=created_at,
                ),
                events=[
                    SimpleEventRecord(
                        event_id="event-stock",
                        report_id="report-c",
                        event_name="公司公告签订大额订单",
                        event_time_text="2026-06-05",
                        event_time_normalized="2026-06-05",
                        event_content="春秋电子公告签订大额订单。",
                        event_type="stock",
                        event_scope="stock",
                        scope_reason="单公司订单事件。",
                        source_name="公司公告",
                        source_url="https://example.com/order",
                        affected_stock_codes_json='[{"stock_code":"603890","stock_name":"春秋电子"}]',
                        created_at=created_at,
                        updated_at=created_at,
                    ),
                    SimpleEventRecord(
                        event_id="event-industry",
                        report_id="report-c",
                        event_name="AI PC 产业链需求升温",
                        event_time_text="2026-06-05",
                        event_time_normalized="2026-06-05",
                        event_content="AI PC 需求提升带动产业链关注。",
                        event_type="industry",
                        event_scope="industry",
                        scope_reason="行业需求催化。",
                        affected_stock_codes_json='[{"stock_code":"603890","stock_name":"春秋电子"}]',
                        affected_industries_json='["消费电子"]',
                        affected_themes_json='["AI PC"]',
                        created_at=created_at,
                        updated_at=created_at,
                    ),
                ],
            )

            backend.upsert_simple_bundle(bundle)

            stock_events = backend.query_market_events(filters={"event_type": "stock"}, page=1, page_size=20)
            industry_events = backend.query_market_events(filters={"event_type": "industry"}, page=1, page_size=20)

            self.assertEqual(stock_events["total_count"], 1)
            self.assertEqual(industry_events["total_count"], 1)
            self.assertEqual(stock_events["items"][0]["event_type"], "stock")
            self.assertEqual(industry_events["items"][0]["event_type"], "industry")

    def test_llm_judge_merges_ambiguous_industry_events_and_uses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stockkb.duckdb"
            kb_settings = EventKBSettings(
                duckdb_path=db_path,
                llm_extract_enabled=False,
                llm_extract_base_url="",
                llm_extract_model="",
                llm_extract_api_key="",
                llm_extract_temperature=0.0,
                llm_extract_timeout=30,
                llm_extract_max_blocks=24,
                llm_merge_enabled=True,
                llm_merge_base_url="https://llm.example.com",
                llm_merge_model="judge-model",
                llm_merge_api_key="test-key",
                llm_merge_temperature=0.0,
                llm_merge_timeout=30,
                llm_merge_confidence_threshold=0.8,
                llm_merge_max_judges=20,
                llm_merge_prompt_version="v1",
            )
            backend = DuckDBBackend(db_path, kb_settings)
            created_at = datetime.now(timezone.utc).isoformat()

            first_bundle = SimpleReportBundle(
                report=SimpleReportRecord(
                    report_id="report-llm-a",
                    source_path="minio://stockinfo/2026/06/06/002395_双象股份.md",
                    source_name="002395_双象股份.md",
                    report_title="双象股份(002395)上涨分析报告（2026-06-06）",
                    stock_code="002395",
                    stock_name="双象股份",
                    report_date="2026-06-06",
                    created_at=created_at,
                    updated_at=created_at,
                ),
                events=[
                    SimpleEventRecord(
                        event_id="llm-event-a",
                        report_id="report-llm-a",
                        event_name="PMMA产业链价格景气度提升",
                        event_time_text="2026-06-06",
                        event_time_normalized="2026-06-06",
                        event_content="PMMA价格90天上涨4.43%，产业链景气度改善。",
                        event_type="industry",
                        event_scope="industry",
                        scope_reason="行业价格数据催化。",
                        affected_stock_codes_json='[{"stock_code":"002395","stock_name":"双象股份"}]',
                        affected_industries_json='["PMMA"]',
                        affected_themes_json='["PMMA涨价"]',
                        evidence_text="PMMA价格90天上涨4.43%，产业链景气度改善。",
                        created_at=created_at,
                        updated_at=created_at,
                    ),
                ],
            )
            second_bundle = SimpleReportBundle(
                report=SimpleReportRecord(
                    report_id="report-llm-b",
                    source_path="minio://stockinfo/2026/06/06/300221_银禧科技.md",
                    source_name="300221_银禧科技.md",
                    report_title="银禧科技(300221)上涨分析报告（2026-06-06）",
                    stock_code="300221",
                    stock_name="银禧科技",
                    report_date="2026-06-06",
                    created_at=created_at,
                    updated_at=created_at,
                ),
                events=[
                    SimpleEventRecord(
                        event_id="llm-event-b",
                        report_id="report-llm-b",
                        event_name="PMMA报价持续上行",
                        event_time_text="2026年6月6日",
                        event_time_normalized="2026-06-06",
                        event_content="PMMA近90日涨幅4.43%，价格升至高位。",
                        event_type="industry",
                        event_scope="industry",
                        scope_reason="行业价格数据催化。",
                        affected_stock_codes_json='[{"stock_code":"300221","stock_name":"银禧科技"}]',
                        affected_industries_json='["PMMA"]',
                        affected_themes_json='["PMMA涨价"]',
                        evidence_text="PMMA近90日涨幅4.43%，价格升至高位。",
                        created_at=created_at,
                        updated_at=created_at,
                    ),
                ],
            )

            class _FakeResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self) -> dict[str, object]:
                    return {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"same_event": true, "confidence": 0.93, "reason": "关键数值、日期、主题一致"}'
                                }
                            }
                        ]
                    }

            with patch("stockrag.event_kb.market_event_judge.requests.post", return_value=_FakeResponse()) as mock_post:
                backend.upsert_simple_bundle(first_bundle)
                backend.upsert_simple_bundle(second_bundle)
                backend.rebuild_market_events()

            self.assertEqual(mock_post.call_count, 1)

            stats = backend.stats()
            self.assertEqual(stats["market_event_judge_cache"], 1)

            query_result = backend.query_market_events(filters={"event_type": "industry"}, page=1, page_size=20)
            self.assertEqual(query_result["total_count"], 1)
            item = query_result["items"][0]
            self.assertEqual(item["merge_method"], "llm")

            detail_result = backend.query_market_event_detail(item["event_key"])
            self.assertTrue(detail_result["found"])
            self.assertEqual(detail_result["event"]["merge_method"], "llm")
            self.assertEqual(sorted(detail_result["event"]["source_event_ids"]), ["llm-event-a", "llm-event-b"])


if __name__ == "__main__":
    unittest.main()
