import api from './client'

export function listStockTags() {
  return api.get('/api/stock-tags')
}

export function createStockTag(payload) {
  return api.post('/api/stock-tags', payload)
}

export function deleteStockTag(tagId) {
  return api.delete(`/api/stock-tags/${tagId}`)
}

export function addStockTagBindings(tagId, stockCodes) {
  return api.post(`/api/stock-tags/${tagId}/bindings`, { stock_codes: stockCodes })
}
