from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from stockrag.event_kb.schemas import SimpleEventRecord, SimpleReportBundle, SimpleReportRecord
from stockrag.event_kb.storage import DuckDBBackend


class EventSourceFieldTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import duckdb  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest(f"duckdb is not installed: {exc}") from exc

    def test_event_source_fields_round_trip_through_duckdb(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stockkb.duckdb"
            backend = DuckDBBackend(db_path)
            created_at = datetime.now(timezone.utc).isoformat()
            bundle = SimpleReportBundle(
                report=SimpleReportRecord(
                    report_id="report-1",
                    source_path="/tmp/reports/603890_春秋电子.md",
                    source_name="603890_春秋电子.md",
                    report_title="春秋电子上涨分析报告",
                    stock_code="603890",
                    stock_name="春秋电子",
                    report_date="2026-06-01",
                    risk_summary="高位概念炒作风险",
                    created_at=created_at,
                    updated_at=created_at,
                ),
                events=[
                    SimpleEventRecord(
                        event_id="event-with-source",
                        report_id="report-1",
                        event_name="Computex 2026 发布 RTX Spark",
                        event_time_text="2026-06-01",
                        event_time_normalized="2026-06-01",
                        event_content="黄仁勋在 Computex 2026 发布 RTX Spark。",
                        canonical_event_key="anchor-1|2026-06-01|industry|603890",
                        event_type="industry",
                        event_scope="industry",
                        scope_reason="影响消费电子产业链",
                        source_name="The Verge",
                        source_url="https://www.theverge.com/tech/940844/computex-2026",
                        affected_stock_codes_json='[{"stock_code":"603890","stock_name":"春秋电子"}]',
                        affected_industries_json='["元器件"]',
                        affected_themes_json='["消费电子","AI PC"]',
                        anchor_block_id="block-computex",
                        evidence_text="Computex 2026大会上黄仁勋发布RTX Spark。",
                        created_at=created_at,
                        updated_at=created_at,
                    ),
                    SimpleEventRecord(
                        event_id="event-without-source",
                        report_id="report-1",
                        event_name="消费电子板块涨停潮",
                        event_time_text="2026-06-01",
                        event_time_normalized="2026-06-01",
                        event_content="消费电子板块多股涨停。",
                        event_type="industry",
                        event_scope="industry",
                        scope_reason="板块联动",
                        source_name="",
                        source_url="",
                        affected_stock_codes_json='[{"stock_code":"603890","stock_name":"春秋电子"}]',
                        affected_industries_json='["元器件"]',
                        affected_themes_json='["消费电子"]',
                        created_at=created_at,
                        updated_at=created_at,
                    ),
                ],
            )

            backend.upsert_simple_bundle(bundle)

            query_result = backend.query_simple_events(filters={}, page=1, page_size=10)
            events_by_id = {item["event_id"]: item for item in query_result["events"]}

            self.assertEqual(events_by_id["event-with-source"]["source_name"], "The Verge")
            self.assertEqual(
                events_by_id["event-with-source"]["source_url"],
                "https://www.theverge.com/tech/940844/computex-2026",
            )
            self.assertEqual(events_by_id["event-with-source"]["canonical_event_key"], "anchor-1|2026-06-01|industry|603890")
            self.assertEqual(events_by_id["event-with-source"]["anchor_block_id"], "block-computex")
            self.assertEqual(events_by_id["event-with-source"]["evidence_text"], "Computex 2026大会上黄仁勋发布RTX Spark。")
            self.assertEqual(events_by_id["event-without-source"]["source_name"], "")
            self.assertEqual(events_by_id["event-without-source"]["source_url"], "")

            detail_result = backend.query_simple_event_detail("event-with-source")

            self.assertTrue(detail_result["found"])
            self.assertEqual(detail_result["event"]["source_name"], "The Verge")
            self.assertEqual(
                detail_result["event"]["source_url"],
                "https://www.theverge.com/tech/940844/computex-2026",
            )
            self.assertEqual(detail_result["event"]["canonical_event_key"], "anchor-1|2026-06-01|industry|603890")
            self.assertEqual(detail_result["event"]["anchor_block_id"], "block-computex")
            self.assertEqual(detail_result["event"]["evidence_text"], "Computex 2026大会上黄仁勋发布RTX Spark。")
            self.assertEqual(detail_result["event"]["source_path"], "/tmp/reports/603890_春秋电子.md")
            self.assertEqual(detail_result["event"]["report_source_name"], "603890_春秋电子.md")

    def test_market_event_detail_includes_event_source_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stockkb.duckdb"
            backend = DuckDBBackend(db_path)
            created_at = datetime.now(timezone.utc).isoformat()
            bundle = SimpleReportBundle(
                report=SimpleReportRecord(
                    report_id="report-2",
                    source_path="minio://stockinfo/2026/06/04/002395_双象股份.md",
                    source_name="002395_双象股份.md",
                    report_title="双象股份(002395)上涨分析报告（2026-06-04）",
                    stock_code="002395",
                    stock_name="双象股份",
                    report_date="2026-06-04",
                    risk_summary="项目进展与价格回落风险。",
                    created_at=created_at,
                    updated_at=created_at,
                ),
                events=[
                    SimpleEventRecord(
                        event_id="pmma-event-1",
                        report_id="report-2",
                        event_name="PMMA价格90天上涨4.43%至15700元/吨",
                        event_time_text="2026-06-04",
                        event_time_normalized="2026-06-04",
                        event_content="PMMA产业链价格强势。",
                        event_type="industry",
                        event_scope="industry",
                        scope_reason="行业价格数据影响产业链。",
                        source_name="新浪财经/生意社",
                        source_url="https://finance.sina.com.cn/example",
                        affected_stock_codes_json='[{"stock_code":"002395","stock_name":"双象股份"}]',
                        affected_industries_json='["PMMA"]',
                        affected_themes_json='["PMMA涨价"]',
                        created_at=created_at,
                        updated_at=created_at,
                    ),
                ],
            )

            backend.upsert_simple_bundle(bundle)

            market_events = backend.query_market_events(filters={"event_type": "industry"}, page=1, page_size=20)
            self.assertEqual(market_events["total_count"], 1)
            event_key = market_events["items"][0]["event_key"]
            detail_result = backend.query_market_event_detail(event_key)

            self.assertTrue(detail_result["found"])
            self.assertEqual(len(detail_result["event"]["source_reports"]), 1)
            source_report = detail_result["event"]["source_reports"][0]
            self.assertEqual(source_report["source_name"], "新浪财经/生意社")
            self.assertEqual(source_report["source_url"], "https://finance.sina.com.cn/example")
            self.assertEqual(source_report["report_title"], "双象股份(002395)上涨分析报告（2026-06-04）")


if __name__ == "__main__":
    unittest.main()
