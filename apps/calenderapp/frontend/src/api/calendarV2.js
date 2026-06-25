import api from './client'

export function getCalendarV2Health() {
  return api.get('/api/calendar-v2/health')
}

export function getCalendarV2FilterMeta() {
  return api.get('/api/calendar-v2/filters/meta')
}

export function listCalendarV2Events(params = {}) {
  return api.get('/api/calendar-v2/events', { params })
}

export function getCalendarV2Upcoming(params = {}) {
  return api.get('/api/calendar-v2/upcoming', { params })
}

export function getCalendarV2EventDetail(eventKey) {
  return api.get(`/api/calendar-v2/events/${eventKey}`)
}

export function saveCalendarV2Override(eventKey, payload) {
  return api.post(`/api/calendar-v2/events/${eventKey}/override`, payload)
}
