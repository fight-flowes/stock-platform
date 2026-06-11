import api from './client'

export function listEvents(params = {}) {
  return api.get('/api/events/', { params })
}

export function createEvent(payload) {
  return api.post('/api/events/', payload)
}

export function updateEvent(id, payload) {
  return api.put(`/api/events/${id}`, payload)
}

export function deleteEvent(id) {
  return api.delete(`/api/events/${id}`)
}

export function upcomingEvents(params = {}) {
  return api.get('/api/events/upcoming', { params })
}

export function statisticsEvents(params = {}) {
  return api.get('/api/events/statistics', { params })
}

export function importEventsCsv(file) {
  const form = new FormData()
  form.append('file', file)
  return api.post('/api/events/import', form, { headers: { 'Content-Type': 'multipart/form-data' } })
}
