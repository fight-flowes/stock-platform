/**
 * @typedef {Object} MarketEventFilters
 * @property {string} date_from
 * @property {string} date_to
 * @property {string} keyword
 * @property {string} industry
 * @property {string} theme
 * @property {string} event_type
 * @property {boolean|null} favorites_only
 * @property {boolean|null} is_cross_stock
 * @property {number|null} min_affected_stock_count
 * @property {boolean|null} is_active  DEPRECATED — see kb_market_event schema. Frozen at false for new rows; UI no longer renders the "发酵中" badge that consumed this field. Reserved for redesign.
 */

/**
 * @typedef {Object} MarketEventStock
 * @property {string} stock_code
 * @property {string} stock_name
 */

/**
 * @typedef {Object} MarketEventSourceReport
 * @property {string} report_id
 * @property {string} report_title
 * @property {string} stock_code
 * @property {string} stock_name
 * @property {string} report_date
 * @property {string} source_name
 * @property {string} source_url
 * @property {string} source_path
 */

/**
 * @typedef {Object} MarketEventListItem
 * @property {string} event_key
 * @property {string} event_name
 * @property {string} event_time_text
 * @property {string} event_content
 * @property {string} event_type
 * @property {string} event_scope
 * @property {string} scope_reason
 * @property {string} primary_industry
 * @property {string} primary_theme
 * @property {string[]} affected_industries
 * @property {string[]} affected_themes
 * @property {number} affected_stock_count
 * @property {MarketEventStock[]} affected_stocks_preview
 * @property {number} source_report_count
 * @property {string} first_seen_date
 * @property {string} latest_active_date
 * @property {string[]} active_dates
 * @property {boolean} is_cross_stock
 * @property {boolean} is_active  DEPRECATED — frozen at false for new events. Historical rows preserved.
 * @property {string} review_status
 * @property {string} review_updated_at
 * @property {string} record_source
 * @property {boolean} is_favorite
 */

/**
 * @typedef {Object} MarketEventDetail
 * @property {string} event_key
 * @property {string} event_name
 * @property {string} event_time_text
 * @property {string} event_content
 * @property {string} event_type
 * @property {string} event_scope
 * @property {string} scope_reason
 * @property {string} primary_industry
 * @property {string} primary_theme
 * @property {string[]} affected_industries
 * @property {string[]} affected_themes
 * @property {string} risk_summary
 * @property {string} first_seen_date
 * @property {string} latest_active_date
 * @property {string[]} active_dates
 * @property {MarketEventStock[]} affected_stocks
 * @property {MarketEventSourceReport[]} source_reports
 * @property {string[]} source_event_ids
 * @property {string} review_status
 * @property {string} review_updated_at
 * @property {string} record_source
 * @property {boolean} is_favorite
 */

/**
 * @typedef {Object} MarketEventTimelinePoint
 * @property {string} date
 * @property {number} affected_stock_count
 * @property {MarketEventStock[]} stocks
 * @property {number} source_report_count
 */

/**
 * @typedef {Object} MarketEventReview
 * @property {string} event_key
 * @property {string} review_status
 * @property {string} review_version
 * @property {string} review_source
 * @property {string} event_truth
 * @property {string} time_truth
 * @property {string} content_truth
 * @property {string} disposition
 * @property {number} confidence
 * @property {string} headline
 * @property {string} summary
 * @property {Object} review_payload
 * @property {Object} source_snapshot
 * @property {string} error_message
 * @property {string} requested_at
 * @property {string} completed_at
 * @property {string} created_at
 * @property {string} updated_at
 */

/**
 * @typedef {Object} MarketEventFilterMeta
 * @property {string[]} industries
 * @property {string[]} themes
 * @property {string} date_min
 * @property {string} date_max
 */

export function createDefaultMarketEventFilters(overrides = {}) {
  return {
    date_from: '',
    date_to: '',
    keyword: '',
    industry: '',
    theme: '',
    event_type: 'all',
    favorites_only: null,
    is_cross_stock: null,
    min_affected_stock_count: null,
    is_active: null,
    ...overrides
  }
}

export function createDefaultMarketEventListItem() {
  return {
    event_key: '',
    event_name: '',
    event_time_text: '',
    event_content: '',
    event_type: '',
    event_scope: '',
    scope_reason: '',
    primary_industry: '',
    primary_theme: '',
    affected_industries: [],
    affected_themes: [],
    affected_stock_count: 0,
    affected_stocks_preview: [],
    source_report_count: 0,
    first_seen_date: '',
    latest_active_date: '',
    active_dates: [],
    is_cross_stock: false,
    is_active: false,
    review_status: '',
    review_updated_at: '',
    record_source: 'market',
    is_favorite: false
  }
}

export function createDefaultMarketEventDetail() {
  return {
    event_key: '',
    event_name: '',
    event_time_text: '',
    event_content: '',
    event_type: '',
    event_scope: '',
    scope_reason: '',
    primary_industry: '',
    primary_theme: '',
    affected_industries: [],
    affected_themes: [],
    risk_summary: '',
    first_seen_date: '',
    latest_active_date: '',
    active_dates: [],
    affected_stocks: [],
    source_reports: [],
    source_event_ids: [],
    review_status: '',
    review_updated_at: '',
    record_source: 'market',
    is_favorite: false
  }
}

export function createDefaultMarketEventTimelinePoint() {
  return {
    date: '',
    affected_stock_count: 0,
    stocks: [],
    source_report_count: 0
  }
}

export function createDefaultMarketEventFilterMeta() {
  return {
    industries: [],
    themes: [],
    date_min: '',
    date_max: ''
  }
}

export function createDefaultMarketEventReview() {
  return {
    event_key: '',
    review_status: '',
    review_version: '',
    review_source: '',
    event_truth: '',
    time_truth: '',
    content_truth: '',
    disposition: '',
    confidence: 0,
    headline: '',
    summary: '',
    review_payload: {},
    source_snapshot: {},
    error_message: '',
    requested_at: '',
    completed_at: '',
    created_at: '',
    updated_at: ''
  }
}
