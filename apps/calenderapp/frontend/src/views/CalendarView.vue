<template>
  <el-row :gutter="16">
    <el-col :xs="24" :lg="7">
      <el-card shadow="never" class="card">
        <template #header>
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px">
            <div style="font-weight: 700">筛选</div>
            <div style="display: flex; align-items: center; gap: 8px">
              <el-button size="small" @click="resetFilters">重置</el-button>
              <el-button size="small" type="primary" :loading="loading" @click="reload">应用</el-button>
            </div>
          </div>
        </template>

        <el-form label-width="78px">
          <el-form-item label="关键词">
            <el-input v-model.trim="filters.q" clearable placeholder="标题 / 描述" @input="onFilterInput" />
          </el-form-item>
          <el-form-item label="重要性">
            <el-select v-model="filters.importance_min" clearable placeholder="全部" style="width: 100%" @change="onFilterChange">
              <el-option v-for="n in [5, 4, 3, 2, 1]" :key="n" :label="`≥ ${n}`" :value="n" />
            </el-select>
          </el-form-item>
          <el-form-item label="类型">
            <el-select
              v-model="filters.event_type"
              clearable
              filterable
              placeholder="全部"
              style="width: 100%"
              @change="onFilterChange"
            >
              <el-option v-for="opt in typeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="股票">
            <el-input v-model.trim="filters.stock_code" clearable placeholder="代码（如 600519）" @input="onFilterInput" />
          </el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never" class="card" style="margin-top: 12px">
        <template #header>
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px">
            <div style="font-weight: 700">即将到期</div>
            <el-button size="small" :loading="upcomingLoading" @click="loadUpcoming">刷新</el-button>
          </div>
        </template>

        <el-empty v-if="!upcomingLoading && upcoming.length === 0" description="未来 7 天暂无事件" />
        <el-skeleton v-else-if="upcomingLoading" :rows="5" animated />
        <div v-else style="display: flex; flex-direction: column; gap: 10px">
          <div
            v-for="ev in upcoming"
            :key="ev.id"
            style="display: flex; flex-direction: column; gap: 4px; padding: 10px; border-radius: 10px; background: rgba(15, 23, 42, 0.03)"
          >
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px">
              <div style="font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
                {{ ev.title }}
              </div>
              <el-tag :type="importanceTagType(ev.importance)">★ {{ ev.importance }}</el-tag>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px">
              <div style="color: #64748b; font-size: 12px">{{ ev.event_date }}</div>
              <el-button link type="primary" @click="jumpToDate(ev.event_date)">定位</el-button>
            </div>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="card" style="margin-top: 12px">
        <template #header>
          <div style="font-weight: 700">当前区间统计</div>
        </template>
        <el-skeleton v-if="statsLoading" :rows="3" animated />
        <el-empty v-else-if="!stats" description="暂无统计数据" />
        <div v-else style="display: flex; flex-direction: column; gap: 10px">
          <div style="display: flex; align-items: center; justify-content: space-between">
            <div style="color: #64748b">事件总数</div>
            <div style="font-weight: 800">{{ stats.total || 0 }}</div>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between">
            <div style="color: #64748b">高重要性(≥4)</div>
            <div style="font-weight: 800">{{ highImportanceCount }}</div>
          </div>
        </div>
      </el-card>
    </el-col>

    <el-col :xs="24" :lg="17">
      <el-card shadow="never" class="card">
        <template #header>
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap">
            <div style="font-weight: 800">股票事件日历</div>
            <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
              <el-button type="primary" @click="openCreateDialog()">
                <el-icon><Plus /></el-icon>
                添加事件
              </el-button>
              <el-button @click="downloadEventsTemplate">下载模板</el-button>
              <el-upload
                :show-file-list="false"
                :http-request="uploadEventsCsv"
                :before-upload="beforeCsvUpload"
                accept=".csv,text/csv"
              >
                <el-button :loading="importing">上传 CSV</el-button>
              </el-upload>
              <el-button :loading="loading" @click="reload">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </div>
        </template>

        <FullCalendar ref="calendarRef" :options="calendarOptions" />
      </el-card>
    </el-col>
  </el-row>

  <el-drawer v-model="drawerVisible" size="420px" :with-header="false">
    <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px">
      <div style="display: flex; flex-direction: column; gap: 2px">
        <div style="font-weight: 900; font-size: 16px">{{ selectedDate || '-' }}</div>
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
          <div style="color: #64748b; font-size: 12px">
            {{
              selectedDateMeta
                ? selectedDateMeta.holiday.type === 'rest'
                  ? `${selectedDateMeta.holiday.name} · 休`
                  : selectedDateMeta.holiday.type === 'work'
                    ? `${selectedDateMeta.lunarText} · 班`
                    : selectedDateMeta.lunarText
                : '当日事件'
            }}
          </div>
          <el-tag v-if="selectedDateMeta && selectedDateMeta.holiday.type === 'rest'" type="danger" size="small">休</el-tag>
          <el-tag v-else-if="selectedDateMeta && selectedDateMeta.holiday.type === 'work'" type="warning" size="small">班</el-tag>
        </div>
      </div>
      <el-button type="primary" size="small" @click="openCreateDialog(selectedDate)">
        <el-icon><Plus /></el-icon>
        添加
      </el-button>
    </div>

    <el-empty v-if="selectedDateEvents.length === 0" description="暂无事件" />
    <div v-else style="display: flex; flex-direction: column; gap: 10px">
      <el-card v-for="ev in selectedDateEvents" :key="ev.id" shadow="never" class="card">
        <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 10px">
          <div style="flex: 1; min-width: 0">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px">
              <el-tag :type="importanceTagType(ev.importance)">★ {{ ev.importance }}</el-tag>
              <el-tag v-if="ev.event_type" type="info">{{ eventTypeLabel(ev.event_type) }}</el-tag>
            </div>
            <div style="font-weight: 800; line-height: 20px">{{ ev.title }}</div>
            <div v-if="ev.stock_list && ev.stock_list.length" style="margin-top: 6px; color: #475569; font-size: 12px">
              {{ ev.stock_list.join(', ') }}
            </div>
            <div v-if="ev.description" style="margin-top: 8px; color: #64748b; font-size: 12px; line-height: 18px">
              {{ ev.description }}
            </div>
          </div>

          <div style="display: flex; flex-direction: column; gap: 8px">
            <el-button size="small" @click="openEditDialog(ev)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="onDelete(ev)">删除</el-button>
          </div>
        </div>
      </el-card>
    </div>
  </el-drawer>

  <el-dialog v-model="dialogVisible" :title="dialogTitle" width="780px">
    <EventForm :model-value="editingEvent" :event-types="eventTypes" @submit="onSubmit" @cancel="dialogVisible = false" />
  </el-dialog>

  <el-dialog v-model="importDialogVisible" title="导入结果" width="720px">
    <el-skeleton v-if="importing" :rows="6" animated />
    <div v-else-if="importResult" style="display: flex; flex-direction: column; gap: 12px">
      <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
        <el-tag type="success">新增 {{ importResult.created || 0 }}</el-tag>
        <el-tag type="warning">更新 {{ importResult.updated || 0 }}</el-tag>
        <el-tag :type="importResult.failed ? 'danger' : 'info'">失败 {{ importResult.failed || 0 }}</el-tag>
        <el-tag v-if="importResult.warnings" type="info">告警 {{ importResult.warnings || 0 }}</el-tag>
        <div style="color: #64748b; font-size: 12px">总行数 {{ importResult.total || 0 }}</div>
      </div>

      <div v-if="importResult.error_csv_base64" style="display: flex; justify-content: flex-end">
        <el-button type="primary" plain @click="downloadImportErrors">下载错误日志</el-button>
      </div>

      <el-alert
        v-if="importResult.failed"
        type="error"
        show-icon
        :closable="false"
        title="部分行导入失败（仅展示前 200 条）"
      />
      <el-table v-if="importResult.error_rows && importResult.error_rows.length" :data="importResult.error_rows" size="small">
        <el-table-column prop="row" label="行号" width="80" />
        <el-table-column prop="error" label="错误" min-width="260" />
        <el-table-column prop="event_date" label="日期" width="120" />
        <el-table-column prop="title" label="标题" min-width="200" />
      </el-table>

      <el-alert
        v-if="importResult.warning_rows && importResult.warning_rows.length"
        type="warning"
        show-icon
        :closable="false"
        title="存在告警（仅展示前 200 条）"
      />
      <el-table v-if="importResult.warning_rows && importResult.warning_rows.length" :data="importResult.warning_rows" size="small">
        <el-table-column prop="row" label="行号" width="80" />
        <el-table-column prop="warning" label="告警" min-width="320" />
        <el-table-column prop="event_date" label="日期" width="120" />
        <el-table-column prop="title" label="标题" min-width="200" />
      </el-table>
    </div>
    <template #footer>
      <el-button @click="importDialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/daygrid'
import interactionPlugin from '@fullcalendar/interaction'
import listPlugin from '@fullcalendar/list'
import timeGridPlugin from '@fullcalendar/timegrid'
import zhCnLocale from '@fullcalendar/core/locales/zh-cn'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import EventForm from '../components/EventForm.vue'
import { createEvent, deleteEvent, importEventsCsv, listEvents, statisticsEvents, upcomingEvents, updateEvent } from '../api/events'
import { getLunarDayText } from '../utils/lunar'
import { getHolidayStatus } from '../utils/holiday'

const calendarRef = ref()

const loading = ref(false)
const items = ref([])
const eventTypes = ref({})

const filters = reactive({
  q: '',
  importance_min: null,
  event_type: '',
  stock_code: ''
})

const visibleRange = reactive({
  start_date: null,
  end_date: null
})

const drawerVisible = ref(false)
const selectedDate = ref(null)

const selectedDateMeta = computed(() => {
  if (!selectedDate.value) return null
  const d = new Date(`${selectedDate.value}T00:00:00`)
  const lunarText = getLunarDayText(d)
  const holiday = getHolidayStatus(d)
  return { lunarText, holiday }
})

const dialogVisible = ref(false)
const dialogTitle = ref('添加事件')
const editingEvent = ref(null)

const importing = ref(false)
const importDialogVisible = ref(false)
const importResult = ref(null)

const upcomingLoading = ref(false)
const upcoming = ref([])

const statsLoading = ref(false)
const stats = ref(null)

const typeOptions = computed(() => {
  const map = eventTypes.value || {}
  return Object.keys(map).map((k) => ({ value: k, label: map[k] }))
})

const highImportanceCount = computed(() => {
  const by = stats.value?.by_importance || {}
  return Number(by['5'] || 0) + Number(by['4'] || 0)
})

const selectedDateEvents = computed(() => {
  if (!selectedDate.value) return []
  const d = selectedDate.value
  return items.value
    .filter((ev) => ev.event_date === d)
    .sort((a, b) => (Number(b.importance || 0) - Number(a.importance || 0)) || String(a.title || '').localeCompare(String(b.title || '')))
})

function eventTypeLabel(code) {
  if (!code) return ''
  return eventTypes.value?.[code] || code
}

function importanceColor(importance) {
  const v = Number(importance || 1)
  if (v >= 5) return '#ef4444'
  if (v === 4) return '#f59e0b'
  if (v === 3) return '#3b82f6'
  if (v === 2) return '#10b981'
  return '#64748b'
}

function importanceTagType(importance) {
  const v = Number(importance || 1)
  if (v >= 5) return 'danger'
  if (v === 4) return 'warning'
  if (v === 3) return 'primary'
  if (v === 2) return 'success'
  return 'info'
}

const calendarEvents = computed(() => {
  return items.value.map((ev) => {
    const stock = Array.isArray(ev.stock_list) && ev.stock_list.length ? ` ${ev.stock_list[0]}` : ''
    const title = `${ev.title}${stock}`.trim()
    const color = importanceColor(ev.importance)
    return {
      id: String(ev.id),
      title,
      start: ev.event_date,
      allDay: true,
      importance: Number(ev.importance || 0),
      backgroundColor: color,
      borderColor: color,
      textColor: '#ffffff',
      extendedProps: ev
    }
  })
})

function eventContent(arg) {
  if (arg.view?.type !== 'dayGridMonth') return undefined

  const wrap = document.createElement('div')
  wrap.className = 'sc-evt'

  const dot = document.createElement('span')
  dot.className = 'sc-evt-dot'
  dot.style.backgroundColor = arg.event.backgroundColor || '#64748b'

  const title = document.createElement('span')
  title.className = 'sc-evt-title'
  title.textContent = arg.event.title || ''

  wrap.appendChild(dot)
  wrap.appendChild(title)
  return { domNodes: [wrap] }
}

function dayCellContent(arg) {
  if (arg.view?.type !== 'dayGridMonth') return undefined
  const solarText = String(arg.dayNumberText || '').replace(/日$/, '')
  const lunarText = getLunarDayText(arg.date)
  const holiday = getHolidayStatus(arg.date)

  const wrap = document.createElement('div')
  wrap.className = 'sc-daycell'

  const solarEl = document.createElement('div')
  solarEl.className = 'sc-solar'
  solarEl.textContent = solarText

  const lunarEl = document.createElement('div')
  lunarEl.className = holiday.type === 'rest' ? 'sc-lunar sc-holiday' : 'sc-lunar'

  if (holiday.type === 'rest') {
    lunarEl.textContent = `${holiday.name} · 休`
  } else if (holiday.type === 'work') {
    lunarEl.textContent = `${lunarText} · 班`
  } else {
    lunarEl.textContent = lunarText
  }

  wrap.appendChild(solarEl)
  wrap.appendChild(lunarEl)
  return { domNodes: [wrap] }
}

const calendarOptions = computed(() => ({
  plugins: [dayGridPlugin, interactionPlugin, listPlugin, timeGridPlugin],
  initialView: 'dayGridMonth',
  locale: zhCnLocale,
  height: 'auto',
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
  },
  buttonText: {
    today: '今天',
    month: '月',
    week: '周',
    day: '日',
    list: '列表'
  },
  events: calendarEvents.value,
  dayCellContent: (arg) => dayCellContent(arg),
  eventContent: (arg) => eventContent(arg),
  displayEventTime: false,
  eventOrder: '-importance,title',
  eventOrderStrict: true,
  moreLinkText: (num) => `+${num}`,
  datesSet: (arg) => onDatesSet(arg),
  dateClick: (arg) => onDateClick(arg),
  eventClick: (arg) => onEventClick(arg),
  dayMaxEventRows: 3
}))

function resetFilters() {
  filters.q = ''
  filters.importance_min = null
  filters.event_type = ''
  filters.stock_code = ''
}

let filterTimer = null
function onFilterInput() {
  if (filterTimer) clearTimeout(filterTimer)
  filterTimer = setTimeout(() => reload(), 350)
}

function onFilterChange() {
  reload()
}

function apiBase() {
  return import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000'
}

function downloadEventsTemplate() {
  window.open(`${apiBase()}/api/events/template.csv`, '_blank')
}

function beforeCsvUpload(file) {
  const name = String(file?.name || '').toLowerCase()
  if (!name.endsWith('.csv')) {
    ElMessage.error('仅支持 CSV 文件')
    return false
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('文件过大（最大 5MB）')
    return false
  }
  return true
}

function downloadBase64Csv(base64, filename) {
  const bin = atob(base64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  const blob = new Blob([bytes], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'import_errors.csv'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function downloadImportErrors() {
  if (!importResult.value?.error_csv_base64) return
  downloadBase64Csv(importResult.value.error_csv_base64, importResult.value.error_csv_filename)
}

async function uploadEventsCsv(options) {
  importing.value = true
  importDialogVisible.value = true
  importResult.value = null
  try {
    const resp = await importEventsCsv(options.file)
    importResult.value = resp?.data || null
    ElMessage.success('导入完成')
    await reload()
    options?.onSuccess?.(resp)
  } catch (e) {
    ElMessage.error(e?.message || '导入失败')
    options?.onError?.(e)
  } finally {
    importing.value = false
  }
}

async function reload() {
  if (!visibleRange.start_date || !visibleRange.end_date) return
  loading.value = true
  try {
    const params = {
      page: 1,
      page_size: 200,
      start_date: visibleRange.start_date,
      end_date: visibleRange.end_date
    }
    if (filters.q) params.q = filters.q
    if (filters.importance_min) params.importance_min = filters.importance_min
    if (filters.event_type) params.event_type = filters.event_type
    if (filters.stock_code) params.stock_code = filters.stock_code

    const resp = await listEvents(params)
    items.value = resp?.data?.items || []
    eventTypes.value = resp?.data?.event_types || {}
    await loadStatistics()
  } catch (e) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadUpcoming() {
  upcomingLoading.value = true
  try {
    const resp = await upcomingEvents({ days: 7, importance_min: 3 })
    upcoming.value = resp?.data || []
  } catch (e) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    upcomingLoading.value = false
  }
}

async function loadStatistics() {
  if (!visibleRange.start_date || !visibleRange.end_date) {
    stats.value = null
    return
  }
  statsLoading.value = true
  try {
    const resp = await statisticsEvents({ start_date: visibleRange.start_date, end_date: visibleRange.end_date })
    stats.value = resp?.data || null
  } catch (e) {
    stats.value = null
  } finally {
    statsLoading.value = false
  }
}

function openCreateDialog(dateStr = null) {
  dialogTitle.value = '添加事件'
  editingEvent.value = {
    event_date: dateStr || new Date().toISOString().slice(0, 10),
    title: '',
    importance: 3,
    event_type: '',
    source: '',
    description: '',
    stock_list: []
  }
  dialogVisible.value = true
}

function openEditDialog(ev) {
  dialogTitle.value = '编辑事件'
  editingEvent.value = { ...ev }
  dialogVisible.value = true
}

async function onSubmit(payload) {
  try {
    if (editingEvent.value && editingEvent.value.id) {
      await updateEvent(editingEvent.value.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createEvent(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await reload()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  }
}

async function onDelete(ev) {
  try {
    await ElMessageBox.confirm(`确定删除事件：${ev.title} 吗？`, '删除确认', { type: 'warning' })
    await deleteEvent(ev.id)
    ElMessage.success('删除成功')
    await reload()
  } catch (e) {
    if (e === 'cancel') return
    ElMessage.error(e?.message || '删除失败')
  }
}

function onDatesSet(arg) {
  visibleRange.start_date = String(arg.startStr || '').slice(0, 10)
  const end = new Date(arg.end)
  end.setDate(end.getDate() - 1)
  visibleRange.end_date = end.toISOString().slice(0, 10)
  reload()
}

function onDateClick(arg) {
  selectedDate.value = String(arg.dateStr || '').slice(0, 10)
  drawerVisible.value = true
}

function onEventClick(arg) {
  const ev = arg?.event?.extendedProps
  if (!ev) return
  selectedDate.value = ev.event_date
  drawerVisible.value = true
}

function jumpToDate(dateStr) {
  const api = calendarRef.value?.getApi?.()
  if (!api) return
  api.gotoDate(dateStr)
  selectedDate.value = dateStr
  drawerVisible.value = true
}

onMounted(async () => {
  await loadUpcoming()
})
</script>
