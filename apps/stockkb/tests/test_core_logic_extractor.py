from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from stockrag.event_kb.extractors import extract_core_logic
from stockrag.event_kb.parsers import parse_markdown_document
from stockrag.event_kb.schemas import SimpleReportBundle, SimpleReportRecord
from stockrag.event_kb.storage import DuckDBBackend


class CoreLogicExtractorTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import duckdb  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest(f"duckdb is not installed: {exc}") from exc

    def test_extract_core_logic_from_named_section(self) -> None:
        document = parse_markdown_document(
            """
# 双象股份(002395)上涨分析报告（2026-06-04）

## 上涨核心逻辑

**超跌反弹叠加 PMMA 产业链景气度回升，主力资金净流入推动涨停。**

## 风险提示

- 业绩下滑风险
            """.strip()
        )

        result = extract_core_logic(document)

        self.assertEqual(result, "超跌反弹叠加 PMMA 产业链景气度回升，主力资金净流入推动涨停。")

    def test_core_logic_round_trip_through_duckdb(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stockkb.duckdb"
            backend = DuckDBBackend(db_path)
            created_at = datetime.now(timezone.utc).isoformat()
            bundle = SimpleReportBundle(
                report=SimpleReportRecord(
                    report_id="report-core-logic",
                    source_path="minio://stockinfo/2026/06/04/002395_双象股份.md",
                    source_name="002395_双象股份.md",
                    report_title="双象股份(002395)上涨分析报告（2026-06-04）",
                    stock_code="002395",
                    stock_name="双象股份",
                    report_date="2026-06-04",
                    core_logic="超跌反弹叠加 PMMA 产业链景气度回升。",
                    risk_summary="项目落地与业绩承压风险。",
                    created_at=created_at,
                    updated_at=created_at,
                ),
                events=[],
            )

            backend.upsert_simple_bundle(bundle)
            result = backend.query_simple_reports(filters={"stock_code": "002395"}, page=1, page_size=10)

            self.assertEqual(result["reports"][0]["core_logic"], "超跌反弹叠加 PMMA 产业链景气度回升。")


if __name__ == "__main__":
    unittest.main()
