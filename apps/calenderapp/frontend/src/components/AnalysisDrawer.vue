<template>
  <el-drawer
    :model-value="visible"
    :size="drawerSize"
    direction="rtl"
    destroy-on-close
    class="analysis-drawer"
    :class="{ 'analysis-drawer--expanded': isExpanded }"
    @close="handleDrawerClose"
  >
    <template #header>
      <div class="analysis-header">
        <div class="analysis-session-controls">
          <el-dropdown
            trigger="click"
            :disabled="status === 'creating' || status === 'streaming'"
            @command="handleSessionCommand"
          >
            <el-button size="small" class="analysis-session-button">
              <span class="analysis-session-button-text">会话</span>
              <el-icon class="analysis-session-button-arrow"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu class="analysis-session-menu">
                <el-dropdown-item
                  v-for="item in sessions"
                  :key="item.session_id"
                  :command="item.session_id"
                  :class="{ 'analysis-session-menu__item--active': item.session_id === sessionId }"
                >
                  {{ formatSessionLabel(item) }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-button
            size="small"
            class="analysis-new-session-action"
            :disabled="status === 'creating' || status === 'streaming'"
            @click="handleResetSession"
          >
            新建对话
          </el-button>
        </div>

        <div class="analysis-actions">
          <el-button
            circle
            size="small"
            class="analysis-header-icon"
            :disabled="status === 'creating' || status === 'streaming'"
            @click="handleRefresh"
          >
            <el-icon><Refresh /></el-icon>
          </el-button>
          <el-button
            circle
            size="small"
            class="analysis-header-icon"
            @click="toggleExpanded"
          >
            <el-icon v-if="isExpanded"><ScaleToOriginal /></el-icon>
            <el-icon v-else><FullScreen /></el-icon>
          </el-button>
          <div class="analysis-header-spacer"></div>
        </div>
      </div>
    </template>

    <div class="analysis-body">
      <div ref="scrollRef" class="analysis-messages">
        <AnalysisWelcome
          v-if="showWelcome"
          @select-example="handleExample"
        />

        <div v-if="status === 'creating'" class="analysis-loading">
          <el-skeleton :rows="4" animated />
        </div>

        <template v-else>
          <AnalysisMessageBubble
            v-for="msg in renderedMessages"
            :key="msg.id"
            :msg="msg"
          />

          <div v-if="showThinkingPlaceholder" class="analysis-thinking-row">
            <div class="analysis-thinking-avatar">
              <VibeTradingIcon />
            </div>
            <div class="analysis-thinking-text">
              <el-icon class="analysis-thinking-spinner"><Loading /></el-icon>
              <span>Thinking...</span>
            </div>
          </div>

          <AnalysisToolProgress
            v-if="toolCalls.length > 0"
            :tool-calls="toolCalls"
            :latest-thinking="latestThinking"
            :status="status"
          />
        </template>
      </div>

      <div class="analysis-footer">
        <div class="analysis-composer">
          <el-input
            v-model="input"
            type="textarea"
            resize="none"
            :autosize="{ minRows: 1, maxRows: 6 }"
            class="analysis-composer-input"
            :placeholder="status === 'streaming' ? '正在分析中…' : '例如：复盘今天市场主线，并给出明天的观察点'"
            :disabled="status === 'creating'"
            @keydown.enter.exact.prevent="handleSend"
            @keydown.enter.shift.exact.stop
          />
          <el-button
            v-if="status === 'streaming'"
            type="warning"
            circle
            class="analysis-composer-button analysis-composer-button--stop"
            @click="handleCancel"
          >
            <el-icon><VideoPause /></el-icon>
          </el-button>
          <el-button
            v-else
            type="primary"
            circle
            class="analysis-composer-button"
            :disabled="!input.trim() || status === 'creating'"
            @click="handleSend"
          >
            <el-icon><Promotion /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown, FullScreen, Loading, Promotion, Refresh, ScaleToOriginal, VideoPause } from '@element-plus/icons-vue'
import AnalysisMessageBubble from './AnalysisMessageBubble.vue'
import AnalysisToolProgress from './AnalysisToolProgress.vue'
import AnalysisWelcome from './AnalysisWelcome.vue'
import VibeTradingIcon from './VibeTradingIcon.vue'
import { useAnalysisDrawer } from '../composables/useAnalysisDrawer'

const input = ref('')
const scrollRef = ref(null)
const isExpanded = ref(false)
const {
  visible,
  sessionId,
  messages,
  sessions,
  status,
  toolCalls,
  latestThinking,
  openDrawer,
  closeDrawer,
  sendMessage,
  cancelMessage,
  resetSession,
  switchSession,
  loadMessages,
  loadSessions,
} = useAnalysisDrawer()

const renderedMessages = computed(() => {
  return messages.value.filter((msg) => {
    if (msg.role === 'assistant' && msg.status === 'streaming' && !String(msg.content || '').trim()) {
      return false
    }
    return true
  })
})

const showWelcome = computed(() => messages.value.length === 0 && status.value !== 'creating')
const showThinkingPlaceholder = computed(() => {
  if (status.value !== 'streaming') return false
  const hasVisibleAssistantText = messages.value.some((msg) => {
    return msg.role === 'assistant' && String(msg.content || '').trim()
  })
  return !hasVisibleAssistantText && toolCalls.value.length === 0
})
const drawerSize = computed(() => (isExpanded.value ? 'min(1160px, 92vw)' : 'min(820px, 96vw)'))

async function scrollToBottom() {
  await nextTick()
  const el = scrollRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

async function submitText(text) {
  const content = String(text || '').trim()
  if (!content) return
  input.value = ''
  try {
    await sendMessage(content)
    await scrollToBottom()
  } catch (e) {
    ElMessage.error(e?.message || '发送失败')
  }
}

async function handleSend() {
  await submitText(input.value)
}

async function handleExample(prompt) {
  await submitText(prompt)
}

async function handleCancel() {
  try {
    await cancelMessage()
  } catch (e) {
    ElMessage.error(e?.message || '停止失败')
  }
}

async function handleResetSession() {
  try {
    input.value = ''
    await resetSession()
    await scrollToBottom()
  } catch (e) {
    ElMessage.error(e?.message || '新建会话失败')
  }
}

function formatSessionLabel(item) {
  const title = String(item?.title || '').trim() || shortSessionId(item?.session_id)
  return title.length > 36 ? `${title.slice(0, 36)}...` : title
}

function shortSessionId(value) {
  return String(value || '').slice(0, 12)
}

async function handleSessionCommand(value) {
  try {
    await switchSession(value)
    await scrollToBottom()
  } catch (e) {
    ElMessage.error(e?.message || '切换会话失败')
  }
}

async function handleRefresh() {
  try {
    await loadSessions()
    if (sessionId.value) {
      await loadMessages()
      await scrollToBottom()
    }
    ElMessage({
      message: '已刷新',
      type: 'success',
      duration: 1200,
      showClose: false,
    })
  } catch (e) {
    ElMessage.error(e?.message || '刷新失败')
  }
}

function toggleExpanded() {
  isExpanded.value = !isExpanded.value
}

function handleDrawerClose() {
  isExpanded.value = false
  closeDrawer()
}

watch(
  () => [
    renderedMessages.value.map(item => `${item.id}:${item.content.length}:${item.status}`).join('|'),
    toolCalls.value.map(item => `${item.tool}:${item.status}:${item.progress?.current || 0}:${item.progress?.total || 0}:${item.elapsed_s || 0}`).join('|'),
    status.value,
  ].join('::'),
  async () => {
    await scrollToBottom()
  }
)

defineExpose({
  openDrawer,
})
</script>

<style scoped>
.analysis-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.analysis-session-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.analysis-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.analysis-header-spacer {
  width: 1px;
}

.analysis-session-button {
  min-width: 78px;
  border-radius: 999px;
  border-color: var(--el-border-color);
  background: var(--el-fill-color-blank);
  padding: 0 14px;
}

.analysis-session-button-text {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.analysis-session-button-arrow {
  margin-left: 4px;
  font-size: 12px;
}

.analysis-new-session-action {
  border-radius: 999px;
  padding: 0 14px;
}

.analysis-session-button:hover,
.analysis-new-session-action:hover {
  border-color: var(--el-color-primary-light-5);
}

:deep(.analysis-session-menu__item--active) {
  color: var(--el-color-primary);
  font-weight: 600;
}

.analysis-header-icon {
  border-color: var(--el-border-color);
  background: var(--el-fill-color-blank);
}

.analysis-header-icon:hover {
  border-color: var(--el-color-primary-light-5);
}

.analysis-body {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.analysis-messages {
  flex: 1;
  overflow: auto;
  padding: 6px 6px 18px;
  min-height: 0;
}

.analysis-loading {
  padding: 24px 8px;
}

.analysis-thinking-row {
  display: flex;
  gap: 12px;
  margin-bottom: 18px;
}

.analysis-thinking-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
}

.analysis-thinking-text {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding-top: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.analysis-thinking-spinner {
  color: var(--el-color-primary);
  animation: analysis-spin 1s linear infinite;
}

.analysis-footer {
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 12px;
  background: color-mix(in srgb, var(--el-bg-color) 90%, transparent);
  backdrop-filter: blur(12px);
}

.analysis-composer {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 20px;
  background: var(--el-fill-color-blank);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
}

.analysis-composer-input {
  flex: 1;
}

.analysis-composer-input :deep(.el-textarea__inner) {
  padding: 8px 0;
  border: 0;
  box-shadow: none;
  background: transparent;
  font-size: 13px;
  line-height: 1.7;
  min-height: 40px !important;
}

.analysis-composer-input :deep(.el-textarea__inner::placeholder) {
  font-size: 12px;
}

.analysis-composer-input :deep(.el-textarea__inner:focus) {
  box-shadow: none;
}

.analysis-composer-button {
  flex: 0 0 auto;
  flex-shrink: 0;
  width: 42px;
  min-width: 42px;
  height: 42px;
  min-height: 42px;
  padding: 0;
}

.analysis-composer-button :deep(.el-icon) {
  font-size: 16px;
}

.analysis-composer-button--stop {
  box-shadow: none;
}

@keyframes analysis-spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

:global(.dark) .analysis-footer {
  border-top-color: rgba(148, 163, 184, 0.22);
}

@media (max-width: 640px) {
  .analysis-header {
    flex-direction: column;
  }

  .analysis-actions {
    width: 100%;
  }

  .analysis-footer-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
