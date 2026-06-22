import api from './client'

// Eventradar forward-looking events, proxied through calenderapp.
// The client interceptor unwraps the response to `{code, message, data, ...}` —
// callers should read `.data` for the actual payload.

export function getAnnouncementsHealth() {
  return api.get('/api/announcements/health')
}

export function listAnnouncements(payload) {
  // payload: { page, page_size, sort_by, sort_order, filters: {...} }
  // filters supports: date_from, date_to, scope, event_type, source,
  // keyword, industry, theme, stock_code, importance_min, has_leader (bool|null)
  // `source` accepts a single value ("em_yjyg") or a comma-separated list
  // ("em_gsrl,em_yjyg" — unions a platform's multiple sources).
  return api.post('/api/announcements', payload)
}

export function getAnnouncementDetail(eventId) {
  return api.get(`/api/announcements/${eventId}`)
}

export function getAnnouncementFilterMeta() {
  return api.get('/api/announcements/filters/meta')
}

export function getAnnouncementSourceCounts() {
  // Returns `{counts: {source_id: int}}` — drives the platform/source tab
  // badges. Sources with zero rows aren't included; the frontend layers
  // placeholders for not-yet-integrated platforms on top of this.
  return api.get('/api/announcements/source-counts')
}
