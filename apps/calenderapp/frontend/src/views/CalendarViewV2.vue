<template>
  <div :class="['calendar-v2-view', { 'calendar-v2-view--dark': calendarThemeKey === 'dark' }]">
    <el-row :gutter="16" class="calendar-top-grid">
      <el-col :xs="24" :lg="7">
        <el-card shadow="never" class="calendar-hero">
          <div class="hero-layout">
            <div class="hero-copy">
              <div class="hero-title">
                <span class="hero-title-icon">
                  <el-icon><Calendar /></el-icon>
                </span>
                <span>可信事件日历</span>
              </div>
              <div class="hero-subtitle">只展示来自收藏事件、已完成核查的可用日历事件。</div>

              <div class="hero-source-panel">
                <div class="hero-source-head">
                  <div class="summary-label">数据源状态</div>
                  <el-tag :type="healthTagType" effect="plain" size="small">{{ healthText }}</el-tag>
                </div>
                <div class="hero-source-subtitle">当前页面直接读取 stockkb DuckDB</div>
                <div class="hero-source-grid">
                  <div class="source-status-line">
                    <span>已核查事件</span>
                    <strong>{{ health.reviewed_event_count || 0 }}</strong>
                  </div>
                  <div class="source-status-line">
                    <span>可入日历</span>
                    <strong>{{ health.calendar_ready_count || 0 }}</strong>
                  </div>
                </div>
              </div>

              <div class="hero-stats">
                <div class="summary-chip">
                  <div class="summary-label">已入历</div>
                  <div class="summary-value">{{ stats.calendar_ready_total || 0 }}</div>
                </div>
                <div class="summary-chip">
                  <div class="summary-label">待核查</div>
                  <div class="summary-value">{{ stats.pending_total || 0 }}</div>
                </div>
                <div class="summary-chip">
                  <div class="summary-label">谨慎采用</div>
                  <div class="summary-value">{{ stats.caution_total || 0 }}</div>
                </div>
                <div class="summary-chip">
                  <div class="summary-label">时间待确认</div>
                  <div class="summary-value">{{ stats.unresolved_time_total || 0 }}</div>
                </div>
                <div class="summary-chip summary-chip--accent">
                  <div class="summary-label">手动纳入</div>
                  <div class="summary-value">{{ stats.manual_include_total || 0 }}</div>
                </div>
                <div class="summary-chip summary-chip--accent">
                  <div class="summary-label">手动排除</div>
                  <div class="summary-value">{{ stats.manual_exclude_total || 0 }}</div>
                </div>
              </div>
            </div>

            <div class="filter-panel">
              <div class="filter-grid">
                <div class="filter-field filter-field--wide">
                  <div class="filter-label">时间范围</div>
                  <el-date-picker
                    v-model="dateRange"
                    type="daterange"
                    unlink-panels
                    range-separator="—"
                    start-placeholder="开始日期"
                    end-placeholder="结束日期"
                    value-format="YYYY-MM-DD"
                    clearable
                    class="field-control"
                    @change="loadEvents"
                  />
                </div>

                <div class="filter-field">
                  <div class="filter-label">行业</div>
                  <el-select
                    v-model="filters.industry"
                    clearable
                    filterable
                    placeholder="全部行业"
                    class="field-control"
                    @change="loadEvents"
                  >
                    <el-option v-for="item in filterMeta.industries" :key="item" :label="item" :value="item" />
                  </el-select>
                </div>

                <div class="filter-field">
                  <div class="filter-label">状态</div>
                  <el-select
                    v-model="filters.status"
                    placeholder="全部状态"
                    class="field-control"
                    @change="loadEvents"
                  >
                    <el-option label="全部" value="all" />
                    <el-option label="可信入历" value="trusted" />
                    <el-option label="待核查" value="pending" />
                    <el-option label="谨慎采用" value="caution" />
                    <el-option label="已排除" value="excluded" />
                  </el-select>
                </div>

                <div class="filter-field">
                  <div class="filter-label">类型</div>
                  <el-select
                    v-model="filters.eventType"
                    clearable
                    placeholder="全部类型"
                    class="field-control"
                    @change="loadEvents"
                  >
                    <el-option label="全部类型" value="all" />
                    <el-option v-for="item in filterMeta.event_types" :key="item" :label="eventTypeLabel(item)" :value="item" />
                  </el-select>
                </div>

                <div class="filter-field">
                  <div class="filter-label">覆写视图</div>
                  <el-select
                    v-model="filters.overrideMode"
                    placeholder="全部"
                    class="field-control"
                    @change="loadEvents"
                  >
                    <el-option label="全部事件" value="all" />
                    <el-option label="仅看手动覆写" value="manual" />
                    <el-option label="仅看自动判断" value="auto" />
                    <el-option label="仅看手动纳入" value="manual_include" />
                    <el-option label="仅看手动排除" value="manual_exclude" />
                  </el-select>
                </div>

                <div class="filter-field filter-field--wide">
                  <div class="filter-label">事件检索</div>
                  <el-input
                    v-model.trim="filters.keyword"
                    placeholder="搜索事件标题、内容、行业、股票或核查摘要"
                    clearable
                    class="field-control"
                    @keyup.enter="loadEvents"
                    @clear="loadEvents"
                  />
                </div>
              </div>

              <div class="filter-actions">
                <el-button @click="resetFilters">重置</el-button>
                <el-button type="primary" :loading="loading" @click="loadEvents">刷新</el-button>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="17">
        <el-card shadow="never" class="calendar-main-card calendar-main-card--primary">
          <template #header>
            <div class="card-header">
              <div class="card-header-copy">
                <div class="card-title">月历视图</div>
              </div>
              <el-tag type="info" effect="plain">当前 {{ readyItems.length }} 条</el-tag>
            </div>
          </template>

          <FullCalendar :key="calendarThemeKey" ref="calendarRef" :options="calendarOptions" />
        </el-card>
      </el-col>
    </el-row>

    <el-dialog
      v-model="detailVisible"
      width="min(960px, 92vw)"
      top="4vh"
      destroy-on-close
      class="calendar-detail-dialog"
    >
      <template #header>
        <div class="detail-header">
          <div class="detail-title">{{ detailItem?.event_name || '事件详情' }}</div>
          <div class="detail-tags" v-if="detailItem">
            <el-tag size="small" :type="reviewBucketTagType(detailItem.review_bucket)" effect="plain">
              {{ reviewBucketLabel(detailItem.review_bucket) }}
            </el-tag>
            <el-tag size="small" type="info" effect="plain">
              {{ formatDateRange(detailItem) }}
            </el-tag>
          </div>
        </div>
      </template>

      <el-skeleton v-if="detailLoading" :rows="8" animated />
      <div v-else-if="detailItem" class="detail-body">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="事件类型">{{ eventTypeLabel(detailItem.event_type) }}</el-descriptions-item>
          <el-descriptions-item label="核查结论">{{ reviewBucketLabel(detailItem.review_bucket) }}</el-descriptions-item>
          <el-descriptions-item label="时间判断">{{ truthLabel(detailItem.time_truth) }}</el-descriptions-item>
          <el-descriptions-item label="内容判断">{{ truthLabel(detailItem.content_truth) }}</el-descriptions-item>
        </el-descriptions>

        <div class="override-toolbar">
          <div class="override-toolbar-copy">
            <div class="detail-block-title">日历管理</div>
            <div class="override-toolbar-note">
              {{
                detailItem.override_note
                  ? `备注：${detailItem.override_note}`
                  : '你可以手动纳入、移出，或恢复自动判断。'
              }}
            </div>
          </div>
          <div class="override-toolbar-actions">
            <el-button
              v-if="detailItem.calendar_source !== 'manual_include'"
              type="primary"
              :loading="overrideSaving"
              @click="openIncludeDialog(detailItem)"
            >
              加入日历
            </el-button>
            <el-button
              v-if="detailItem.calendar_source !== 'manual_exclude'"
              :loading="overrideSaving"
              @click="excludeFromCalendar(detailItem)"
            >
              移出日历
            </el-button>
            <el-button
              v-if="detailItem.override_decision"
              :loading="overrideSaving"
              @click="clearOverride(detailItem)"
            >
              恢复自动判断
            </el-button>
          </div>
        </div>

        <div class="detail-block">
          <div class="detail-block-title">核查摘要</div>
          <div class="detail-paragraph">{{ detailItem.review_summary || '暂无核查摘要' }}</div>
        </div>

        <div class="detail-block" v-if="detailItem.event_content">
          <div class="detail-block-title">事件内容</div>
          <div class="detail-paragraph">{{ detailItem.event_content }}</div>
        </div>

        <div class="detail-block" v-if="detailItem.affected_stocks?.length">
          <div class="detail-block-title">关联股票</div>
          <div class="chip-row">
            <el-tag
              v-for="stock in detailItem.affected_stocks"
              :key="`${stock.stock_code}-${stock.stock_name}`"
              size="small"
              effect="plain"
            >
              {{ stock.stock_name || stock.stock_code }}
              <span v-if="stock.stock_name && stock.stock_code">（{{ stock.stock_code }}）</span>
            </el-tag>
          </div>
        </div>

        <div class="detail-block" v-if="detailEventSources(detailItem).length || detailItem.source_reports?.length">
          <div class="detail-block-title">来源信息</div>
          <div v-if="detailEventSources(detailItem).length" class="source-group">
            <div class="source-group-title">事件来源</div>
            <div class="report-list">
              <div
                v-for="source in detailEventSources(detailItem)"
                :key="`${source.source_name}-${source.source_url}`"
                class="report-card"
              >
                <div class="report-meta report-meta--stack">
                  <span class="report-meta-label">来源平台</span>
                  <span>{{ source.source_name || '来源平台未识别' }}</span>
                </div>
                <div class="report-meta report-meta--stack" v-if="source.source_url">
                  <span class="report-meta-label">原始 URL</span>
                  <a
                    :href="source.source_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="report-link"
                  >
                    {{ source.source_url }}
                  </a>
                </div>
              </div>
            </div>
          </div>

          <div v-if="detailItem.source_reports?.length" class="source-group">
            <div class="source-group-title">报告来源</div>
            <div class="report-list">
              <div v-for="report in detailItem.source_reports" :key="report.report_id" class="report-card">
                <div class="report-meta">
                  <span>{{ report.report_date || '未知日期' }}</span>
                  <span>{{ formatReportSource(report) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog
      v-model="overrideDialogVisible"
      title="手动加入日历"
      width="min(520px, 92vw)"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="入历日期">
          <el-date-picker
            v-model="overrideDateRange"
            type="daterange"
            unlink-panels
            range-separator="—"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            class="field-control"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model.trim="overrideForm.note"
            type="textarea"
            :rows="3"
            maxlength="200"
            show-word-limit
            placeholder="例如：已人工确认日期，以会期为准"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="overrideDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="overrideSaving" @click="submitIncludeOverride">确认加入</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="pendingDayVisible"
      :title="pendingDayTitle"
      width="min(720px, 92vw)"
      destroy-on-close
      class="calendar-pending-dialog"
    >
      <el-empty v-if="pendingDayItems.length === 0" description="当天没有未入历事件" />
      <div v-else class="pending-day-list">
        <button
          v-for="item in pendingDayItems"
          :key="item.event_key"
          type="button"
          :class="['pending-day-item', pendingItemToneClass(item)]"
          @click="openPendingDayDetail(item)"
        >
          <div class="pending-day-name">{{ item.event_name }}</div>
          <div class="pending-day-meta">
            <span>{{ formatDateRange(item) }}</span>
            <span>{{ reviewBucketLabel(item.review_bucket) }}</span>
          </div>
        </button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/daygrid'
import interactionPlugin from '@fullcalendar/interaction'
import listPlugin from '@fullcalendar/list'
import zhCnLocale from '@fullcalendar/core/locales/zh-cn'
import { Calendar } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getHolidayStatus } from '../utils/holiday'
import { getLunarDayText } from '../utils/lunar'
import {
  getCalendarV2EventDetail,
  getCalendarV2FilterMeta,
  getCalendarV2Health,
  listCalendarV2Events,
  saveCalendarV2Override
} from '../api/calendarV2'

const calendarRef = ref()
const calendarThemeKey = ref(document.documentElement.classList.contains('dark') ? 'dark' : 'light')
const loading = ref(false)
const detailLoading = ref(false)
const overrideSaving = ref(false)

const items = ref([])
const filterMeta = ref({
  industries: [],
  event_types: [],
  date_min: '',
  date_max: ''
})
const stats = ref({})
const health = ref({})

const detailVisible = ref(false)
const detailItem = ref(null)
const overrideDialogVisible = ref(false)
const pendingDayVisible = ref(false)
const pendingDayDate = ref('')
const pendingDayItems = ref([])
const overrideTargetKey = ref('')
const overrideDateRange = ref([])
const overrideForm = reactive({
  note: ''
})

const today = new Date()
const monthStart = new Date(today.getFullYear(), today.getMonth(), 1)
const monthEnd = new Date(today.getFullYear(), today.getMonth() + 1, 0)

const dateRange = ref([
  formatDate(monthStart),
  formatDate(monthEnd)
])

let themeObserver = null

const filters = reactive({
  keyword: '',
  industry: '',
  status: 'all',
  eventType: 'all',
  overrideMode: 'all'
})

const readyItems = computed(() => items.value.filter((item) => item.calendar_ready))
const backlogItems = computed(() => items.value.filter((item) => !item.calendar_ready))
const datedBacklogItems = computed(() => backlogItems.value.filter((item) => String(item?.calendar_date_start || '').trim()))
const pendingDayTitle = computed(() => (pendingDayDate.value ? `未入历事件 · ${pendingDayDate.value}` : '未入历事件'))
const pendingMarkersByDate = computed(() => {
  const grouped = new Map()

  for (const item of datedBacklogItems.value) {
    for (const dateText of expandDateKeys(item.calendar_date_start, item.calendar_date_end || item.calendar_date_start)) {
      if (!grouped.has(dateText)) {
        grouped.set(dateText, [])
      }
      grouped.get(dateText).push(item)
    }
  }

  for (const [dateText, sourceItems] of grouped.entries()) {
    grouped.set(
      dateText,
      [...sourceItems].sort((left, right) => {
        return String(left.event_name || '').localeCompare(String(right.event_name || ''), 'zh-CN')
      })
    )
  }

  return grouped
})
const healthTagType = computed(() => (health.value?.status === 'ok' ? 'success' : 'danger'))
const healthText = computed(() => (health.value?.status === 'ok' ? '已连接' : '异常'))

const calendarEvents = computed(() => {
  return readyItems.value.map((item) => {
    const endExclusive = toExclusiveEnd(item.calendar_date_end || item.calendar_date_start)
    return {
      id: item.event_key,
      title: item.event_name,
      start: item.calendar_date_start,
      end: endExclusive,
      allDay: true,
      extendedProps: item
    }
  })
})

const calendarOptions = computed(() => ({
  plugins: [dayGridPlugin, interactionPlugin, listPlugin],
  initialView: 'dayGridMonth',
  locale: zhCnLocale,
  height: 'auto',
  fixedWeekCount: false,
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: 'dayGridMonth,listWeek'
  },
  buttonText: {
    today: '今天',
    month: '月',
    list: '列表'
  },
  events: calendarEvents.value,
  dayCellContent: (arg) => renderDayCell(arg),
  datesSet: async (arg) => {
    const nextRange = getViewDateRange(arg)
    const currentRange = [
      String(dateRange.value?.[0] || ''),
      String(dateRange.value?.[1] || '')
    ]

    if (nextRange && (nextRange[0] !== currentRange[0] || nextRange[1] !== currentRange[1])) {
      dateRange.value = nextRange
      await loadEvents()
      return
    }

    nextTick(() => {
      syncPendingDayMarkers()
    })
  },
  eventDidMount: (arg) => {
    const item = arg?.event?.extendedProps
    if (item) {
      arg.el.style.setProperty('--cv2-event-fill', eventFillColor(item))
      arg.el.style.setProperty('--cv2-event-text', eventTextColor(item))
      arg.el.style.setProperty('--cv2-event-border', eventBorderColor(item))
      arg.el.setAttribute('title', buildEventTooltip(item))
    }
  },
  displayEventTime: false,
  eventOrder: 'start,title',
  moreLinkText: (num) => `+${num}`,
  dayMaxEventRows: 3,
  eventClick: (arg) => {
    const item = arg?.event?.extendedProps
    if (item) {
      openEventDetail(item)
    }
  }
}))

function formatDate(input) {
  const d = new Date(input)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function getViewDateRange(arg) {
  const view = arg?.view
  const start = view?.currentStart || arg?.start
  const endExclusive = view?.currentEnd || arg?.end
  if (!start || !endExclusive) return null

  const end = new Date(endExclusive)
  end.setDate(end.getDate() - 1)
  return [formatDate(start), formatDate(end)]
}

function toExclusiveEnd(dateText) {
  if (!dateText) return undefined
  const d = new Date(dateText)
  d.setDate(d.getDate() + 1)
  return formatDate(d)
}

function eventFillColor(item) {
  const dark = document.documentElement.classList.contains('dark')
  if (item?.calendar_source === 'manual_include') return 'rgba(15, 159, 120, 0.16)'
  if (item?.review_bucket === 'caution') return 'rgba(217, 119, 6, 0.14)'
  return dark ? 'rgba(148, 163, 184, 0.14)' : 'rgba(241, 245, 249, 0.98)'
}

function eventTextColor(item) {
  const dark = document.documentElement.classList.contains('dark')
  if (item?.calendar_source === 'manual_include') return '#065f46'
  if (item?.review_bucket === 'caution') return '#92400e'
  return dark ? 'rgba(226, 232, 240, 0.94)' : '#334155'
}

function eventBorderColor(item) {
  const dark = document.documentElement.classList.contains('dark')
  if (item?.calendar_source === 'manual_include') return 'rgba(15, 159, 120, 0.28)'
  if (item?.review_bucket === 'caution') return 'rgba(217, 119, 6, 0.26)'
  return dark ? 'rgba(148, 163, 184, 0.2)' : 'rgba(148, 163, 184, 0.18)'
}

function pendingItemToneClass(item) {
  if (item?.calendar_source === 'manual_include') return 'pending-day-item--manual-include'
  if (item?.calendar_source === 'manual_exclude') return 'pending-day-item--manual-exclude'
  if (item?.review_bucket === 'caution') return 'pending-day-item--caution'
  return 'pending-day-item--pending'
}

function renderDayCell(arg) {
  if (arg.view?.type !== 'dayGridMonth') return undefined
  const solarText = String(arg.dayNumberText || '').replace(/日$/, '')
  const lunarText = getLunarDayText(arg.date)
  const holiday = getHolidayStatus(arg.date)

  const wrap = document.createElement('div')
  wrap.className = 'cv2-daycell'

  const solar = document.createElement('div')
  solar.className = 'cv2-solar'
  solar.textContent = solarText

  const lunar = document.createElement('div')
  lunar.className = holiday.type === 'rest' ? 'cv2-lunar cv2-lunar--holiday' : 'cv2-lunar'
  if (holiday.type === 'rest') {
    lunar.textContent = `${holiday.name} · 休`
  } else if (holiday.type === 'work') {
    lunar.textContent = `${lunarText} · 班`
  } else {
    lunar.textContent = lunarText
  }

  wrap.appendChild(solar)
  wrap.appendChild(lunar)
  return { domNodes: [wrap] }
}

function syncPendingDayMarkers() {
  const root = calendarRef.value?.$el
  if (!root) return

  const cells = root.querySelectorAll('.fc-daygrid-day[data-date]')
  for (const cell of cells) {
    const frame = cell.querySelector('.fc-daygrid-day-frame')
    if (!frame) continue

    frame.classList.remove('cv2-dayframe--has-pending')
    frame.querySelectorAll('.cv2-pending-day-marker').forEach((node) => node.remove())

    const dateText = String(cell.getAttribute('data-date') || '')
    const pendingItems = pendingMarkersByDate.value.get(dateText) || []
    if (!pendingItems.length) continue

    frame.classList.add('cv2-dayframe--has-pending')

    const marker = document.createElement('button')
    marker.type = 'button'
    marker.className = 'cv2-pending-day-marker'
    marker.title = buildPendingMarkerTooltip(dateText, pendingItems)
    marker.setAttribute('aria-label', `查看 ${dateText} 的未入历事件，共 ${pendingItems.length} 条`)

    const icon = document.createElement('span')
    icon.className = 'cv2-pending-day-marker__clock'

    const hand = document.createElement('span')
    hand.className = 'cv2-pending-day-marker__clock-hand'
    icon.appendChild(hand)

    const count = document.createElement('span')
    count.className = 'cv2-pending-day-marker__count'
    count.textContent = pendingItems.length > 9 ? '9+' : String(pendingItems.length)

    marker.appendChild(icon)
    marker.appendChild(count)
    marker.addEventListener('click', (event) => {
      event.preventDefault()
      event.stopPropagation()
      openPendingDayDialog(dateText, pendingItems)
    })

    frame.appendChild(marker)
  }
}

function eventTypeLabel(value) {
  const mapping = {
    industry: '行业事件',
    stock: '个股事件',
    policy: '政策事件',
    macro: '宏观事件',
    other: '其他'
  }
  return mapping[value] || value || '未分类'
}

function scopeLabel(value) {
  const mapping = {
    industry: '行业',
    stock: '个股',
    cross_stock: '跨股票',
    mixed: '复合'
  }
  return mapping[value] || value || '—'
}

function truthLabel(value) {
  const mapping = {
    true: '真实',
    dubious: '存疑',
    unverified: '未证实',
    accurate: '准确',
    mostly_accurate: '基本准确',
    unsupported: '缺少支撑',
    time_aligned: '时间匹配',
    time_mismatch: '时间不匹配',
    time_dubious: '时间存疑',
    time_unknown: '时间未知'
  }
  return mapping[value] || value || '—'
}

function reviewBucketLabel(value) {
  const mapping = {
    trusted: '可信入历',
    pending: '待核查',
    caution: '谨慎采用',
    excluded: '已排除'
  }
  return mapping[value] || value || '未分类'
}

function reviewBucketTagType(value) {
  const mapping = {
    trusted: 'success',
    pending: 'warning',
    caution: 'info',
    excluded: 'danger'
  }
  return mapping[value] || 'info'
}

function calendarSourceLabel(value) {
  const mapping = {
    rule: '自动判断',
    manual_include: '手动纳入',
    manual_exclude: '手动排除'
  }
  return mapping[value] || '自动判断'
}

function calendarSourceShortLabel(value) {
  const mapping = {
    manual_include: '手动纳入',
    manual_exclude: '手动排除'
  }
  return mapping[value] || '自动'
}

function calendarSourceTagType(value) {
  const mapping = {
    manual_include: 'success',
    manual_exclude: 'danger',
    rule: 'info'
  }
  return mapping[value] || 'info'
}

function overrideStatusLabel(item) {
  if (!item?.override_decision) return '无覆写'
  return item.override_decision === 'include' ? '已手动纳入' : '已手动排除'
}

function formatDateRange(item) {
  if (!item?.calendar_date_start) {
    return item?.event_time_text || '时间待确认'
  }
  if (!item.calendar_date_end || item.calendar_date_end === item.calendar_date_start) {
    return item.calendar_date_start
  }
  return `${item.calendar_date_start} — ${item.calendar_date_end}`
}

function formatReportSource(report) {
  if (report?.stock_name && report?.stock_code) {
    return `${report.stock_name}（${report.stock_code}）`
  }
  return report?.stock_name || report?.stock_code || report?.report_title || '报告来源未识别'
}

function detailEventSources(item) {
  const rows = Array.isArray(item?.source_events) ? item.source_events : []
  const deduped = []
  const seen = new Set()

  for (const row of rows) {
    const sourceName = String(row?.source_name || '').trim()
    const sourceUrl = String(row?.source_url || '').trim()
    if (!sourceName && !sourceUrl) continue
    const key = `${sourceName}__${sourceUrl}`
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push({
      source_name: sourceName,
      source_url: sourceUrl,
    })
  }

  return deduped
}

function expandDateKeys(startDate, endDate) {
  const start = String(startDate || '').trim()
  const end = String(endDate || '').trim() || start
  if (!start) return []
  const startValue = new Date(start)
  const endValue = new Date(end)
  if (Number.isNaN(startValue.getTime()) || Number.isNaN(endValue.getTime()) || endValue < startValue) {
    return [start]
  }

  const days = []
  const cursor = new Date(startValue)
  let guard = 0
  while (cursor <= endValue && guard < 366) {
    days.push(formatDate(cursor))
    cursor.setDate(cursor.getDate() + 1)
    guard += 1
  }
  return days
}

function buildPendingMarkerTooltip(dateText, pendingItems) {
  const rows = Array.isArray(pendingItems) ? pendingItems : []
  const preview = rows.slice(0, 3).map((item) => `- ${item.event_name || '事件'}`)
  const suffix = rows.length > 3 ? `\n- 另有 ${rows.length - 3} 条` : ''
  return [`${dateText} 未入历事件 ${rows.length} 条`, ...preview].join('\n') + suffix
}

function openPendingDayDialog(dateText, sourceItems) {
  pendingDayDate.value = String(dateText || '')
  pendingDayItems.value = Array.isArray(sourceItems) ? sourceItems : []
  pendingDayVisible.value = true
}

function openPendingDayDetail(item) {
  pendingDayVisible.value = false
  openEventDetail(item)
}

function formatConfidence(value) {
  if (value === null || value === undefined || value === '') return '—'
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return String(value)
  return `${Math.round(numeric * 100)}%`
}

function buildEventTooltip(item) {
  const relatedStocks = Array.isArray(item?.affected_stocks) ? item.affected_stocks : []
  const stockLabels = relatedStocks
    .map((stock) => {
      const stockName = String(stock?.stock_name || '').trim()
      const stockCode = String(stock?.stock_code || '').trim()
      if (stockName && stockCode) return `${stockName}(${stockCode})`
      return stockName || stockCode
    })
    .filter(Boolean)

  const lines = [
    item?.event_name || '事件'
  ]
  if (stockLabels.length) {
    const preview = stockLabels.slice(0, 3).join('、')
    const suffix = stockLabels.length > 3 ? ` 等${stockLabels.length}只` : ''
    lines.push(`${preview}${suffix}`)
  }
  if (item?.override_note) {
    lines.push(`备注：${item.override_note}`)
  }
  return lines.join('\n')
}

function buildQueryParams() {
  return {
    start_date: dateRange.value?.[0] || '',
    end_date: dateRange.value?.[1] || '',
    keyword: filters.keyword || '',
    industry: filters.industry || '',
    status: filters.status || 'all',
    event_type: filters.eventType || 'all',
    override_mode: filters.overrideMode || 'all'
  }
}

async function loadHealth() {
  try {
    const resp = await getCalendarV2Health()
    health.value = resp?.data || {}
  } catch (error) {
    health.value = { status: 'error' }
  }
}

async function loadFilterMeta() {
  try {
    const resp = await getCalendarV2FilterMeta()
    filterMeta.value = resp?.data || filterMeta.value
  } catch (error) {
    ElMessage.error(error?.message || '筛选项加载失败')
  }
}

async function loadEvents() {
  loading.value = true
  try {
    const resp = await listCalendarV2Events(buildQueryParams())
    items.value = resp?.data?.items || []
    stats.value = resp?.data?.stats || {}
  } catch (error) {
    ElMessage.error(error?.message || '可信事件加载失败')
  } finally {
    loading.value = false
  }
}

async function openEventDetail(item) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    const resp = await getCalendarV2EventDetail(item.event_key)
    detailItem.value = resp?.data || item
  } catch (error) {
    detailItem.value = item
    ElMessage.error(error?.message || '事件详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

function openIncludeDialog(item) {
  overrideTargetKey.value = item.event_key
  overrideDateRange.value = [
    item.calendar_date_start || '',
    item.calendar_date_end || item.calendar_date_start || ''
  ].filter(Boolean)
  overrideForm.note = item.override_note || ''
  overrideDialogVisible.value = true
}

async function submitIncludeOverride() {
  if (!overrideTargetKey.value) return
  if (!Array.isArray(overrideDateRange.value) || !overrideDateRange.value[0]) {
    ElMessage.warning('请先选择入历日期')
    return
  }

  overrideSaving.value = true
  try {
    const resp = await saveCalendarV2Override(overrideTargetKey.value, {
      decision: 'include',
      calendar_date_start: overrideDateRange.value[0],
      calendar_date_end: overrideDateRange.value[1] || overrideDateRange.value[0],
      note: overrideForm.note || ''
    })
    detailItem.value = resp?.data || detailItem.value
    overrideDialogVisible.value = false
    ElMessage.success('已加入日历')
    await refreshCalendarData()
  } catch (error) {
    ElMessage.error(error?.message || '加入日历失败')
  } finally {
    overrideSaving.value = false
  }
}

async function excludeFromCalendar(item) {
  try {
    await ElMessageBox.confirm('确认将该事件移出日历吗？它仍会保留在收藏事件链路中。', '移出日历', {
      type: 'warning',
      confirmButtonText: '确认移出',
      cancelButtonText: '取消'
    })
  } catch (error) {
    return
  }

  overrideSaving.value = true
  try {
    const resp = await saveCalendarV2Override(item.event_key, {
      decision: 'exclude',
      note: item.override_note || ''
    })
    detailItem.value = resp?.data || detailItem.value
    ElMessage.success('已移出日历')
    await refreshCalendarData()
  } catch (error) {
    ElMessage.error(error?.message || '移出日历失败')
  } finally {
    overrideSaving.value = false
  }
}

async function clearOverride(item) {
  overrideSaving.value = true
  try {
    const resp = await saveCalendarV2Override(item.event_key, {
      decision: 'clear'
    })
    detailItem.value = resp?.data || detailItem.value
    ElMessage.success('已恢复自动判断')
    await refreshCalendarData()
  } catch (error) {
    ElMessage.error(error?.message || '恢复自动判断失败')
  } finally {
    overrideSaving.value = false
  }
}

function resetFilters() {
  filters.keyword = ''
  filters.industry = ''
  filters.status = 'all'
  filters.eventType = 'all'
  filters.overrideMode = 'all'
  dateRange.value = [formatDate(monthStart), formatDate(monthEnd)]
  loadEvents()
}

async function refreshCalendarData() {
  await Promise.all([loadHealth(), loadEvents()])
}

function syncThemeKey() {
  const nextTheme = document.documentElement.classList.contains('dark') ? 'dark' : 'light'
  if (calendarThemeKey.value !== nextTheme) {
    calendarThemeKey.value = nextTheme
  }
}

onMounted(async () => {
  themeObserver = new MutationObserver(() => {
    syncThemeKey()
  })
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['class']
  })

  await Promise.all([loadHealth(), loadFilterMeta(), loadEvents()])
})

onBeforeUnmount(() => {
  themeObserver?.disconnect()
  themeObserver = null
})

watch(pendingMarkersByDate, async () => {
  await nextTick()
  syncPendingDayMarkers()
})
</script>

<style scoped>
.calendar-v2-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: transparent;
  --fc-page-bg-color: transparent;
  --fc-neutral-bg-color: var(--cv2-calendar-head-bg);
  --fc-border-color: var(--cv2-day-border);
  --fc-list-event-hover-bg-color: var(--cv2-panel-muted-bg);
  --cv2-card-bg: var(--el-bg-color);
  --cv2-panel-bg: var(--el-bg-color-overlay);
  --cv2-panel-muted-bg: var(--el-fill-color-light);
  --cv2-panel-soft-bg: var(--el-fill-color-blank);
  --cv2-border: var(--el-border-color-light);
  --cv2-border-strong: var(--el-border-color);
  --cv2-text-primary: var(--el-text-color-primary);
  --cv2-text-regular: var(--el-text-color-regular);
  --cv2-text-secondary: var(--el-text-color-secondary);
  --cv2-shadow: 0 14px 28px rgba(15, 23, 42, 0.05);
  --cv2-calendar-head-bg: var(--el-fill-color-light);
  --cv2-calendar-btn-bg: var(--el-bg-color);
  --cv2-calendar-btn-hover-bg: var(--el-fill-color-light);
  --cv2-calendar-list-bg: var(--el-fill-color-light);
  --cv2-today-bg: rgba(37, 99, 235, 0.08);
  --cv2-event-dot-ring: rgba(255, 255, 255, 0.74);
  --cv2-accent-soft: rgba(37, 99, 235, 0.08);
  --cv2-warning-soft: rgba(245, 158, 11, 0.12);
  --cv2-success-soft: rgba(16, 185, 129, 0.12);
  --cv2-danger-soft: rgba(239, 68, 68, 0.1);
  --cv2-day-bg: #fcfcfd;
  --cv2-day-border: rgba(148, 163, 184, 0.16);
  --cv2-day-text: #0f172a;
  --cv2-day-subtext: #94a3b8;
  --cv2-day-today-bg: rgba(37, 99, 235, 0.07);
  --cv2-day-today-text: #1d4ed8;
  --cv2-event-fill-trusted: rgba(59, 130, 246, 0.07);
  --cv2-event-text-trusted: #334155;
  --cv2-event-border-trusted: rgba(59, 130, 246, 0.16);
  --cv2-pending-marker-bg: rgba(252, 252, 253, 0.96);
  --cv2-pending-marker-border: rgba(100, 116, 139, 0.28);
  --cv2-pending-marker-hover-border: rgba(37, 99, 235, 0.3);
  --cv2-pending-marker-hover-text: #1d4ed8;
}

.calendar-top-grid {
  align-items: stretch;
}

.calendar-v2-view--dark {
  --cv2-card-bg: var(--el-bg-color);
  --cv2-panel-bg: var(--el-bg-color-overlay);
  --cv2-panel-muted-bg: rgba(30, 41, 59, 0.72);
  --cv2-panel-soft-bg: rgba(15, 23, 42, 0.72);
  --cv2-border: rgba(148, 163, 184, 0.22);
  --cv2-border-strong: rgba(148, 163, 184, 0.32);
  --cv2-shadow: 0 18px 36px rgba(2, 6, 23, 0.24);
  --cv2-calendar-head-bg: rgba(30, 41, 59, 0.72);
  --cv2-calendar-btn-bg: rgba(15, 23, 42, 0.76);
  --cv2-calendar-btn-hover-bg: rgba(37, 99, 235, 0.16);
  --cv2-calendar-list-bg: rgba(15, 23, 42, 0.76);
  --cv2-today-bg: rgba(59, 130, 246, 0.14);
  --cv2-event-dot-ring: rgba(15, 23, 42, 0.72);
  --cv2-accent-soft: rgba(37, 99, 235, 0.14);
  --cv2-warning-soft: rgba(245, 158, 11, 0.16);
  --cv2-success-soft: rgba(16, 185, 129, 0.16);
  --cv2-danger-soft: rgba(239, 68, 68, 0.14);
  --cv2-day-bg: rgba(15, 23, 42, 0.42);
  --cv2-day-border: rgba(148, 163, 184, 0.22);
  --cv2-day-text: rgba(226, 232, 240, 0.94);
  --cv2-day-subtext: rgba(148, 163, 184, 0.88);
  --cv2-day-today-bg: rgba(59, 130, 246, 0.12);
  --cv2-day-today-text: #93c5fd;
  --cv2-event-fill-trusted: rgba(59, 130, 246, 0.12);
  --cv2-event-text-trusted: rgba(226, 232, 240, 0.94);
  --cv2-event-border-trusted: rgba(96, 165, 250, 0.2);
  --cv2-pending-marker-bg: rgba(15, 23, 42, 0.92);
  --cv2-pending-marker-border: rgba(148, 163, 184, 0.26);
  --cv2-pending-marker-hover-border: rgba(96, 165, 250, 0.42);
  --cv2-pending-marker-hover-text: #93c5fd;
}

.calendar-hero,
.calendar-main-card {
  border: 1px solid var(--cv2-border);
  border-radius: 20px;
  background: var(--cv2-panel-bg);
  box-shadow: var(--cv2-shadow);
}

.hero-layout {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
}

.calendar-hero {
  height: 100%;
}

.calendar-hero :deep(.el-card__body) {
  height: 100%;
}

.hero-copy {
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: none;
}

.hero-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 21px;
  font-weight: 900;
  line-height: 1.2;
  color: var(--cv2-text-primary);
}

.hero-title-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.12);
  flex: none;
}

.hero-subtitle {
  max-width: 760px;
  font-size: 13px;
  color: var(--cv2-text-regular);
  line-height: 1.6;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.summary-chip {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--cv2-border);
  background: var(--cv2-panel-soft-bg);
}

.summary-chip--accent {
  background: var(--cv2-accent-soft);
  border-color: rgba(37, 99, 235, 0.2);
}

.summary-label {
  font-size: 12px;
  color: var(--cv2-text-secondary);
}

.summary-value {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 800;
  color: var(--cv2-text-primary);
}

.hero-source-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid var(--cv2-border);
  background: var(--cv2-panel-soft-bg);
}

.hero-source-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.hero-source-subtitle {
  font-size: 12px;
  color: var(--cv2-text-secondary);
  line-height: 1.5;
}

.hero-source-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.filter-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border-radius: 18px;
  border: 1px solid var(--cv2-border);
  background: var(--cv2-panel-soft-bg);
  flex: 1 1 auto;
  min-height: 0;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-content: start;
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-field--wide {
  grid-column: 1 / -1;
}

.filter-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--cv2-text-secondary);
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.field-control {
  width: 100%;
}

.filter-panel :deep(.el-input__wrapper),
.filter-panel :deep(.el-select__wrapper),
.filter-panel :deep(.el-range-editor.el-input__wrapper) {
  min-height: 40px;
  border-radius: 14px;
  background: var(--cv2-card-bg);
  box-shadow: 0 0 0 1px var(--cv2-border) inset;
}

.calendar-main-grid {
  align-items: start;
}

.filter-panel :deep(.el-input__wrapper.is-focus),
.filter-panel :deep(.el-select__wrapper.is-focused),
.filter-panel :deep(.el-range-editor.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1px rgba(37, 99, 235, 0.4) inset,
    0 10px 24px rgba(37, 99, 235, 0.1);
}

.calendar-main-grid {
  align-items: start;
}

.calendar-main-card :deep(.el-card__body) {
  padding: 18px 18px 20px;
}

.calendar-main-card--primary {
  height: 100%;
}

.calendar-main-card--primary :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-header-copy {
  min-width: 0;
}

.card-title {
  font-size: 16px;
  font-weight: 800;
  color: var(--cv2-text-primary);
}

.card-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: var(--cv2-text-secondary);
}

.report-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.backlog-name,
.report-title,
.detail-title {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  min-width: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--cv2-text-primary);
  line-height: 1.35;
  word-break: break-word;
}

.report-meta,
.source-status-line {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--cv2-text-secondary);
  font-size: 12px;
}

.pending-day-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.pending-day-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid var(--cv2-border);
  border-radius: 12px;
  background: var(--cv2-panel-soft-bg);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s ease, background-color 0.16s ease;
}

.pending-day-item:hover {
  border-color: rgba(37, 99, 235, 0.24);
  background: var(--cv2-card-bg);
}

.pending-day-item--pending {
  border-left: 3px solid rgba(100, 116, 139, 0.45);
}

.pending-day-item--caution {
  border-left: 3px solid rgba(217, 119, 6, 0.58);
}

.pending-day-item--manual-include {
  border-left: 3px solid rgba(15, 159, 120, 0.62);
}

.pending-day-item--manual-exclude {
  border-left: 3px solid rgba(239, 68, 68, 0.52);
}

.pending-day-name {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.4;
  color: var(--cv2-text-primary);
  word-break: break-word;
}

.pending-day-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--cv2-text-secondary);
}

.report-meta--stack {
  flex-direction: column;
  gap: 4px;
}

.report-meta-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--cv2-text-secondary);
}

.report-link {
  color: var(--el-color-primary);
  text-decoration: none;
  word-break: break-all;
}

.report-link:hover {
  text-decoration: underline;
}

.source-group + .source-group {
  margin-top: 12px;
}

.source-group-title {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 700;
  color: var(--cv2-text-secondary);
}

.detail-paragraph,
.report-summary {
  margin-top: 6px;
  color: var(--cv2-text-regular);
  line-height: 1.65;
}

.report-summary {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.report-summary {
  -webkit-line-clamp: 3;
}

.source-status-line {
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--cv2-panel-muted-bg);
  border: 1px solid var(--cv2-border);
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.detail-tags,
.chip-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.detail-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.override-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid var(--cv2-border);
  background: var(--cv2-panel-muted-bg);
}

.override-toolbar-copy {
  min-width: 0;
}

.override-toolbar-note {
  margin-top: 6px;
  color: var(--cv2-text-secondary);
  line-height: 1.7;
}

.override-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.detail-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-block-title {
  font-size: 14px;
  font-weight: 800;
  color: var(--cv2-text-primary);
}

.report-card {
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--cv2-panel-muted-bg);
  border: 1px solid var(--cv2-border);
}

:deep(.fc) {
  --fc-border-color: var(--cv2-border-strong);
  --fc-page-bg-color: transparent;
  --fc-neutral-bg-color: var(--cv2-calendar-head-bg);
  --fc-list-event-hover-bg-color: rgba(37, 99, 235, 0.08);
  --fc-today-bg-color: var(--cv2-today-bg);
}

:deep(.fc .fc-toolbar-title) {
  font-size: 18px;
  font-weight: 900;
  color: var(--cv2-text-primary);
}

:deep(.fc .fc-button-primary) {
  border-color: rgba(37, 99, 235, 0.18);
  background: var(--cv2-calendar-btn-bg);
  color: var(--el-color-primary);
  box-shadow: none;
}

:deep(.fc .fc-button-primary:hover),
:deep(.fc .fc-button-primary:focus) {
  border-color: rgba(37, 99, 235, 0.34);
  background: var(--cv2-calendar-btn-hover-bg);
  color: #1d4ed8;
}

:deep(.fc .fc-button-primary.fc-button-active) {
  border-color: rgba(37, 99, 235, 0.5);
  background: rgba(37, 99, 235, 0.12);
  color: #1d4ed8;
}

:deep(.fc-theme-standard td),
:deep(.fc-theme-standard th) {
  border-color: var(--fc-border-color);
}

:deep(.fc .fc-scrollgrid),
:deep(.fc .fc-scrollgrid-section > td),
:deep(.fc .fc-view-harness),
:deep(.fc .fc-daygrid-body),
:deep(.fc .fc-daygrid-body table) {
  background: transparent;
}

:deep(.fc .fc-col-header-cell),
:deep(.fc .fc-list-day-cushion) {
  background: var(--cv2-calendar-head-bg);
}

:deep(.fc .fc-col-header-cell-cushion),
:deep(.fc .fc-daygrid-day-number),
:deep(.fc .fc-list-event-title),
:deep(.fc .fc-list-event-time) {
  color: var(--cv2-text-primary);
}

:deep(.fc .fc-daygrid-day.fc-day-today) {
  background: transparent;
}

:deep(.fc .fc-daygrid-day) {
  background: transparent;
}

:deep(.fc .fc-daygrid-day-frame) {
  min-height: 140px;
  position: relative;
  margin: 2px;
  border-radius: 10px;
  background: var(--cv2-day-bg);
  box-shadow: inset 0 0 0 1px var(--cv2-day-border);
  overflow: hidden;
}

:deep(.fc .fc-daygrid-day.fc-day-today .fc-daygrid-day-frame) {
  background: var(--cv2-day-today-bg);
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.18);
}

.calendar-v2-view--dark :deep(.fc .fc-daygrid-day-frame) {
  background: rgba(15, 23, 42, 0.72);
  box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.22);
}

.calendar-v2-view--dark :deep(.fc .fc-daygrid-day.fc-day-today .fc-daygrid-day-frame) {
  background: rgba(59, 130, 246, 0.12);
  box-shadow: inset 0 0 0 1px rgba(96, 165, 250, 0.28);
}

:deep(.fc .fc-daygrid-day-top) {
  padding: 6px 34px 0 8px;
}

:deep(.fc .fc-daygrid-day-events) {
  padding: 2px 6px 8px;
}

:deep(.fc .fc-daygrid-event-harness) {
  margin-top: 4px;
}

:deep(.fc .fc-daygrid-event) {
  display: block;
  padding: 3px 8px;
  border-radius: 8px;
  background: var(--cv2-event-fill, rgba(248, 250, 252, 0.96));
  border: 1px solid var(--cv2-event-border, rgba(148, 163, 184, 0.18));
  box-shadow: none;
}

:deep(.fc .fc-daygrid-event .fc-event-main) {
  color: var(--cv2-event-text, #334155);
}

:deep(.fc .fc-daygrid-event .fc-event-title) {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

:deep(.fc .fc-daygrid-more-link) {
  margin-top: 4px;
  font-size: 11px;
  color: var(--cv2-text-secondary);
}

:deep(.fc .fc-list-day-cushion) {
  background: var(--cv2-calendar-list-bg);
}

:deep(.cv2-daycell) {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
}

:deep(.cv2-solar) {
  font-weight: 800;
  color: var(--cv2-day-text);
}

:deep(.fc .fc-daygrid-day.fc-day-today .cv2-solar) {
  color: var(--cv2-day-today-text);
}

:deep(.cv2-lunar) {
  font-size: 11px;
  color: var(--cv2-day-subtext);
  margin-left: auto;
  white-space: nowrap;
}

:deep(.cv2-lunar--holiday) {
  color: #dc2626;
}

:deep(.cv2-pending-day-marker) {
  position: absolute;
  right: 8px;
  top: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border-radius: 999px;
  border: 1px solid var(--cv2-pending-marker-border);
  background: var(--cv2-pending-marker-bg);
  color: var(--cv2-text-secondary);
  z-index: 8;
  pointer-events: auto;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}

:deep(.cv2-pending-day-marker:hover) {
  border-color: var(--cv2-pending-marker-hover-border);
  color: var(--cv2-pending-marker-hover-text);
}

:deep(.cv2-pending-day-marker__clock) {
  position: relative;
  width: 11px;
  height: 11px;
  border: 1.5px solid currentColor;
  border-radius: 999px;
  box-sizing: border-box;
}

:deep(.cv2-pending-day-marker__clock::before) {
  content: '';
  position: absolute;
  top: 1px;
  left: 50%;
  width: 1.5px;
  height: 3.5px;
  background: currentColor;
  border-radius: 999px;
  transform: translateX(-50%);
  transform-origin: center bottom;
}

:deep(.cv2-pending-day-marker__clock-hand) {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 1.5px;
  height: 3px;
  background: currentColor;
  border-radius: 999px;
  transform: translate(-10%, -85%) rotate(50deg);
  transform-origin: center bottom;
}

:deep(.cv2-pending-day-marker__count) {
  position: absolute;
  top: -5px;
  right: -6px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: var(--el-color-warning);
  color: #fff;
  font-size: 10px;
  font-weight: 800;
  line-height: 16px;
  text-align: center;
}

:deep(.fc .fc-list-event-title) {
  font-weight: 700;
}

@media (max-width: 1280px) {
  .hero-stats {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 860px) {
  .hero-stats,
  .hero-source-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .pending-day-list {
    grid-template-columns: 1fr;
  }

  .card-header,
  .detail-header,
  .override-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .calendar-main-card :deep(.el-card__body) {
    padding: 14px;
  }
}
</style>
