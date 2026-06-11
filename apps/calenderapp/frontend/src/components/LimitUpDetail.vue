<template>
  <div class="limit-up-detail">
    <div class="detail-header">
      <div class="stock-info">
        <div class="stock-name">{{ item.stock_name }}</div>
        <div class="stock-code">{{ item.stock_code }}</div>
      </div>
      <div class="header-actions">
        <el-button type="primary" size="small" @click="emit('edit', item)">编辑</el-button>
        <el-button size="small" @click="emit('close')">关闭</el-button>
      </div>
    </div>

    <el-divider />

    <!-- 走势分析切换 -->
    <div class="chart-section">
      <div class="chart-header">
        <el-radio-group v-model="chartType" size="small" @change="onChartTypeChange">
          <el-radio-button label="kline">90日K线</el-radio-button>
          <el-radio-button label="intraday">分时线 (当日)</el-radio-button>
        </el-radio-group>
        <el-button size="small" :loading="chartLoading" @click="loadChartData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
      
      <!-- 点击K线显示的信息 -->
      <div v-if="selectedKline" class="kline-info-bar">
        <span class="kline-date">{{ selectedKline.date }}</span>
        <span class="kline-item">开: <b>{{ selectedKline.open }}</b></span>
        <span class="kline-item">高: <b class="high">{{ selectedKline.high }}</b></span>
        <span class="kline-item">低: <b class="low">{{ selectedKline.low }}</b></span>
        <span class="kline-item">收: <b>{{ selectedKline.close }}</b></span>
        <span class="kline-item" :class="{ up: selectedKline.pctChg > 0, down: selectedKline.pctChg < 0 }">
          涨跌: <b>{{ selectedKline.pctChg > 0 ? '+' : '' }}{{ selectedKline.pctChg }}%</b>
        </span>
        <span class="kline-item">换手: <b>{{ selectedKline.turnoverRate }}%</b></span>
      </div>
      
      <div class="chart-container" v-loading="chartLoading">
        <div v-if="chartType === 'kline'" ref="klineChart" class="chart"></div>
        <div v-else ref="intradayChart" class="chart"></div>
        <div v-if="chartError" class="chart-error">
          <el-empty :description="chartError" :image-size="80" />
        </div>
      </div>
    </div>

    <el-divider />

    <!-- 核心指标 -->
    <div class="core-metrics">
      <div class="metric-item">
        <div class="metric-value">{{ item.consecutive_days }}</div>
        <div class="metric-label">连板</div>
      </div>
      <div class="metric-item">
        <div class="metric-value stars">
          <span v-for="i in item.strength_level" :key="i">★</span>
        </div>
        <div class="metric-label">强度</div>
      </div>
      <div class="metric-item">
        <div class="metric-value">{{ formatAmount(item.seal_amount) }}</div>
        <div class="metric-label">封单</div>
      </div>
      <div class="metric-item">
        <div class="metric-value">{{ item.first_limit_time || '-' }}</div>
        <div class="metric-label">封板时间</div>
      </div>
    </div>

    <!-- 详细信息 -->
    <el-descriptions :column="2" border size="small" class="detail-info">
      <el-descriptions-item label="涨停日期">{{ item.limit_up_date }}</el-descriptions-item>
      <el-descriptions-item label="涨停类型">{{ limitUpTypeLabel }}</el-descriptions-item>
      <el-descriptions-item label="开板次数">{{ item.open_count === 0 ? '一字板' : item.open_count + '次' }}</el-descriptions-item>
      <el-descriptions-item label="换手率">{{ item.turnover_rate ? item.turnover_rate + '%' : '-' }}</el-descriptions-item>
      <el-descriptions-item label="所属行业">{{ item.industry || '-' }}</el-descriptions-item>
      <el-descriptions-item label="封单比">{{ item.seal_ratio ? item.seal_ratio.toFixed(2) + '%' : '-' }}</el-descriptions-item>
    </el-descriptions>

    <!-- 概念标签 -->
    <div v-if="item.concept_tags?.length" class="section">
      <div class="section-title">概念标签</div>
      <div class="concept-tags">
        <el-tag v-for="tag in item.concept_tags" :key="tag" size="small">{{ tag }}</el-tag>
      </div>
    </div>

    <!-- 资金动向 -->
    <div class="section">
      <div class="section-title">资金动向</div>
      <div class="fund-flow">
        <div class="fund-item" :class="{ positive: item.institution_net_buy > 0 }">
          <span class="fund-label">机构净买</span>
          <span class="fund-value">{{ formatAmount(item.institution_net_buy) }}</span>
        </div>
        <div class="fund-item" :class="{ positive: item.hot_money_net_buy > 0 }">
          <span class="fund-label">游资净买</span>
          <span class="fund-value">{{ formatAmount(item.hot_money_net_buy) }}</span>
        </div>
        <div class="fund-item" :class="{ positive: item.north_net_buy > 0 }">
          <span class="fund-label">北向资金</span>
          <span class="fund-value">{{ formatAmount(item.north_net_buy) }}</span>
        </div>
        <div class="fund-item total" :class="{ positive: item.total_net_buy > 0 }">
          <span class="fund-label">合计净买</span>
          <span class="fund-value">{{ formatAmount(item.total_net_buy) }}</span>
        </div>
      </div>
    </div>

    <!-- 涨停原因 -->
    <div v-if="item.reason_detail" class="section">
      <div class="section-title">涨停原因</div>
      <div class="reason-content">
        <el-tag v-if="item.reason_category" size="small" type="info" style="margin-bottom: 8px">
          {{ reasonCategoryLabel }}
        </el-tag>
        <div class="reason-text">{{ item.reason_detail }}</div>
      </div>
    </div>

    <!-- 龙头标识 -->
    <div v-if="item.is_dragon_head" class="dragon-badge">
      <span>🐉 空间龙头 #{{ item.dragon_rank }}</span>
    </div>

    <!-- 元数据 -->
    <div class="metadata">
      <span>数据来源: {{ item.source }}</span>
      <span>创建时间: {{ formatTime(item.created_at) }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, nextTick, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getLimitUpKline, getLimitUpIntraday } from '../api/limitUp'

const props = defineProps({
  item: { type: Object, required: true }
})

const emit = defineEmits(['edit', 'close'])

// 图表相关
const chartType = ref('kline')
const chartLoading = ref(false)
const chartError = ref('')
const klineChart = ref(null)
const intradayChart = ref(null)
let klineInstance = null
let intradayInstance = null
let klineDataCache = []  // 缓存K线数据
const selectedKline = ref(null)  // 选中的K线信息

const limitUpTypeLabel = computed(() => {
  const map = {
    'first_board': '首板',
    'multi_board': '连板',
    'broken_board': '炸板'
  }
  return map[props.item.limit_up_type] || props.item.limit_up_type
})

const reasonCategoryLabel = computed(() => {
  const map = {
    'concept': '概念催化',
    'fund': '资金推动',
    'announcement': '公告利好',
    'technical': '技术反弹',
    'event': '事件驱动'
  }
  return map[props.item.reason_category] || props.item.reason_category
})

function onChartTypeChange() {
  chartError.value = ''
  loadChartData()
}

async function loadChartData() {
  if (!props.item.id) return
  
  chartLoading.value = true
  chartError.value = ''
  
  try {
    if (chartType.value === 'kline') {
      await loadKlineData()
    } else {
      await loadIntradayData()
    }
  } catch (e) {
    chartError.value = e?.message || '加载失败'
  } finally {
    chartLoading.value = false
  }
}

async function loadKlineData() {
  // 传入涨停日期，解决分区表ID冲突问题
  const resp = await getLimitUpKline(props.item.id, props.item.limit_up_date, 90)
  if (resp?.code !== 200 || !resp?.data?.kline?.length) {
    chartError.value = resp?.message || '暂无K线数据'
    return
  }
  
  const data = resp.data
  klineDataCache = data.kline  // 缓存数据
  selectedKline.value = null  // 重置选中状态
  await nextTick()
  
  if (klineChart.value) {
    if (klineInstance) klineInstance.dispose()
    klineInstance = echarts.init(klineChart.value)
    
    // 格式化日期为 MM/DD 格式
    const dates = data.kline.map(d => {
      const dateStr = String(d.date)
      return dateStr.length === 8 ? `${dateStr.slice(4,6)}/${dateStr.slice(6,8)}` : dateStr
    })
    const ohlc = data.kline.map(d => [d.open, d.close, d.low, d.high])
    const volumes = data.kline.map(d => d.volume)
    const pctChgs = data.kline.map(d => d.pct_chg)
    
    klineInstance.setOption({
      animation: false,
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', label: { show: false } },
        formatter: function(params) {
          const kline = params.find(p => p.seriesName === 'K线')
          if (!kline) return ''
          const idx = kline.dataIndex
          const d = klineDataCache[idx]
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
        { 
          scale: true, 
          gridIndex: 1, 
          splitLine: { show: false },
          axisLabel: { show: false },
          axisTick: { show: false },
          axisLine: { show: false }
        }
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
    })
    
    // 添加点击事件
    klineInstance.on('click', function(params) {
      if (params.seriesName === 'K线') {
        const dataIndex = params.dataIndex
        const klineItem = klineDataCache[dataIndex]
        if (klineItem) {
          const dateStr = klineItem.date
          selectedKline.value = {
            date: dateStr.length === 8 
              ? `${dateStr.slice(0,4)}-${dateStr.slice(4,6)}-${dateStr.slice(6,8)}` 
              : dateStr,
            open: klineItem.open,
            high: klineItem.high,
            low: klineItem.low,
            close: klineItem.close,
            pctChg: klineItem.pct_chg,
            turnoverRate: klineItem.turnover_rate ? klineItem.turnover_rate.toFixed(2) : '-'
          }
        }
      }
    })
  }
}

async function loadIntradayData() {
  // 传入涨停日期，解决分区表ID冲突问题
  const resp = await getLimitUpIntraday(props.item.id, props.item.limit_up_date)
  if (resp?.code !== 200) {
    chartError.value = resp?.message || '暂无分时数据'
    return
  }
  
  const data = resp.data
  
  if (!data.intraday?.length) {
    chartError.value = data.message || '暂无分时数据（需专业版权限）'
    return
  }
  
  await nextTick()
  
  if (intradayChart.value) {
    if (intradayInstance) intradayInstance.dispose()
    intradayInstance = echarts.init(intradayChart.value)
    
    const times = data.intraday.map(d => d.time?.slice(8) || '')
    const prices = data.intraday.map(d => d.price)
    const limitUpPrice = data.limit_up_price
    
    const series = [
      {
        name: '分时价格',
        type: 'line',
        data: prices,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1.5 },
        areaStyle: { opacity: 0.1 }
      }
    ]
    
    // 涨停价线
    if (limitUpPrice) {
      series.push({
        name: '涨停价',
        type: 'line',
        data: Array(times.length).fill(limitUpPrice),
        lineStyle: { type: 'dashed', color: '#ef4444', width: 1 },
        symbol: 'none'
      })
    }
    
    intradayInstance.setOption({
      title: {
        show: false
      },
      tooltip: {
        trigger: 'axis',
        formatter: '{b}<br/>价格: {c}'
      },
      grid: { left: '10%', right: '5%', top: '15%', bottom: '15%' },
      xAxis: {
        type: 'category',
        data: times,
        axisLabel: { fontSize: 10, interval: 59 }
      },
      yAxis: {
        type: 'value',
        scale: true,
        splitLine: { lineStyle: { type: 'dashed' } }
      },
      series
    })
  }
}

function formatAmount(amount) {
  if (!amount) return '-'
  const yi = amount / 100000000
  if (Math.abs(yi) >= 1) return `${yi > 0 ? '+' : ''}${yi.toFixed(2)}亿`
  const wan = amount / 10000
  return `${wan > 0 ? '+' : ''}${wan.toFixed(0)}万`
}

function formatTime(time) {
  if (!time) return '-'
  return time.replace('T', ' ').slice(0, 19)
}

onMounted(() => {
  loadChartData()
})

watch(() => props.item.id, () => {
  chartType.value = 'kline'
  loadChartData()
})
</script>

<style scoped>
.limit-up-detail {
  padding: 16px;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
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

.chart-section {
  margin-bottom: 8px;
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
  gap: 16px;
  padding: 10px 16px;
  margin-bottom: 8px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  font-size: 13px;
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
  height: 280px;
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

.core-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.metric-item {
  text-align: center;
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.metric-value {
  font-size: 20px;
  font-weight: 800;
  color: var(--el-color-primary);
}

.metric-value.stars {
  color: #f59e0b;
}

.metric-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.detail-info {
  margin-bottom: 16px;
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

.concept-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.fund-flow {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.fund-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.fund-item.positive {
  background: rgba(239, 68, 68, 0.1);
}

.fund-item.total {
  grid-column: span 2;
  background: var(--el-fill-color);
}

.fund-label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.fund-value {
  font-weight: 600;
  font-size: 13px;
}

.fund-item.positive .fund-value {
  color: #ef4444;
}

.reason-content {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.reason-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
}

.dragon-badge {
  margin: 16px 0;
  padding: 12px;
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(239, 68, 68, 0.1));
  border-radius: 8px;
  text-align: center;
  font-size: 16px;
  font-weight: 700;
  color: #f59e0b;
}

.metadata {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
  font-size: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  justify-content: space-between;
}
</style>