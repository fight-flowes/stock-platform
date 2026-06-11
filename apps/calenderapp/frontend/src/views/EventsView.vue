<template>
  <div class="events-view">
    <el-row :gutter="16" class="events-main-grid">
      <el-col :xs="24" :lg="7">
        <div class="events-left-column">
          <el-card shadow="never" class="events-toolbar-card">
            <EventFilters
              v-model="filters"
              :loading="loadingList"
              @search="onSearch"
              @reset="onReset"
            />

            <div class="events-stats-divider"></div>

            <div class="events-summary-grid">
              <div class="events-summary-chip">
                <div class="summary-label">即将发生</div>
                <div class="summary-value">{{ futureCount }}</div>
              </div>
              <div class="events-summary-chip">
                <div class="summary-label">已发生</div>
                <div class="summary-value">{{ pastCount }}</div>
              </div>
              <div class="events-summary-chip">
                <div class="summary-label">行业事件</div>
                <div class="summary-value">{{ industryCount }}</div>
              </div>
              <div class="events-summary-chip">
                <div class="summary-label">个股事件</div>
                <div class="summary-value">{{ stockCount }}</div>
              </div>
            </div>
          </el-card>

          <EventList
            card-title="即将发生"
            :sections="futureSections"
            :loading="loadingList"
            :selected-event-key="selectedEventKey"
            :total-count="futureCount"
            :hide-section-header="true"
            @select="selectEvent"
          />
        </div>
      </el-col>

      <el-col :xs="24" :lg="17">
        <div class="events-right-column">
          <EventList
            card-title="已发生"
            :sections="paginatedPastSections"
            :loading="loadingList"
            :selected-event-key="selectedEventKey"
            :total-count="filteredPastCount"
            :hide-section-header="true"
            :scope-filter="pastEventTypeFilter"
            @select="selectEvent"
          >
            <template #header-extra>
              <div class="events-header-filter">
                <el-select
                  :model-value="pastEventTypeFilter"
                  size="small"
                  class="events-scope-select"
                  @change="onEventTypeChange"
                >
                  <el-option label="行业事件" value="industry" />
                  <el-option label="个股事件" value="stock" />
                  <el-option label="所有" value="all" />
                </el-select>
              </div>
            </template>
          </EventList>

          <div class="events-pagination">
            <el-pagination
              v-model:current-page="page"
              v-model:page-size="pageSize"
              :page-sizes="[20, 50, 100]"
              :total="filteredPastCount"
              layout="total, sizes, prev, pager, next"
              @size-change="onPaginationChange"
              @current-change="onPaginationChange"
            />
          </div>
        </div>
      </el-col>
    </el-row>

    <el-dialog
      v-model="detailVisible"
      width="min(960px, 92vw)"
      top="4vh"
      destroy-on-close
      class="event-detail-dialog"
    >
      <EventDetail
        :event="selectedEvent"
        :loading="loadingDetail"
        @open-report="openReport"
        @open-stock="openStock"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import EventDetail from '../components/EventDetail.vue'
import EventFilters from '../components/EventFilters.vue'
import EventList from '../components/EventList.vue'
import {
  getMarketEventDetail,
  listMarketEvents
} from '../api/stockkb'
import {
  createDefaultMarketEventDetail,
  createDefaultMarketEventFilters
} from '../types/marketEvent'

const router = useRouter()
const today = new Date()
const todayText = today.toISOString().slice(0, 10)
const monthStartText = `${todayText.slice(0, 8)}01`

const loadingList = ref(false)
const loadingDetail = ref(false)

const filters = ref(
  createDefaultMarketEventFilters({
    date_from: monthStartText,
    date_to: todayText,
    event_type: 'all'
  })
)
const items = ref([])
const page = ref(1)
const pageSize = ref(50)
const pastEventTypeFilter = ref('industry')

const selectedEventKey = ref('')
const selectedEvent = ref(null)
const detailVisible = ref(false)

const selectedPastEventType = computed(() => normalizeEventTypeFilter(pastEventTypeFilter.value))
const futureItems = computed(() => items.value.filter(item => isFutureEvent(item)))
const rawPastItems = computed(() => items.value.filter(item => !isFutureEvent(item)))
const filteredPastItems = computed(() => {
  const dateFrom = normalizeComparableDate(filters.value.date_from)
  const dateTo = normalizeComparableDate(filters.value.date_to)

  return rawPastItems.value.filter((item) => {
    const resolvedDate = resolveEventDate(item)
    if (!resolvedDate) {
      return false
    }
    if (dateFrom && resolvedDate < dateFrom) {
      return false
    }
    if (dateTo && resolvedDate > dateTo) {
      return false
    }
    return true
  })
})
const scopedPastItems = computed(() => {
  if (selectedPastEventType.value === 'all') {
    return filteredPastItems.value
  }
  return filteredPastItems.value.filter(item => resolveMarketEventType(item) === selectedPastEventType.value)
})
const paginatedPastItems = computed(() => {
  const start = Math.max(0, (page.value - 1) * pageSize.value)
  return scopedPastItems.value.slice(start, start + pageSize.value)
})

const futureSections = computed(() => {
  return buildTimelineSection('future', futureItems.value)
})
const paginatedPastSections = computed(() => {
  return buildTimelineSection('past', paginatedPastItems.value)
})

const futureCount = computed(() => futureItems.value.length)
const pastCount = computed(() => filteredPastItems.value.length)
const industryCount = computed(() => {
  return [...futureItems.value, ...filteredPastItems.value].filter(item => resolveMarketEventType(item) === 'industry').length
})
const stockCount = computed(() => {
  return [...futureItems.value, ...filteredPastItems.value].filter(item => resolveMarketEventType(item) === 'stock').length
})
const filteredPastCount = computed(() => {
  return scopedPastItems.value.length
})
const visibleItems = computed(() => [...futureItems.value, ...paginatedPastItems.value])

onMounted(async () => {
  await loadEvents()
})

watch([filteredPastCount, pageSize], () => {
  const maxPage = Math.max(1, Math.ceil(filteredPastCount.value / pageSize.value))
  if (page.value > maxPage) {
    page.value = maxPage
  }
})

function buildTimelineSection(sectionKey, sourceItems) {
  const targetMap = new Map()

  for (const item of sourceItems) {
    const dateKey = resolveEventDate(item)
    const dateLabel = dateKey || '未明确日期'
    if (!targetMap.has(dateLabel)) {
      targetMap.set(dateLabel, {
        dateKey: dateKey || `${sectionKey}-unknown`,
        dateLabel,
        industryEvents: [],
        stockEvents: [],
        totalCount: 0
      })
    }
    const group = targetMap.get(dateLabel)
    if (resolveMarketEventType(item) === 'industry') {
      group.industryEvents.push(item)
    } else {
      group.stockEvents.push(item)
    }
    group.totalCount += 1
  }

  return [{
    key: sectionKey,
    title: sectionKey === 'future' ? '即将发生' : '已发生',
    summary: '',
    emptyText: sectionKey === 'future' ? '暂无即将发生的事件' : '暂无已发生的事件',
    groups: sortGroups([...targetMap.values()], sectionKey === 'future')
  }]
}

async function loadEvents() {
  loadingList.value = true
  try {
    items.value = await fetchAllFavoriteEvents()

    if (!items.value.length) {
      selectedEventKey.value = ''
      selectedEvent.value = null
      detailVisible.value = false
      return
    }

    const currentExists = visibleItems.value.some(item => item.event_key === selectedEventKey.value)
    if (!currentExists) {
      selectedEventKey.value = ''
      selectedEvent.value = null
      detailVisible.value = false
    }
  } catch (e) {
    ElMessage.error(e?.message || '加载事件中心失败')
  } finally {
    loadingList.value = false
  }
}

async function selectEvent(item) {
  if (!item?.event_key) return
  selectedEventKey.value = item.event_key
  const loaded = await loadEventDetail(item.event_key)
  if (loaded) {
    detailVisible.value = true
  }
}

async function loadEventDetail(eventKey) {
  loadingDetail.value = true
  try {
    const resp = await getMarketEventDetail(eventKey)
    const data = resp?.data || {}
    selectedEvent.value = data.event || createDefaultMarketEventDetail()
    return true
  } catch (e) {
    selectedEvent.value = null
    ElMessage.error(e?.message || '加载事件详情失败')
    return false
  } finally {
    loadingDetail.value = false
  }
}

async function onSearch() {
  page.value = 1
  await loadEvents()
}

async function onReset() {
  page.value = 1
  await loadEvents()
}

async function onEventTypeChange(value) {
  pastEventTypeFilter.value = normalizeEventTypeFilter(value)
  page.value = 1
}

function onPaginationChange() {
  const currentExists = visibleItems.value.some(item => item.event_key === selectedEventKey.value)
  if (!currentExists) {
    selectedEventKey.value = ''
    selectedEvent.value = null
    detailVisible.value = false
  }
}

function openReport(report) {
  const stockCode = report?.stock_code || ''
  const stockName = report?.stock_name || ''
  const reportDate = report?.report_date || ''
  if (!stockCode || !reportDate) {
    ElMessage.info('该来源报告缺少股票代码或日期，暂时无法联动打开')
    return
  }
  router.push({
    path: '/',
    query: {
      stock_code: stockCode,
      stock_name: stockName,
      report_date: reportDate,
      open: 'analysis',
      source: 'events'
    }
  })
}

function openStock(stock) {
  const stockCode = stock?.stock_code || stock?.code || ''
  if (!stockCode) return
  router.push({
    path: '/stocks',
    query: {
      code: stockCode,
      name: stock?.stock_name || stock?.name || '',
      open: 'detail',
      source: 'events'
    }
  })
}

function resolveMarketEventType(item) {
  const eventType = String(item?.event_type || '').trim().toLowerCase()
  if (eventType === 'industry' || eventType === 'stock') {
    return eventType
  }
  const eventScope = String(item?.event_scope || '').trim().toLowerCase()
  if (eventScope === 'industry' || eventScope === 'mixed' || eventScope === 'macro') {
    return 'industry'
  }
  return 'stock'
}

function normalizeEventTypeFilter(value) {
  const normalized = String(value || '').trim().toLowerCase()
  if (normalized === 'industry' || normalized === 'stock') {
    return normalized
  }
  return 'all'
}

function resolveEventDate(item) {
  const fullDate = extractFullDate(item?.event_time_text)
    || extractFullDate(item?.latest_active_date)
    || extractFullDate(item?.first_seen_date)
  if (fullDate) return fullDate

  const monthDay = extractMonthDay(item?.event_time_text)
  if (monthDay) {
    const baseYear = extractYear(item?.first_seen_date) || new Date().getFullYear()
    return `${baseYear}-${monthDay.month}-${monthDay.day}`
  }
  return ''
}

function isFutureEvent(item) {
  const resolved = resolveEventDate(item)
  if (resolved) {
    return resolved > todayText
  }
  return /未来|预计|将于|待|预期/.test(String(item?.event_time_text || ''))
}

async function fetchAllFavoriteEvents() {
  const resp = await listMarketEvents({
    page: 1,
    page_size: 200,
    sort_by: 'latest_active_date',
    sort_order: 'desc',
    filters: {
      keyword: filters.value.keyword || '',
      favorites_only: true,
    },
  })
  const data = resp?.data || {}
  return Array.isArray(data.items) ? data.items : []
}

function normalizeComparableDate(value) {
  const fullDate = extractFullDate(value)
  return fullDate || ''
}

function sortGroups(groups, asc) {
  const sorted = [...groups].sort((left, right) => {
    const leftKey = left.dateLabel === '未明确日期' ? (asc ? '9999-12-31' : '') : left.dateLabel
    const rightKey = right.dateLabel === '未明确日期' ? (asc ? '9999-12-31' : '') : right.dateLabel
    return asc ? leftKey.localeCompare(rightKey) : rightKey.localeCompare(leftKey)
  })
  for (const group of sorted) {
    group.industryEvents.sort((a, b) => (b.affected_stock_count || 0) - (a.affected_stock_count || 0))
    group.stockEvents.sort((a, b) => String(a.event_name || '').localeCompare(String(b.event_name || '')))
  }
  return sorted
}

function extractFullDate(value) {
  const match = String(value || '').match(/(20\d{2}-\d{2}-\d{2})/)
  return match ? match[1] : ''
}

function extractYear(value) {
  const match = String(value || '').match(/(20\d{2})-/)
  return match ? Number(match[1]) : 0
}

function extractMonthDay(value) {
  const match = String(value || '').match(/(\d{1,2})月(\d{1,2})日/)
  if (!match) return null
  return {
    month: match[1].padStart(2, '0'),
    day: match[2].padStart(2, '0')
  }
}
</script>

<style scoped>
.events-view {
  display: flex;
  flex-direction: column;
  color: var(--el-text-color-primary);
}

.events-main-grid {
  align-items: flex-start;
}

.events-toolbar-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 22px;
  background: linear-gradient(180deg, var(--el-bg-color) 0%, var(--el-fill-color-blank) 100%);
  padding: 16px 18px;
  box-shadow: 0 18px 42px rgba(148, 163, 184, 0.08);
}

.events-stats-divider {
  height: 1px;
  margin: 18px 0;
  background: linear-gradient(
    90deg,
    transparent,
    var(--el-border-color-light),
    transparent
  );
}

.events-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.events-summary-chip {
  padding: 14px 14px 15px;
  border-radius: 16px;
  background: linear-gradient(180deg, var(--el-bg-color-overlay) 0%, var(--el-fill-color-blank) 100%);
  border: 1px solid var(--el-border-color-light);
  box-shadow: 0 10px 24px rgba(148, 163, 184, 0.08);
}

.events-scope-select {
  width: 128px;
}

.events-header-filter {
  display: flex;
  align-items: center;
  gap: 0;
  min-width: 0;
}

.summary-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.summary-value {
  margin-top: 6px;
  font-size: 22px;
  font-weight: 900;
  color: var(--el-text-color-primary);
}

.events-left-column,
.events-right-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.events-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 0 4px;
}

:deep(.event-board-card) {
  border-radius: 22px;
  border: 1px solid var(--el-border-color-lighter);
  background: linear-gradient(180deg, var(--el-bg-color) 0%, var(--el-fill-color-blank) 100%);
  box-shadow: 0 18px 42px rgba(148, 163, 184, 0.08);
}

:deep(.event-board-card .el-card__header) {
  padding-bottom: 10px;
  border-bottom-color: var(--el-border-color-lighter);
}

:deep(.event-board-card .el-card__body) {
  padding-top: 14px;
}

:deep(.event-detail-dialog .el-dialog) {
  --sc-event-dialog-bg: var(--el-bg-color-overlay);
  --el-dialog-bg-color: var(--sc-event-dialog-bg);
  --el-dialog-padding-primary: 0;
  border-radius: 24px;
  overflow: hidden;
  background: var(--sc-event-dialog-bg);
  border: none;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.16);
  padding: 0;
}

:deep(.event-detail-dialog .el-dialog__header) {
  padding: 0;
}

:deep(.event-detail-dialog .el-dialog__body) {
  padding: 0;
  background: var(--sc-event-dialog-bg);
}

@media (max-width: 768px) {
  .events-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
