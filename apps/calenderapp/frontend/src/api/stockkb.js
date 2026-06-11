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
