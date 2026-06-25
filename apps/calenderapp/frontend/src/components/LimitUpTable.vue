<template>
  <el-card shadow="never" class="card">
    <template #header>
      <div style="display: flex; align-items: center; justify-content: space-between">
        <span style="font-weight: 700">涨停股列表</span>
        <div style="display: flex; align-items: center; gap: 8px">
          <el-button size="small" type="primary" :loading="batchUpdating" :disabled="selectedCount === 0" @click="$emit('batch-update')">
            批量更新{{ selectedCount > 0 ? ` (${selectedCount})` : '' }}
          </el-button>
          <el-button size="small" @click="loadFavorites" :loading="favoritesLoading">
            <el-icon><Star /></el-icon>
            同步收藏
          </el-button>
          <el-button size="small" :loading="loading" @click="$emit('refresh')">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>
    </template>

    <el-table
      class="limit-up-table"
      :data="rows" 
      v-loading="loading" 
      style="width: 100%" 
      @selection-change="onSelectionChange"
      @row-click="(row) => $emit('select', row)"
    >
      <el-table-column type="selection" width="55" />
      <el-table-column prop="stock_code" label="代码" width="110" />
      <el-table-column prop="stock_name" label="名称" min-width="90" />
      <el-table-column label="价格" width="108" align="right">
        <template #header>
          <el-dropdown trigger="click" @command="handlePriceFilterCommand">
            <span
              class="column-filter-label"
              :class="{ 'column-filter-label--active': isPriceFilterActive }"
              @click.stop
            >
              价格
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="all">全部</el-dropdown-item>
                <el-dropdown-item command="lte30">&lt;=30</el-dropdown-item>
                <el-dropdown-item command="gt30">&gt;30</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template #default="{ row }">
          <span style="color: #f56c6c; font-weight: 600">{{ row.close ? row.close.toFixed(2) : '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="换手率" width="85" align="right">
        <template #default="{ row }">
          <span :style="{ color: row.turnover_rate > 20 ? '#f56c6c' : row.turnover_rate > 10 ? '#e6a23c' : '#606266' }">
            {{ row.turnover_rate ? row.turnover_rate.toFixed(2) + '%' : '-' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="量比" width="70" align="right">
        <template #default="{ row }">
          <span :style="{ color: row.volume_ratio > 5 ? '#f56c6c' : row.volume_ratio > 2 ? '#e6a23c' : '#606266', fontWeight: row.volume_ratio > 2 ? '600' : 'normal' }">
            {{ row.volume_ratio ? row.volume_ratio.toFixed(2) : '-' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="连板" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="consecutiveTagType(row.consecutive_days)" size="small">
            {{ row.consecutive_days }}板
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="强度" width="90" align="center">
        <template #default="{ row }">
          <span v-for="i in row.strength_level" :key="i" style="color: #f59e0b; font-size: 12px">★</span>
        </template>
      </el-table-column>
      <el-table-column label="封单" width="90">
        <template #default="{ row }">
          {{ formatAmount(row.seal_amount) }}
        </template>
      </el-table-column>
      <el-table-column prop="first_limit_time" label="封板时间" width="90" />
      <el-table-column label="开板" width="100" align="center">
        <template #header>
          <el-dropdown trigger="click" @command="handleOpenCountFilterCommand">
            <span
              class="column-filter-label"
              :class="{ 'column-filter-label--active': isOpenCountFilterActive }"
              @click.stop
            >
              开板
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="all">全部</el-dropdown-item>
                <el-dropdown-item command="flat">一字</el-dropdown-item>
                <el-dropdown-item command="lte3">&lt;=3</el-dropdown-item>
                <el-dropdown-item command="gt3">&gt;3</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template #default="{ row }">
          <el-tag v-if="row.open_count === 0" type="success" size="small">一字</el-tag>
          <el-tag v-else :type="row.open_count <= 2 ? 'warning' : 'danger'" size="small">
            {{ row.open_count }}次
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="industry" label="行业" width="90" />
      <el-table-column label="资金" width="100">
        <template #default="{ row }">
          <div style="font-size: 12px; line-height: 1.4">
            <div v-if="row.institution_net_buy > 0" style="color: #3b82f6">
              机构 {{ formatAmount(row.institution_net_buy) }}
            </div>
            <div v-if="row.hot_money_net_buy > 0" style="color: #10b981">
              游资 {{ formatAmount(row.hot_money_net_buy) }}
            </div>
            <div v-if="!row.institution_net_buy && !row.hot_money_net_buy">-</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="118" fixed="right">
        <template #default="{ row }">
          <div style="display: flex; align-items: center; gap: 4px">
            <el-button
              link
              :type="isFavorite(row.stock_code) ? 'warning' : 'default'"
              size="small"
              @click.stop="handleToggleFavorite(row)"
              :icon="isFavorite(row.stock_code) ? StarFilled : Star"
              title="收藏"
            />
            <template v-if="row.has_analysis_report">
              <el-button
                type="primary"
                link
                size="small"
                title="查看事件与原报告"
                aria-label="查看事件与原报告"
                @click.stop="$emit('stockkb', row)"
              >
                事件
              </el-button>
            </template>
            <template v-else>
              <el-button
                type="danger"
                link
                size="small"
                disabled
                class="analysis-unavailable"
                title="MinIO 中暂无 Markdown 报告"
                aria-label="MinIO 中暂无 Markdown 报告"
                @click.stop
              >
                事件
              </el-button>
            </template>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div style="margin-top: 16px; display: flex; justify-content: flex-end">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @size-change="(val) => $emit('page-change', currentPage, val)"
        @current-change="(val) => $emit('page-change', val, pageSize)"
      />
    </div>
  </el-card>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { Refresh, Star, StarFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { listFavorites, toggleFavorite, upsertStock } from '../api/stocks'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  filters: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSizeProp: { type: Number, default: 20 },
  selectedCount: { type: Number, default: 0 },
  batchUpdating: { type: Boolean, default: false }
})

const emit = defineEmits(['select', 'stockkb', 'refresh', 'page-change', 'selection-change', 'batch-update', 'update:filters'])

const currentPage = ref(props.page)
const pageSize = ref(props.pageSizeProp)
const favoritesSet = ref(new Set())
const favoritesLoading = ref(false)
const isPriceFilterActive = computed(() => {
  const minValue = props.filters?.close_min
  const maxValue = props.filters?.close_max
  return !(
    (minValue === null || minValue === undefined || minValue === '') &&
    (maxValue === null || maxValue === undefined || maxValue === '')
  )
})
const isOpenCountFilterActive = computed(() => {
  const minValue = props.filters?.open_count_min
  const maxValue = props.filters?.open_count_max
  return !(
    (minValue === null || minValue === undefined || minValue === '') &&
    (maxValue === null || maxValue === undefined || maxValue === '')
  )
})

watch(() => props.page, (val) => { currentPage.value = val })
watch(() => props.pageSizeProp, (val) => { pageSize.value = val })

// 加载收藏列表
async function loadFavorites() {
  favoritesLoading.value = true
  try {
    const resp = await listFavorites()
    const favorites = resp?.data || []
    favoritesSet.value = new Set(favorites.map(f => {
      // 处理代码格式 (去掉.SH/.SZ后缀)
      const code = f.code || ''
      return code.split('.')[0]
    }))
  } catch (e) {
    console.error('加载收藏失败:', e)
  } finally {
    favoritesLoading.value = false
  }
}

// 判断是否收藏
function isFavorite(code) {
  const pureCode = code?.split('.')[0] || code
  return favoritesSet.value.has(pureCode)
}

// 切换收藏状态
async function handleToggleFavorite(row) {
  try {
    const code = row.stock_code
    
    // 如果股票不在库中，先添加
    if (!isFavorite(code)) {
      try {
        await upsertStock({
          code: code,
          name: row.stock_name,
          exchange: code.startsWith('6') ? 'SH' : 'SZ'
        })
      } catch (e) {
        // 忽略已存在的错误
      }
    }
    
    await toggleFavorite(code)
    
    // 更新本地状态
    const pureCode = code?.split('.')[0] || code
    if (favoritesSet.value.has(pureCode)) {
      favoritesSet.value.delete(pureCode)
      ElMessage.success('已取消收藏')
    } else {
      favoritesSet.value.add(pureCode)
      ElMessage.success('已添加收藏')
    }
  } catch (e) {
    ElMessage.error(e?.message || '操作失败')
  }
}

function consecutiveTagType(days) {
  if (days >= 5) return 'danger'
  if (days >= 3) return 'warning'
  return 'primary'
}

function formatAmount(amount) {
  if (!amount) return '-'
  const yi = amount / 100000000
  if (yi >= 1) return `${yi.toFixed(2)}亿`
  const wan = amount / 10000
  return `${wan.toFixed(0)}万`
}

function onSelectionChange(selection) {
  emit('selection-change', selection)
}

function updateFilters(patch) {
  emit('update:filters', patch)
}

function handlePriceFilterCommand(command) {
  if (command === 'all') {
    updateFilters({ close_min: null, close_max: null })
    return
  }
  if (command === 'lte30') {
    updateFilters({ close_min: null, close_max: 30 })
    return
  }
  updateFilters({ close_min: 30, close_max: null })
}

function handleOpenCountFilterCommand(command) {
  if (command === 'all') {
    updateFilters({ open_count_min: null, open_count_max: null })
    return
  }
  if (command === 'flat') {
    updateFilters({ open_count_min: null, open_count_max: 0 })
    return
  }
  if (command === 'lte3') {
    updateFilters({ open_count_min: null, open_count_max: 3 })
    return
  }
  updateFilters({ open_count_min: 3, open_count_max: null })
}

onMounted(() => {
  loadFavorites()
})
</script>

<style scoped>
.card {
  min-height: 400px;
}

.column-filter-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 22px;
  padding: 1px 6px;
  border: 1px solid transparent;
  border-radius: 4px;
  box-sizing: border-box;
  vertical-align: middle;
  color: var(--el-table-header-text-color, var(--el-text-color-secondary));
  font: inherit;
  font-weight: 600;
  line-height: inherit;
  cursor: pointer;
}

.column-filter-label--active {
  border-color: transparent;
}

.analysis-unavailable.is-disabled {
  color: #ef4444 !important;
  opacity: 1 !important;
  cursor: not-allowed;
}

:deep(.limit-up-table .el-table-fixed-column--right.is-first-column::before) {
  box-shadow: none !important;
}
</style>
