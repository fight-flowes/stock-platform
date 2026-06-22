<template>
  <div class="announcements-view">
    <!-- Hero strip -->
    <el-card shadow="never" class="announcements-hero">
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
    </el-card>

    <!-- Level 1: Platform tabs -->
    <el-card shadow="never" class="platform-toolbar">
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

      <!-- Filters row -->
      <div class="filter-row">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="—"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          size="small"
          value-format="YYYY-MM-DD"
          clearable
          style="width: 240px;"
          @change="onFilterChange"
        />
        <el-select
          v-model="industry"
          placeholder="行业（任意）"
          size="small"
          clearable
          filterable
          style="width: 170px;"
          @change="onFilterChange"
        >
          <el-option v-for="ind in filterMeta.industries" :key="ind" :label="ind" :value="ind" />
        </el-select>
        <el-input
          v-model="keyword"
          placeholder="搜索标题 / 内容"
          size="small"
          clearable
          style="width: 200px;"
          @keyup.enter="onFilterChange"
          @clear="onFilterChange"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="importanceMin" placeholder="重要度" size="small" clearable style="width: 120px;" @change="onFilterChange">
          <el-option label="≥ 1 星" :value="1" />
          <el-option label="≥ 2 星" :value="2" />
          <el-option label="= 3 星" :value="3" />
        </el-select>
        <el-button size="small" :loading="loading" @click="onFilterChange">
          <el-icon><Refresh /></el-icon>
          <span style="margin-left: 4px;">刷新</span>
        </el-button>
      </div>
    </el-card>

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

    <!-- Detail dialog -->
    <el-dialog v-model="detailVisible" :title="detailEvent?.event_name || '事件详情'" width="640px" append-to-body>
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
  { id: 'cninfo', label: '巨潮资讯', sourceIds: null, placeholder: true },
  { id: 'xueqiu', label: '雪球', sourceIds: null, placeholder: true },
  { id: 'sina', label: '新浪财经', sourceIds: null, placeholder: true },
]

// Source labels for the 2nd-level tabs (only shown when a platform is selected)
const SOURCE_LABELS = {
  em_gsrl: '股市日历·公司动态',
  em_yjyg: '业绩预告',
  wallstreet_macro: '宏观日历',
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

const dateRange = ref([])
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
  ipo_subscribe: '新股申购', ipo_listing: '新股上市', buyback: '回购',
  restructuring: '资产重组', guarantee: '对外担保', pledge: '股份质押',
  macro_data: '宏观数据', policy_meeting: '政策会议', industry_event: '行业活动',
}
const TYPE_TAG_TYPES = {
  earnings_forecast: 'success', earnings_express: 'success', earnings_disclose: 'success',
  unlock: 'danger', restructuring: 'warning', guarantee: 'info', pledge: 'info',
  macro_data: 'warning', policy_meeting: 'warning', industry_event: 'success',
}
function typeLabel(t) { return TYPE_LABELS[t] || t || '—' }
function typeTagType(t) { return TYPE_TAG_TYPES[t] || '' }

const SOURCE_LABEL_MAP = {
  em_gsrl: '东财·股市日历', em_yjyg: '东财·业绩预告',
  wallstreet_macro: '华尔街见闻', cninfo_yypl: '巨潮·预约披露',
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
.announcements-view { display: flex; flex-direction: column; gap: 14px; padding: 4px; }

.announcements-hero {
  background: linear-gradient(135deg, var(--el-color-primary-light-9) 0%, var(--el-color-warning-light-9) 100%);
  border: none;
}
.hero-title { display: flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 600; }
.hero-subtitle { margin-top: 4px; font-size: 13px; color: var(--el-text-color-regular); }
.hero-status { margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; }

.platform-toolbar { border: 1px solid var(--el-border-color-lighter); }
.platform-tabs, .source-tabs, .filter-row {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
}
.source-tabs { margin-top: 10px; }
.filter-row { margin-top: 12px; }

.tab-badge {
  margin-left: 4px; font-size: 11px; opacity: 0.7;
}

.table-card { border: 1px solid var(--el-border-color-lighter); }
.list-header { display: flex; align-items: baseline; justify-content: space-between; }
.list-title { font-size: 15px; font-weight: 600; }
.list-count { font-size: 12px; color: var(--el-text-color-secondary); }

.event-table { cursor: pointer; }
.event-name { color: var(--el-text-color-primary); }
.tag { margin-right: 4px; margin-bottom: 2px; }
.dim { color: var(--el-text-color-disabled); }
.leader-chip {
  display: inline-block; padding: 1px 6px; border-radius: 4px;
  background: var(--el-color-warning-light-9); color: var(--el-color-warning-dark-2); font-size: 12px;
}
.source-cell { font-size: 12px; color: var(--el-text-color-secondary); }
.pagination-bar { display: flex; justify-content: flex-end; padding: 12px 0 4px; }
.stock-chip { display: inline-block; margin: 0 6px 4px 0; padding: 1px 6px; border-radius: 4px; background: var(--el-fill-color-light); font-size: 12px; }
.content-block { margin-top: 12px; }
.block-label { margin-bottom: 6px; font-size: 13px; font-weight: 600; }
.content-block pre {
  margin: 0; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px;
  font-family: inherit; font-size: 13px; line-height: 1.6; white-space: pre-wrap;
  word-break: break-word; max-height: 320px; overflow-y: auto;
}
</style>