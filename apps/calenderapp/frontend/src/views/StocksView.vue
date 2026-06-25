<template>
  <div class="stocks-page">
    <!-- 顶部工具栏：标题 + 状态 + 搜索 融合一块 -->
    <el-card shadow="never" class="page-header-card">
      <div class="page-header">
        <div class="page-header-main">
          <div class="page-title">⭐ 我的股票</div>
          <div class="page-status">
            <el-tag size="small" type="info" effect="plain">收藏池 {{ total }} 只</el-tag>
            <el-tag size="small" type="warning" effect="plain">分组 {{ groups.length }} 个</el-tag>
            <el-tag size="small" type="success" effect="plain">标签 {{ tags.length }} 个</el-tag>
            <el-tag v-if="selectedStocks.length > 0" size="small" type="primary" effect="plain">
              已选 {{ selectedStocks.length }} 只
            </el-tag>
          </div>
          <div class="search-row">
            <el-input
              v-model.trim="q"
              clearable
              placeholder="输入代码或名称搜索股票"
              class="search-input"
              @keyup.enter="onSearch"
              @input="onSearchInput"
            >
              <template #prepend>🔍</template>
              <template #append>
                <el-button :loading="searching" @click="onSearch">搜索</el-button>
              </template>
            </el-input>
          </div>
        </div>

        <!-- 搜索结果：紧贴搜索框下方，同属这一块 -->
        <div v-if="searchResults.length > 0" class="search-results-panel">
          <div class="search-results-header">
            搜索结果（{{ searchResults.length }}）— 点击查看详情，或点 ⭐ 加入收藏
            <el-button link size="small" @click="clearSearch">清空</el-button>
          </div>
          <div class="search-results-list">
            <div
              v-for="s in searchResults"
              :key="s.code"
              class="search-result-item"
              @click="openStockDrawer({ code: s.code, name: s.name })"
            >
              <div class="result-main">
                <span class="result-code">{{ s.code }}</span>
                <el-tag v-if="s.exchange" type="info" size="small">{{ s.exchange }}</el-tag>
                <span class="result-name">{{ s.name }}</span>
              </div>
              <el-button
                link
                :type="s.is_favorite ? 'warning' : 'default'"
                size="small"
                :icon="s.is_favorite ? StarFilled : Star"
                title="收藏"
                @click.stop="handleToggleFavorite(s.code)"
              />
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <StocksWorkbenchBar
      :groups="groups"
      :tags="tags"
      :selected-group-id="selectedGroupId"
      :selected-tag-ids="selectedTagIds"
      :ungrouped-only="ungroupedOnly"
      :selected-count="selectedStocks.length"
      :loading="loading"
      :batch-group-loading="batchGroupLoading"
      :batch-tag-loading="batchTagLoading"
      @change-group-scope="onGroupScopeChange"
      @update:selected-tag-ids="onTagFilterChange"
      @manage-groups="groupManagerVisible = true"
      @manage-tags="tagManagerVisible = true"
      @add-group-stocks="openAddGroupStocksDialog"
      @batch-add-group="handleBatchAddGroup"
      @batch-add-tag="handleBatchAddTag"
    />

    <!-- 主面板：收藏股票列表 -->
    <el-card shadow="never" class="favorites-card">
      <template #header>
        <div class="favorites-header">
          <div class="favorites-title">
            收藏列表
            <span class="favorites-count">{{ total }} 只</span>
          </div>
          <div class="favorites-toolbar">
            <div class="favorites-summary">
              <span v-if="activeGroupName" class="summary-chip">{{ activeGroupName }}</span>
              <span v-if="selectedTagIds.length > 0" class="summary-chip">按标签筛选</span>
              <span v-if="ungroupedOnly" class="summary-chip">仅未分组</span>
            </div>
            <div class="favorites-toolbar-actions">
              <el-button
                size="small"
                type="primary"
                :loading="cacheUpdating"
                :disabled="selectedStocks.length === 0"
                @click="handleBatchUpdateCache"
              >
                批量更新{{ selectedStocks.length > 0 ? ` (${selectedStocks.length})` : '' }}
              </el-button>
              <el-button size="small" :loading="loading" @click="reload">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </div>
        </div>
      </template>

      <el-empty
        v-if="!loading && rows.length === 0"
        :image-size="100"
        description=""
      >
        <template #description>
          <div class="empty-text">
            <template v-if="selectedGroupId">
              <p style="font-size: 15px; color: #606266; margin-bottom: 8px;">当前分组暂无股票</p>
              <p style="font-size: 13px; color: #909399; margin-bottom: 12px;">通过搜索将股票加入“{{ activeGroupName }}”分组</p>
              <el-button type="primary" plain @click="openAddGroupStocksDialog">添加股票</el-button>
            </template>
            <template v-else>
              <p style="font-size: 15px; color: #606266; margin-bottom: 8px;">还没有收藏的股票</p>
              <p style="font-size: 13px; color: #909399;">使用上方搜索框找一只股票，点 ⭐ 加入收藏</p>
            </template>
          </div>
        </template>
      </el-empty>

      <el-table
        v-else
        ref="stocksTableRef"
        :data="sortedRowsWithQuotes"
        v-loading="loading || quotesLoading"
        style="width: 100%"
        @row-click="openStockDrawer"
        @selection-change="handleSelectionChange"
        @sort-change="handleTableSortChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="code" label="代码" width="110">
          <template #default="{ row }">
            <span class="code-cell">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="200" />
        <el-table-column
          prop="quote_close"
          label="最新价"
          width="90"
          align="right"
          sortable="custom"
        >
          <template #default="{ row }">
            <span
              v-if="row.quote?.close"
              :style="{ color: (row.quote?.pct_chg || 0) >= 0 ? '#ef4444' : '#22c55e', fontWeight: 600 }"
            >{{ row.quote.close.toFixed(2) }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="quote_pct_chg"
          label="涨跌幅"
          width="100"
          align="right"
          sortable="custom"
        >
          <template #default="{ row }">
            <span
              v-if="row.quote?.pct_chg !== null && row.quote?.pct_chg !== undefined"
              :style="{ color: (row.quote.pct_chg || 0) >= 0 ? '#ef4444' : '#22c55e', fontWeight: 600 }"
            >
              {{ (row.quote.pct_chg || 0) >= 0 ? '+' : '' }}{{ row.quote.pct_chg.toFixed(2) }}%
            </span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="换手率" width="90" align="right">
          <template #default="{ row }">
            <span v-if="row.quote?.turnover_rate">{{ row.quote.turnover_rate.toFixed(2) }}%</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="流通市值" width="110" align="right">
          <template #default="{ row }">
            <span v-if="row.quote?.circ_mv">{{ formatMarketValue(row.quote.circ_mv) }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="最近涨停" width="120" align="right">
          <template #default="{ row }">
            <div v-if="row.latest_limit_up_date" class="limit-up-cell">
              <div class="limit-up-date">{{ row.latest_limit_up_date }}</div>
              <el-tag
                v-if="row.latest_consecutive_days"
                size="small"
                :type="row.latest_consecutive_days >= 3 ? 'danger' : 'warning'"
              >{{ row.latest_consecutive_days }}板</el-tag>
            </div>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="行业" width="140" align="right">
          <template #default="{ row }">
            <span v-if="row.latest_industry">{{ row.latest_industry }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="分组" min-width="180">
          <template #default="{ row }">
            <div class="chip-cell">
              <template v-if="row.groups?.length">
                <el-tag
                  v-for="group in row.groups.slice(0, 2)"
                  :key="group.id"
                  size="small"
                  effect="plain"
                >
                  {{ group.name }}
                </el-tag>
                <span v-if="row.groups.length > 2" class="chip-more">+{{ row.groups.length - 2 }}</span>
              </template>
              <span v-else class="muted">-</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="标签" min-width="160">
          <template #default="{ row }">
            <div class="chip-cell">
              <template v-if="row.tags?.length">
                <el-tag
                  v-for="tag in row.tags.slice(0, 2)"
                  :key="tag.id"
                  size="small"
                  effect="plain"
                  type="success"
                >
                  {{ tag.name }}
                </el-tag>
                <span v-if="row.tags.length > 2" class="chip-more">+{{ row.tags.length - 2 }}</span>
              </template>
              <span v-else class="muted">-</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="220">
          <template #default="{ row }">
            <el-tooltip
              :content="row.note"
              placement="top-start"
              :disabled="!row.note"
            >
              <button
                type="button"
                class="note-cell"
                :class="{ 'is-empty': !row.note }"
                @click.stop="openNoteDialog(row)"
              >
                {{ row.note || '添加' }}
              </button>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              size="small"
              @click.stop="openOrganizerDialog(row)"
            >
              归类
            </el-button>
            <el-button
              link
              :type="row.is_favorite ? 'warning' : 'default'"
              size="small"
              :icon="row.is_favorite ? StarFilled : Star"
              title="取消收藏"
              @click.stop="handleToggleFavorite(row.code)"
            />
          </template>
        </el-table-column>
      </el-table>

      <div v-if="rows.length > 0" class="table-footer">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          :total="total"
          @size-change="reload"
          @current-change="reload"
        />
      </div>
    </el-card>

    <!-- 股票详情抽屉（保留原有 K 线 + 公司信息）-->
    <el-drawer v-model="drawerVisible" size="520px" :with-header="false" :before-close="closeDrawer">
      <div class="stock-detail">
        <div class="detail-header">
          <div class="stock-info">
            <div class="stock-name">{{ stockInfo?.name || currentStock?.name || '-' }}</div>
            <div class="stock-code">{{ stockInfo?.ts_code || currentStock?.code }}</div>
          </div>
          <div class="header-actions">
            <el-button
              size="small"
              :type="currentStockIsFavorite ? 'warning' : 'primary'"
              :loading="drawerFavToggling"
              :icon="currentStockIsFavorite ? StarFilled : Star"
              @click="onDrawerToggleFavorite"
            >
              {{ currentStockIsFavorite ? '已收藏' : '加入收藏' }}
            </el-button>
            <el-button size="small" @click="closeDrawer">关闭</el-button>
          </div>
        </div>

        <el-divider />

        <el-skeleton v-if="drawerLoading" :rows="8" animated />
        <div v-else>
          <div class="section">
            <div class="section-head">
              <div class="section-title">归类信息</div>
              <el-button size="small" type="primary" plain @click="openOrganizerDialog(currentStock)">
                编辑归类
              </el-button>
            </div>
            <div class="drawer-chip-grid">
              <div class="drawer-chip-block">
                <div class="drawer-chip-label">分组</div>
                <div class="chip-cell">
                  <template v-if="currentStockGroups.length">
                    <el-tag v-for="group in currentStockGroups" :key="group.id" size="small" effect="plain">
                      {{ group.name }}
                    </el-tag>
                  </template>
                  <span v-else class="muted">-</span>
                </div>
              </div>
              <div class="drawer-chip-block">
                <div class="drawer-chip-label">标签</div>
                <div class="chip-cell">
                  <template v-if="currentStockTags.length">
                    <el-tag v-for="tag in currentStockTags" :key="tag.id" size="small" type="success" effect="plain">
                      {{ tag.name }}
                    </el-tag>
                  </template>
                  <span v-else class="muted">-</span>
                </div>
              </div>
            </div>
          </div>

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

          <div class="metadata">
            <span>数据来源: Tushare</span>
          </div>
        </div>
      </div>
    </el-drawer>

    <StockOrganizerPopover
      v-model="organizerVisible"
      :stock-code="organizerStock?.code || ''"
      :stock-name="organizerStock?.name || ''"
      :group-ids="organizerGroupIds"
      :tag-ids="organizerTagIds"
      :groups="groups"
      :tags="tags"
      :loading="organizerLoading"
      :saving="organizerSaving"
      @save="saveOrganizer"
    />

    <StockGroupManagerDialog
      v-model="groupManagerVisible"
      :groups="groups"
      :saving="groupManagerSaving"
      @create="handleCreateGroup"
      @update-group="handleUpdateGroup"
      @delete-group="handleDeleteGroup"
      @reorder-groups="handleReorderGroups"
    />

    <StockTagManagerDialog
      v-model="tagManagerVisible"
      :tags="tags"
      :saving="tagManagerSaving"
      @create="handleCreateTag"
      @delete-tag="handleDeleteTag"
    />

    <StockGroupAddStocksDialog
      v-model="addGroupStocksVisible"
      :group-name="activeGroupName"
      :results="addGroupStocksResults"
      :selected-codes="addGroupStocksSelectedCodes"
      :searching="addGroupStocksSearching"
      :submitting="addGroupStocksSubmitting"
      @search="searchStocksForGroup"
      @submit="submitAddGroupStocks"
    />

    <el-dialog v-model="noteDialogVisible" title="编辑备注" width="520px">
      <div class="note-dialog-stock">
        {{ noteStock?.name || '-' }}
        <span class="note-dialog-code">{{ noteStock?.code || '' }}</span>
      </div>
      <el-input
        v-model="noteDraft"
        type="textarea"
        :rows="5"
        maxlength="500"
        show-word-limit
        placeholder="写下你关注这只股票的原因，例如：英伟达GB300平台集成超级电容器"
      />
      <template #footer>
        <el-button @click="noteDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="noteSaving" @click="saveStockNote">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref, nextTick, computed, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Star, StarFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import StocksWorkbenchBar from '../components/StocksWorkbenchBar.vue'
import StockGroupAddStocksDialog from '../components/StockGroupAddStocksDialog.vue'
import StockOrganizerPopover from '../components/StockOrganizerPopover.vue'
import StockGroupManagerDialog from '../components/StockGroupManagerDialog.vue'
import StockTagManagerDialog from '../components/StockTagManagerDialog.vue'
import {
  listStocks, searchStocks, getStockKline, getStockInfo,
  getRealtimeQuotes, toggleFavorite, updateQuotesCache, getStockOrganizer, updateStockOrganizer, updateStockNote,
} from '../api/stocks'
import {
  addStockGroupMembers,
  createStockGroup,
  deleteStockGroup,
  listStockGroups,
  updateStockGroup,
} from '../api/stockGroups'
import {
  addStockTagBindings,
  createStockTag,
  deleteStockTag,
  listStockTags,
} from '../api/stockTags'

const route = useRoute()

// === 顶部搜索 ===
const q = ref('')
const searching = ref(false)
const searchResults = ref([])
let searchDebounceTimer = null

// === 主面板：收藏股票列表 ===
const loading = ref(false)
const rows = ref([])
const quotes = ref({})           // {code: {close, pct_chg, total_mv, circ_mv, turnover_rate}}
const quotesLoading = ref(false)
const cacheUpdating = ref(false)
const stocksTableRef = ref(null)
const selectedStocks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const sortState = ref({ prop: '', order: null })
const groups = ref([])
const tags = ref([])
const selectedGroupId = ref(null)
const selectedTagIds = ref([])
const ungroupedOnly = ref(false)
const organizerVisible = ref(false)
const organizerStock = ref(null)
const organizerGroupIds = ref([])
const organizerTagIds = ref([])
const organizerLoading = ref(false)
const organizerSaving = ref(false)
const groupManagerVisible = ref(false)
const tagManagerVisible = ref(false)
const groupManagerSaving = ref(false)
const tagManagerSaving = ref(false)
const batchGroupLoading = ref(false)
const batchTagLoading = ref(false)
const addGroupStocksVisible = ref(false)
const addGroupStocksSearching = ref(false)
const addGroupStocksSubmitting = ref(false)
const addGroupStocksResults = ref([])
const addGroupStocksSelectedCodes = ref([])
const noteDialogVisible = ref(false)
const noteSaving = ref(false)
const noteStock = ref(null)
const noteDraft = ref('')
let listReloadToken = 0

// === 抽屉详情 ===
const drawerVisible = ref(false)
const drawerLoading = ref(false)
const drawerFavToggling = ref(false)
const currentStock = ref(null)
const stockInfo = ref(null)
const klineData = ref([])
const klineDataCache = ref([])
const klineChartRef = ref(null)
let klineChart = null
const klineLoading = ref(false)
const klineError = ref('')
const selectedKline = ref(null)
const latestClose = ref(null)
const latestPctChg = ref(null)
const totalMarketValue = ref(null)
const circMarketValue = ref(null)

// 抽屉里"加入收藏"按钮的状态：rows 列表里有这个 code 就视为已收藏。
// 依赖 rows 而不是 currentStock.is_favorite，因为搜索结果里点开的股票
// rows 里可能没有，需要看主收藏列表当前状态。
const currentStockIsFavorite = computed(() => {
  const code = currentStock.value?.code
  if (!code) return false
  return rows.value.some(r => r.code === code && r.is_favorite)
})

const currentStockRow = computed(() => {
  const code = currentStock.value?.code
  if (!code) return null
  return rows.value.find(row => row.code === code) || null
})

const currentStockGroups = computed(() => currentStockRow.value?.groups || [])
const currentStockTags = computed(() => currentStockRow.value?.tags || [])
const activeGroupName = computed(() => {
  if (!selectedGroupId.value) return ''
  return groups.value.find(group => group.id === selectedGroupId.value)?.name || '按分组筛选'
})
const activeGroup = computed(() => {
  if (!selectedGroupId.value) return null
  return groups.value.find(group => group.id === selectedGroupId.value) || null
})

const marketTypeLabel = computed(() => {
  const market = stockInfo.value?.market
  if (!market) return '-'
  const map = {
    'main': '主板', '中小板': '中小板', '创业板': '创业板',
    '科创板': '科创板', '北交所': '北交所',
  }
  return map[market] || market
})

// 把 rows 和 quotes 合并展示
const rowsWithQuotes = computed(() => rows.value.map(row => ({
  ...row,
  quote: quotes.value[row.code] || {
    close: row.cache_close, pct_chg: row.cache_pct_chg,
    total_mv: row.cache_total_mv, circ_mv: row.cache_circ_mv,
    turnover_rate: row.cache_turnover_rate,
  },
})))

const sortedRowsWithQuotes = computed(() => {
  const items = [...rowsWithQuotes.value]
  const { prop, order } = sortState.value
  if (!prop || !order) return items

  const direction = order === 'ascending' ? 1 : -1
  return items.sort((left, right) => {
    const leftValue = getSortableValue(left, prop)
    const rightValue = getSortableValue(right, prop)

    const leftMissing = leftValue === null || leftValue === undefined
    const rightMissing = rightValue === null || rightValue === undefined
    if (leftMissing && rightMissing) return 0
    if (leftMissing) return 1
    if (rightMissing) return -1

    if (leftValue === rightValue) return 0
    return leftValue > rightValue ? direction : -direction
  })
})

// === 搜索 ===
function onSearchInput() {
  // 输入时防抖搜索，但不打扰主面板
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  if (!q.value || q.value.length < 1) {
    searchResults.value = []
    return
  }
  searchDebounceTimer = setTimeout(() => onSearch(), 350)
}

async function onSearch() {
  if (!q.value) {
    searchResults.value = []
    return
  }
  searching.value = true
  try {
    const resp = await searchStocks(q.value, 12)
    const results = resp?.data || []
    // 标注哪些已被收藏（让 ⭐ 显示金色）
    const favCodes = new Set(rows.value.filter(r => r.is_favorite).map(r => r.code))
    searchResults.value = results.map(r => ({ ...r, is_favorite: favCodes.has(r.code) }))
  } catch (e) {
    ElMessage.error(e?.message || '搜索失败')
  } finally {
    searching.value = false
  }
}

function clearSearch() {
  q.value = ''
  searchResults.value = []
}

function getSortableValue(row, prop) {
  if (prop === 'quote_close') return row.quote?.close
  if (prop === 'quote_pct_chg') return row.quote?.pct_chg
  return null
}

function handleTableSortChange({ prop, order }) {
  sortState.value = { prop: prop || '', order: order || null }
}

async function loadOrganizerMeta() {
  try {
    const [groupsResp, tagsResp] = await Promise.all([
      listStockGroups(),
      listStockTags(),
    ])
    groups.value = groupsResp?.data || []
    tags.value = tagsResp?.data || []
  } catch (e) {
    ElMessage.error(e?.message || '加载分组标签失败')
  }
}

// === 主面板：收藏股票列表 ===
async function reload() {
  const currentToken = ++listReloadToken
  loading.value = true
  try {
    const resp = await listStocks({
      page: page.value,
      page_size: pageSize.value,
      is_favorite: true,
      group_id: selectedGroupId.value || undefined,
      tag_ids: selectedTagIds.value.length ? selectedTagIds.value.join(',') : undefined,
      ungrouped_only: ungroupedOnly.value || undefined,
    })
    if (currentToken !== listReloadToken) return
    // axios 拦截器返回整个响应体（含 code/message/data/timestamp），
    // paginated() 把列表包在 data.items / data.total 里
    rows.value = resp?.data?.items || []
    total.value = resp?.data?.total || 0
    // 拉这些股票的实时行情
    await loadRealtimeQuotes(currentToken)
  } catch (e) {
    if (currentToken === listReloadToken) {
      ElMessage.error(e?.message || '加载失败')
    }
  } finally {
    if (currentToken === listReloadToken) {
      loading.value = false
    }
  }
}

async function loadRealtimeQuotes(requestToken = listReloadToken) {
  const codes = rows.value.map(r => r.code).filter(Boolean)
  if (codes.length === 0) return
  quotesLoading.value = true
  try {
    const resp = await getRealtimeQuotes(codes)
    if (requestToken !== listReloadToken) return
    const data = resp?.data || {}
    quotes.value = data
  } catch (e) {
    // 行情拉不到不致命，继续展示 cache_*
    console.warn('实时行情加载失败：', e?.message)
  } finally {
    if (requestToken === listReloadToken) {
      quotesLoading.value = false
    }
  }
}

function handleSelectionChange(selection) {
  selectedStocks.value = selection
}

function onTagFilterChange(value) {
  selectedTagIds.value = Array.isArray(value) ? value : []
  page.value = 1
  reload()
}

function onGroupScopeChange(payload) {
  selectedGroupId.value = payload?.groupId || null
  ungroupedOnly.value = !!payload?.ungroupedOnly
  page.value = 1
  reload()
}

async function handleBatchUpdateCache() {
  if (selectedStocks.value.length === 0) return
  cacheUpdating.value = true
  try {
    const codes = selectedStocks.value.map(s => s.code)
    const resp = await updateQuotesCache(codes)
    ElMessage.success(`已更新 ${resp?.data?.updated || resp?.data?.updated_count || codes.length} 只股票行情`)
    await reload()
    stocksTableRef.value?.clearSelection()
  } catch (e) {
    ElMessage.error(e?.message || '更新失败')
  } finally {
    cacheUpdating.value = false
  }
}

async function handleToggleFavorite(code) {
  try {
    await toggleFavorite(code)
    // 收藏状态切换后：
    //   - 如果原本在主面板（is_favorite=true）→ 现在变 false → 主面板移除
    //   - 如果原本不在主面板（搜索结果里）→ 现在变 true → 主面板出现
    // 简单粗暴：reload 主面板 + 同步搜索结果里的星标。
    await reload()
    if (searchResults.value.length > 0) {
      // 重新打字段，让 ⭐ 跟随收藏状态
      const favCodes = new Set(rows.value.filter(r => r.is_favorite).map(r => r.code))
      searchResults.value = searchResults.value.map(r => ({
        ...r, is_favorite: favCodes.has(r.code),
      }))
    }
    ElMessage.success('已更新')
  } catch (e) {
    ElMessage.error(e?.message || '操作失败')
  }
}

async function onDrawerToggleFavorite() {
  if (!currentStock.value?.code) return
  drawerFavToggling.value = true
  try {
    await toggleFavorite(currentStock.value.code)
    await reload()
    ElMessage.success(currentStockIsFavorite.value ? '已加入收藏' : '已取消收藏')
  } catch (e) {
    ElMessage.error(e?.message || '操作失败')
  } finally {
    drawerFavToggling.value = false
  }
}

async function openOrganizerDialog(row) {
  if (!row?.code) return
  organizerVisible.value = true
  organizerLoading.value = true
  organizerStock.value = { code: row.code, name: row.name || currentStock.value?.name || '' }
  organizerGroupIds.value = []
  organizerTagIds.value = []
  try {
    const resp = await getStockOrganizer(row.code)
    organizerGroupIds.value = resp?.data?.group_ids || []
    organizerTagIds.value = resp?.data?.tag_ids || []
  } catch (e) {
    ElMessage.error(e?.message || '加载归类信息失败')
  } finally {
    organizerLoading.value = false
  }
}

async function saveOrganizer(payload) {
  organizerSaving.value = true
  try {
    await updateStockOrganizer(payload.stockCode, {
      group_ids: payload.group_ids,
      tag_ids: payload.tag_ids,
    })
    ElMessage.success('归类已更新')
    organizerVisible.value = false
    await Promise.all([reload(), loadOrganizerMeta()])
  } catch (e) {
    ElMessage.error(e?.message || '更新归类失败')
  } finally {
    organizerSaving.value = false
  }
}

async function handleBatchAddGroup(groupId) {
  if (!selectedStocks.value.length) return
  const groupName = groups.value.find(group => group.id === groupId)?.name || '目标分组'
  batchGroupLoading.value = true
  try {
    const count = selectedStocks.value.length
    await addStockGroupMembers(groupId, selectedStocks.value.map(item => item.code))
    ElMessage.success(`已将 ${count} 只股票加入“${groupName}”`)
    await Promise.all([reload(), loadOrganizerMeta()])
    stocksTableRef.value?.clearSelection()
    selectedStocks.value = []
  } catch (e) {
    ElMessage.error(e?.message || '批量加入分组失败')
  } finally {
    batchGroupLoading.value = false
  }
}

async function handleBatchAddTag(tagId) {
  if (!selectedStocks.value.length) return
  const tagName = tags.value.find(tag => tag.id === tagId)?.name || '目标标签'
  batchTagLoading.value = true
  try {
    const count = selectedStocks.value.length
    await addStockTagBindings(tagId, selectedStocks.value.map(item => item.code))
    ElMessage.success(`已为 ${count} 只股票添加“${tagName}”`)
    await Promise.all([reload(), loadOrganizerMeta()])
    stocksTableRef.value?.clearSelection()
    selectedStocks.value = []
  } catch (e) {
    ElMessage.error(e?.message || '批量添加标签失败')
  } finally {
    batchTagLoading.value = false
  }
}

async function handleCreateGroup(payload) {
  groupManagerSaving.value = true
  try {
    await createStockGroup(payload)
    ElMessage.success('分组已创建')
    await loadOrganizerMeta()
  } catch (e) {
    ElMessage.error(e?.message || '创建分组失败')
  } finally {
    groupManagerSaving.value = false
  }
}

async function handleUpdateGroup({ groupId, payload }) {
  groupManagerSaving.value = true
  try {
    await updateStockGroup(groupId, payload)
    ElMessage.success('分组已更新')
    await Promise.all([loadOrganizerMeta(), reload()])
  } catch (e) {
    ElMessage.error(e?.message || '更新分组失败')
  } finally {
    groupManagerSaving.value = false
  }
}

async function handleReorderGroups(groupIds) {
  const reorderedGroups = groupIds
    .map(groupId => groups.value.find(group => group.id === groupId))
    .filter(Boolean)
  if (reorderedGroups.length !== groups.value.length) return

  groups.value = reorderedGroups
  groupManagerSaving.value = true
  try {
    const changedGroups = reorderedGroups.filter((group, index) => Number(group.sort_order || 0) !== index + 1)
    if (changedGroups.length === 0) return

    await Promise.all(changedGroups.map((group, index) => {
      const nextSortOrder = reorderedGroups.findIndex(item => item.id === group.id) + 1
      return updateStockGroup(group.id, { sort_order: nextSortOrder })
    }))

    ElMessage.success('分组顺序已更新')
    await Promise.all([loadOrganizerMeta(), reload()])
  } catch (e) {
    ElMessage.error(e?.message || '调整分组顺序失败')
    await loadOrganizerMeta()
  } finally {
    groupManagerSaving.value = false
  }
}

async function handleDeleteGroup(groupId) {
  groupManagerSaving.value = true
  try {
    await deleteStockGroup(groupId)
    if (selectedGroupId.value === groupId) {
      selectedGroupId.value = null
    }
    ElMessage.success('分组已删除')
    await Promise.all([loadOrganizerMeta(), reload()])
  } catch (e) {
    ElMessage.error(e?.message || '删除分组失败')
  } finally {
    groupManagerSaving.value = false
  }
}

async function handleCreateTag(payload) {
  tagManagerSaving.value = true
  try {
    await createStockTag(payload)
    ElMessage.success('标签已创建')
    await loadOrganizerMeta()
  } catch (e) {
    ElMessage.error(e?.message || '创建标签失败')
  } finally {
    tagManagerSaving.value = false
  }
}

async function handleDeleteTag(tagId) {
  tagManagerSaving.value = true
  try {
    await deleteStockTag(tagId)
    selectedTagIds.value = selectedTagIds.value.filter(item => item !== tagId)
    ElMessage.success('标签已删除')
    await Promise.all([loadOrganizerMeta(), reload()])
  } catch (e) {
    ElMessage.error(e?.message || '删除标签失败')
  } finally {
    tagManagerSaving.value = false
  }
}

function openAddGroupStocksDialog() {
  if (!activeGroup.value) {
    ElMessage.info('请先选择一个分组')
    return
  }
  addGroupStocksVisible.value = true
  addGroupStocksResults.value = []
  addGroupStocksSelectedCodes.value = []
}

async function searchStocksForGroup(keyword) {
  const query = String(keyword || '').trim()
  if (!query) {
    addGroupStocksResults.value = []
    return
  }
  addGroupStocksSearching.value = true
  try {
    const resp = await searchStocks(query, 20)
    addGroupStocksResults.value = resp?.data || []
  } catch (e) {
    ElMessage.error(e?.message || '搜索股票失败')
  } finally {
    addGroupStocksSearching.value = false
  }
}

async function submitAddGroupStocks(stockCodes) {
  if (!activeGroup.value || !stockCodes?.length) return
  addGroupStocksSubmitting.value = true
  try {
    await addStockGroupMembers(activeGroup.value.id, stockCodes)
    ElMessage.success(`已将 ${stockCodes.length} 只股票加入“${activeGroup.value.name}”`)
    addGroupStocksVisible.value = false
    addGroupStocksResults.value = []
    addGroupStocksSelectedCodes.value = []
    await Promise.all([reload(), loadOrganizerMeta()])
  } catch (e) {
    ElMessage.error(e?.message || '添加股票到分组失败')
  } finally {
    addGroupStocksSubmitting.value = false
  }
}

function openNoteDialog(row) {
  if (!row?.code) return
  noteStock.value = { code: row.code, name: row.name || '' }
  noteDraft.value = row.note || ''
  noteDialogVisible.value = true
}

async function saveStockNote() {
  if (!noteStock.value?.code) return
  noteSaving.value = true
  try {
    const normalizedNote = String(noteDraft.value || '').trim()
    await updateStockNote(noteStock.value.code, { note: normalizedNote })

    rows.value = rows.value.map((row) => (
      row.code === noteStock.value.code
        ? { ...row, note: normalizedNote }
        : row
    ))

    if (currentStock.value?.code === noteStock.value.code) {
      currentStock.value = {
        ...currentStock.value,
        note: normalizedNote,
      }
    }

    noteDialogVisible.value = false
    ElMessage.success(normalizedNote ? '备注已保存' : '备注已清空')
  } catch (e) {
    ElMessage.error(e?.message || '保存备注失败')
  } finally {
    noteSaving.value = false
  }
}

// === 抽屉详情 ===
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
    const infoResp = await getStockInfo(row.code)
    stockInfo.value = infoResp?.data || null
    await loadKlineData()
  } catch (e) {
    ElMessage.error(e?.message || '获取数据失败')
  } finally {
    drawerLoading.value = false
  }
}

function closeDrawer() {
  drawerVisible.value = false
  if (klineChart) {
    klineChart.dispose()
    klineChart = null
  }
}

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
    const latest = klineData.value[klineData.value.length - 1]
    if (latest) {
      latestClose.value = latest.close
      latestPctChg.value = latest.pct_chg
      totalMarketValue.value = latest.total_mv
      circMarketValue.value = latest.circ_mv
    }
    await nextTick()
    setTimeout(() => renderKlineChart(), 100)
  } catch (e) {
    klineError.value = e?.message || '获取K线数据失败'
  } finally {
    klineLoading.value = false
  }
}

function renderKlineChart() {
  if (!klineChartRef.value || klineData.value.length === 0) return
  if (klineChart) klineChart.dispose()
  klineChart = echarts.init(klineChartRef.value)

  const dates = klineData.value.map(d => {
    const dateStr = String(d.date)
    return dateStr.length === 8 ? `${dateStr.slice(4, 6)}/${dateStr.slice(6, 8)}` : dateStr
  })
  const ohlc = klineData.value.map(d => [d.open, d.close, d.low, d.high])
  const volumes = klineData.value.map(d => d.volume)

  const option = {
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', label: { show: false } },
      formatter(params) {
        const kline = params.find(p => p.seriesName === 'K线')
        if (!kline) return ''
        const idx = kline.dataIndex
        const d = klineDataCache.value[idx]
        if (!d) return ''
        const color = d.close >= d.open ? '#ef4444' : '#22c55e'
        const dateStr = String(d.date)
        const formattedDate = dateStr.length === 8
          ? `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}` : dateStr
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
      },
    },
    grid: [
      { left: '8%', right: '8%', top: '5%', height: '60%' },
      { left: '8%', right: '8%', top: '72%', height: '20%' },
    ],
    xAxis: [
      { type: 'category', data: dates, axisLabel: { fontSize: 10 } },
      { type: 'category', gridIndex: 1, data: dates, axisLabel: { show: false } },
    ],
    yAxis: [
      { scale: true, axisLabel: { fontSize: 10 } },
      { gridIndex: 1, scale: true, axisLabel: { fontSize: 10 } },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', data: ohlc,
        itemStyle: {
          color: '#ef4444', color0: '#22c55e',
          borderColor: '#ef4444', borderColor0: '#22c55e',
        },
      },
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumes,
        itemStyle: {
          color(params) {
            const d = klineDataCache.value[params.dataIndex]
            return d && d.close >= d.open ? '#ef4444' : '#22c55e'
          },
        },
      },
    ],
  }

  klineChart.setOption(option)
  klineChart.on('click', function (params) {
    if (params.seriesName !== 'K线') return
    const d = klineDataCache.value[params.dataIndex]
    if (!d) return
    const dateStr = String(d.date)
    const formattedDate = dateStr.length === 8
      ? `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}` : dateStr
    selectedKline.value = {
      date: formattedDate, open: d.open, high: d.high, low: d.low, close: d.close,
      pctChg: d.pct_chg, turnoverRate: d.turnover_rate ? d.turnover_rate.toFixed(2) : '-',
    }
  })
}

watch(drawerVisible, (visible) => {
  if (!visible && klineChart) {
    klineChart.dispose()
    klineChart = null
  }
})

// === 工具函数 ===
function formatMarketValue(val) {
  if (!val) return '-'
  // val 单位：万元
  if (val >= 10000) return `${(val / 10000).toFixed(2)}亿`
  return `${val.toFixed(2)}万`
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const s = String(dateStr)
  if (s.length === 8) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
  return s
}

// === 路由跳转兼容：从其他页面带 code 跳过来时自动开抽屉 ===
async function handleRouteQuery() {
  const code = route.query.code
  const name = route.query.name || ''
  const open = route.query.open
  if (code && open === 'detail') {
    openStockDrawer({ code, name })
  }
}

onMounted(async () => {
  await Promise.all([reload(), loadOrganizerMeta()])
  await handleRouteQuery()
})

watch(() => route.query, () => {
  handleRouteQuery()
})

onUnmounted(() => {
  if (klineChart) {
    klineChart.dispose()
    klineChart = null
  }
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
})
</script>

<style scoped>
.stocks-page {
  min-height: 100vh;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: var(--el-bg-color-page);
}

.page-header-card,
.favorites-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 22px;
  background: linear-gradient(180deg, var(--el-bg-color) 0%, var(--el-fill-color-blank) 100%);
  box-shadow: 0 18px 42px rgba(148, 163, 184, 0.08);
}

.page-header-card :deep(.el-card__body),
.favorites-card :deep(.el-card__body) {
  padding: 18px 18px 16px;
}

.favorites-card :deep(.el-card__header) {
  padding: 18px 18px 12px;
  border-bottom-color: var(--el-border-color-lighter);
}

.page-header {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 标题 + 状态 tag + 搜索框 融合到同一行 */
.page-header-main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.page-title {
  font-size: 21px;
  font-weight: 800;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

.page-subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}

.page-status {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.page-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* 搜索框：在融合行里靠右、自适应宽度 */
.search-row {
  display: flex;
  flex: 1 1 320px;
  min-width: 240px;
  max-width: 520px;
  margin-left: auto;
}

.search-input {
  width: 100%;
}

/* 搜索结果：紧贴搜索框下方，属于同一块，不再有独立间距 */
.search-results-panel {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
  overflow: hidden;
}

.search-results-header {
  padding: 8px 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-results-list {
  max-height: 280px;
  overflow-y: auto;
}

.search-result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.search-result-item:last-child {
  border-bottom: none;
}

.search-result-item:hover {
  background: var(--el-color-primary-light-9);
}

.result-main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.result-code {
  font-weight: 700;
  font-size: 13px;
  color: var(--el-color-primary);
}

.result-name {
  color: var(--el-text-color-regular);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 主面板 */
.favorites-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.favorites-title {
  font-weight: 800;
  font-size: 15px;
}

.favorites-count {
  margin-left: 10px;
  font-size: 13px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
}

.favorites-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.favorites-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.favorites-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.summary-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.code-cell {
  color: var(--el-color-primary);
  font-weight: 600;
  cursor: pointer;
}

.muted {
  color: var(--el-text-color-disabled);
}

.limit-up-cell {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.limit-up-date {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.chip-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.chip-more {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.note-cell {
  display: block;
  width: 100%;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  font-size: 13px;
  line-height: 1.5;
  color: var(--el-text-color-regular);
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.note-cell.is-empty {
  color: var(--el-color-primary);
}

.note-cell:hover {
  color: var(--el-color-primary);
}

.note-dialog-stock {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.note-dialog-code {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
}

.table-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.empty-text {
  text-align: center;
}

@media (max-width: 900px) {
  .stocks-page {
    padding: 12px;
  }

  /* 窄屏下融合行换行：标题/tag 一行，搜索框独占下一行 */
  .page-header-main {
    flex-direction: column;
    align-items: stretch;
  }

  .search-row {
    margin-left: 0;
    max-width: none;
  }
}

/* === 抽屉样式（保留原有设计） === */
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
  color: var(--el-text-color-secondary);
  font-size: 13px;
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
  font-size: 20px;
  font-weight: 800;
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
  margin-bottom: 8px;
}

.kline-info-bar {
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  font-size: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
}

.kline-date {
  font-weight: 700;
}

.kline-item .high { color: #ef4444; }
.kline-item .low { color: #22c55e; }
.kline-item.up b { color: #ef4444; }
.kline-item.down b { color: #22c55e; }

.chart-container {
  position: relative;
  height: 320px;
}

.chart {
  width: 100%;
  height: 100%;
}

.chart-error {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-light);
}

.section {
  margin-top: 16px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.section-title {
  font-weight: 700;
  margin-bottom: 8px;
  font-size: 14px;
}

.drawer-chip-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.drawer-chip-block {
  padding: 12px;
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
}

.drawer-chip-label {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}

.business-content {
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
  max-height: 200px;
  overflow-y: auto;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.intro-content {
  max-height: 240px;
}

.metadata {
  margin-top: 16px;
  font-size: 11px;
  color: var(--el-text-color-disabled);
  text-align: right;
}
</style>
