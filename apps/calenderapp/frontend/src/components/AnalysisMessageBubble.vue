<template>
  <div :class="['analysis-msg-row', `analysis-msg-row--${msg.role}`]">
    <div v-if="showAssistantAvatar" class="analysis-msg-avatar">
      <VibeTradingIcon />
    </div>

    <div :class="['analysis-msg-main', `analysis-msg-main--${msg.role}`]">
      <div v-if="isAssistant" class="analysis-copy-wrap">
        <el-button
          text
          size="small"
          class="analysis-copy-button"
          :aria-label="copied ? '已复制' : '复制'"
          @click="handleCopy"
        >
          <el-icon v-if="copied"><Check /></el-icon>
          <el-icon v-else><CopyDocument /></el-icon>
        </el-button>
      </div>

      <div :class="['analysis-msg-bubble', `analysis-msg-bubble--${msg.role}`]">
        <div
          v-if="isAssistant"
          class="analysis-md"
          v-html="renderedContent"
        />
        <div v-else class="analysis-msg-text">{{ msg.content }}</div>
      </div>

      <div class="analysis-msg-meta">
        <span>{{ formatTime(msg.timestamp) }}</span>
        <span v-if="msg.status === 'streaming'">生成中...</span>
        <span v-else-if="msg.status === 'error'">失败</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, CopyDocument } from '@element-plus/icons-vue'
import { renderAnalysisMarkdown } from '../utils/analysisMarkdown'
import VibeTradingIcon from './VibeTradingIcon.vue'

const props = defineProps({
  msg: {
    type: Object,
    required: true,
  },
})

const copied = ref(false)

const isAssistant = computed(() => props.msg.role === 'assistant')
const showAssistantAvatar = computed(() => props.msg.role === 'assistant' || props.msg.role === 'error')
const renderedContent = computed(() => renderAnalysisMarkdown(props.msg.content || ''))

function formatTime(ts) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleTimeString()
  } catch {
    return ''
  }
}

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(props.msg.content || '')
    copied.value = true
    window.setTimeout(() => {
      copied.value = false
    }, 1500)
  } catch {
    ElMessage.error('复制失败')
  }
}
</script>

<style scoped>
.analysis-msg-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.analysis-msg-row--user {
  justify-content: flex-end;
}

.analysis-msg-avatar {
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  flex: 0 0 32px;
  width: 32px;
  min-height: 32px;
  padding-top: 12px;
}

.analysis-msg-avatar :deep(svg) {
  width: 20px;
  height: 20px;
}

.analysis-msg-main {
  position: relative;
  min-width: 0;
}

.analysis-msg-main--user {
  max-width: min(82%, 760px);
}

.analysis-msg-main--assistant,
.analysis-msg-main--error {
  flex: 1 1 auto;
  max-width: calc(100% - 44px);
}

.analysis-copy-wrap {
  display: flex;
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1;
  justify-content: flex-end;
}

.analysis-copy-button {
  padding: 0;
  width: 24px;
  height: 24px;
  min-width: 24px;
  min-height: 24px;
  border-radius: 999px;
  color: var(--el-text-color-placeholder);
  background: color-mix(in srgb, var(--el-fill-color-blank) 88%, transparent);
}

.analysis-copy-button:hover {
  color: var(--el-text-color-regular);
  background: color-mix(in srgb, var(--el-fill-color) 92%, transparent);
}

.analysis-msg-bubble {
  border-radius: 18px;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.68;
  word-break: break-word;
}

.analysis-msg-bubble--user {
  border-top-right-radius: 8px;
  background: var(--el-color-primary);
  color: #fff;
}

.analysis-msg-bubble--assistant {
  border-top-left-radius: 8px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
  padding-right: 40px;
  width: 100%;
  box-sizing: border-box;
}

.analysis-msg-bubble--error {
  border: 1px solid rgba(239, 68, 68, 0.18);
  border-top-left-radius: 8px;
  background: rgba(239, 68, 68, 0.08);
  color: #b91c1c;
  width: 100%;
  box-sizing: border-box;
}

.analysis-msg-text {
  white-space: pre-wrap;
}

.analysis-msg-meta {
  display: flex;
  gap: 10px;
  margin-top: 6px;
  font-size: 10px;
  color: var(--el-text-color-placeholder);
}

.analysis-msg-row--user .analysis-msg-meta {
  justify-content: flex-end;
}

.analysis-md :deep(h1),
.analysis-md :deep(h2),
.analysis-md :deep(h3),
.analysis-md :deep(h4) {
  margin: 0 0 10px;
  font-weight: 800;
  line-height: 1.4;
}

.analysis-md :deep(h1) {
  font-size: 18px;
}

.analysis-md :deep(h2) {
  font-size: 16px;
}

.analysis-md :deep(h3) {
  font-size: 14px;
}

.analysis-md :deep(p) {
  margin: 0 0 10px;
}

.analysis-md :deep(p:last-child) {
  margin-bottom: 0;
}

.analysis-md :deep(ul),
.analysis-md :deep(ol) {
  margin: 0 0 10px 18px;
  padding: 0;
}

.analysis-md :deep(li + li) {
  margin-top: 4px;
}

.analysis-md :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 12px;
  border-left: 3px solid var(--el-color-primary-light-3);
  background: rgba(37, 99, 235, 0.06);
  border-radius: 0 10px 10px 0;
}

.analysis-md :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.08);
  font-size: 11px;
  font-family: 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
}

.analysis-md :deep(pre.analysis-md-code) {
  margin: 12px 0;
  padding: 12px 14px;
  overflow: auto;
  border-radius: 12px;
  background: #0f172a;
  color: #e2e8f0;
}

.analysis-md :deep(pre.analysis-md-code code) {
  padding: 0;
  background: transparent;
  color: inherit;
}

.analysis-md :deep(.analysis-md-table-wrap) {
  overflow-x: auto;
  margin: 12px 0;
}

.analysis-md :deep(.analysis-md-table) {
  width: 100%;
  min-width: 320px;
  border-collapse: collapse;
  font-size: 12px;
}

.analysis-md :deep(.analysis-md-table th),
.analysis-md :deep(.analysis-md-table td) {
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-light);
  text-align: left;
  vertical-align: top;
}

.analysis-md :deep(.analysis-md-table th) {
  background: rgba(148, 163, 184, 0.12);
  font-weight: 700;
}

.analysis-md :deep(a) {
  color: var(--el-color-primary);
  text-decoration: none;
}

.analysis-md :deep(a:hover) {
  text-decoration: underline;
}

.analysis-md :deep(hr) {
  margin: 14px 0;
  border: 0;
  border-top: 1px solid var(--el-border-color-light);
}

:global(.dark) .analysis-msg-bubble--assistant {
  background: rgba(30, 41, 59, 0.92);
  color: #e2e8f0;
}

:global(.dark) .analysis-md code {
  background: rgba(148, 163, 184, 0.16);
}

:global(.dark) .analysis-md blockquote {
  background: rgba(59, 130, 246, 0.12);
}

:global(.dark) .analysis-md .analysis-md-table th {
  background: rgba(148, 163, 184, 0.12);
}
</style>
