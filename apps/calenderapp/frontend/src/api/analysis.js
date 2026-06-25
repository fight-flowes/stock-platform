import api from './client'

const baseURL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000').replace(/\/$/, '')

function unwrapData(resp, fallback = null) {
  if (resp && typeof resp === 'object' && 'data' in resp) {
    return resp.data ?? fallback
  }
  return resp ?? fallback
}

function requireSessionId(sessionId) {
  const value = String(sessionId || '').trim()
  if (!value) {
    throw new Error('sessionId 不能为空')
  }
  return value
}

function normalizeMessage(item, index = 0) {
  return {
    message_id: String(item?.message_id || `msg_${index}`),
    session_id: String(item?.session_id || ''),
    role: item?.role === 'user' ? 'user' : 'assistant',
    content: String(item?.content || ''),
    created_at: item?.created_at || '',
    linked_attempt_id: item?.linked_attempt_id || null,
    metadata: item?.metadata || null,
  }
}

function normalizeSession(item, index = 0) {
  return {
    session_id: String(item?.session_id || `session_${index}`),
    title: String(item?.title || ''),
    status: String(item?.status || 'idle'),
    created_at: item?.created_at || '',
    updated_at: item?.updated_at || '',
    last_attempt_id: item?.last_attempt_id || null,
  }
}

export async function listAnalysisSessions(limit = 50) {
  const safeLimit = Math.max(1, Math.min(Number(limit || 50), 200))
  const resp = await api.get('/api/analysis/sessions', {
    params: { limit: safeLimit },
  })
  const data = unwrapData(resp, {})
  const items = Array.isArray(data?.items) ? data.items : []

  return {
    items: items.map(normalizeSession),
  }
}

export async function createAnalysisSession(title = 'Eventra-Trading') {
  const resp = await api.post('/api/analysis/session', { title })
  const data = unwrapData(resp, {})

  return {
    session_id: String(data.session_id || ''),
    title: String(data.title || title),
    status: String(data.status || 'idle'),
    created_at: data.created_at || '',
    updated_at: data.updated_at || '',
  }
}

export async function getAnalysisMessages(sessionId) {
  const sid = requireSessionId(sessionId)
  const resp = await api.get(`/api/analysis/session/${sid}/messages`)
  const data = unwrapData(resp, {})
  const items = Array.isArray(data?.items) ? data.items : []

  return {
    items: items.map(normalizeMessage),
  }
}

export async function sendAnalysisMessage(sessionId, content) {
  const sid = requireSessionId(sessionId)
  const text = String(content || '').trim()
  if (!text) {
    throw new Error('content 不能为空')
  }

  const resp = await api.post(`/api/analysis/session/${sid}/messages`, {
    content: text,
  })
  const data = unwrapData(resp, {})

  return {
    status: String(data.status || 'accepted'),
    session_id: String(data.session_id || sid),
    upstream: data.upstream || null,
  }
}

export async function cancelAnalysisSession(sessionId) {
  const sid = requireSessionId(sessionId)
  const resp = await api.post(`/api/analysis/session/${sid}/cancel`)
  const data = unwrapData(resp, {})

  return {
    status: String(data.status || 'cancelled'),
  }
}

export function buildAnalysisSseUrl(sessionId) {
  const sid = requireSessionId(sessionId)
  return `${baseURL}/api/analysis/session/${sid}/events`
}
