import api from './client'

export function listStockGroups() {
  return api.get('/api/stock-groups')
}

export function createStockGroup(payload) {
  return api.post('/api/stock-groups', payload)
}

export function updateStockGroup(groupId, payload) {
  return api.patch(`/api/stock-groups/${groupId}`, payload)
}

export function deleteStockGroup(groupId) {
  return api.delete(`/api/stock-groups/${groupId}`)
}

export function addStockGroupMembers(groupId, stockCodes) {
  return api.post(`/api/stock-groups/${groupId}/members`, { stock_codes: stockCodes })
}
