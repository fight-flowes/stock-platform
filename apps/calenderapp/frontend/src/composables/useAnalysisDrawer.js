import { computed, ref } from 'vue'
import {
  buildAnalysisSseUrl,
  cancelAnalysisSession,
  createAnalysisSession,
  getAnalysisMessages,
  listAnalysisSessions,
  sendAnalysisMessage,
} from '../api/analysis'

const visible = ref(false)
const sessionId = ref('')
const status = ref('idle') // idle | creating | streaming | error
const messages = ref([])
const sessions = ref([])
const eventSource = ref(null)
const streamingMessageId = ref('')
const toolCalls = ref([])
const latestThinking = ref('')

function nowTs() {
  return Date.now()
}

function createMessage({
  id,
  role,
  content,
  timestamp = nowTs(),
  status: messageStatus = 'done',
}) {
  return {
    id,
    role,
    content,
    timestamp,
    status: messageStatus,
  }
}

function normalizeHistory(items = []) {
  return items
    .filter(item => item && String(item.content || '').trim())
    .map((item, index) => createMessage({
      id: item.message_id || `msg_${index}`,
      role: item.role === 'user' ? 'user' : 'assistant',
      content: item.content || '',
      timestamp: item.created_at ? new Date(item.created_at).getTime() : nowTs(),
      status: 'done',
    }))
}

function destroyEventSource() {
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
  }
}

function resetTurnArtifacts() {
  toolCalls.value = []
  latestThinking.value = ''
}

function resetToLandingState() {
  destroyEventSource()
  sessionId.value = ''
  messages.value = []
  streamingMessageId.value = ''
  status.value = 'idle'
  resetTurnArtifacts()
}

async function ensureSession() {
  if (sessionId.value) return sessionId.value
  status.value = 'creating'
  try {
    const resp = await createAnalysisSession('Eventra-Trading')
    sessionId.value = resp.session_id
    await loadSessions()
    status.value = 'idle'
    return sessionId.value
  } catch (e) {
    status.value = 'error'
    throw e
  }
}

async function loadSessions() {
  const resp = await listAnalysisSessions(50)
  sessions.value = Array.isArray(resp.items) ? resp.items : []
}

async function loadMessages() {
  if (!sessionId.value) return
  const resp = await getAnalysisMessages(sessionId.value)
  messages.value = normalizeHistory(resp.items || [])
}

function appendStreamingDelta(delta) {
  if (!streamingMessageId.value) return
  const target = messages.value.find(item => item.id === streamingMessageId.value)
  if (!target) return
  target.content += delta
}

function upsertToolCall(toolName, patch = {}) {
  const cleanToolName = String(toolName || '').trim()
  if (!cleanToolName) return

  const existing = toolCalls.value.find(item => item.tool === cleanToolName)
  if (existing) {
    Object.assign(existing, patch)
    return
  }

  toolCalls.value.push({
    id: cleanToolName,
    tool: cleanToolName,
    status: 'running',
    timestamp: nowTs(),
    progress: undefined,
    elapsed_ms: undefined,
    elapsed_s: undefined,
    ...patch,
  })
}

function finishStreaming(nextStatus = 'done', summary = '') {
  if (!streamingMessageId.value) return
  const target = messages.value.find(item => item.id === streamingMessageId.value)
  if (target) {
    if (!target.content.trim() && summary) {
      target.content = summary
    }
    target.status = nextStatus
  }
  streamingMessageId.value = ''
}

function connectSSE() {
  if (!sessionId.value || eventSource.value) return

  const es = new EventSource(buildAnalysisSseUrl(sessionId.value))
  eventSource.value = es

  es.addEventListener('text_delta', (event) => {
    try {
      const data = JSON.parse(event.data || '{}')
      appendStreamingDelta(String(data.delta || ''))
    } catch {
      // ignore malformed delta
    }
  })

  es.addEventListener('thinking_done', (event) => {
    try {
      const data = JSON.parse(event.data || '{}')
      latestThinking.value = String(data.content || latestThinking.value || '')
    } catch {
      // ignore malformed thinking payload
    }
  })

  es.addEventListener('tool_call', (event) => {
    try {
      const data = JSON.parse(event.data || '{}')
      const toolName = String(data.tool || '')
      upsertToolCall(toolName, {
        status: 'running',
        timestamp: nowTs(),
      })
    } catch {
      // ignore malformed tool call payload
    }
  })

  es.addEventListener('tool_result', (event) => {
    try {
      const data = JSON.parse(event.data || '{}')
      const toolName = String(data.tool || '')
      upsertToolCall(toolName, {
        status: data.status === 'ok' ? 'ok' : 'error',
        preview: String(data.preview || ''),
        elapsed_ms: Number(data.elapsed_ms || 0) || undefined,
        progress: undefined,
      })
    } catch {
      // ignore malformed tool result payload
    }
  })

  es.addEventListener('tool_heartbeat', (event) => {
    try {
      const data = JSON.parse(event.data || '{}')
      const toolName = String(data.tool || '')
      upsertToolCall(toolName, {
        elapsed_s: Number(data.elapsed_s || 0) || undefined,
      })
    } catch {
      // ignore malformed heartbeat payload
    }
  })

  es.addEventListener('tool_progress', (event) => {
    try {
      const data = JSON.parse(event.data || '{}')
      const toolName = String(data.tool || '')
      const nextProgress = {}
      if (typeof data.stage === 'string' && data.stage) nextProgress.stage = data.stage
      if (typeof data.message === 'string' && data.message) nextProgress.message = data.message
      if (typeof data.current === 'number') nextProgress.current = data.current
      if (typeof data.total === 'number') nextProgress.total = data.total
      upsertToolCall(toolName, {
        progress: nextProgress,
      })
    } catch {
      // ignore malformed progress payload
    }
  })

  es.addEventListener('attempt.completed', (event) => {
    let summary = ''
    try {
      const data = JSON.parse(event.data || '{}')
      summary = String(data.summary || '')
    } catch {
      // ignore malformed completion payload
    }
    finishStreaming('done', summary)
    status.value = 'idle'
  })

  es.addEventListener('attempt.failed', (event) => {
    let message = '执行失败'
    try {
      const data = JSON.parse(event.data || '{}')
      message = String(data.error || message)
    } catch {
      // ignore malformed failure payload
    }

    if (!streamingMessageId.value) {
      messages.value.push(createMessage({
        id: `err_${nowTs()}`,
        role: 'error',
        content: message,
        status: 'error',
      }))
    } else {
      finishStreaming('error')
      messages.value.push(createMessage({
        id: `err_${nowTs()}`,
        role: 'error',
        content: message,
        status: 'error',
      }))
    }
    status.value = 'error'
  })

  es.onerror = () => {
    if (status.value === 'streaming') {
      status.value = 'error'
    }
  }
}

async function openDrawer() {
  visible.value = true
  resetToLandingState()
  await loadSessions()
}

function closeDrawer() {
  visible.value = false
  destroyEventSource()
}

async function resetSession() {
  resetToLandingState()
  await loadSessions()
}

async function switchSession(nextSessionId) {
  const sid = String(nextSessionId || '').trim()
  if (!sid || sid === sessionId.value) return

  destroyEventSource()
  sessionId.value = sid
  messages.value = []
  streamingMessageId.value = ''
  status.value = 'idle'
  resetTurnArtifacts()
  await loadMessages()
  connectSSE()
}

async function sendMessage(content) {
  const sid = await ensureSession()
  connectSSE()
  resetTurnArtifacts()

  messages.value.push(createMessage({
    id: `user_${nowTs()}`,
    role: 'user',
    content,
    status: 'done',
  }))

  const assistantId = `assistant_${nowTs()}`
  streamingMessageId.value = assistantId
  messages.value.push(createMessage({
    id: assistantId,
    role: 'assistant',
    content: '',
    status: 'streaming',
  }))

  status.value = 'streaming'

  try {
    await sendAnalysisMessage(sid, content)
  } catch (e) {
    finishStreaming('error')
    status.value = 'error'
    messages.value.push(createMessage({
      id: `err_${nowTs()}`,
      role: 'error',
      content: e?.message || '发送失败',
      status: 'error',
    }))
    throw e
  }
}

async function cancelMessage() {
  if (!sessionId.value) return
  await cancelAnalysisSession(sessionId.value)
  finishStreaming('done')
  status.value = 'idle'
}

export function useAnalysisDrawer() {
  return {
    visible: computed(() => visible.value),
    sessionId: computed(() => sessionId.value),
    messages: computed(() => messages.value),
    sessions: computed(() => sessions.value),
    status: computed(() => status.value),
    toolCalls: computed(() => toolCalls.value),
    latestThinking: computed(() => latestThinking.value),
    openDrawer,
    closeDrawer,
    resetSession,
    switchSession,
    sendMessage,
    cancelMessage,
    loadMessages,
    loadSessions,
  }
}
