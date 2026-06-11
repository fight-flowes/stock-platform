from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
import re
from typing import Any

from ..config import EventKBSettings
from ..market_event_builder import MarketEventBuilder
from ..market_event_judge import MarketEventJudge
from ..schemas import SimpleReportBundle
from .ddl import DDL_STATEMENTS


class DuckDBBackend:
    def __init__(self, db_path: Path, kb_settings: EventKBSettings | None = None) -> None:
        self.db_path = db_path
        self.kb_settings = kb_settings
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            for statement in DDL_STATEMENTS:
                conn.execute(statement)
            self._ensure_simple_report_columns(conn)
            self._ensure_simple_event_columns(conn)
            self._ensure_market_event_columns(conn)
            self._ensure_market_event_member_columns(conn)
            self._ensure_market_event_judge_cache_columns(conn)

    def upsert_simple_bundle(self, bundle: SimpleReportBundle) -> None:
        self.ensure_schema()
        with self._connect() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                report_id = bundle.report.report_id
                conn.execute("DELETE FROM kb_simple_event WHERE report_id = ?", [report_id])
                conn.execute("DELETE FROM kb_simple_report WHERE report_id = ?", [report_id])
                self._insert_record(conn, "kb_simple_report", asdict(bundle.report), replace=True)
                self._insert_many(conn, "kb_simple_event", bundle.events, replace=True)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        self.rebuild_market_events()

    def rebuild_market_events(self) -> dict[str, int]:
        self.ensure_schema()
        rows = self._load_market_event_source_rows()
        builder = MarketEventBuilder(judge=self._build_market_event_judge())
        market_events, members = builder.build(rows)
        with self._connect() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.execute("DELETE FROM kb_market_event_member")
                conn.execute("DELETE FROM kb_market_event")
                for item in market_events:
                    self._insert_record(conn, "kb_market_event", item, replace=True)
                for item in members:
                    self._insert_record(conn, "kb_market_event_member", item, replace=True)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return {
            "market_events": len(market_events),
            "market_event_members": len(members),
        }

    def _build_market_event_judge(self):
        if self.kb_settings is None:
            return None
        judge = MarketEventJudge(
            self.kb_settings,
            load_cache=self.get_market_event_judge_cache,
            save_cache=self.upsert_market_event_judge_cache,
        )
        return judge.judge

    def stats(self) -> dict[str, int]:
        if not self.db_path.exists():
            return {
                "simple_reports": 0,
                "simple_events": 0,
                "market_events": 0,
                "market_event_members": 0,
                "market_event_judge_cache": 0,
            }
        self.ensure_schema()
        with self._connect() as conn:
            return {
                "simple_reports": int(conn.execute("SELECT COUNT(*) FROM kb_simple_report").fetchone()[0]),
                "simple_events": int(conn.execute("SELECT COUNT(*) FROM kb_simple_event").fetchone()[0]),
                "market_events": int(conn.execute("SELECT COUNT(*) FROM kb_market_event").fetchone()[0]),
                "market_event_members": int(conn.execute("SELECT COUNT(*) FROM kb_market_event_member").fetchone()[0]),
                "market_event_judge_cache": int(conn.execute("SELECT COUNT(*) FROM kb_market_event_judge_cache").fetchone()[0]),
            }

    def query_simple_reports(
        self,
        *,
        filters: dict[str, Any],
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "report_date",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        page, page_size, offset = self._normalize_pagination(page, page_size)
        order = "DESC" if str(sort_order).lower() == "desc" else "ASC"
        sort_column = {
            "report_date": "r.report_date",
            "stock_code": "r.stock_code",
            "stock_name": "r.stock_name",
            "report_title": "r.report_title",
            "event_count": "event_count",
        }.get(sort_by, "r.report_date")
        from_sql = """
            FROM kb_simple_report r
            LEFT JOIN kb_simple_event e ON e.report_id = r.report_id
            WHERE 1 = 1
        """
        where_sql: list[str] = []
        params: list[Any] = []
        self._append_simple_report_filters(where_sql, params, filters)
        count_sql = f"SELECT COUNT(DISTINCT r.report_id) {from_sql} {' '.join(where_sql)}"
        sql = [
            """
            SELECT
                r.report_id,
                r.report_title,
                r.core_logic,
                r.stock_code,
                r.stock_name,
                r.report_date,
                r.risk_summary,
                COUNT(DISTINCT e.event_id) AS event_count
            """,
            from_sql,
            *where_sql,
            """
            GROUP BY
                r.report_id, r.report_title, r.core_logic, r.stock_code, r.stock_name, r.report_date, r.risk_summary
            """,
            f"ORDER BY {sort_column} {order}, r.stock_code ASC",
            "LIMIT ? OFFSET ?",
        ]
        if not self.db_path.exists():
            return self._empty_page("reports", filters, page, page_size, sort_by, sort_order)
        self.ensure_schema()

        with self._connect() as conn:
            total_count = int(conn.execute(count_sql, params).fetchone()[0])
            rows = conn.execute("\n".join(sql), [*params, page_size, offset]).fetchall()
            columns = [item[0] for item in conn.description]
            reports = [
                self._serialize_mapping(dict(zip(columns, row, strict=True)))
                for row in rows
            ]
        return self._build_page_response(
            "reports",
            reports,
            total_count=total_count,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters,
        )

    def query_simple_events(
        self,
        *,
        filters: dict[str, Any],
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "event_time_normalized",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        page, page_size, offset = self._normalize_pagination(page, page_size)
        order = "DESC" if str(sort_order).lower() == "desc" else "ASC"
        sort_column = {
            "event_time_normalized": "e.event_time_normalized",
            "event_name": "e.event_name",
            "report_date": "r.report_date",
            "stock_code": "r.stock_code",
        }.get(sort_by, "e.event_time_normalized")
        from_sql = """
            FROM kb_simple_event e
            JOIN kb_simple_report r ON r.report_id = e.report_id
            LEFT JOIN kb_simple_event_favorite f ON f.event_id = e.event_id
            WHERE 1 = 1
        """
        where_sql: list[str] = []
        params: list[Any] = []
        self._append_simple_event_filters(where_sql, params, filters)
        count_sql = f"SELECT COUNT(DISTINCT e.event_id) {from_sql} {' '.join(where_sql)}"
        sql = [
            """
            SELECT
                e.event_id,
                e.report_id,
                e.event_name,
                e.event_time_text,
                e.event_time_normalized,
                e.event_content,
                e.canonical_event_key,
                e.event_type,
                e.event_scope,
                e.scope_reason,
                e.source_name,
                e.source_url,
                e.affected_stock_codes_json,
                e.affected_industries_json,
                e.affected_themes_json,
                e.anchor_block_id,
                e.evidence_text,
                CASE WHEN f.event_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_favorite,
                r.stock_code,
                r.stock_name,
                r.report_date,
                r.report_title,
                r.risk_summary
            """,
            from_sql,
            *where_sql,
            f"ORDER BY {sort_column} {order}, e.event_name ASC",
            "LIMIT ? OFFSET ?",
        ]
        if not self.db_path.exists():
            return self._empty_page("events", filters, page, page_size, sort_by, sort_order)
        self.ensure_schema()

        with self._connect() as conn:
            total_count = int(conn.execute(count_sql, params).fetchone()[0])
            rows = conn.execute("\n".join(sql), [*params, page_size, offset]).fetchall()
            columns = [item[0] for item in conn.description]
            events = [
                self._hydrate_simple_event_payload(
                    self._serialize_mapping(dict(zip(columns, row, strict=True)))
                )
                for row in rows
            ]
        return self._build_page_response(
            "events",
            events,
            total_count=total_count,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters,
        )

    def query_simple_event_detail(self, event_id: str) -> dict[str, Any]:
        if not event_id.strip() or not self.db_path.exists():
            return {"found": False, "event_id": event_id}
        self.ensure_schema()

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    e.event_id,
                    e.report_id,
                    e.event_name,
                    e.event_time_text,
                    e.event_time_normalized,
                    e.event_content,
                    e.canonical_event_key,
                    e.event_type,
                    e.event_scope,
                    e.scope_reason,
                    e.source_name,
                    e.source_url,
                    e.affected_stock_codes_json,
                    e.affected_industries_json,
                    e.affected_themes_json,
                    e.anchor_block_id,
                    e.evidence_text,
                    CASE WHEN f.event_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_favorite,
                    r.stock_code,
                    r.stock_name,
                    r.report_date,
                    r.report_title,
                    r.risk_summary,
                    r.source_path,
                    r.source_name AS report_source_name
                FROM kb_simple_event e
                JOIN kb_simple_report r ON r.report_id = e.report_id
                LEFT JOIN kb_simple_event_favorite f ON f.event_id = e.event_id
                WHERE e.event_id = ?
                """,
                [event_id],
            ).fetchone()
            if row is None:
                return {"found": False, "event_id": event_id}
            columns = [item[0] for item in conn.description]
            payload = self._hydrate_simple_event_payload(
                self._serialize_mapping(dict(zip(columns, row, strict=True)))
            )
        return {"found": True, "event_id": event_id, "event": payload}

    def query_market_events(
        self,
        *,
        filters: dict[str, Any],
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "latest_active_date",
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        page, page_size, offset = self._normalize_pagination(page, page_size)
        if not self.db_path.exists():
            return self._empty_page("items", filters, page, page_size, sort_by, sort_order)
        self.ensure_schema()
        self._ensure_market_event_cache()
        order = "DESC" if str(sort_order).lower() == "desc" else "ASC"
        sort_column = {
            "latest_active_date": "latest_active_date",
            "first_seen_date": "first_seen_date",
            "affected_stock_count": "affected_stock_count",
            "event_name": "event_name",
        }.get(sort_by, "latest_active_date")
        where_sql: list[str] = ["WHERE 1 = 1"]
        params: list[Any] = []
        self._append_market_event_filters(where_sql, params, filters)
        count_sql = f"SELECT COUNT(*) FROM kb_market_event {' '.join(where_sql)}"
        sql = [
            """
            SELECT
                event_key,
                event_name,
                event_time_text,
                event_content,
                event_type,
                event_scope,
                scope_reason,
                primary_industry,
                primary_theme,
                affected_stock_count,
                affected_stocks_preview_json,
                affected_industries_json,
                affected_themes_json,
                source_report_count,
                first_seen_date,
                latest_active_date,
                active_dates_json,
                is_cross_stock,
                is_active,
                EXISTS (
                    SELECT 1
                    FROM kb_market_event_member m
                    JOIN kb_simple_event_favorite f ON f.event_id = m.event_id
                    WHERE m.event_key = kb_market_event.event_key
                ) AS is_favorite,
                merge_method
            FROM kb_market_event
            """,
            *where_sql,
            f"ORDER BY {sort_column} {order}, event_name ASC",
            "LIMIT ? OFFSET ?",
        ]
        with self._connect() as conn:
            total_count = int(conn.execute(count_sql, params).fetchone()[0])
            rows = conn.execute("\n".join(sql), [*params, page_size, offset]).fetchall()
            columns = [item[0] for item in conn.description]
            items = [
                self._hydrate_market_event_payload(
                    self._serialize_mapping(dict(zip(columns, row, strict=True))),
                    include_detail=False,
                )
                for row in rows
            ]
        return self._build_page_response(
            "items",
            items,
            total_count=total_count,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters,
        )

    def query_market_event_detail(self, event_key: str) -> dict[str, Any]:
        if not event_key.strip() or not self.db_path.exists():
            return {"found": False, "event_key": event_key}
        self.ensure_schema()
        self._ensure_market_event_cache()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    event_key,
                    event_name,
                    event_time_text,
                    event_content,
                    event_type,
                    event_scope,
                    scope_reason,
                    primary_industry,
                    primary_theme,
                    risk_summary,
                    affected_stocks_json,
                    affected_industries_json,
                    affected_themes_json,
                    source_event_ids_json,
                    first_seen_date,
                    latest_active_date,
                    active_dates_json,
                    is_cross_stock,
                    is_active,
                    EXISTS (
                        SELECT 1
                        FROM kb_market_event_member m
                        JOIN kb_simple_event_favorite f ON f.event_id = m.event_id
                        WHERE m.event_key = kb_market_event.event_key
                    ) AS is_favorite,
                    merge_method
                FROM kb_market_event
                WHERE event_key = ?
                """,
                [event_key],
            ).fetchone()
            if row is None:
                return {"found": False, "event_key": event_key}
            columns = [item[0] for item in conn.description]
            payload = self._hydrate_market_event_payload(
                self._serialize_mapping(dict(zip(columns, row, strict=True))),
                include_detail=True,
            )
            payload["source_reports"] = self._load_market_event_source_reports_for_key(conn, event_key)
        return {"found": True, "event_key": event_key, "event": payload}

    def query_market_event_timeline(self, event_key: str) -> dict[str, Any]:
        if not event_key.strip() or not self.db_path.exists():
            return {"event_key": event_key, "timeline": []}
        self.ensure_schema()
        self._ensure_market_event_cache()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT timeline_json FROM kb_market_event WHERE event_key = ?",
                [event_key],
            ).fetchone()
            if row is None:
                return {"event_key": event_key, "timeline": []}
            timeline = self._parse_json_list(self._serialize_value(row[0]))
            return {
                "event_key": event_key,
                "timeline": [self._serialize_mapping(point) for point in timeline if isinstance(point, dict)],
            }
        return {"event_key": event_key, "timeline": []}

    def query_market_event_filter_meta(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return {
                "industries": [],
                "themes": [],
                "date_min": "",
                "date_max": "",
            }
        self.ensure_schema()
        self._ensure_market_event_cache()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT primary_industry, primary_theme, first_seen_date, latest_active_date
                FROM kb_market_event
                """
            ).fetchall()
        industries = sorted({str(row[0] or "").strip() for row in rows if str(row[0] or "").strip()})
        themes = sorted({str(row[1] or "").strip() for row in rows if str(row[1] or "").strip()})
        date_values = [
            str(row[2] or "")
            for row in rows
            if self._parse_date_like(row[2])
        ] + [
            str(row[3] or "")
            for row in rows
            if self._parse_date_like(row[3])
        ]
        sorted_dates = sorted({value for value in date_values if value})
        return {
            "industries": industries,
            "themes": themes,
            "date_min": sorted_dates[0] if sorted_dates else "",
            "date_max": sorted_dates[-1] if sorted_dates else "",
        }

    def set_simple_event_favorite(self, event_id: str, *, is_favorite: bool) -> dict[str, Any]:
        event_id = str(event_id or "").strip()
        if not event_id:
            raise ValueError("event_id 不能为空")
        if not self.db_path.exists():
            return {"found": False, "event_id": event_id, "is_favorite": False}
        self.ensure_schema()
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            event_exists = conn.execute(
                "SELECT 1 FROM kb_simple_event WHERE event_id = ?",
                [event_id],
            ).fetchone()
            if event_exists is None:
                return {"found": False, "event_id": event_id, "is_favorite": False}
            if is_favorite:
                existing_created_at = conn.execute(
                    "SELECT created_at FROM kb_simple_event_favorite WHERE event_id = ?",
                    [event_id],
                ).fetchone()
                created_at = existing_created_at[0] if existing_created_at else now
                conn.execute("DELETE FROM kb_simple_event_favorite WHERE event_id = ?", [event_id])
                conn.execute(
                    """
                    INSERT INTO kb_simple_event_favorite (event_id, created_at, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    [event_id, created_at, now],
                )
            else:
                conn.execute("DELETE FROM kb_simple_event_favorite WHERE event_id = ?", [event_id])
        return {"found": True, "event_id": event_id, "is_favorite": bool(is_favorite)}

    def _connect(self, *, read_only: bool = False):
        try:
            import duckdb
        except ImportError as exc:
            raise RuntimeError(
                "DuckDB is not installed in the current environment. "
                "Run `pip install duckdb` or `pip install -e .` before using stockkb."
            ) from exc
        return duckdb.connect(str(self.db_path), read_only=read_only)

    def _insert_many(self, conn: Any, table: str, items: list[Any], *, replace: bool = False) -> None:
        for item in items:
            self._insert_record(conn, table, asdict(item), replace=replace)

    def _insert_record(self, conn: Any, table: str, record: dict[str, Any], *, replace: bool = False) -> None:
        payload = {key: self._normalize_value(value) for key, value in record.items()}
        columns = list(payload.keys())
        placeholders = ", ".join("?" for _ in columns)
        insert_keyword = "INSERT OR REPLACE" if replace else "INSERT"
        conn.execute(
            f"{insert_keyword} INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[column] for column in columns],
        )

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        if value == "":
            return None
        return value

    def _append_simple_report_filters(self, sql: list[str], params: list[Any], filters: dict[str, Any]) -> None:
        supported_exact = {
            "stock_code": "r.stock_code",
            "report_date": "r.report_date",
        }
        supported_like = {
            "stock_name": "r.stock_name",
            "report_title": "r.report_title",
        }
        self._validate_filter_keys(filters, {*supported_exact, *supported_like}, "kb-query-simple-reports")
        for key, column in supported_exact.items():
            value = filters.get(key)
            if value is None or value == "":
                continue
            sql.append(f"AND {column} = ?")
            params.append(value)
        for key, column in supported_like.items():
            value = filters.get(key)
            if value is None or value == "":
                continue
            sql.append(f"AND LOWER({column}) LIKE LOWER(?)")
            params.append(f"%{value}%")

    def _append_simple_event_filters(self, sql: list[str], params: list[Any], filters: dict[str, Any]) -> None:
        supported_exact = {
            "stock_code": "r.stock_code",
            "report_date": "r.report_date",
            "report_id": "e.report_id",
        }
        supported_like = {
            "stock_name": "r.stock_name",
            "event_name": "e.event_name",
            "report_title": "r.report_title",
        }
        self._validate_filter_keys(filters, {*supported_exact, *supported_like}, "kb-query-simple-events")
        for key, column in supported_exact.items():
            value = filters.get(key)
            if value is None or value == "":
                continue
            sql.append(f"AND {column} = ?")
            params.append(value)
        for key, column in supported_like.items():
            value = filters.get(key)
            if value is None or value == "":
                continue
            sql.append(f"AND LOWER({column}) LIKE LOWER(?)")
            params.append(f"%{value}%")

    def _append_market_event_filters(self, sql: list[str], params: list[Any], filters: dict[str, Any]) -> None:
        self._validate_market_event_filter_keys(filters)
        keyword = str(filters.get("keyword") or "").strip()
        industry = str(filters.get("industry") or "").strip()
        theme = str(filters.get("theme") or "").strip()
        event_type = str(filters.get("event_type") or "").strip().lower()
        date_from = str(filters.get("date_from") or "").strip()
        date_to = str(filters.get("date_to") or "").strip()
        min_count = filters.get("min_affected_stock_count")
        favorites_only = filters.get("favorites_only")
        is_cross_stock = filters.get("is_cross_stock")
        is_active = filters.get("is_active")

        if keyword:
            sql.append("AND LOWER(CONCAT(event_name, ' ', event_content, ' ', primary_industry, ' ', primary_theme)) LIKE LOWER(?)")
            params.append(f"%{keyword}%")
        if industry:
            sql.append("AND LOWER(primary_industry) LIKE LOWER(?)")
            params.append(f"%{industry}%")
        if theme:
            sql.append("AND LOWER(primary_theme) LIKE LOWER(?)")
            params.append(f"%{theme}%")
        if event_type in {"industry", "stock"}:
            sql.append("AND event_type = ?")
            params.append(event_type)
        if date_from:
            sql.append("AND (latest_active_date IS NULL OR latest_active_date >= ?)")
            params.append(date_from)
        if date_to:
            sql.append("AND (first_seen_date IS NULL OR first_seen_date <= ?)")
            params.append(date_to)
        if min_count not in (None, ""):
            sql.append("AND affected_stock_count >= ?")
            params.append(int(min_count))
        if favorites_only:
            sql.append(
                """
                AND EXISTS (
                    SELECT 1
                    FROM kb_market_event_member m
                    JOIN kb_simple_event_favorite f ON f.event_id = m.event_id
                    WHERE m.event_key = kb_market_event.event_key
                )
                """
            )
        if is_cross_stock is not None:
            sql.append("AND is_cross_stock = ?")
            params.append(bool(is_cross_stock))
        if is_active is not None:
            sql.append("AND is_active = ?")
            params.append(bool(is_active))

    def _validate_market_event_filter_keys(self, filters: dict[str, Any]) -> None:
        supported = {
            "date_from",
            "date_to",
            "keyword",
            "industry",
            "theme",
            "event_type",
            "favorites_only",
            "is_cross_stock",
            "min_affected_stock_count",
            "is_active",
        }
        self._validate_filter_keys(filters, supported, "kb-query-market-events")

    def _validate_filter_keys(self, filters: dict[str, Any], supported: set[str], command_name: str) -> None:
        invalid = sorted(key for key in filters if key not in supported)
        if invalid:
            allowed = ", ".join(sorted(supported))
            invalid_text = ", ".join(invalid)
            raise ValueError(f"Unsupported {command_name} filter key(s): {invalid_text}. Allowed keys: {allowed}")

    def _normalize_pagination(self, page: int, page_size: int) -> tuple[int, int, int]:
        if page < 1:
            raise ValueError("`page` must be >= 1")
        if page_size < 1 or page_size > 500:
            raise ValueError("`page_size` must be between 1 and 500")
        offset = (page - 1) * page_size
        return page, page_size, offset

    def _serialize_mapping(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {key: self._serialize_value(value) for key, value in payload.items()}

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    def _hydrate_simple_event_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["affected_stocks"] = self._parse_json_list(normalized.get("affected_stock_codes_json"))
        normalized["affected_industries"] = self._parse_json_string_list(normalized.get("affected_industries_json"))
        normalized["affected_themes"] = self._parse_json_string_list(normalized.get("affected_themes_json"))
        normalized["event_scope"] = str(normalized.get("event_scope") or "")
        normalized["scope_reason"] = str(normalized.get("scope_reason") or "")
        normalized["canonical_event_key"] = str(normalized.get("canonical_event_key") or "")
        normalized["event_type"] = str(normalized.get("event_type") or "")
        normalized["source_name"] = str(normalized.get("source_name") or "")
        normalized["source_url"] = str(normalized.get("source_url") or "")
        normalized["anchor_block_id"] = str(normalized.get("anchor_block_id") or "")
        normalized["evidence_text"] = str(normalized.get("evidence_text") or "")
        normalized["report_source_name"] = str(normalized.get("report_source_name") or "")
        normalized["is_favorite"] = bool(normalized.get("is_favorite", False))
        return normalized

    def _hydrate_market_event_payload(self, payload: dict[str, Any], *, include_detail: bool) -> dict[str, Any]:
        normalized = dict(payload)
        normalized["event_type"] = str(normalized.get("event_type") or "")
        normalized["event_scope"] = str(normalized.get("event_scope") or "")
        normalized["scope_reason"] = str(normalized.get("scope_reason") or "")
        normalized["primary_industry"] = str(normalized.get("primary_industry") or "")
        normalized["primary_theme"] = str(normalized.get("primary_theme") or "")
        normalized["affected_stock_count"] = int(normalized.get("affected_stock_count") or 0)
        normalized["source_report_count"] = int(normalized.get("source_report_count") or 0)
        normalized["source_event_count"] = int(normalized.get("source_event_count") or 0)
        normalized["merge_method"] = str(normalized.get("merge_method") or "")
        normalized["is_favorite"] = bool(normalized.get("is_favorite", False))
        normalized["affected_stocks_preview"] = self._parse_json_list(normalized.get("affected_stocks_preview_json"))
        normalized["affected_industries"] = self._parse_json_string_list(normalized.get("affected_industries_json"))
        normalized["affected_themes"] = self._parse_json_string_list(normalized.get("affected_themes_json"))
        normalized["active_dates"] = self._parse_json_string_list(normalized.get("active_dates_json"))
        normalized["is_cross_stock"] = bool(normalized.get("is_cross_stock", False))
        normalized["is_active"] = bool(normalized.get("is_active", False))
        if include_detail:
            normalized["risk_summary"] = str(normalized.get("risk_summary") or "")
            normalized["affected_stocks"] = self._parse_json_list(normalized.get("affected_stocks_json"))
            normalized["source_event_ids"] = self._parse_json_string_list(normalized.get("source_event_ids_json"))
            normalized["source_reports"] = []
        return normalized

    def get_market_event_judge_cache(self, pair_key: str) -> dict[str, Any] | None:
        if not pair_key.strip() or not self.db_path.exists():
            return None
        self.ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT pair_key, left_event_id, right_event_id, same_event, confidence, reason, model, prompt_version
                FROM kb_market_event_judge_cache
                WHERE pair_key = ?
                """,
                [pair_key],
            ).fetchone()
            if row is None:
                return None
            columns = [item[0] for item in conn.description]
            return self._serialize_mapping(dict(zip(columns, row, strict=True)))

    def upsert_market_event_judge_cache(self, payload: dict[str, Any]) -> None:
        self.ensure_schema()
        record = dict(payload)
        now = datetime.utcnow().isoformat()
        record.setdefault("created_at", now)
        record["updated_at"] = now
        with self._connect() as conn:
            self._insert_record(conn, "kb_market_event_judge_cache", record, replace=True)

    def _load_market_event_source_rows(self) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    e.event_id,
                    e.report_id,
                    e.event_name,
                    e.event_time_text,
                    e.event_time_normalized,
                    e.event_content,
                    e.canonical_event_key,
                    e.event_type,
                    e.event_scope,
                    e.scope_reason,
                    e.source_name,
                    e.source_url,
                    e.affected_stock_codes_json,
                    e.affected_industries_json,
                    e.affected_themes_json,
                    e.anchor_block_id,
                    e.evidence_text,
                    r.stock_code,
                    r.stock_name,
                    r.report_date,
                    r.report_title,
                    r.risk_summary,
                    r.source_path,
                    r.source_name AS report_source_name
                FROM kb_simple_event e
                JOIN kb_simple_report r ON r.report_id = e.report_id
                """
            ).fetchall()
            columns = [item[0] for item in conn.description]
        return [
            self._hydrate_simple_event_payload(
                self._serialize_mapping(dict(zip(columns, row, strict=True)))
            )
            for row in rows
        ]

    def _build_market_event_groups(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            event_key = self._make_market_event_key(row)
            grouped.setdefault(event_key, []).append(row)

        results: list[dict[str, Any]] = []
        for event_key, items in grouped.items():
            first_item = items[0]
            event_name = str(first_item.get("event_name") or "")
            event_time_text = str(first_item.get("event_time_text") or "")
            event_content = self._pick_longest_text(item.get("event_content") for item in items)
            risk_summary = self._pick_longest_text(item.get("risk_summary") for item in items)
            affected_stocks = self._merge_affected_stocks(items)
            affected_industries = self._merge_string_lists(item.get("affected_industries") for item in items)
            affected_themes = self._merge_string_lists(item.get("affected_themes") for item in items)
            event_scope = self._pick_event_scope(items)
            scope_reason = self._pick_longest_text(item.get("scope_reason") for item in items)
            active_dates = self._sorted_report_dates(items)
            primary_theme = affected_themes[0] if affected_themes else self._infer_primary_theme(event_name, event_content)
            primary_industry = affected_industries[0] if affected_industries else self._infer_primary_industry(primary_theme, event_name, event_content)
            source_reports = self._build_market_event_source_reports(items)
            latest_active_date = active_dates[-1] if active_dates else ""
            first_seen_date = active_dates[0] if active_dates else ""
            timeline = self._build_market_event_timeline(items)
            results.append(
                {
                    "event_key": event_key,
                    "event_name": event_name,
                    "event_time_text": event_time_text,
                    "event_content": event_content,
                    "event_scope": event_scope,
                    "scope_reason": scope_reason,
                    "primary_industry": primary_industry,
                    "primary_theme": primary_theme,
                    "risk_summary": risk_summary,
                    "affected_stock_count": len(affected_stocks),
                    "affected_stocks_preview": affected_stocks[:3],
                    "affected_stocks": affected_stocks,
                    "affected_industries": affected_industries,
                    "affected_themes": affected_themes,
                    "source_report_count": len(source_reports),
                    "source_reports": source_reports,
                    "source_event_ids": sorted({str(item.get("event_id") or "") for item in items if item.get("event_id")}),
                    "first_seen_date": first_seen_date,
                    "latest_active_date": latest_active_date,
                    "active_dates": active_dates,
                    "is_cross_stock": len(affected_stocks) > 1,
                    "is_active": self._is_active_date(latest_active_date),
                    "timeline": timeline,
                }
            )
        return results

    def _filter_market_event_groups(self, groups: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
        self._validate_market_event_filter_keys(filters)
        keyword = str(filters.get("keyword") or "").strip().lower()
        industry = str(filters.get("industry") or "").strip().lower()
        theme = str(filters.get("theme") or "").strip().lower()
        date_from = self._parse_date_like(filters.get("date_from"))
        date_to = self._parse_date_like(filters.get("date_to"))
        min_count = filters.get("min_affected_stock_count")
        is_cross_stock = filters.get("is_cross_stock")
        is_active = filters.get("is_active")

        filtered: list[dict[str, Any]] = []
        for item in groups:
            first_seen_date = self._parse_date_like(item.get("first_seen_date"))
            latest_active_date = self._parse_date_like(item.get("latest_active_date"))
            if date_from and latest_active_date and latest_active_date < date_from:
                continue
            if date_to and first_seen_date and first_seen_date > date_to:
                continue
            if keyword:
                haystack = " ".join(
                    [
                        str(item.get("event_name") or ""),
                        str(item.get("event_content") or ""),
                        str(item.get("primary_industry") or ""),
                        str(item.get("primary_theme") or ""),
                    ]
                ).lower()
                if keyword not in haystack:
                    continue
            if industry and industry not in str(item.get("primary_industry") or "").lower():
                continue
            if theme and theme not in str(item.get("primary_theme") or "").lower():
                continue
            if min_count not in (None, "") and int(item.get("affected_stock_count") or 0) < int(min_count):
                continue
            if is_cross_stock is not None and bool(item.get("is_cross_stock")) != bool(is_cross_stock):
                continue
            if is_active is not None and bool(item.get("is_active")) != bool(is_active):
                continue
            filtered.append(item)
        return filtered

    def _sort_market_event_groups(
        self,
        groups: list[dict[str, Any]],
        *,
        sort_by: str,
        sort_order: str,
    ) -> list[dict[str, Any]]:
        reverse = str(sort_order).lower() == "desc"
        key_map = {
            "latest_active_date": lambda item: str(item.get("latest_active_date") or ""),
            "first_seen_date": lambda item: str(item.get("first_seen_date") or ""),
            "affected_stock_count": lambda item: int(item.get("affected_stock_count") or 0),
            "event_name": lambda item: str(item.get("event_name") or ""),
        }
        key_fn = key_map.get(sort_by, key_map["latest_active_date"])
        return sorted(
            groups,
            key=lambda item: (key_fn(item), str(item.get("event_name") or "")),
            reverse=reverse,
        )

    def _make_market_event_key(self, row: dict[str, Any]) -> str:
        event_name = str(row.get("event_name") or "")
        normalized_name = self._normalize_market_event_name(event_name)
        normalized_title = re.sub(r"[^0-9a-z]+", "_", normalized_name).strip("_")
        title_hash = hashlib.sha1(normalized_name.encode("utf-8")).hexdigest()[:10] if normalized_name else "event"
        if normalized_title:
            return f"mkt_{normalized_title}_{title_hash}"
        return f"mkt_{title_hash}"

    def _normalize_market_event_name(self, value: str) -> str:
        raw = str(value or "").strip().lower()
        raw = raw.replace("nvidia", "英伟达")
        raw = raw.replace("reits", "reits")
        raw = re.sub(r"[\s\u3000\"'“”‘’（）()，,。:：;；、】【/\\-]+", "", raw)
        return raw

    def _merge_affected_stocks(self, items: list[dict[str, Any]]) -> list[dict[str, str]]:
        merged: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in items:
            for stock in item.get("affected_stocks") or []:
                if not isinstance(stock, dict):
                    continue
                stock_code = str(stock.get("stock_code") or "").strip()
                stock_name = str(stock.get("stock_name") or "").strip()
                dedupe_key = stock_code or stock_name
                if not dedupe_key or dedupe_key in seen:
                    continue
                merged.append({"stock_code": stock_code, "stock_name": stock_name})
                seen.add(dedupe_key)
        return merged

    def _merge_string_lists(self, values: Any) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for raw_items in values:
            items = raw_items if isinstance(raw_items, list) else []
            for raw in items:
                text = str(raw or "").strip()
                normalized = text.lower()
                if not text or normalized in seen:
                    continue
                merged.append(text)
                seen.add(normalized)
        return merged

    def _pick_event_scope(self, items: list[dict[str, Any]]) -> str:
        priority = {"mixed": 4, "industry": 3, "macro": 2, "stock": 1, "": 0}
        best = ""
        for item in items:
            value = str(item.get("event_scope") or "").strip().lower()
            if priority.get(value, 0) > priority.get(best, 0):
                best = value
        return best

    def _build_market_event_source_reports(self, items: list[dict[str, Any]]) -> list[dict[str, str]]:
        reports: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in items:
            report_id = str(item.get("report_id") or "").strip()
            if not report_id or report_id in seen:
                continue
            reports.append(
                {
                    "report_id": report_id,
                    "report_title": str(item.get("report_title") or ""),
                    "stock_code": str(item.get("stock_code") or ""),
                    "stock_name": str(item.get("stock_name") or ""),
                    "report_date": self._extract_iso_date(str(item.get("report_date") or "")) or str(item.get("report_date") or ""),
                    "source_name": str(item.get("source_name") or ""),
                    "source_url": str(item.get("source_url") or ""),
                    "source_path": str(item.get("source_path") or ""),
                }
            )
            seen.add(report_id)
        reports.sort(key=lambda item: (item.get("report_date") or "", item.get("stock_code") or ""))
        return reports

    def _build_market_event_timeline(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        timeline_map: dict[str, dict[str, Any]] = {}
        for item in items:
            report_date = self._extract_iso_date(str(item.get("report_date") or "")) or str(item.get("report_date") or "")
            if not report_date:
                continue
            entry = timeline_map.setdefault(
                report_date,
                {
                    "date": report_date,
                    "stocks": [],
                    "affected_stock_count": 0,
                    "source_report_count": 0,
                },
            )
            seen_codes = {str(stock.get("stock_code") or stock.get("stock_name") or "") for stock in entry["stocks"]}
            for stock in item.get("affected_stocks") or []:
                if not isinstance(stock, dict):
                    continue
                dedupe_key = str(stock.get("stock_code") or stock.get("stock_name") or "")
                if not dedupe_key or dedupe_key in seen_codes:
                    continue
                entry["stocks"].append(
                    {
                        "stock_code": str(stock.get("stock_code") or ""),
                        "stock_name": str(stock.get("stock_name") or ""),
                    }
                )
                seen_codes.add(dedupe_key)
            entry["affected_stock_count"] = len(entry["stocks"])
            entry["source_report_count"] = entry.get("source_report_count", 0) + 1
        return [timeline_map[key] for key in sorted(timeline_map)]

    def _sorted_report_dates(self, items: list[dict[str, Any]]) -> list[str]:
        dates = {
            self._extract_iso_date(str(item.get("report_date") or ""))
            for item in items
            if self._extract_iso_date(str(item.get("report_date") or ""))
        }
        return sorted(date_value for date_value in dates if date_value)

    def _pick_longest_text(self, values: Any) -> str:
        texts = [str(value or "").strip() for value in values if str(value or "").strip()]
        if not texts:
            return ""
        return max(texts, key=len)

    def _infer_primary_theme(self, event_name: str, event_content: str) -> str:
        text = f"{event_name} {event_content}"
        theme_keywords = (
            "超级电容",
            "机器人",
            "工业机器人",
            "REITs",
            "煤炭",
            "煤矿安全",
            "电力",
            "算力",
            "白酒",
            "区块链",
            "半导体",
            "光刻胶",
            "储能",
            "风电",
            "消费",
        )
        for keyword in theme_keywords:
            if keyword in text:
                return keyword
        return ""

    def _infer_primary_industry(self, primary_theme: str, event_name: str, event_content: str) -> str:
        theme_industry_map = {
            "超级电容": "电子",
            "机器人": "机械设备",
            "工业机器人": "机械设备",
            "REITs": "房地产",
            "煤炭": "煤炭",
            "煤矿安全": "煤炭",
            "电力": "公用事业",
            "算力": "计算机",
            "白酒": "食品饮料",
            "区块链": "计算机",
            "半导体": "电子",
            "光刻胶": "电子",
            "储能": "电力设备",
            "风电": "电力设备",
            "消费": "商贸零售",
        }
        if primary_theme in theme_industry_map:
            return theme_industry_map[primary_theme]
        text = f"{event_name} {event_content}"
        if "煤" in text:
            return "煤炭"
        if "电" in text:
            return "公用事业"
        return ""

    def _is_active_date(self, latest_active_date: str) -> bool:
        parsed = self._parse_date_like(latest_active_date)
        if parsed is None:
            return False
        return (date.today() - parsed).days <= 5

    def _parse_date_like(self, value: Any) -> date | None:
        raw = self._extract_iso_date(str(value or ""))
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _extract_iso_date(self, text: str) -> str:
        match = re.search(r"(20\d{2}-\d{2}-\d{2})", str(text or ""))
        return match.group(1) if match else ""

    def _parse_json_list(self, value: Any) -> list[Any]:
        if not value:
            return []
        if isinstance(value, list):
            return value
        if not isinstance(value, str):
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    def _parse_json_string_list(self, value: Any) -> list[str]:
        parsed = self._parse_json_list(value)
        items: list[str] = []
        seen: set[str] = set()
        for raw in parsed:
            text = str(raw or "").strip()
            normalized = text.lower()
            if not text or normalized in seen:
                continue
            items.append(text)
            seen.add(normalized)
        return items

    def _ensure_market_event_cache(self) -> None:
        if not self.db_path.exists():
            return
        with self._connect() as conn:
            simple_event_count = int(conn.execute("SELECT COUNT(*) FROM kb_simple_event").fetchone()[0])
            market_event_count = int(conn.execute("SELECT COUNT(*) FROM kb_market_event").fetchone()[0])
        if simple_event_count > 0 and market_event_count == 0:
            self.rebuild_market_events()

    def _load_market_event_source_reports_for_key(self, conn: Any, event_key: str) -> list[dict[str, str]]:
        rows = conn.execute(
            """
            SELECT
                m.report_id,
                r.report_title,
                r.stock_code,
                r.stock_name,
                r.report_date,
                e.source_name,
                e.source_url,
                r.source_path
            FROM kb_market_event_member m
            JOIN kb_simple_event e ON e.event_id = m.event_id
            JOIN kb_simple_report r ON r.report_id = m.report_id
            WHERE m.event_key = ?
            ORDER BY r.report_date ASC, r.stock_code ASC
            """,
            [event_key],
        ).fetchall()
        columns = [item[0] for item in conn.description]
        reports: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in rows:
            payload = self._serialize_mapping(dict(zip(columns, row, strict=True)))
            report_id = str(payload.get("report_id") or "").strip()
            if not report_id or report_id in seen:
                continue
            reports.append(
                {
                    "report_id": report_id,
                    "report_title": str(payload.get("report_title") or ""),
                    "stock_code": str(payload.get("stock_code") or ""),
                    "stock_name": str(payload.get("stock_name") or ""),
                    "report_date": self._extract_iso_date(str(payload.get("report_date") or "")) or str(payload.get("report_date") or ""),
                    "source_name": str(payload.get("source_name") or ""),
                    "source_url": str(payload.get("source_url") or ""),
                    "source_path": str(payload.get("source_path") or ""),
                }
            )
            seen.add(report_id)
        return reports

    def _ensure_simple_event_columns(self, conn: Any) -> None:
        existing_columns = {
            str(row[1]).strip().lower()
            for row in conn.execute("PRAGMA table_info('kb_simple_event')").fetchall()
        }
        required_columns = {
            "canonical_event_key": "VARCHAR",
            "event_type": "VARCHAR",
            "event_scope": "VARCHAR",
            "scope_reason": "VARCHAR",
            "source_name": "VARCHAR",
            "source_url": "VARCHAR",
            "affected_industries_json": "VARCHAR",
            "affected_themes_json": "VARCHAR",
            "anchor_block_id": "VARCHAR",
            "evidence_text": "VARCHAR",
        }
        for column_name, column_type in required_columns.items():
            if column_name in existing_columns:
                continue
            conn.execute(f"ALTER TABLE kb_simple_event ADD COLUMN {column_name} {column_type}")

    def _ensure_market_event_columns(self, conn: Any) -> None:
        existing_columns = {
            str(row[1]).strip().lower()
            for row in conn.execute("PRAGMA table_info('kb_market_event')").fetchall()
        }
        required_columns = {
            "event_type": "VARCHAR",
            "event_scope": "VARCHAR",
            "scope_reason": "VARCHAR",
            "primary_industry": "VARCHAR",
            "primary_theme": "VARCHAR",
            "risk_summary": "VARCHAR",
            "affected_stock_count": "INTEGER",
            "affected_stocks_preview_json": "VARCHAR",
            "affected_stocks_json": "VARCHAR",
            "affected_industries_json": "VARCHAR",
            "affected_themes_json": "VARCHAR",
            "source_report_count": "INTEGER",
            "source_event_count": "INTEGER",
            "source_event_ids_json": "VARCHAR",
            "first_seen_date": "VARCHAR",
            "latest_active_date": "VARCHAR",
            "active_dates_json": "VARCHAR",
            "is_cross_stock": "BOOLEAN",
            "is_active": "BOOLEAN",
            "timeline_json": "VARCHAR",
            "merge_method": "VARCHAR",
            "merge_confidence": "DOUBLE",
            "merge_reason": "VARCHAR",
            "created_at": "TIMESTAMP",
            "updated_at": "TIMESTAMP",
        }
        for column_name, column_type in required_columns.items():
            if column_name in existing_columns:
                continue
            conn.execute(f"ALTER TABLE kb_market_event ADD COLUMN {column_name} {column_type}")

    def _ensure_market_event_member_columns(self, conn: Any) -> None:
        existing_columns = {
            str(row[1]).strip().lower()
            for row in conn.execute("PRAGMA table_info('kb_market_event_member')").fetchall()
        }
        required_columns = {
            "is_primary": "BOOLEAN",
            "merge_method": "VARCHAR",
            "merge_confidence": "DOUBLE",
            "merge_reason": "VARCHAR",
            "created_at": "TIMESTAMP",
        }
        for column_name, column_type in required_columns.items():
            if column_name in existing_columns:
                continue
            conn.execute(f"ALTER TABLE kb_market_event_member ADD COLUMN {column_name} {column_type}")

    def _ensure_market_event_judge_cache_columns(self, conn: Any) -> None:
        existing_columns = {
            str(row[1]).strip().lower()
            for row in conn.execute("PRAGMA table_info('kb_market_event_judge_cache')").fetchall()
        }
        required_columns = {
            "left_event_id": "VARCHAR",
            "right_event_id": "VARCHAR",
            "same_event": "BOOLEAN",
            "confidence": "DOUBLE",
            "reason": "VARCHAR",
            "model": "VARCHAR",
            "prompt_version": "VARCHAR",
            "created_at": "TIMESTAMP",
            "updated_at": "TIMESTAMP",
        }
        for column_name, column_type in required_columns.items():
            if column_name in existing_columns:
                continue
            conn.execute(f"ALTER TABLE kb_market_event_judge_cache ADD COLUMN {column_name} {column_type}")

    def _ensure_simple_report_columns(self, conn: Any) -> None:
        existing_columns = {
            str(row[1]).strip().lower()
            for row in conn.execute("PRAGMA table_info('kb_simple_report')").fetchall()
        }
        required_columns = {
            "core_logic": "VARCHAR",
        }
        for column_name, column_type in required_columns.items():
            if column_name in existing_columns:
                continue
            conn.execute(f"ALTER TABLE kb_simple_report ADD COLUMN {column_name} {column_type}")

    def _empty_page(
        self,
        field_name: str,
        filters: dict[str, Any],
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> dict[str, Any]:
        return self._build_page_response(
            field_name,
            [],
            total_count=0,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters,
        )

    def _build_page_response(
        self,
        field_name: str,
        items: list[dict[str, Any]],
        *,
        total_count: int,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "count": len(items),
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_order": sort_order.lower(),
            "has_more": (page - 1) * page_size + len(items) < total_count,
            "filters": filters,
            field_name: items,
        }
