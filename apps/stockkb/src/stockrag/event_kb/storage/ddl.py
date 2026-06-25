from __future__ import annotations


DDL_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS kb_simple_report (
        report_id VARCHAR PRIMARY KEY,
        source_path VARCHAR NOT NULL,
        source_name VARCHAR NOT NULL,
        report_title VARCHAR NOT NULL,
        core_logic VARCHAR,
        stock_code VARCHAR,
        stock_name VARCHAR,
        report_date VARCHAR,
        risk_summary VARCHAR,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kb_simple_event (
        event_id VARCHAR PRIMARY KEY,
        report_id VARCHAR NOT NULL,
        event_name VARCHAR NOT NULL,
        event_time_text VARCHAR,
        event_time_normalized VARCHAR,
        event_content VARCHAR,
        canonical_event_key VARCHAR,
        event_type VARCHAR,
        event_scope VARCHAR,
        scope_reason VARCHAR,
        source_name VARCHAR,
        source_url VARCHAR,
        affected_stock_codes_json VARCHAR,
        affected_industries_json VARCHAR,
        affected_themes_json VARCHAR,
        anchor_block_id VARCHAR,
        evidence_text VARCHAR,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kb_market_event (
        event_key VARCHAR PRIMARY KEY,
        event_name VARCHAR NOT NULL,
        event_time_text VARCHAR,
        event_content VARCHAR,
        event_type VARCHAR,
        event_scope VARCHAR,
        scope_reason VARCHAR,
        primary_industry VARCHAR,
        primary_theme VARCHAR,
        risk_summary VARCHAR,
        affected_stock_count INTEGER,
        affected_stocks_preview_json VARCHAR,
        affected_stocks_json VARCHAR,
        affected_industries_json VARCHAR,
        affected_themes_json VARCHAR,
        source_report_count INTEGER,
        source_event_count INTEGER,
        source_event_ids_json VARCHAR,
        first_seen_date VARCHAR,
        latest_active_date VARCHAR,
        active_dates_json VARCHAR,
        is_cross_stock BOOLEAN,
        -- is_active: DEPRECATED. Old "5-day activity" heuristic, see
        -- market_event_builder._is_active_date for historical reference.
        -- New writes always set FALSE; historical rows preserved as-is.
        -- The column itself is kept (no ALTER TABLE) until a fresh
        -- activity concept replaces it.
        is_active BOOLEAN,
        timeline_json VARCHAR,
        merge_method VARCHAR,
        merge_confidence DOUBLE,
        merge_reason VARCHAR,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kb_market_event_member (
        event_key VARCHAR NOT NULL,
        event_id VARCHAR NOT NULL,
        report_id VARCHAR NOT NULL,
        is_primary BOOLEAN,
        merge_method VARCHAR,
        merge_confidence DOUBLE,
        merge_reason VARCHAR,
        created_at TIMESTAMP,
        PRIMARY KEY (event_key, event_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kb_market_event_judge_cache (
        pair_key VARCHAR PRIMARY KEY,
        left_event_id VARCHAR NOT NULL,
        right_event_id VARCHAR NOT NULL,
        same_event BOOLEAN,
        confidence DOUBLE,
        reason VARCHAR,
        model VARCHAR,
        prompt_version VARCHAR,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kb_simple_event_favorite (
        event_id VARCHAR PRIMARY KEY,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kb_market_event_review (
        event_key VARCHAR PRIMARY KEY,
        review_status VARCHAR NOT NULL,
        review_version VARCHAR,
        review_source VARCHAR,
        vibe_session_id VARCHAR,
        event_truth VARCHAR,
        time_truth VARCHAR,
        content_truth VARCHAR,
        disposition VARCHAR,
        confidence DOUBLE,
        headline VARCHAR,
        summary VARCHAR,
        review_payload VARCHAR,
        source_snapshot VARCHAR,
        error_message VARCHAR,
        requested_at TIMESTAMP,
        completed_at TIMESTAMP,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    )
    """,
)
