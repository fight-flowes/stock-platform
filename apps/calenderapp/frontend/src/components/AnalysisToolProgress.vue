<template>
  <div v-if="visible" class="analysis-progress-card">
    <button type="button" class="analysis-progress-summary" @click="expanded = !expanded">
      <el-icon class="analysis-progress-arrow">
        <ArrowDown v-if="expanded" />
        <ArrowRight v-else />
      </el-icon>

      <el-icon v-if="isRunning" class="analysis-progress-state analysis-progress-state--running">
        <Loading />
      </el-icon>
      <el-icon v-else-if="hasError" class="analysis-progress-state analysis-progress-state--error">
        <CircleCloseFilled />
      </el-icon>
      <el-icon v-else class="analysis-progress-state analysis-progress-state--done">
        <SuccessFilled />
      </el-icon>

      <span class="analysis-progress-summary-text">{{ summaryText }}</span>
    </button>

    <div v-if="!expanded && latestThinking" class="analysis-thinking-preview">
      {{ latestThinking }}
    </div>

    <div v-if="expanded" class="analysis-progress-list">
      <div
        v-for="(tool, index) in toolCalls"
        :key="`${tool.tool}_${index}`"
        class="analysis-progress-item"
      >
        <div class="analysis-progress-item-header">
          <span class="analysis-progress-tree">{{ index === toolCalls.length - 1 ? '└' : '├' }}</span>
          <el-icon v-if="tool.status === 'running'" class="analysis-progress-state analysis-progress-state--running">
            <Loading />
          </el-icon>
          <el-icon v-else-if="tool.status === 'error'" class="analysis-progress-state analysis-progress-state--error">
            <CircleCloseFilled />
          </el-icon>
          <el-icon v-else class="analysis-progress-state analysis-progress-state--done">
            <SuccessFilled />
          </el-icon>
          <span class="analysis-progress-tool">{{ formatToolName(tool.tool) }}</span>
          <span v-if="tool.elapsed_s || tool.elapsed_ms" class="analysis-progress-time">
            {{ formatDuration(tool.elapsed_s, tool.elapsed_ms) }}
          </span>
        </div>

        <div v-if="tool.progress?.stage || hasDeterminateProgress(tool)" class="analysis-progress-subline">
          <span v-if="tool.progress?.stage" class="analysis-progress-stage">{{ tool.progress.stage }}</span>
          <el-progress
            v-if="hasDeterminateProgress(tool)"
            :percentage="getProgressPercent(tool)"
            :stroke-width="6"
            :show-text="false"
            status="success"
          />
          <span v-if="hasDeterminateProgress(tool)" class="analysis-progress-fraction">
            {{ tool.progress.current }}/{{ tool.progress.total }}
          </span>
        </div>

        <div v-if="tool.progress?.message" class="analysis-progress-message">
          {{ tool.progress.message }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowDown, ArrowRight, CircleCloseFilled, Loading, SuccessFilled } from '@element-plus/icons-vue'

const props = defineProps({
  toolCalls: {
    type: Array,
    default: () => [],
  },
  latestThinking: {
    type: String,
    default: '',
  },
  status: {
    type: String,
    default: 'idle',
  },
})

const expanded = ref(false)

const visible = computed(() => props.toolCalls.length > 0)
const isRunning = computed(() => props.status === 'streaming' || props.toolCalls.some(item => item.status === 'running'))
const hasError = computed(() => props.toolCalls.some(item => item.status === 'error'))

const summaryText = computed(() => {
  if (!props.toolCalls.length) return ''
  const runningTool = props.toolCalls.find(item => item.status === 'running')
  if (runningTool) {
    return `正在调用 ${formatToolName(runningTool.tool)}`
  }
  const totalSeconds = props.toolCalls.reduce((sum, item) => {
    if (item.elapsed_s) return sum + item.elapsed_s
    if (item.elapsed_ms) return sum + item.elapsed_ms / 1000
    return sum
  }, 0)
  const durationText = totalSeconds > 0 ? ` · ${totalSeconds.toFixed(1)}s` : ''
  return `本轮已完成 ${props.toolCalls.length} 个步骤${durationText}`
})

watch(
  () => props.status,
  (next) => {
    if (next === 'streaming') expanded.value = true
  },
  { immediate: true }
)

function formatToolName(name) {
  const raw = String(name || '').trim()
  if (!raw) return '处理中'
  const mapped = {
    web_search: '网页搜索',
    search_news: '新闻搜索',
    read_url: '读取网页',
    backtest_strategy: '策略回测',
    get_stock_data: '股票数据',
    get_market_snapshot: '市场快照',
    render_report: '生成报告',
  }[raw]
  if (mapped) return mapped
  return raw.replace(/_/g, ' ')
}

function hasDeterminateProgress(tool) {
  const current = Number(tool?.progress?.current)
  const total = Number(tool?.progress?.total)
  return Number.isFinite(current) && Number.isFinite(total) && total > 0
}

function getProgressPercent(tool) {
  if (!hasDeterminateProgress(tool)) return 0
  const current = Number(tool.progress.current)
  const total = Number(tool.progress.total)
  return Math.max(0, Math.min(100, Math.round((current / total) * 100)))
}

function formatDuration(elapsedSeconds, elapsedMs) {
  if (elapsedSeconds) return `${Number(elapsedSeconds).toFixed(0)}s`
  if (elapsedMs) return `${(Number(elapsedMs) / 1000).toFixed(1)}s`
  return ''
}
</script>

<style scoped>
.analysis-progress-card {
  margin-bottom: 18px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 16px;
  background: color-mix(in srgb, var(--el-fill-color-light) 72%, transparent);
  overflow: hidden;
}

.analysis-progress-summary {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 0;
  background: transparent;
  cursor: pointer;
  color: var(--el-text-color-regular);
  text-align: left;
}

.analysis-progress-arrow {
  color: var(--el-text-color-placeholder);
}

.analysis-progress-state {
  font-size: 14px;
}

.analysis-progress-state--running {
  color: var(--el-color-primary);
}

.analysis-progress-state--error {
  color: var(--el-color-danger);
}

.analysis-progress-state--done {
  color: var(--el-color-success);
}

.analysis-progress-summary-text {
  font-size: 12px;
  font-weight: 600;
}

.analysis-thinking-preview {
  padding: 0 12px 10px 38px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.analysis-progress-list {
  padding: 0 12px 12px 12px;
  border-top: 1px solid var(--el-border-color-extra-light);
}

.analysis-progress-item + .analysis-progress-item {
  margin-top: 12px;
}

.analysis-progress-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.analysis-progress-tree {
  width: 12px;
  color: var(--el-text-color-placeholder);
  flex: 0 0 auto;
}

.analysis-progress-tool {
  flex: 1;
  min-width: 0;
  font-size: 11px;
  color: var(--el-text-color-primary);
}

.analysis-progress-time {
  font-size: 10px;
  color: var(--el-text-color-placeholder);
}

.analysis-progress-subline {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  padding-left: 28px;
}

.analysis-progress-stage {
  font-size: 10px;
  color: var(--el-text-color-secondary);
}

.analysis-progress-fraction {
  font-size: 10px;
  color: var(--el-text-color-placeholder);
}

.analysis-progress-message {
  margin-top: 5px;
  padding-left: 28px;
  font-size: 10px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
</style>
