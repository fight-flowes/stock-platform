<template>
  <div class="announcements-view">
    <div class="sticky-header">
      <el-card shadow="never" class="announcements-hero">
        <div class="hero-layout">
          <div class="hero-copy">
            <div class="hero-title">
              <el-icon><Bell /></el-icon>
              <span>公告 · 预期事件</span>
            </div>
            <div class="hero-subtitle">
              覆盖多个数据平台的预期事件（业绩预告、公司动态、宏观日历等）
            </div>
            <div class="hero-status">
              <el-tag size="small" :type="healthBadgeType" effect="plain">
                数据源：<b>eventradar</b> · {{ healthBadgeText }}
              </el-tag>
              <el-tag v-if="total > 0" size="small" type="info" effect="plain">
                共 {{ total }} 条事件
              </el-tag>
            </div>
          </div>

          <div class="filter-panel">
            <div class="filter-body">
              <div class="filter-field">
                <div class="filter-label">时间范围</div>
                <div class="filter-inline">
                  <el-date-picker
                    v-model="dateRange"
                    type="daterange"
                    range-separator="—"
                    start-placeholder="开始日期"
                    end-placeholder="结束日期"
                    size="small"
                    value-format="YYYY-MM-DD"
                    clearable
                    class="filter-date-range"
                    @change="onFilterChange"
                  />
                </div>
              </div>

              <div class="filter-field">
                <div class="filter-label">筛选条件</div>
                <div class="filter-inline">
                  <el-select
                    v-model="importanceMin"
                    placeholder="重要度"
                    size="small"
                    clearable
                    class="filter-select filter-select--narrow"
                    @change="onFilterChange"
                  >
                    <el-option label="≥ 1 星" :value="1" />
                    <el-option label="≥ 2 星" :value="2" />
                    <el-option label="= 3 星" :value="3" />
                  </el-select>
                  <el-select
                    v-model="industry"
                    placeholder="行业（任意）"
                    size="small"
                    clearable
                    filterable
                    class="filter-select"
                    @change="onFilterChange"
                  >
                    <el-option v-for="ind in filterMeta.industries" :key="ind" :label="ind" :value="ind" />
                  </el-select>
                </div>
              </div>

              <div class="filter-field">
                <div class="filter-label">事件检索</div>
                <div class="filter-inline">
                  <el-input
                    v-model="keyword"
                    placeholder="搜索标题、内容或关键词"
                    size="small"
                    clearable
                    class="filter-keyword-input"
                    @keyup.enter="onFilterChange"
                    @clear="onFilterChange"
                  >
                    <template #prefix><el-icon><Search /></el-icon></template>
                  </el-input>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="platform-toolbar">
        <div class="platform-toolbar-top">
          <div class="platform-tabs">
            <el-button
              v-for="plat in platforms"
              :key="plat.id"
              :type="activePlatform === plat.id ? 'primary' : 'default'"
              size="small"
              :disabled="plat.placeholder"
              @click="selectPlatform(plat.id)"
            >
              {{ plat.label }}
              <span class="tab-badge">{{ platCount(plat) }}</span>
            </el-button>
          </div>

          <div class="platform-toolbar-actions">
            <el-button size="small" :loading="loading" @click="onFilterChange">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>

        <!-- Level 2: Source tabs (shown when a specific platform is selected) -->
        <div v-if="activePlatform !== 'all'" class="source-tabs">
          <el-button
            v-for="src in currentSourceOptions"
            :key="src.id"
            :type="activeSource === src.id ? 'primary' : 'default'"
            size="small"
            plain
            @click="selectSource(src.id)"
          >
            {{ src.label }}
            <span class="tab-badge">{{ sourceCounts[src.id] || 0 }}</span>
          </el-button>
        </div>
      </el-card>
    </div>

    <div class="main-content">
      <!-- Table -->
      <el-card shadow="never" class="table-card">
        <template #header>
          <div class="list-header">
            <span class="list-title">事件列表</span>
            <span class="list-count">
              {{ total === 0 ? '无数据' : `第 ${page} 页 / 共 ${totalPages} 页` }}
            </span>
          </div>
        </template>

        <el-table v-loading="loading" :data="items" stripe size="default" empty-text="没有符合条件的事件"
          class="event-table" @row-click="openDetail" @sort-change="onSortChange">
          <el-table-column prop="expected_at" label="日期" width="110" sortable="custom" />
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="typeTagType(row.event_type)" effect="plain">{{ typeLabel(row.event_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="标题" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="event-name">{{ row.event_name || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="行业" min-width="150">
            <template #default="{ row }">
              <template v-if="row.affected_industries?.length">
                <el-tag v-for="tag in row.affected_industries.slice(0, 2)" :key="tag" size="small" effect="plain" class="tag">
                  {{ tag }}
                </el-tag>
              </template>
              <span v-else class="dim">—</span>
            </template>
          </el-table-column>
          <el-table-column label="龙头" min-width="120">
            <template #default="{ row }">
              <template v-if="row.leaders?.length">
                <span v-for="l in row.leaders.slice(0, 1)" :key="l.stock_code" class="leader-chip">
                  {{ l.stock_name }}
                </span>
              </template>
              <span v-else class="dim">—</span>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="120">
            <template #default="{ row }">
              <span class="source-cell">{{ sourceLabel(row.source) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="importance" label="重要度" width="100" sortable="custom">
            <template #default="{ row }">
              <el-rate :model-value="row.importance" :max="3" disabled size="small" />
            </template>
          </el-table-column>
        </el-table>

        <div v-if="total > 0" class="pagination-bar">
          <el-pagination
            v-model:current-page="page" v-model:page-size="pageSize"
            :page-sizes="[20, 50, 100]" :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            background @current-change="fetchPage" @size-change="fetchPage" />
        </div>
      </el-card>
    </div>
    <!-- Detail dialog -->
    <el-dialog
      v-model="detailVisible"
      :title="detailEvent?.event_name || '事件详情'"
      width="min(720px, 92vw)"
      append-to-body
      destroy-on-close
      class="announcement-detail-dialog"
    >
      <div v-if="detailEvent" class="event-detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="日期">{{ detailEvent.expected_at }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ typeLabel(detailEvent.event_type) }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ sourceLabel(detailEvent.source) }}</el-descriptions-item>
          <el-descriptions-item label="重要度"><el-rate :model-value="detailEvent.importance" :max="3" disabled size="small" /></el-descriptions-item>
          <el-descriptions-item v-if="detailEvent.expected_at_end" label="结束日期">{{ detailEvent.expected_at_end }}</el-descriptions-item>
          <el-descriptions-item v-if="detailEvent.affected_industries?.length" label="相关行业" :span="2">
            <el-tag v-for="tag in detailEvent.affected_industries" :key="tag" size="small" effect="plain" class="tag">{{ tag }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="detailEvent.affected_stocks?.length" label="相关股票" :span="2">
            <span v-for="s in detailEvent.affected_stocks" :key="s.stock_code" class="stock-chip">{{ s.stock_name }} <span class="dim">{{ s.stock_code }}</span></span>
          </el-descriptions-item>
          <el-descriptions-item v-if="detailEvent.leaders?.length" label="龙头股" :span="2">
            <span v-for="l in detailEvent.leaders" :key="l.stock_code" class="leader-chip">{{ l.stock_name }} <span class="dim">{{ l.stock_code }}</span></span>
          </el-descriptions-item>
        </el-descriptions>
        <div v-if="detailEvent.event_content" class="content-block">
          <div class="block-label">事件内容</div>
          <pre>{{ detailEvent.event_content }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Bell, Refresh, Search } from '@element-plus/icons-vue'
import { getAnnouncementFilterMeta, getAnnouncementsHealth, getAnnouncementSourceCounts, listAnnouncements } from '../api/announcements'

// ====== Static platform registry ======
// One source of truth for platform → source mapping. Adding a new data
// platform later is one entry in this list — no other code changes needed.
const PLATFORMS = [
  { id: 'all', label: '全部', sourceIds: null, placeholder: false },
  { id: 'em', label: '东方财富', sourceIds: ['em_gsrl', 'em_yjyg'], placeholder: false },
  { id: 'wsc', label: '华尔街见闻', sourceIds: ['wallstreet_macro'], placeholder: false },
  { id: 'cninfo', label: '巨潮资讯', sourceIds: ['cninfo_ipo'], placeholder: false },
  { id: 'xueqiu', label: '雪球', sourceIds: ['xq_insider'], placeholder: false },
  { id: 'sina', label: '新浪财经', sourceIds: null, placeholder: true },
]

// Source labels for the 2nd-level tabs (only shown when a platform is selected)
const SOURCE_LABELS = {
  em_gsrl: '股市日历·公司动态',
  em_yjyg: '业绩预告',
  wallstreet_macro: '宏观日历',
  cninfo_ipo: '新股申购',
  xq_insider: '内部交易',
}

// ====== URL ↔ state bindings ======
// Route query params: ?platform=em&source=em_yjyg
const route = useRoute()
const router = useRouter()

const activePlatform = ref(decodeParam(route.query.platform, 'all'))
const activeSource = ref(decodeParam(route.query.source, ''))

function decodeParam(val, fallback) {
  if (!val || typeof val !== 'string') return fallback
  return val.trim() || fallback
}

function formatDate(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function createDefaultDateRange() {
  const start = new Date()
  const end = new Date(start)
  end.setDate(end.getDate() + 7)
  return [formatDate(start), formatDate(end)]
}

/** Selected platform object */
const currentPlatform = computed(() => PLATFORMS.find(p => p.id === activePlatform.value) || PLATFORMS[0])

/** Source options for the 2nd-level tabs under the current platform */
const currentSourceOptions = computed(() => {
  const p = currentPlatform.value
  if (!p.sourceIds || p.placeholder) return []
  return p.sourceIds.map(sid => ({ id: sid, label: SOURCE_LABELS[sid] || sid }))
})

/** The `source` value for the backend filter: comma-separated or empty */
function sourceFilter() {
  const p = currentPlatform.value
  if (p.placeholder || p.id === 'all') return ''
  if (activeSource.value && p.sourceIds?.includes(activeSource.value)) {
    return activeSource.value
  }
  // No source selected → union all sources for this platform
  return p.sourceIds?.join(',') || ''
}

// ====== View state ======
const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const sortBy = ref('importance')
const sortOrder = ref('desc')

const dateRange = ref(createDefaultDateRange())
const industry = ref('')
const keyword = ref('')
const importanceMin = ref(null)

const sourceCounts = reactive({})
const filterMeta = reactive({ industries: [] })
const health = reactive({ status: 'unknown' })

const detailVisible = ref(false)
const detailEvent = ref(null)

const platforms = PLATFORMS  // exposed to template

// ====== Platform count badge ======
function platCount(plat) {
  if (plat.id === 'all') {
    const vals = Object.values(sourceCounts)
    return vals.length === 0 ? '' : vals.reduce((a, b) => a + b, 0)
  }
  if (plat.placeholder) return ''
  const ids = plat.sourceIds || []
  let sum = 0
  for (const sid of ids) sum += sourceCounts[sid] || 0
  return sum || ''
}

// ====== Health badge ======
const healthBadgeType = computed(() => {
  if (health.status === 'healthy') return 'success'
  if (health.status === 'not_configured') return 'info'
  return 'info'
})
const healthBadgeText = computed(() => {
  if (health.status === 'healthy') return '正常'
  if (health.status === 'not_configured') return '未配置'
  return '检测中'
})

// ====== Pagination ======
const totalPages = computed(() => (total.value === 0 ? 0 : Math.ceil(total.value / pageSize.value)))

// ====== Label maps ======
const TYPE_LABELS = {
  earnings_forecast: '业绩预告', earnings_express: '业绩快报', earnings_disclose: '财报预披露',
  unlock: '限售解禁', shareholders_meeting: '股东大会', dividend: '分红派息',
  ipo_subscribe: '新股申购', ipo_lottery: '中签公告', ipo_payment: '中签缴款', ipo_listing: '新股上市',
  buyback: '回购', insider_trade: '内部交易',
  restructuring: '资产重组', guarantee: '对外担保', pledge: '股份质押',
  macro_data: '宏观数据', policy_meeting: '政策会议', industry_event: '行业活动',
}
const TYPE_TAG_TYPES = {
  earnings_forecast: 'success', earnings_express: 'success', earnings_disclose: 'success',
  unlock: 'danger', restructuring: 'warning', guarantee: 'info', pledge: 'info',
  macro_data: 'warning', policy_meeting: 'warning', industry_event: 'success',
  ipo_subscribe: 'warning', ipo_lottery: 'warning', ipo_payment: 'warning', ipo_listing: 'warning',
  insider_trade: 'danger',
}
function typeLabel(t) { return TYPE_LABELS[t] || t || '—' }
function typeTagType(t) { return TYPE_TAG_TYPES[t] || '' }

const SOURCE_LABEL_MAP = {
  em_gsrl: '东财·股市日历', em_yjyg: '东财·业绩预告',
  wallstreet_macro: '华尔街见闻', cninfo_yypl: '巨潮·预约披露',
  cninfo_ipo: '巨潮·新股申购',
  xq_insider: '雪球·内部交易',
}
function sourceLabel(s) { return SOURCE_LABEL_MAP[s] || s || '—' }

// ====== API actions ======
async function loadHealth() {
  try { const r = await getAnnouncementsHealth(); health.status = r?.data?.status || 'unknown' }
  catch { health.status = 'unreachable' }
}

async function loadSourceCounts() {
  try {
    const r = await getAnnouncementSourceCounts()
    const data = r?.data?.counts || {}
    Object.keys(data).forEach(k => { sourceCounts[k] = data[k] })
  } catch { /* non-fatal */ }
}

async function loadFilterMeta() {
  try {
    const r = await getAnnouncementFilterMeta()
    const d = r?.data || {}
    filterMeta.industries = Array.isArray(d.industries) ? d.industries : []
  } catch { /* non-fatal */ }
}

function buildFilters() {
  const f = {}
  const src = sourceFilter()
  if (src) f.source = src
  if (dateRange.value && dateRange.value.length === 2) {
    f.date_from = dateRange.value[0]; f.date_to = dateRange.value[1]
  }
  if (industry.value) f.industry = industry.value
  if (keyword.value) f.keyword = keyword.value
  if (importanceMin.value) f.importance_min = importanceMin.value
  return f
}

async function fetchPage() {
  loading.value = true
  try {
    const resp = await listAnnouncements({
      page: page.value, page_size: pageSize.value,
      sort_by: sortBy.value, sort_order: sortOrder.value,
      filters: buildFilters(),
    })
    const d = resp?.data || {}
    items.value = Array.isArray(d.items) ? d.items : []
    total.value = Number.isFinite(d.total_count) ? d.total_count : 0
  } catch (err) {
    ElMessage.error(err?.message || '加载失败')
    items.value = []; total.value = 0
  } finally { loading.value = false }
}

// ====== URL sync ======
function syncUrl() {
  const q = {}
  if (activePlatform.value !== 'all') q.platform = activePlatform.value
  if (activeSource.value) q.source = activeSource.value
  router.replace({ query: q }).catch(() => {})
}

function selectPlatform(id) {
  if (id === activePlatform.value) return
  const plat = PLATFORMS.find(p => p.id === id)
  if (plat?.placeholder) {
    ElMessage.info(`${plat.label} 数据源正在开发中`)
    return
  }
  activePlatform.value = id
  activeSource.value = ''
  page.value = 1
  syncUrl(); fetchPage()
}

function selectSource(id) {
  activeSource.value = id
  page.value = 1
  syncUrl(); fetchPage()
}

function onFilterChange() { page.value = 1; fetchPage() }
function onSortChange({ prop, order }) {
  sortBy.value = prop || 'importance'
  sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
  fetchPage()
}
function openDetail(row) { detailEvent.value = row; detailVisible.value = true }

// ====== Bootstrap ======
onMounted(async () => {
  // Load counts + meta in parallel, then the first page
  await Promise.all([loadHealth(), loadSourceCounts(), loadFilterMeta()])
  await fetchPage()
})
</script>

<style scoped>
.announcements-view {
  min-height: 100vh;
  background: var(--el-bg-color-page);
}

.sticky-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px 16px 0;
  background: var(--el-bg-color-page);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.main-content {
  padding: 16px;
}

.announcements-hero {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 22px;
  background: linear-gradient(180deg, var(--el-bg-color) 0%, var(--el-fill-color-blank) 100%);
  box-shadow: 0 18px 42px rgba(148, 163, 184, 0.08);
}

.announcements-hero :deep(.el-card__body) {
  padding: 18px 18px 16px;
}

.hero-layout {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.hero-copy {
  min-width: 0;
  flex: 1 1 320px;
}

.filter-panel {
  flex: 1 1 520px;
  min-width: min(100%, 520px);
}

.filter-body {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.hero-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

.hero-subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}

.hero-status {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.platform-toolbar,
.table-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 22px;
  background: linear-gradient(180deg, var(--el-bg-color) 0%, var(--el-fill-color-blank) 100%);
  box-shadow: 0 18px 42px rgba(148, 163, 184, 0.08);
}

.platform-toolbar :deep(.el-card__body),
.table-card :deep(.el-card__body) {
  padding: 18px 18px 16px;
}

.table-card :deep(.el-card__header) {
  padding: 18px 18px 12px;
  border-bottom-color: var(--el-border-color-lighter);
}

.platform-tabs,
.source-tabs {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
}

.platform-toolbar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.platform-tabs {
  flex: 1;
  min-width: 0;
}

.platform-toolbar-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex: 0 0 auto;
}

.source-tabs { margin-top: 12px; }

.filter-field {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color-overlay);
  box-shadow: 0 10px 24px rgba(148, 163, 184, 0.05);
}

.filter-label {
  flex: 0 0 72px;
  font-size: 13px;
  font-weight: 700;
  color: var(--el-text-color-regular);
}

.filter-inline {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.platform-tabs :deep(.el-button),
.source-tabs :deep(.el-button) {
  border-radius: 999px;
}

.filter-date-range {
  width: min(280px, 100%);
  max-width: 100%;
}

.filter-select {
  width: 170px;
}

.filter-select--narrow {
  width: 120px;
}

.filter-keyword-input {
  width: 100%;
}

.filter-panel :deep(.el-input__wrapper),
.filter-panel :deep(.el-select__wrapper),
.filter-panel :deep(.el-range-editor.el-input__wrapper) {
  border-radius: 12px;
  box-shadow: none;
}

.filter-panel :deep(.el-input__wrapper.is-focus),
.filter-panel :deep(.el-select__wrapper.is-focused),
.filter-panel :deep(.el-range-editor.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--el-color-primary) inset;
}

.tab-badge {
  margin-left: 4px; font-size: 11px; opacity: 0.7;
}

.list-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.list-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.list-count { font-size: 12px; color: var(--el-text-color-secondary); }

.event-table {
  cursor: pointer;
}

.event-table :deep(.el-table__row) {
  transition: background-color 0.18s ease;
}

.event-name {
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.tag { margin-right: 4px; margin-bottom: 2px; }
.dim { color: var(--el-text-color-disabled); }
.leader-chip {
  display: inline-block; padding: 1px 6px; border-radius: 4px;
  background: var(--el-color-warning-light-9); color: var(--el-color-warning-dark-2); font-size: 12px;
}
.source-cell { font-size: 12px; color: var(--el-text-color-secondary); }

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding: 18px 4px 2px;
}

.stock-chip { display: inline-block; margin: 0 6px 4px 0; padding: 1px 6px; border-radius: 4px; background: var(--el-fill-color-light); font-size: 12px; }
.content-block { margin-top: 12px; }
.block-label { margin-bottom: 6px; font-size: 13px; font-weight: 600; }
.content-block pre {
  margin: 0; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px;
  font-family: inherit; font-size: 13px; line-height: 1.6; white-space: pre-wrap;
  word-break: break-word; max-height: 320px; overflow-y: auto;
}

:deep(.announcement-detail-dialog .el-dialog) {
  border-radius: 24px;
  overflow: hidden;
  border: none;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.16);
}

:deep(.announcement-detail-dialog .el-dialog__header) {
  margin-right: 0;
  padding: 18px 22px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

:deep(.announcement-detail-dialog .el-dialog__title) {
  font-size: 18px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

:deep(.announcement-detail-dialog .el-dialog__body) {
  padding: 18px 22px 24px;
  background: linear-gradient(180deg, var(--el-bg-color-overlay) 0%, var(--el-fill-color-blank) 100%);
}

.event-detail :deep(.el-descriptions) {
  border-radius: 16px;
  overflow: hidden;
}

.event-detail :deep(.el-descriptions__label) {
  font-weight: 600;
}

@media (max-width: 900px) {
  .sticky-header,
  .main-content {
    padding-left: 12px;
    padding-right: 12px;
  }

  .hero-layout {
    flex-direction: column;
    align-items: stretch;
  }

  .platform-toolbar-top {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-field,
  .filter-inline {
    align-items: stretch;
    flex-direction: column;
  }

  .filter-label {
    flex: none;
  }

  .filter-date-range,
  .filter-select,
  .filter-select--narrow {
    width: 100%;
  }

  .platform-toolbar-actions {
    justify-content: flex-end;
  }
}
</style>
