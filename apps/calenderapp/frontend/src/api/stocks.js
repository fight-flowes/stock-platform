import api from './client'

export function searchStocks(q, limit = 10) {
  return api.get('/api/stocks/search', { params: { q, limit } })
}

export function listStocks(params = {}) {
  return api.get('/api/stocks/', { params })
}

export function getStockByCode(code) {
  return api.get(`/api/stocks/${code}`)
}

export function getStockKline(code, days = 60) {
  return api.get(`/api/stocks/${code}/kline`, { params: { days } })
}

export function getStockInfo(code) {
  return api.get(`/api/stocks/${code}/info`)
}

export function getRealtimeQuotes(codes) {
  return api.get('/api/stocks/realtime', { params: { codes: codes.join(',') } })
}

export function listFavorites() {
  return api.get('/api/stocks/favorites')
}

export function toggleFavorite(code) {
  return api.post(`/api/stocks/${code}/favorite`)
}

export function deleteStock(code) {
  return api.delete(`/api/stocks/${code}`)
}

export function updateQuotesCache(codes = null) {
  const params = codes ? { codes: codes.join(',') } : {}
  return api.post('/api/stocks/cache/update', null, { params })
}

export function upsertStock(payload) {
  return api.post('/api/stocks/', payload)
}

export function getStockOrganizer(code) {
  return api.get(`/api/stocks/${code}/organizer`)
}

export function updateStockOrganizer(code, payload) {
  return api.put(`/api/stocks/${code}/organizer`, payload)
}

export function updateStockNote(code, payload) {
  return api.put(`/api/stocks/${code}/note`, payload)
}
