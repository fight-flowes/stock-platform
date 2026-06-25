import api from './client'

export function getStockkbHealth() {
  return api.get('/api/stockkb/health')
}

export function getStockkbReportSummary(stockCode, reportDate) {
  return api.get('/api/stockkb/report', {
    params: {
      stock_code: stockCode,
      report_date: reportDate
    }
  })
}

export function listStockkbEvents(payload) {
  return api.post('/api/stockkb/events', payload)
}

export function getStockkbEventDetail(eventId) {
  return api.get(`/api/stockkb/events/${eventId}`)
}

export function favoriteStockkbEvent(eventId) {
  return api.post(`/api/stockkb/events/${eventId}/favorite`)
}

export function unfavoriteStockkbEvent(eventId) {
  return api.delete(`/api/stockkb/events/${eventId}/favorite`)
}

export function unfavoriteMarketEvent(eventKey) {
  // Bulk-unfavorite the whole market event — one click from the /events
  // page clears every underlying simple-event favorite tied to this
  // event_key, removing the card from the favourites-only list.
  return api.delete(`/api/stockkb/market-events/${eventKey}/favorite`)
}

export function listMarketEvents(payload) {
  return api.post('/api/stockkb/market-events', payload)
}

export function getMarketEventDetail(eventKey) {
  return api.get(`/api/stockkb/market-events/${eventKey}`)
}

export function getMarketEventTimeline(eventKey) {
  return api.get(`/api/stockkb/market-events/${eventKey}/timeline`)
}

export function getMarketEventFilterMeta() {
  return api.get('/api/stockkb/market-events/filters/meta')
}

export function getMarketEventReview(eventKey) {
  return api.get(`/api/stockkb/market-events/${eventKey}/review`)
}

export function runMarketEventReview(eventKey) {
  return api.post(`/api/stockkb/market-events/${eventKey}/review/run`)
}

export function refreshMarketEventReview(eventKey) {
  return api.post(`/api/stockkb/market-events/${eventKey}/review/refresh`)
}
