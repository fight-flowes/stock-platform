<template>
  <div class="limit-up-page">
    <!-- 顶部日期选择（固定） -->
    <div class="sticky-header">
      <LimitUpHeader
        :selected-date="selectedDate"
        :quick-dates="quickDates"
        :syncing="syncing"
        @update:selected-date="selectedDate = $event"
        @date-change="onQuickDateChange"
        @create="openCreateDialog"
        @sync="syncFromTushareNow"
        @sync-full="syncFullFromTushareNow"
        @sync-batch="openBatchSyncDialog"
        @identify-dragon="identifyDragonNow"
        @download="downloadLimitUpData"
      />
    </div>

    <!-- 主内容区域 -->
    <div class="main-content">
      <!-- Tab 切换 -->
      <el-tabs v-model="activeTab" class="main-tabs">
      <!-- 涨停概览 -->
      <el-tab-pane label="涨停概览" name="overview">
        <LimitUpStats :stats="stats" :rows="rows" />
        
        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :xs="24" :lg="12">
            <ConsecutiveBoard :trade-date="selectedDate" @select="onStockSelect" />
          </el-col>
          <el-col :xs="24" :lg="12">
            <SectorHeat
              :industry-data="stats.by_industry || {}"
              :concept-data="conceptData"
              :loading="statsLoading"
              @select="onSectorSelect"
            />
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 涨停列表 -->
      <el-tab-pane label="涨停列表" name="list">
        <el-row :gutter="16">
          <el-col :xs="24" :lg="6">
            <LimitUpFilters :filters="filters" @update:filters="onFilterChange" />
            <FundFlow 
              :start-date="selectedDate" 
              :end-date="selectedDate" 
              @select="onStockSelect" 
            />
          </el-col>
          <el-col :xs="24" :lg="18">
            <LimitUpTable
              :rows="rows"
              :loading="loading"
              :total="total"
              :page="page"
              :page-size-prop="pageSize"
              :selected-count="selectedRows.length"
              :batch-updating="batchUpdating"
              @select="onStockSelect"
              @refresh="reload"
              @page-change="onPageChange"
              @selection-change="onSelectionChange"
              @batch-update="openBatchUpdateDialog"
              @stockkb="openStockkbDialog"
            />
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 资金流向 -->
      <el-tab-pane label="资金流向" name="fund">
        <el-row :gutter="16">
          <el-col :xs="24" :lg="12">
            <el-card shadow="never" class="card">
              <template #header>
                <div style="font-weight: 700; color: #3b82f6">🏦 机构净买入 TOP20</div>
              </template>
              <el-table :data="fundData.institution_top" v-loading="fundLoading" max-height="500">
                <el-table-column type="index" label="#" width="50" />
                <el-table-column prop="stock_name" label="股票" min-width="100" />
                <el-table-column label="连板" width="70">
                  <template #default="{ row }">
                    <el-tag :type="consecutiveTagType(row.consecutive_days)" size="small">
                      {{ row.consecutive_days }}板
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="机构净买" width="100">
                  <template #default="{ row }">
                    <span style="color: #ef4444; font-weight: 600">
                      {{ formatAmount(row.institution_net_buy) }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="industry" label="行业" width="90" />
              </el-table>
            </el-card>
          </el-col>
          <el-col :xs="24" :lg="12">
            <el-card shadow="never" class="card">
              <template #header>
                <div style="font-weight: 700; color: #10b981">🎯 游资净买入 TOP20</div>
              </template>
              <el-table :data="fundData.hot_money_top" v-loading="fundLoading" max-height="500">
                <el-table-column type="index" label="#" width="50" />
                <el-table-column prop="stock_name" label="股票" min-width="100" />
                <el-table-column label="连板" width="70">
                  <template #default="{ row }">
                    <el-tag :type="consecutiveTagType(row.consecutive_days)" size="small">
                      {{ row.consecutive_days }}板
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="游资净买" width="100">
                  <template #default="{ row }">
                    <span style="color: #ef4444; font-weight: 600">
                      {{ formatAmount(row.hot_money_net_buy) }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="industry" label="行业" width="90" />
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
    </div>

    <!-- 详情弹窗 -->
    <el-drawer v-model="detailVisible" size="480px" :with-header="false">
      <LimitUpDetail 
        v-if="selectedStock" 
        :item="selectedStock" 
        @edit="openEditDialog" 
        @close="detailVisible = false" 
      />
    </el-drawer>

    <!-- 分析报告弹窗 -->
    <el-dialog
      v-model="analysisVisible"
      width="min(1100px, 92vw)"
      top="4vh"
      destroy-on-close
      class="analysis-dialog"
    >
      <div v-if="analysisLoading" class="analysis-loading">
        <el-icon class="is-loading" :size="32" style="color: #409eff"><Loading /></el-icon>
        <div style="margin-top: 16px">正在加载报告...</div>
      </div>

      <div v-else-if="analysisData?.full_report" class="analysis-report markdown-body" v-html="renderedAnalysisReport"></div>

      <el-empty v-else description="暂无 Markdown 报告" />
    </el-dialog>

    <StockkbEventDialog
      v-model="stockkbVisible"
      :stock="stockkbStock"
      :report-date="selectedDate"
      @view-analysis="openAnalysisFromStockkb"
    />

    <!-- 表单弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <LimitUpForm :model-value="editingItem" @submit="onSubmit" @cancel="dialogVisible = false" />
    </el-dialog>

    <!-- 批量同步弹窗 -->
    <el-dialog v-model="batchSyncDialogVisible" title="批量同步" width="500px">
      <el-form label-width="100px">
        <el-form-item label="开始日期">
          <el-date-picker v-model="batchSyncStart" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="batchSyncEnd" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchSyncDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="syncing" @click="syncBatchNow">开始同步</el-button>
      </template>
    </el-dialog>

    <!-- 导入结果弹窗 -->
    <el-dialog v-model="importResultVisible" title="导入结果" width="600px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="总数">{{ importResult.total }}</el-descriptions-item>
        <el-descriptions-item label="成功">{{ importResult.created }}</el-descriptions-item>
        <el-descriptions-item label="更新">{{ importResult.updated }}</el-descriptions-item>
        <el-descriptions-item label="失败">{{ importResult.failed }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="importResult.errors?.length" style="margin-top: 16px">
        <el-alert type="error" :closable="false">
          <template #title>错误详情（前10条）</template>
          <div v-for="(e, i) in importResult.errors.slice(0, 10)" :key="i" style="font-size: 12px">
            行 {{ e.row }}: {{ e.error }} ({{ e.stock_code }})
          </div>
        </el-alert>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import LimitUpHeader from '../components/LimitUpHeader.vue'
import LimitUpStats from '../components/LimitUpStats.vue'
import LimitUpFilters from '../components/LimitUpFilters.vue'
import LimitUpTable from '../components/LimitUpTable.vue'
import ConsecutiveBoard from '../components/ConsecutiveBoard.vue'
import SectorHeat from '../components/SectorHeat.vue'
import FundFlow from '../components/FundFlow.vue'
import LimitUpForm from '../components/LimitUpForm.vue'
import LimitUpDetail from '../components/LimitUpDetail.vue'
import StockkbEventDialog from '../components/StockkbEventDialog.vue'
import { renderMarkdown } from '../utils/markdown'
import {
  batchUpdateLimitUps,
  createLimitUp,
  deleteLimitUp,
  listLimitUps,
  updateLimitUp,
  getStatistics,
  getFundFlowRank,
  getConceptHot,
  syncFromTushare,
  syncFullFromTushare,
  syncDateRange,
  identifyDragon,
  getTradingDays
} from '../api/limitUp'
import { analyzeLimitUp, getLimitUpAnalysis } from '../api/limitUp'

const route = useRoute()
const router = useRouter()

// ==================== 状态 ====================
const activeTab = ref('overview')
const selectedDate = ref(new Date().toISOString().slice(0, 10))
const tradingDays = ref([])
const syncing = ref(false)

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filters = reactive({
  consecutive_min: null,
  strength_min: null,
  industry: '',
  concept: '',
  q: ''
})

const statsLoading = ref(false)
const stats = ref({})
const conceptData = ref({})

const fundLoading = ref(false)
const fundData = ref({ institution_top: [], hot_money_top: [] })

const dialogVisible = ref(false)
const dialogTitle = ref('添加涨停记录')
const editingItem = ref(null)
const selectedRows = ref([])
const batchUpdating = ref(false)

const detailVisible = ref(false)
const selectedStock = ref(null)

const analysisVisible = ref(false)
const analysisLoading = ref(false)
const analysisData = ref(null)
const stockkbVisible = ref(false)
const stockkbStock = ref(null)

const batchSyncDialogVisible = ref(false)
const batchSyncStart = ref('')
const batchSyncEnd = ref('')

const importResultVisible = ref(false)
const importResult = ref({})

const renderedAnalysisReport = computed(() => {
  return renderMarkdown(analysisData.value?.full_report || '')
})

// ==================== 计算属性 ====================
const quickDates = computed(() => {
  if (tradingDays.value.length === 0) {
    const today = new Date()
    const dates = []
    for (let i = 0; i < 5; i++) {
      const d = new Date(today.getTime() - i * 24 * 60 * 60 * 1000)
      dates.push({
        label: `${d.getMonth() + 1}/${d.getDate()}`,
        value: d.toISOString().slice(0, 10)
      })
    }
    return dates
  }
  return tradingDays.value.slice(0, 5).map(dateStr => {
    const d = new Date(dateStr)
    return { label: `${d.getMonth() + 1}/${d.getDate()}`, value: dateStr }
  })
})

// ==================== 数据加载 ====================
async function loadTradingDays() {
  const today = new Date()
  const startDate = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000)
  try {
    const days = await getTradingDays(
      startDate.toISOString().slice(0, 10),
      today.toISOString().slice(0, 10)
    )
    tradingDays.value = days
    if (days.length > 0 && !days.includes(selectedDate.value)) {
      selectedDate.value = days[0]
    }
  } catch (e) {
    console.error('获取交易日失败:', e)
  }
}

async function reload() {
  loading.value = true
  try {
    const resp = await listLimitUps({
      page: page.value,
      page_size: pageSize.value,
      start_date: selectedDate.value,
      end_date: selectedDate.value,
      ...filters
    })
    rows.value = resp?.data?.items || []
    total.value = resp?.data?.total || 0
    selectedRows.value = []
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  statsLoading.value = true
  try {
    const resp = await getStatistics(selectedDate.value, selectedDate.value)
    stats.value = resp?.data || {}
  } catch (e) {
    console.error('加载统计失败:', e)
  } finally {
    statsLoading.value = false
  }
}

async function loadFundFlow() {
  fundLoading.value = true
  try {
    const resp = await getFundFlowRank(selectedDate.value, selectedDate.value, 20)
    fundData.value = resp?.data || { institution_top: [], hot_money_top: [] }
  } catch (e) {
    console.error('加载资金流向失败:', e)
  } finally {
    fundLoading.value = false
  }
}

// ==================== 事件处理 ====================
function onQuickDateChange(date) {
  selectedDate.value = date
  onDateChange()
}

async function onDateChange() {
  page.value = 1
  await reload()
  await loadStats()
  await loadFundFlow()
}

function onFilterChange(newFilters) {
  Object.assign(filters, newFilters)
  page.value = 1
  reload()
}

function onPageChange(newPage, newPageSize) {
  page.value = newPage
  pageSize.value = newPageSize
  reload()
}

function onStockSelect(stock) {
  selectedStock.value = stock
  detailVisible.value = true
}

function onSelectionChange(selection) {
  selectedRows.value = Array.isArray(selection) ? selection : []
}

function onSectorSelect(type, name) {
  // SectorHeat emit('select', activeTab, name)
  // type: 'industry' 或 'concept'
  // name: 行业名称或概念名称
  if (type === 'industry') {
    filters.industry = name
    filters.concept = ''
  } else if (type === 'concept') {
    filters.concept = name
    filters.industry = ''
  }
  activeTab.value = 'list'
  reload()
}

// ==================== CRUD 操作 ====================
function openCreateDialog() {
  editingItem.value = null
  dialogTitle.value = '添加涨停记录'
  dialogVisible.value = true
}

function openEditDialog(item) {
  editingItem.value = item
  dialogTitle.value = '编辑涨停记录'
  dialogVisible.value = true
  detailVisible.value = false
}

function openBatchUpdateDialog() {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要更新的涨停记录')
    return
  }
  onBatchUpdateSubmit()
}

async function onSubmit(formData) {
  try {
    if (editingItem.value) {
      await updateLimitUp(editingItem.value.id, formData)
      ElMessage.success('更新成功')
    } else {
      await createLimitUp(formData)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    reload()
    loadStats()
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '操作失败')
  }
}

async function onBatchUpdateSubmit() {
  batchUpdating.value = true
  try {
    const items = selectedRows.value.map((row) => ({
      id: row.id,
      stock_code: row.stock_code,
      limit_up_date: row.limit_up_date
    }))
    const resp = await batchUpdateLimitUps(items)
    ElMessage.success(resp?.message || '自动更新成功')
    await reload()
    await loadStats()
    await loadFundFlow()
  } catch (e) {
    ElMessage.error(e?.message || '自动更新失败')
  } finally {
    batchUpdating.value = false
  }
}

// ==================== 同步操作 ====================
async function syncFromTushareNow() {
  syncing.value = true
  try {
    const resp = await syncFromTushare(selectedDate.value)
    if (resp?.code === 200 || resp?.success) {
      ElMessage.success(resp?.message || '同步成功')
      await reload()
      await loadStats()
    } else {
      ElMessage.error(resp?.message || '同步失败')
    }
  } catch (e) {
    console.error('同步失败:', e)
    ElMessage.error(e?.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

async function syncFullFromTushareNow() {
  syncing.value = true
  try {
    const resp = await syncFullFromTushare(selectedDate.value)
    console.log('完整同步返回:', resp)
    if (resp?.code === 200 || resp?.success) {
      ElMessage.success(resp?.message || '完整同步成功')
      // 等待同步完成后刷新数据
      await reload()
      await loadStats()
      await loadFundFlow()
    } else {
      ElMessage.error(resp?.message || '同步失败')
    }
  } catch (e) {
    console.error('完整同步失败:', e)
    ElMessage.error(e?.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

function openBatchSyncDialog() {
  batchSyncStart.value = selectedDate.value
  batchSyncEnd.value = selectedDate.value
  batchSyncDialogVisible.value = true
}

async function syncBatchNow() {
  if (!batchSyncStart.value || !batchSyncEnd.value) {
    ElMessage.warning('请选择日期范围')
    return
  }
  syncing.value = true
  try {
    const resp = await syncDateRange(batchSyncStart.value, batchSyncEnd.value)
    if (resp?.code === 200 || resp?.success) {
      ElMessage.success(resp?.message || '批量同步成功')
      batchSyncDialogVisible.value = false
      await reload()
      await loadStats()
    } else {
      ElMessage.error(resp?.message || '同步失败')
    }
  } catch (e) {
    console.error('批量同步失败:', e)
    ElMessage.error(e?.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

async function identifyDragonNow() {
  try {
    const resp = await identifyDragon(selectedDate.value)
    if (resp?.code === 200 || resp?.success) {
      ElMessage.success(resp?.message || '龙头识别完成')
      await reload()
      await loadStats()
    } else {
      ElMessage.error(resp?.message || '识别失败')
    }
  } catch (e) {
    console.error('龙头识别失败:', e)
    ElMessage.error(e?.message || '识别失败')
  }
}

// ==================== 分析功能 ====================
async function openAnalysisDrawer(row) {
  analysisVisible.value = true
  analysisLoading.value = true
  analysisData.value = null

  try {
    const resp = await getLimitUpAnalysis(row.stock_code, selectedDate.value)
    if (resp?.code === 200 && resp?.data) {
      analysisData.value = resp.data
    } else {
      // 没有历史分析，执行新分析
      const analyzeResp = await analyzeLimitUp(row.stock_code, selectedDate.value, false)
      if (analyzeResp?.code === 200) {
        analysisData.value = analyzeResp.data
      }
    }
  } catch (e) {
    ElMessage.error('分析失败')
  } finally {
    analysisLoading.value = false
  }
}

function openStockkbDialog(row) {
  stockkbStock.value = row
  stockkbVisible.value = true
}

async function openAnalysisFromStockkb() {
  stockkbVisible.value = false
  if (stockkbStock.value) {
    await openAnalysisDrawer(stockkbStock.value)
  }
}

async function handleRouteAnalysisOpen() {
  if (route.query.open !== 'analysis') return

  const stockCode = String(route.query.stock_code || '').trim()
  const reportDate = String(route.query.report_date || '').trim()
  const stockName = String(route.query.stock_name || '').trim()

  if (!stockCode || !reportDate) return

  activeTab.value = 'list'

  if (selectedDate.value !== reportDate) {
    selectedDate.value = reportDate
    page.value = 1
    await reload()
    await loadStats()
    await loadFundFlow()
  } else if (!rows.value.length) {
    await reload()
    await loadStats()
    await loadFundFlow()
  }

  const targetRow = rows.value.find(row => row.stock_code === stockCode) || {
    stock_code: stockCode,
    stock_name: stockName
  }

  await openAnalysisDrawer(targetRow)
  await clearRouteOpenQuery()
}

async function clearRouteOpenQuery() {
  const nextQuery = { ...route.query }
  delete nextQuery.open
  delete nextQuery.stock_code
  delete nextQuery.stock_name
  delete nextQuery.report_date
  delete nextQuery.source
  await router.replace({ path: route.path, query: nextQuery })
}

// ==================== 工具函数 ====================
function consecutiveTagType(days) {
  if (days >= 5) return 'danger'
  if (days >= 3) return 'warning'
  return 'primary'
}

function formatAmount(amount) {
  if (!amount) return '-'
  const yi = amount / 100000000
  if (Math.abs(yi) >= 1) return `${yi.toFixed(2)}亿`
  return `${(amount / 10000).toFixed(0)}万`
}

// ==================== 下载功能 ====================
async function downloadLimitUpData() {
  // 显示加载提示
  const loadingMsg = ElMessage({
    message: '正在获取数据...',
    type: 'info',
    duration: 0
  })
  
  try {
    // 请求当日全部数据（后端限制 page_size 最大 200）
    const resp = await listLimitUps({
      page: 1,
      page_size: 200,  // 后端限制最大 200
      start_date: selectedDate.value,
      end_date: selectedDate.value,
      ...filters
    })
    
    const allRows = resp?.data?.items || []
    
    loadingMsg.close()
    
    if (allRows.length === 0) {
      ElMessage.warning('暂无数据可下载')
      return
    }
    
    // CSV 表头
    const headers = [
      '股票代码',
      '股票名称',
      '连板数',
      '涨停类型',
      '封单金额(万)',
      '换手率(%)',
      '首次涨停时间',
      '开板次数',
      '所属行业',
      '强度等级',
      '是否龙头',
      '机构净买(万)',
      '游资净买(万)',
      '北向净买(万)'
    ]
    
    // CSV 数据行（单位转换：元 → 万元）
    const dataRows = allRows.map(row => {
      // 涨停类型映射
      const limitUpTypeMap = {
        'first_board': '首板',
        'multi_board': '连板',
        'broken_board': '炸板'
      }
      
      return [
        row.stock_code || '',
        row.stock_name || '',
        row.consecutive_days || 1,
        limitUpTypeMap[row.limit_up_type] || row.limit_up_type || '',  // 转换为中文
        row.seal_amount ? (row.seal_amount / 10000).toFixed(2) : '',  // 元 → 万元
        row.turnover_rate ? row.turnover_rate.toFixed(2) : '',
        row.first_limit_time || '',
        row.open_count || 0,
        row.industry || '',
        row.strength_level || '',
        row.is_dragon_head ? '是' : '否',
        row.institution_net_buy ? (row.institution_net_buy / 10000).toFixed(2) : '',  // 元 → 万元
        row.hot_money_net_buy ? (row.hot_money_net_buy / 10000).toFixed(2) : '',  // 元 → 万元
        row.north_net_buy ? (row.north_net_buy / 10000).toFixed(2) : ''  // 元 → 万元
      ]
    })
    
    // 添加 BOM 以支持中文
    const BOM = '\ufeff'
    const csvContent = BOM + [headers.join(','), ...dataRows.map(r => r.join(','))].join('\n')
    
    // 创建 Blob 并下载
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `涨停列表_${selectedDate.value}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    
    ElMessage.success(`已下载 ${allRows.length} 条涨停数据`)
  } catch (e) {
    loadingMsg.close()
    ElMessage.error('获取数据失败')
    console.error('下载失败:', e)
  }
}

// ==================== 生命周期 ====================
onMounted(async () => {
  await loadTradingDays()
  await reload()
  await loadStats()
  await loadFundFlow()
  await handleRouteAnalysisOpen()
})

watch(
  () => [route.query.open, route.query.stock_code, route.query.report_date],
  async ([open, stockCode, reportDate], [prevOpen, prevStockCode, prevReportDate]) => {
    if (
      open === 'analysis' &&
      (open !== prevOpen || stockCode !== prevStockCode || reportDate !== prevReportDate)
    ) {
      await handleRouteAnalysisOpen()
    }
  }
)
</script>

<style scoped>
.limit-up-page {
  min-height: 100vh;
  background: var(--el-bg-color-page);
}

/* 固定顶部 */
.sticky-header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--el-bg-color);
  padding: 16px 16px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

/* 主内容区域 */
.main-content {
  padding: 16px;
}

.main-tabs {
  margin-top: 0;
}

.card {
  margin-bottom: 16px;
}

.analysis-dialog :deep(.el-dialog) {
  border-radius: 18px;
  overflow: hidden;
}

.analysis-dialog :deep(.el-dialog__header) {
  margin-right: 0;
  padding: 0;
  border-bottom: 0;
  min-height: 0;
}

.analysis-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.analysis-dialog :deep(.el-dialog__headerbtn) {
  top: 14px;
  right: 14px;
}

.analysis-loading {
  display: flex;
  min-height: 60vh;
  align-items: center;
  justify-content: center;
  flex-direction: column;
}

.analysis-report {
  max-height: calc(92vh - 90px);
  overflow: auto;
  padding: 24px;
  background: #fbfdff;
  line-height: 1.7;
  font-size: 14px;
  color: #334155;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin: 16px 0 10px;
  line-height: 1.35;
  color: #0f172a;
}

.markdown-body :deep(h1) {
  margin-top: 0;
  font-size: 30px;
}

.markdown-body :deep(h2) {
  font-size: 22px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e2e8f0;
}

.markdown-body :deep(h3) {
  font-size: 18px;
}

.markdown-body :deep(p) {
  margin: 10px 0;
}

.markdown-body :deep(.md-table-wrap) {
  width: 100%;
  margin: 14px 0;
  overflow-x: auto;
  overflow-y: hidden;
  border: 1px solid #dbe3ee;
  border-radius: 10px;
  background: #ffffff;
  -webkit-overflow-scrolling: touch;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 10px 0;
  padding-left: 20px;
}

.markdown-body :deep(li) {
  margin: 6px 0;
}

.markdown-body :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 12px;
  border-left: 4px solid #94a3b8;
  background: #f1f5f9;
  color: #475569;
}

.markdown-body :deep(table) {
  min-width: 720px;
  width: max-content;
  margin: 0;
  border-collapse: collapse;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  min-width: 120px;
  padding: 12px 14px;
  border: 0;
  border-right: 1px solid #dbe3ee;
  border-bottom: 1px solid #dbe3ee;
  vertical-align: top;
  white-space: normal;
  word-break: break-word;
}

.markdown-body :deep(th) {
  background: #e2e8f0;
  font-weight: 700;
  color: #0f172a;
}

.markdown-body :deep(tr:nth-child(even) td) {
  background: #f8fafc;
}

.markdown-body :deep(tr td:last-child),
.markdown-body :deep(tr th:last-child) {
  border-right: 0;
}

.markdown-body :deep(tbody tr:last-child td) {
  border-bottom: 0;
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  border-radius: 6px;
  background: #e2e8f0;
  color: #0f172a;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}

.markdown-body :deep(pre) {
  margin: 12px 0;
  padding: 12px;
  overflow: auto;
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
}

.markdown-body :deep(a) {
  color: #2563eb;
  text-decoration: none;
  word-break: break-all;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(hr) {
  margin: 18px 0;
  border: 0;
  border-top: 1px solid #dbe3ee;
}

@media (max-width: 768px) {
  .analysis-dialog {
    --el-dialog-width: 96vw;
  }

  .analysis-dialog :deep(.el-dialog) {
    margin-top: 2vh !important;
  }

  .analysis-dialog :deep(.el-dialog__header) {
    padding: 16px 18px 10px;
  }

  .analysis-report {
    max-height: calc(96vh - 82px);
    padding: 16px;
    font-size: 13px;
  }

  .markdown-body :deep(h1) {
    font-size: 24px;
  }

  .markdown-body :deep(h2) {
    font-size: 19px;
  }

  .markdown-body :deep(h3) {
    font-size: 16px;
  }

  .markdown-body :deep(table) {
    min-width: 640px;
  }

  .markdown-body :deep(th),
  .markdown-body :deep(td) {
    min-width: 110px;
    padding: 10px 12px;
  }
}
</style>
