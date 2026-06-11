<template>
  <el-dialog
    :model-value="modelValue"
    width="min(1100px, 94vw)"
    top="4vh"
    class="stockkb-dialog"
    destroy-on-close
    @close="emit('update:modelValue', false)"
  >
    <template #header>
      <div class="stockkb-header">
        <div class="stockkb-title">
          <div class="stockkb-name">{{ stock?.stock_name || stock?.name || '-' }}</div>
          <div class="stockkb-meta">
            <span>{{ stock?.stock_code || stock?.code || '-' }}</span>
            <span>{{ reportDate || '-' }}</span>
            <el-tag size="small" type="info">极简事件</el-tag>
          </div>
        </div>

        <div class="stockkb-actions">
          <el-button size="small" @click="refreshAll" :loading="loadingSummary || loadingEvents">
            刷新
          </el-button>
          <el-button size="small" type="primary" @click="emit('view-analysis')">
            查看原报告
          </el-button>
        </div>
      </div>
    </template>

    <div class="stockkb-body">
      <div class="stockkb-summary-row" v-loading="loadingSummary">
        <div class="summary-chip">
          <div class="summary-label">报告</div>
          <div class="summary-value">{{ summary.report_exists ? '已入库' : '未命中' }}</div>
        </div>
        <div class="summary-chip">
          <div class="summary-label">事件数</div>
          <div class="summary-value">{{ summary.event_count ?? 0 }}</div>
        </div>
        <div class="summary-chip summary-title-chip">
          <div class="summary-label">上涨逻辑</div>
          <div class="summary-value">{{ summary.core_logic || '暂无上涨逻辑' }}</div>
        </div>
        <div class="summary-chip summary-risk-chip">
          <div class="summary-label">风险摘要</div>
          <div class="summary-value summary-risk-text">{{ summary.risk_summary || '暂无风险摘要' }}</div>
        </div>
      </div>

      <div v-if="errorMessage" class="stockkb-error">
        <el-alert :title="errorMessage" type="error" :closable="false" show-icon />
      </div>

      <div v-else-if="!summary.report_exists && !loadingSummary" class="stockkb-empty">
        <el-empty description="当前股票在该日期下暂无 stockkb 事件结果">
          <el-button type="primary" @click="emit('view-analysis')">查看原报告</el-button>
        </el-empty>
      </div>

      <div v-else-if="summary.report_exists && !loadingEvents && events.length === 0" class="stockkb-empty">
        <el-empty description="报告已入库，但暂无可展示事件">
          <el-button type="primary" @click="emit('view-analysis')">查看原报告</el-button>
        </el-empty>
      </div>

      <div v-else class="stockkb-panels">
        <div class="stockkb-left" v-loading="loadingEvents">
          <div class="panel-heading">
            <span>事件列表</span>
            <el-tag size="small" effect="plain">{{ events.length }}</el-tag>
          </div>

          <div class="event-list">
            <div
              v-for="item in events"
              :key="item.event_id"
              :class="['event-card', { active: item.event_id === selectedEventId }]"
              @click="selectEvent(item)"
            >
              <div class="event-card-top">
                <div class="event-title">{{ item.event_name || '未命名事件' }}</div>
                <el-button
                  link
                  class="favorite-icon-button"
                  :type="isFavorite(item) ? 'warning' : 'default'"
                  :icon="isFavorite(item) ? StarFilled : Star"
                  :loading="isFavoriteLoading(item.event_id)"
                  title="收藏事件"
                  aria-label="收藏事件"
                  @click.stop="toggleFavorite(item)"
                />
              </div>
              <div class="event-time">{{ item.event_time_text || item.event_time_normalized || '-' }}</div>
              <div v-if="displayMetaTags(item).length" class="event-tags">
                <el-tag
                  v-for="tag in displayMetaTags(item)"
                  :key="`${item.event_id}-${tag.text}`"
                  size="small"
                  :type="tag.type"
                >
                  {{ tag.text }}
                </el-tag>
              </div>
            </div>

            <el-empty
              v-if="!loadingEvents && events.length === 0"
              description="暂无事件"
              :image-size="64"
            />
          </div>
        </div>

        <div class="stockkb-right" v-loading="loadingDetail">
          <template v-if="selectedDetail?.event">
            <div class="detail-section">
              <div class="detail-title-row">
                <h3>{{ selectedDetail.event.event_name || '未命名事件' }}</h3>
                <div class="detail-time">
                  {{ selectedDetail.event.event_time_text || selectedDetail.event.event_time_normalized || '-' }}
                </div>
              </div>

              <div class="detail-report-bar">
                <div class="detail-report-text">
                  <span class="detail-label">来源报告</span>
                  <span>{{ selectedDetail.event.report_title || summary.report_title || '暂无报告标题' }}</span>
                </div>
                <el-button size="small" type="primary" plain @click="emit('view-analysis')">
                  查看原报告
                </el-button>
              </div>

              <div class="detail-subsection">
                <div class="section-heading">事件类型</div>
                <div class="detail-meta-panel">
                  <div v-if="displayMetaTags(selectedDetail.event).length" class="detail-meta-tags">
                    <el-tag
                      v-for="tag in displayMetaTags(selectedDetail.event)"
                      :key="`detail-${tag.text}`"
                      :type="tag.type"
                    >
                      {{ tag.text }}
                    </el-tag>
                  </div>
                  <div v-if="displayScopeReason(selectedDetail.event)" class="detail-meta-reason">
                    {{ displayScopeReason(selectedDetail.event) }}
                  </div>
                  <div
                    v-else-if="!displayMetaTags(selectedDetail.event).length"
                    class="detail-meta-reason empty"
                  >
                    当前事件尚未补齐类型信息，需按新 schema 重新抽取后才会显示。
                  </div>
                </div>
              </div>

              <div class="detail-subsection">
                <div class="section-heading">事件内容</div>
                <div class="detail-description">
                  {{ selectedDetail.event.event_content || '暂无事件内容' }}
                </div>
              </div>

              <div v-if="hasEventSource(selectedDetail.event)" class="detail-subsection">
                <div class="section-heading">事件来源</div>
                <div class="detail-source-panel">
                  <div v-if="selectedDetail.event.source_name" class="detail-source-row">
                    <span class="detail-source-label">来源平台</span>
                    <span class="detail-source-value">{{ selectedDetail.event.source_name }}</span>
                  </div>
                  <div v-if="selectedDetail.event.source_url" class="detail-source-row">
                    <span class="detail-source-label">原始URL</span>
                    <a
                      class="detail-source-link"
                      :href="selectedDetail.event.source_url"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {{ selectedDetail.event.source_url }}
                    </a>
                  </div>
                </div>
              </div>

              <div class="detail-subsection">
                <div class="section-heading">影响个股</div>
                <div v-if="selectedDetail.event.affected_stocks?.length" class="stock-tag-list">
                  <el-tag
                    v-for="item in selectedDetail.event.affected_stocks"
                    :key="`${item.stock_code}-${item.stock_name}`"
                    size="small"
                  >
                    {{ item.stock_name || '-' }}<span v-if="item.stock_code"> {{ item.stock_code }}</span>
                  </el-tag>
                </div>
                <el-empty v-else description="暂无明确影响个股" :image-size="56" />
              </div>
            </div>
          </template>

          <div v-else class="detail-placeholder">
            <el-empty description="请选择左侧事件查看详情" />
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Star, StarFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  favoriteStockkbEvent,
  getStockkbEventDetail,
  getStockkbReportSummary,
  listStockkbEvents,
  unfavoriteStockkbEvent
} from '../api/stockkb'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  stock: { type: Object, default: null },
  reportDate: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue', 'view-analysis'])

const loadingSummary = ref(false)
const loadingEvents = ref(false)
const loadingDetail = ref(false)
const errorMessage = ref('')
const summary = ref({
  report_exists: false,
  report_title: '',
  core_logic: '',
  event_count: 0,
  risk_summary: ''
})
const events = ref([])
const selectedEventId = ref('')
const selectedDetail = ref(null)
const detailCache = ref(new Map())
const favoriteLoading = ref({})

watch(
  () => props.modelValue,
  async (visible) => {
    if (visible) {
      await refreshAll()
    } else {
      resetState()
    }
  }
)

async function refreshAll() {
  if (!props.stock || !props.reportDate) return
  resetState()
  loadingSummary.value = true
  loadingEvents.value = true

  try {
    const stockCode = props.stock.stock_code || props.stock.code
    const [summaryResp, eventsResp] = await Promise.all([
      getStockkbReportSummary(stockCode, props.reportDate),
      listStockkbEvents({
        stock_code: stockCode,
        report_date: props.reportDate,
        page: 1,
        page_size: 50,
        event_scope: 'default'
      })
    ])
    summary.value = summaryResp?.data || summary.value
    events.value = eventsResp?.data?.items || []

    if (events.value.length > 0) {
      await selectEvent(events.value[0])
    }
  } catch (e) {
    errorMessage.value = e?.message || '加载事件失败'
    ElMessage.error(errorMessage.value)
  } finally {
    loadingSummary.value = false
    loadingEvents.value = false
  }
}

async function selectEvent(item) {
  if (!item?.event_id) return
  selectedEventId.value = item.event_id
  if (detailCache.value.has(item.event_id)) {
    selectedDetail.value = detailCache.value.get(item.event_id)
    return
  }

  loadingDetail.value = true
  try {
    const resp = await getStockkbEventDetail(item.event_id)
    const data = resp?.data || null
    selectedDetail.value = data
    detailCache.value.set(item.event_id, data)
  } catch (e) {
    ElMessage.error(e?.message || '加载事件详情失败')
  } finally {
    loadingDetail.value = false
  }
}

async function toggleFavorite(item) {
  const eventId = String(item?.event_id || '').trim()
  if (!eventId) return

  setFavoriteLoading(eventId, true)
  try {
    if (isFavorite(item)) {
      await unfavoriteStockkbEvent(eventId)
      applyFavoriteState(eventId, false)
      ElMessage.success('已取消收藏')
    } else {
      await favoriteStockkbEvent(eventId)
      applyFavoriteState(eventId, true)
      ElMessage.success('已收藏到事件中心')
    }
  } catch (e) {
    ElMessage.error(e?.message || '收藏操作失败')
  } finally {
    setFavoriteLoading(eventId, false)
  }
}

function resetState() {
  errorMessage.value = ''
  summary.value = {
    report_exists: false,
    report_title: '',
    core_logic: '',
    event_count: 0,
    risk_summary: ''
  }
  events.value = []
  selectedEventId.value = ''
  selectedDetail.value = null
  detailCache.value = new Map()
  favoriteLoading.value = {}
}

function affectedStocksLabel(items) {
  const list = Array.isArray(items) ? items : []
  if (list.length === 0) return '暂无明确影响个股'
  return list
    .map(item => [item.stock_name, item.stock_code].filter(Boolean).join(' '))
    .join(' / ')
}

function eventScopeLabel(scope) {
  const map = {
    stock: '个股事件',
    industry: '行业事件',
    mixed: '混合事件',
    macro: '宏观事件'
  }
  return map[scope] || scope || '未分类'
}

function eventScopeTagType(scope) {
  const map = {
    stock: 'warning',
    industry: 'success',
    mixed: 'primary',
    macro: 'danger'
  }
  return map[scope] || 'info'
}

function displayMetaTags(item) {
  if (!item || typeof item !== 'object') return []
  const tags = []
  const scope = item.event_scope || ''
  if (scope) {
    tags.push({
      text: eventScopeLabel(scope),
      type: eventScopeTagType(scope)
    })
  }
  const industries = Array.isArray(item.affected_industries) ? item.affected_industries : []
  const themes = Array.isArray(item.affected_themes) ? item.affected_themes : []
  if (industries[0]) {
    tags.push({
      text: industries[0],
      type: 'info'
    })
  }
  if (themes[0]) {
    tags.push({
      text: themes[0],
      type: 'success'
    })
  }
  return tags.slice(0, 3)
}

function displayScopeReason(item) {
  const text = String(item?.scope_reason || '').trim()
  if (!text) return ''
  return text.length > 48 ? `${text.slice(0, 48)}...` : text
}

function hasEventSource(item) {
  return Boolean(String(item?.source_name || '').trim() || String(item?.source_url || '').trim())
}

function isFavorite(item) {
  return Boolean(item?.is_favorite)
}

function isFavoriteLoading(eventId) {
  return Boolean(favoriteLoading.value[String(eventId || '').trim()])
}

function setFavoriteLoading(eventId, loading) {
  const key = String(eventId || '').trim()
  if (!key) return
  favoriteLoading.value = {
    ...favoriteLoading.value,
    [key]: Boolean(loading)
  }
}

function applyFavoriteState(eventId, value) {
  const key = String(eventId || '').trim()
  if (!key) return
  const nextValue = Boolean(value)
  events.value = events.value.map((item) => (
    item?.event_id === key
      ? { ...item, is_favorite: nextValue }
      : item
  ))

  const cached = detailCache.value.get(key)
  if (cached?.event) {
    detailCache.value.set(key, {
      ...cached,
      event: {
        ...cached.event,
        is_favorite: nextValue,
      },
    })
  }

  if (selectedDetail.value?.event?.event_id === key) {
    selectedDetail.value = {
      ...selectedDetail.value,
      event: {
        ...selectedDetail.value.event,
        is_favorite: nextValue,
      },
    }
  }
}
</script>

<style scoped>
:deep(.stockkb-dialog .el-dialog) {
  background: var(--el-bg-color-overlay);
}

:deep(.stockkb-dialog .el-dialog__body) {
  background: var(--el-bg-color-overlay);
}

.stockkb-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.stockkb-name {
  font-size: 22px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

.stockkb-meta {
  margin-top: 6px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.stockkb-actions {
  display: flex;
  gap: 8px;
}

.stockkb-body {
  min-height: 68vh;
}

.stockkb-summary-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-chip {
  padding: 14px 16px;
  border-radius: 14px;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-light);
}

.summary-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.summary-value {
  margin-top: 6px;
  font-size: 16px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.summary-title-chip .summary-value,
.summary-risk-chip .summary-value {
  font-size: 14px;
  line-height: 1.6;
}

.summary-risk-text {
  font-weight: 600;
}

.stockkb-panels {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 16px;
  min-height: 56vh;
}

.stockkb-left,
.stockkb-right {
  border: 1px solid var(--el-border-color-light);
  border-radius: 16px;
  background: var(--el-bg-color-overlay);
}

.stockkb-left {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-heading {
  padding: 14px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

.event-list {
  flex: 1;
  overflow: auto;
  padding: 12px;
}

.event-card {
  padding: 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--el-bg-color-overlay);
}

.event-card + .event-card {
  margin-top: 10px;
}

.event-card:hover,
.event-card.active {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.12);
  background: var(--el-color-primary-light-9);
}

.event-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.event-title {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.5;
  color: var(--el-text-color-primary);
}

.favorite-icon-button {
  flex-shrink: 0;
}

.event-time {
  margin-top: 8px;
  flex-shrink: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.event-tags {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-label,
.detail-label {
  display: inline-block;
  margin-right: 8px;
  color: var(--el-text-color-secondary);
}

.stockkb-right {
  overflow: auto;
  padding: 20px;
}

.detail-title-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.detail-title-row h3 {
  margin: 0;
  font-size: 22px;
  line-height: 1.4;
  color: var(--el-text-color-primary);
}

.detail-time {
  flex-shrink: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.detail-report-bar {
  margin-top: 16px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  background: var(--el-bg-color-overlay);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.detail-report-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.detail-subsection + .detail-subsection {
  margin-top: 22px;
}

.section-heading {
  margin: 20px 0 12px;
  font-size: 15px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

.detail-description {
  border-radius: 14px;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-light);
  padding: 14px 16px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}

.detail-source-panel {
  border-radius: 14px;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-light);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-source-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-source-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.detail-source-value,
.detail-source-link {
  line-height: 1.7;
  word-break: break-all;
}

.detail-source-link {
  color: var(--el-color-primary);
  text-decoration: none;
}

.detail-source-link:hover {
  text-decoration: underline;
}

.detail-meta-panel {
  border-radius: 14px;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-light);
  padding: 14px 16px;
}

.detail-meta-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.detail-meta-reason {
  margin-top: 10px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}

.detail-meta-reason.empty {
  color: var(--el-text-color-secondary);
}

.stock-tag-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.detail-placeholder,
.stockkb-empty {
  min-height: 52vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stockkb-error {
  margin-bottom: 16px;
}

@media (max-width: 1080px) {
  .stockkb-summary-row,
  .stockkb-panels {
    grid-template-columns: 1fr;
  }
}
</style>
