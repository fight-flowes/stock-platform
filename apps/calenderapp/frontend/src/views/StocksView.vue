<template>
  <el-row :gutter="16">
    <el-col :xs="24" :lg="6">
      <!-- 搜索股票 -->
      <el-card shadow="never" class="card">
        <template #header>
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px">
            <div style="font-weight: 800">🔍 搜索股票</div>
          </div>
        </template>

        <div style="display: flex; align-items: center; gap: 10px">
          <el-input v-model.trim="q" clearable placeholder="输入代码/名称搜索" @keyup.enter="onSearch" />
          <el-button :loading="searching" type="primary" @click="onSearch">搜索</el-button>
        </div>

        <div style="margin-top: 10px">
          <el-empty v-if="!searching && searchResults.length === 0" description="输入关键词搜索股票" :image-size="40" />
          <el-skeleton v-else-if="searching" :rows="3" animated />
          <div v-else style="display: flex; flex-direction: column; gap: 6px; max-height: 200px; overflow-y: auto">
            <div
              v-for="s in searchResults"
              :key="s.code"
              class="search-result-item"
              @click="openStockDrawer({ code: s.code, name: s.name })"
            >
              <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
                <div style="display: flex; align-items: center; gap: 8px">
                  <span style="font-weight: 600; font-size: 13px">{{ s.code }}</span>
                  <el-tag v-if="s.exchange" type="info" size="small">{{ s.exchange }}</el-tag>
                </div>
                <el-button
                  link
                  :type="s.is_favorite ? 'warning' : 'default'"
                  size="small"
                  @click.stop="handleToggleFavorite(s.code)"
                  :icon="s.is_favorite ? StarFilled : Star"
                  title="收藏"
                />
              </div>
              <div style="margin-top: 2px; color: #64748b; font-size: 12px">{{ s.name }}</div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 收藏股票列表 - 固定滑动窗口 -->
      <el-card shadow="never" class="card favorite-card" style="margin-top: 16px">
        <template #header>
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px">
            <div style="font-weight: 800">⭐ 收藏股票</div>
            <el-button size="small" :loading="favoritesLoading" @click="loadFavorites">刷新</el-button>
          </div>
        </template>

        <div class="favorite-list-container">
          <el-skeleton v-if="favoritesLoading" :rows="3" animated />
          <el-empty v-else-if="favorites.length === 0" description="暂无收藏股票" :image-size="60" />
          <div v-else style="display: flex; flex-direction: column; gap: 6px">
            <div
              v-for="item in favoritesWithQuotes"
              :key="item.code"
              class="favorite-item"
              @click="openStockDrawer(item)"
            >
              <div class="favorite-header">
                <span class="favorite-code">{{ item.code?.split('.')[0] || item.code }}</span>
                <span class="favorite-name">{{ item.name }}</span>
                <el-button
                  link
                  type="warning"
                  size="small"
                  @click.stop="handleToggleFavorite(item.code)"
                  :icon="StarFilled"
                  title="取消收藏"
                />
              </div>
              <div class="favorite-quote" v-if="item.quote">
                <span :style="{ color: (item.quote?.pct_chg || 0) >= 0 ? '#ef4444' : '#22c55e', fontWeight: '600' }">
                  {{ item.quote.close?.toFixed(2) }}
                </span>
                <span :style="{ color: (item.quote?.pct_chg || 0) >= 0 ? '#ef4444' : '#22c55e', fontSize: '12px' }">
                  {{ item.quote.pct_chg >= 0 ? '+' : '' }}{{ item.quote.pct_chg?.toFixed(2) }}%
                </span>
                <span style="color: #909399; font-size: 12px">
                  {{ item.quote.total_mv ? formatMarketValueSimple(item.quote.total_mv) : '-' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </el-col>

    <el-col :xs="24" :lg="18">
      <el-card shadow="never" class="card">
        <template #header>
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap">
            <div style="font-weight: 800">股票列表</div>
            <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
              <el-button @click="downloadStocksTemplate">下载模板</el-button>
              <el-upload
                :show-file-list="false"
                :http-request="uploadStocksCsv"
                :before-upload="beforeCsvUpload"
                accept=".csv,text/csv"
              >
                <el-button :loading="importing">上传 CSV</el-button>
              </el-upload>
              <el-select v-model="exchange" clearable placeholder="交易所" style="width: 120px" @change="reload">
                <el-option label="SH" value="SH" />
                <el-option label="SZ" value="SZ" />
                <el-option label="HK" value="HK" />
                <el-option label="US" value="US" />
              </el-select>
              <el-button :loading="loading" @click="reload">刷新</el-button>
              <el-button 
              :loading="cacheUpdating" 
              :disabled="selectedStocks.length === 0"
              type="primary" 
              @click="handleBatchUpdateCache"
            >
              批量更新行情 {{ selectedStocks.length > 0 ? `(${selectedStocks.length})` : '' }}
            </el-button>
            </div>
          </div>
        </template>

        <el-table 
            ref="stocksTableRef"
            :data="rowsWithQuotes" 
            v-loading="loading || quotesLoading" 
            style="width: 100%" 
            @row-click="openStockDrawer"
            @selection-change="handleSelectionChange"
          >
            <!-- 复选框列 -->
            <el-table-column type="selection" width="55" />
            <el-table-column prop="code" label="代码" width="100">
            <template #default="{ row }">
              <span style="color: #409eff; cursor: pointer">{{ row.code }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" min-width="80" />
          <el-table-column label="最新价" width="80" align="right">
            <template #default="{ row }">
              <span v-if="row.quote?.close" :style="{ color: (row.quote?.pct_chg || 0) >= 0 ? '#ef4444' : '#22c55e', fontWeight: '600' }">
                {{ row.quote.close.toFixed(2) }}
              </span>
              <span v-else style="color: #909399">-</span>
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="85" align="right">
            <template #default="{ row }">
              <span v-if="row.quote?.pct_chg !== null && row.quote?.pct_chg !== undefined" :style="{ color: row.quote.pct_chg >= 0 ? '#ef4444' : '#22c55e' }">
                {{ row.quote.pct_chg >= 0 ? '+' : '' }}{{ row.quote.pct_chg.toFixed(2) }}%
              </span>
              <span v-else style="color: #909399">-</span>
            </template>
          </el-table-column>
          <el-table-column label="总市值" width="90" align="right">
            <template #default="{ row }">
              <span v-if="row.quote?.total_mv" style="font-size: 12px">{{ formatMarketValueSimple(row.quote.total_mv) }}</span>
              <span v-else style="color: #909399">-</span>
            </template>
          </el-table-column>
          <el-table-column label="换手率" width="70" align="right">
            <template #default="{ row }">
              <span v-if="row.quote?.turnover_rate" style="font-size: 12px">{{ row.quote.turnover_rate.toFixed(2) }}%</span>
              <span v-else style="color: #909399">-</span>
            </template>
          </el-table-column>
          <el-table-column label="行业" prop="latest_industry" width="90">
            <template #default="{ row }">
              <span v-if="row.latest_industry" style="font-size: 12px">{{ row.latest_industry }}</span>
              <span v-else style="color: #909399">-</span>
            </template>
          </el-table-column>
          <el-table-column label="涨停" prop="limit_up_count" width="55" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.limit_up_count > 0" size="small" type="danger">{{ row.limit_up_count }}</el-tag>
              <span v-else style="color: #909399">-</span>
            </template>
          </el-table-column>
          <el-table-column label="股东人数" width="80" align="right">
            <template #default="{ row }">
              <span v-if="row.quote?.holder_num" style="font-size: 12px">
                {{ (row.quote.holder_num / 10000).toFixed(2) }}万
              </span>
              <span v-else style="color: #909399">-</span>
            </template>
          </el-table-column>
          <el-table-column label="最新涨停" prop="latest_limit_up_date" width="130">
            <template #default="{ row }">
              <span v-if="row.latest_limit_up_date" style="font-size: 12px">
                {{ row.latest_limit_up_date }}
                <span v-if="row.latest_consecutive_days" style="color: #ef4444; margin-left: 4px">
                  {{ row.latest_consecutive_days }}连板
                </span>
              </span>
              <span v-else style="color: #909399">-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <div style="display: flex; align-items: center; gap: 4px">
                <el-button
                  link
                  :type="row.is_favorite ? 'warning' : 'default'"
                  size="small"
                  @click.stop="handleToggleFavorite(row.code)"
                  :icon="row.is_favorite ? StarFilled : Star"
                  title="收藏"
                />
                <el-popconfirm
                  title="确定删除该股票？"
                  @confirm="handleDeleteStock(row.code)"
                  confirm-button-text="删除"
                  cancel-button-text="取消"
                >
                  <template #reference>
                    <el-button
                      link
                      type="danger"
                      size="small"
                      @click.stop
                      :icon="Delete"
                      title="删除"
                    />
                  </template>
                </el-popconfirm>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div style="display: flex; justify-content: flex-end; margin-top: 12px">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            :total="total"
            @size-change="reload"
            @current-change="reload"
          />
        </div>
      </el-card>
    </el-col>
  </el-row>

  <!-- 股票详情抽屉 -->
  <el-drawer v-model="drawerVisible" size="520px" :with-header="false" :before-close="closeDrawer">
    <div class="stock-detail">
      <div class="detail-header">
        <div class="stock-info">
          <div class="stock-name">{{ stockInfo?.name || currentStock?.name || '-' }}</div>
          <div class="stock-code">{{ stockInfo?.ts_code || currentStock?.code }}</div>
        </div>
        <div class="header-actions">
          <el-button size="small" @click="closeDrawer">关闭</el-button>
        </div>
      </div>

      <el-divider />

      <el-skeleton v-if="drawerLoading" :rows="8" animated />
      <div v-else>
        <!-- 核心指标 -->
        <div class="core-metrics">
          <div class="metric-item">
            <div class="metric-value" :style="{ color: latestPctChg >= 0 ? '#ef4444' : '#22c55e' }">
              {{ latestClose ? latestClose.toFixed(2) : '-' }}
            </div>
            <div class="metric-label">最新价</div>
          </div>
          <div class="metric-item">
            <div class="metric-value" :style="{ color: latestPctChg >= 0 ? '#ef4444' : '#22c55e' }">
              {{ latestPctChg ? (latestPctChg >= 0 ? '+' : '') + latestPctChg.toFixed(2) + '%' : '-' }}
            </div>
            <div class="metric-label">涨跌幅</div>
          </div>
          <div class="metric-item">
            <div class="metric-value">{{ formatMarketValue(totalMarketValue) }}</div>
            <div class="metric-label">总市值</div>
          </div>
          <div class="metric-item">
            <div class="metric-value">{{ formatMarketValue(circMarketValue) }}</div>
            <div class="metric-label">流通市值</div>
          </div>
        </div>

        <!-- K线图 -->
        <div class="chart-section">
          <div class="chart-header">
            <span style="font-weight: 700; font-size: 14px">90日K线</span>
            <el-button size="small" :loading="klineLoading" @click="loadKlineData">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
          
          <!-- K线信息栏 -->
          <div v-if="selectedKline" class="kline-info-bar">
            <span class="kline-date">{{ selectedKline.date }}</span>
            <span class="kline-item">开: <b>{{ selectedKline.open.toFixed(2) }}</b></span>
            <span class="kline-item">高: <b class="high">{{ selectedKline.high.toFixed(2) }}</b></span>
            <span class="kline-item">低: <b class="low">{{ selectedKline.low.toFixed(2) }}</b></span>
            <span class="kline-item">收: <b>{{ selectedKline.close.toFixed(2) }}</b></span>
            <span class="kline-item" :class="{ up: selectedKline.pctChg > 0, down: selectedKline.pctChg < 0 }">
              涨跌: <b>{{ selectedKline.pctChg >= 0 ? '+' : '' }}{{ selectedKline.pctChg.toFixed(2) }}%</b>
            </span>
            <span class="kline-item">换手: <b>{{ selectedKline.turnoverRate }}%</b></span>
          </div>
          
          <div class="chart-container" v-loading="klineLoading">
            <div ref="klineChartRef" class="chart"></div>
            <div v-if="klineError" class="chart-error">
              <el-empty :description="klineError" :image-size="80" />
            </div>
          </div>
        </div>

        <el-divider />

        <!-- 公司基本信息 -->
        <div class="section">
          <div class="section-title">公司基本信息</div>
          <el-descriptions :column="1" border size="small" class="company-info">
            <el-descriptions-item label="股票简称">{{ stockInfo?.name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="所属行业">{{ stockInfo?.industry || '-' }}</el-descriptions-item>
            <el-descriptions-item label="市场类型">{{ marketTypeLabel }}</el-descriptions-item>
            <el-descriptions-item label="所在地区">{{ stockInfo?.area || (stockInfo?.province && stockInfo?.city ? `${stockInfo.province}-${stockInfo.city}` : '-') }}</el-descriptions-item>
            <el-descriptions-item label="上市日期">{{ formatDate(stockInfo?.list_date) }}</el-descriptions-item>
            <el-descriptions-item label="董事长">{{ stockInfo?.chairman || '-' }}</el-descriptions-item>
            <el-descriptions-item label="总经理">{{ stockInfo?.manager || '-' }}</el-descriptions-item>
            <el-descriptions-item label="员工人数">{{ stockInfo?.employees ? `${stockInfo.employees}人` : '-' }}</el-descriptions-item>
            <el-descriptions-item label="沪深港通">
              <el-tag v-if="stockInfo?.is_hs === 'S'" type="success" size="small">沪股通</el-tag>
              <el-tag v-else-if="stockInfo?.is_hs === 'H'" type="success" size="small">深股通</el-tag>
              <el-tag v-else-if="stockInfo?.is_hs === 'SH'" type="success" size="small">沪深港通</el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 主营业务 -->
        <div v-if="stockInfo?.main_business" class="section">
          <div class="section-title">主营业务</div>
          <div class="business-content">{{ stockInfo.main_business }}</div>
        </div>

        <!-- 公司简介 -->
        <div v-if="stockInfo?.introduction" class="section">
          <div class="section-title">公司简介</div>
          <div class="business-content intro-content">{{ stockInfo.introduction }}</div>
        </div>

        <!-- 元数据 -->
        <div class="metadata">
          <span>数据来源: Tushare</span>
        </div>
      </div>
    </div>
  </el-drawer>

  <el-dialog v-model="importDialogVisible" title="导入结果" width="720px">
    <el-skeleton v-if="importing" :rows="6" animated />
    <div v-else-if="importResult" style="display: flex; flex-direction: column; gap: 12px">
      <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
        <el-tag type="success">新增 {{ importResult.created || 0 }}</el-tag>
        <el-tag type="warning">更新 {{ importResult.updated || 0 }}</el-tag>
        <el-tag :type="importResult.failed ? 'danger' : 'info'">失败 {{ importResult.failed || 0 }}</el-tag>
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
        <el-table-column prop="code" label="代码" width="120" />
        <el-table-column prop="name" label="名称" min-width="200" />
      </el-table>
    </div>
    <template #footer>
      <el-button @click="importDialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { onMounted, ref, nextTick, computed, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { importStocksCsv, listStocks, searchStocks, getStockKline, getStockInfo, getRealtimeQuotes, listFavorites, toggleFavorite, updateQuotesCache, deleteStock } from '../api/stocks'
import { Delete, StarFilled, Star } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const q = ref('')
const searching = ref(false)
const searchResults = ref([])

const exchange = ref('')
const loading = ref(false)
const rows = ref([])
const quotes = ref({})  // 实时行情数据
const quotesLoading = ref(false)
const cacheUpdating = ref(false)

// 批量选择相关
const stocksTableRef = ref(null)
const selectedStocks = ref([])

// 收藏相关
const favorites = ref([])
const favoritesQuotes = ref({})
const favoritesLoading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const importing = ref(false)
const importDialogVisible = ref(false)
const importResult = ref(null)

// 抽屉相关
const drawerVisible = ref(false)
const drawerLoading = ref(false)
const currentStock = ref(null)
const stockInfo = ref(null)
const klineData = ref([])
const klineChartRef = ref(null)
const klineLoading = ref(false)
const klineError = ref('')
let klineChart = null
const klineDataCache = ref([])
const selectedKline = ref(null)

// 最新行情
const latestClose = ref(null)
const latestPctChg = ref(null)
const totalMarketValue = ref(null)
const circMarketValue = ref(null)

// 市场类型标签
const marketTypeLabel = computed(() => {
  const map = {
    '主板': '主板',
    '科创板': '科创板',
    '创业板': '创业板',
    '北交所': '北交所'
  }
  return map[stockInfo?.value?.market] || stockInfo?.value?.market || '-'
})

function apiBase() {
  return import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000'
}

function downloadStocksTemplate() {
  window.open(`${apiBase()}/api/stocks/template.csv`, '_blank')
}

function beforeCsvUpload(file) {
  const name = String(file?.name || '').toLowerCase()
  if (!name.endsWith('.csv')) {
    ElMessage.error('仅支持 CSV 文件')
    return false
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.error('文件过大（最大 2MB）')
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

async function uploadStocksCsv(options) {
  importing.value = true
  importDialogVisible.value = true
  importResult.value = null
  try {
    const resp = await importStocksCsv(options.file)
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

async function onSearch() {
  const query = String(q.value || '').trim()
  if (!query) {
    searchResults.value = []
    return
  }
  searching.value = true
  try {
    const resp = await searchStocks(query, 20)
    searchResults.value = resp?.data || []
  } catch (e) {
    ElMessage.error(e?.message || '搜索失败')
  } finally {
    searching.value = false
  }
}

// 合并股票列表和缓存行情
const rowsWithQuotes = computed(() => {
  return rows.value.map(row => {
    // 直接使用缓存数据（已在 stock_dict 中）
    return {
      ...row,
      quote: {
        close: row.cache_close,
        pct_chg: row.cache_pct_chg,
        total_mv: row.cache_total_mv,
        circ_mv: row.cache_circ_mv,
        turnover_rate: row.cache_turnover_rate,
        holder_num: row.cache_holder_num,
        trade_date: row.cache_trade_date
      }
    }
  })
})

// 合并收藏列表和缓存行情
const favoritesWithQuotes = computed(() => {
  return favorites.value.map(item => {
    return {
      ...item,
      quote: {
        close: item.cache_close,
        pct_chg: item.cache_pct_chg,
        total_mv: item.cache_total_mv,
        circ_mv: item.cache_circ_mv,
        turnover_rate: item.cache_turnover_rate
      }
    }
  })
})

async function reload() {
  loading.value = true
  try {
    const resp = await listStocks({
      page: page.value,
      page_size: pageSize.value,
      exchange: exchange.value || undefined
    })
    rows.value = resp?.data?.items || []
    total.value = resp?.data?.total || 0
  } catch (e) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 更新所有股票行情缓存
async function handleUpdateCache() {
  cacheUpdating.value = true
  try {
    // 不传 codes 参数，更新所有股票
    const resp = await updateQuotesCache()
    ElMessage.success(resp?.message || '更新完成')
    // 刷新列表
    await reload()
    await loadFavorites()
  } catch (e) {
    ElMessage.error(e?.message || '更新失败')
  } finally {
    cacheUpdating.value = false
  }
}

// 表格选择变化处理
function handleSelectionChange(selection) {
  selectedStocks.value = selection
}

// 批量更新选中股票行情
async function handleBatchUpdateCache() {
  if (selectedStocks.value.length === 0) {
    ElMessage.warning('请先勾选要更新的股票')
    return
  }
  
  cacheUpdating.value = true
  try {
    const codes = selectedStocks.value.map(s => s.code)
    const resp = await updateQuotesCache(codes)  // 传入选中的股票代码
    ElMessage.success(resp?.message || `更新完成: ${resp?.data?.updated}条`)
    // 清空选择
    stocksTableRef.value?.clearSelection()
    selectedStocks.value = []
    // 刷新列表
    await reload()
    await loadFavorites()
  } catch (e) {
    ElMessage.error(e?.message || '更新失败')
  } finally {
    cacheUpdating.value = false
  }
}

// 格式化市值（简化版）
function formatMarketValueSimple(mv) {
  if (!mv) return '-'
  // Tushare市值单位是万元
  const yi = mv / 10000
  if (yi >= 10000) {
    return `${(yi / 10000).toFixed(1)}万亿`
  }
  return `${yi.toFixed(0)}亿`
}

// 加载收藏股票列表
async function loadFavorites() {
  favoritesLoading.value = true
  try {
    const resp = await listFavorites()
    favorites.value = resp?.data || []
  } catch (e) {
    console.error('加载收藏失败:', e)
  } finally {
    favoritesLoading.value = false
  }
}

// 切换收藏状态
async function handleToggleFavorite(code) {
  try {
    await toggleFavorite(code)
    // 刷新列表
    await reload()
    await loadFavorites()
  } catch (e) {
    ElMessage.error(e?.message || '操作失败')
  }
}

// 删除股票
async function handleDeleteStock(code) {
  try {
    await deleteStock(code)
    ElMessage.success('删除成功')
    // 刷新列表
    await reload()
    await loadFavorites()
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  }
}

// 打开股票抽屉
async function openStockDrawer(row) {
  drawerVisible.value = true
  drawerLoading.value = true
  currentStock.value = row
  stockInfo.value = null
  klineData.value = []
  klineDataCache.value = []
  selectedKline.value = null
  latestClose.value = null
  latestPctChg.value = null
  totalMarketValue.value = null
  circMarketValue.value = null
  klineError.value = ''

  try {
    // 获取公司信息
    const infoResp = await getStockInfo(row.code)
    stockInfo.value = infoResp?.data || null

    // 获取K线数据
    await loadKlineData()
  } catch (e) {
    ElMessage.error(e?.message || '获取数据失败')
  } finally {
    drawerLoading.value = false
  }
}

// 加载K线数据（固定90日）
async function loadKlineData() {
  if (!currentStock.value?.code) return
  
  klineLoading.value = true
  klineError.value = ''
  
  try {
    const resp = await getStockKline(currentStock.value.code, 90)
    if (resp?.code !== 200 || !resp?.data?.kline?.length) {
      klineError.value = resp?.message || '暂无K线数据'
      klineData.value = []
      return
    }
    
    klineData.value = resp.data.kline
    klineDataCache.value = resp.data.kline
    selectedKline.value = null
    
    // 获取最新行情
    const latest = klineData.value[klineData.value.length - 1]
    if (latest) {
      latestClose.value = latest.close
      latestPctChg.value = latest.pct_chg
      totalMarketValue.value = latest.total_mv
      circMarketValue.value = latest.circ_mv
    }
    
    // 等待 DOM 更新后再渲染图表
    await nextTick()
    // 额外等待确保抽屉动画完成
    setTimeout(() => {
      renderKlineChart()
    }, 100)
  } catch (e) {
    klineError.value = e?.message || '获取K线数据失败'
  } finally {
    klineLoading.value = false
  }
}

// 渲染K线图
function renderKlineChart() {
  if (!klineChartRef.value) {
    console.warn('klineChartRef not ready')
    return
  }
  if (klineData.value.length === 0) {
    console.warn('klineData is empty')
    return
  }

  if (klineChart) {
    klineChart.dispose()
  }

  klineChart = echarts.init(klineChartRef.value)

  const dates = klineData.value.map(d => {
    const dateStr = String(d.date)
    return dateStr.length === 8 ? `${dateStr.slice(4,6)}/${dateStr.slice(6,8)}` : dateStr
  })
  const ohlc = klineData.value.map(d => [d.open, d.close, d.low, d.high])
  const volumes = klineData.value.map(d => d.volume)
  const pctChgs = klineData.value.map(d => d.pct_chg)

  const option = {
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', label: { show: false } },
      formatter: function(params) {
        const kline = params.find(p => p.seriesName === 'K线')
        if (!kline) return ''
        const idx = kline.dataIndex
        const d = klineDataCache.value[idx]
        if (!d) return ''
        const color = d.close >= d.open ? '#ef4444' : '#22c55e'
        const dateStr = String(d.date)
        const formattedDate = dateStr.length === 8 
          ? `${dateStr.slice(0,4)}-${dateStr.slice(4,6)}-${dateStr.slice(6,8)}` 
          : dateStr
        return `
          <div style="font-weight: bold">${formattedDate}</div>
          <div>开盘: ${d.open.toFixed(2)}</div>
          <div style="color:${color}">收盘: ${d.close.toFixed(2)}</div>
          <div>最高: ${d.high.toFixed(2)}</div>
          <div>最低: ${d.low.toFixed(2)}</div>
          <div style="color:${color}">涨跌: ${d.pct_chg >= 0 ? '+' : ''}${d.pct_chg.toFixed(2)}%</div>
          <div>成交量: ${(d.volume / 10000).toFixed(2)}万手</div>
          <div>换手率: ${d.turnover_rate ? d.turnover_rate.toFixed(2) : '-'}%</div>
        `
      }
    },
    grid: [
      { left: '10%', right: '8%', top: '10%', height: '60%' },
      { left: '10%', right: '8%', top: '76%', height: '14%' }
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false }, axisPointer: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false }, axisPointer: { show: false } }
    ],
    yAxis: [
      { scale: true, gridIndex: 0, splitLine: { lineStyle: { type: 'dashed' } } },
      { scale: true, gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false }, axisTick: { show: false }, axisLine: { show: false } }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        itemStyle: {
          color: '#ef4444',
          color0: '#22c55e',
          borderColor: '#ef4444',
          borderColor0: '#22c55e'
        }
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: function(params) {
            return pctChgs[params.dataIndex] >= 0 ? '#ef4444' : '#22c55e'
          }
        },
        tooltip: { show: false }
      }
    ]
  }

  klineChart.setOption(option)

  // 添加点击事件
  klineChart.on('click', function(params) {
    if (params.seriesName === 'K线') {
      const idx = params.dataIndex
      const d = klineDataCache.value[idx]
      if (d) {
        const dateStr = String(d.date)
        selectedKline.value = {
          date: dateStr.length === 8 
            ? `${dateStr.slice(0,4)}-${dateStr.slice(4,6)}-${dateStr.slice(6,8)}` 
            : dateStr,
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
          pctChg: d.pct_chg,
          turnoverRate: d.turnover_rate ? d.turnover_rate.toFixed(2) : '-'
        }
      }
    }
  })
}

// 关闭抽屉
function closeDrawer(done) {
  if (klineChart) {
    klineChart.dispose()
    klineChart = null
  }
  if (typeof done === 'function') {
    done()
  } else {
    drawerVisible.value = false
  }
}

async function handleRouteStockOpen() {
  if (route.query.open !== 'detail') return

  const stockCode = String(route.query.code || '').trim()
  const stockName = String(route.query.name || '').trim()
  if (!stockCode) return

  q.value = stockCode
  await openStockDrawer({ code: stockCode, name: stockName })
  await clearRouteOpenQuery()
}

async function clearRouteOpenQuery() {
  const nextQuery = { ...route.query }
  delete nextQuery.open
  delete nextQuery.code
  delete nextQuery.name
  delete nextQuery.source
  await router.replace({ path: route.path, query: nextQuery })
}

// 格式化市值
function formatMarketValue(mv) {
  if (!mv) return '-'
  const yi = mv / 10000  // Tushare的市值单位是万元
  if (yi >= 10000) {
    return `${(yi / 10000).toFixed(2)}万亿`
  }
  return `${yi.toFixed(2)}亿`
}

// 格式化日期
function formatDate(dateStr) {
  if (!dateStr) return '-'
  const str = String(dateStr)
  if (str.length === 8) {
    return `${str.slice(0,4)}-${str.slice(4,6)}-${str.slice(6,8)}`
  }
  return str
}

// 格式化时间
function formatTime(date) {
  if (!date) return '-'
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

// 监听抽屉关闭
watch(drawerVisible, (visible) => {
  if (!visible && klineChart) {
    klineChart.dispose()
    klineChart = null
  }
})

onUnmounted(() => {
  if (klineChart) {
    klineChart.dispose()
    klineChart = null
  }
})

onMounted(async () => {
  await reload()
  await loadFavorites()
  await handleRouteStockOpen()
})

watch(
  () => [route.query.open, route.query.code, route.query.name],
  async ([open, code, name], [prevOpen, prevCode, prevName]) => {
    if (open === 'detail' && (open !== prevOpen || code !== prevCode || name !== prevName)) {
      await handleRouteStockOpen()
    }
  }
)
</script>

<style scoped>
.card {
  margin-bottom: 16px;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  width: 100%;
  padding: 16px;
}

.stock-info .stock-name {
  font-size: 20px;
  font-weight: 800;
}

.stock-info .stock-code {
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.stock-detail {
  padding: 0 16px 16px 16px;
}

.core-metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.metric-item {
  text-align: center;
  padding: 10px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.metric-value {
  font-size: 18px;
  font-weight: 800;
  color: var(--el-color-primary);
}

.metric-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.chart-section {
  margin-bottom: 16px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.kline-info-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  margin-bottom: 8px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  font-size: 12px;
  overflow-x: auto;
}

.kline-date {
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.kline-item {
  color: var(--el-text-color-secondary);
}

.kline-item b {
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.kline-item b.high {
  color: #ef4444;
}

.kline-item b.low {
  color: #22c55e;
}

.kline-item.up b {
  color: #ef4444;
}

.kline-item.down b {
  color: #22c55e;
}

.chart-container {
  height: 260px;
  position: relative;
}

.chart {
  width: 100%;
  height: 100%;
}

.chart-error {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.section {
  margin-bottom: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.company-info {
  margin-bottom: 8px;
}

.business-content {
  padding: 10px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
}

.intro-content {
  max-height: 150px;
  overflow-y: auto;
}

.metadata {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.favorite-item {
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.favorite-item:hover {
  background: var(--el-fill-color);
}

.favorite-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.favorite-code {
  font-weight: 600;
  font-size: 13px;
}

.favorite-name {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.favorite-quote {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
  font-size: 12px;
}

/* 搜索结果项样式 */
.search-result-item {
  padding: 8px 10px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.search-result-item:hover {
  background: var(--el-fill-color);
}

/* 收藏股票固定滑动窗口 */
.favorite-card {
  position: sticky;
  top: 16px;
}

.favorite-list-container {
  max-height: calc(100vh - 380px);
  overflow-y: auto;
}

/* 自定义滚动条 */
.favorite-list-container::-webkit-scrollbar {
  width: 6px;
}

.favorite-list-container::-webkit-scrollbar-track {
  background: var(--el-fill-color-lighter);
  border-radius: 3px;
}

.favorite-list-container::-webkit-scrollbar-thumb {
  background: var(--el-border-color);
  border-radius: 3px;
}

.favorite-list-container::-webkit-scrollbar-thumb:hover {
  background: var(--el-text-color-secondary);
}
</style>
