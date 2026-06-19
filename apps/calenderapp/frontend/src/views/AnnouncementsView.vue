<template>
  <div class="announcements-view">
    <el-card shadow="never" class="announcements-hero">
      <div class="hero-title">
        <el-icon><Bell /></el-icon>
        <span>公告 · 预期事件</span>
      </div>
      <div class="hero-subtitle">
        未来一段时间内可能影响行业 / 龙头个股的预期事件（业绩预告、股东大会、限售解禁、新股、宏观日历等）
      </div>
      <div class="hero-status">
        <el-tag size="small" type="warning" effect="plain">
          数据源：<b>eventradar</b>（开发中）
        </el-tag>
        <el-tag size="small" type="info" effect="plain">
          当前页面为占位预览
        </el-tag>
      </div>
    </el-card>

    <el-card shadow="never" class="announcements-toolbar">
      <div class="toolbar-row">
        <el-segmented
          v-model="activeScope"
          :options="scopeOptions"
          size="small"
          disabled
        />
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="—"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          size="small"
          disabled
          style="width: 260px;"
        />
        <el-input
          v-model="keyword"
          placeholder="搜索行业 / 股票 / 关键词"
          size="small"
          clearable
          disabled
          style="width: 240px;"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button size="small" disabled>刷新</el-button>
      </div>
      <div class="toolbar-hint">
        筛选与查询将在 eventradar 服务接入后启用。
      </div>
    </el-card>

    <el-card shadow="never" class="announcements-list-card">
      <template #header>
        <div class="list-header">
          <span class="list-title">即将到来的事件</span>
          <span class="list-count">{{ mockEvents.length }} 条 · 示例数据</span>
        </div>
      </template>

      <el-table
        :data="mockEvents"
        stripe
        size="default"
        empty-text="暂无数据"
        class="announcements-table"
      >
        <el-table-column prop="expected_at" label="预期日期" width="120" />
        <el-table-column prop="event_type" label="事件类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTagMap[row.event_type] || 'info'" effect="plain">
              {{ row.event_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="event_name" label="事件标题" min-width="260" show-overflow-tooltip />
        <el-table-column prop="scope" label="影响范围" width="130">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.scope === '行业' ? 'success' : row.scope === '宏观' ? 'warning' : ''"
              effect="plain"
            >
              {{ row.scope }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="industries" label="相关行业 / 题材" min-width="200">
          <template #default="{ row }">
            <el-tag
              v-for="tag in row.industries"
              :key="tag"
              size="small"
              effect="plain"
              class="industry-tag"
            >
              {{ tag }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="leaders" label="龙头个股" min-width="180">
          <template #default="{ row }">
            <span v-if="row.leaders?.length" class="leaders">
              {{ row.leaders.join('、') }}
            </span>
            <span v-else class="leaders-empty">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="数据源" width="110" />
        <el-table-column prop="importance" label="重要度" width="100">
          <template #default="{ row }">
            <el-rate
              :model-value="row.importance"
              :max="3"
              disabled
              size="small"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="placeholder-note"
    >
      <template #title>该页面为占位预览</template>
      <template #default>
        实际数据将通过 calenderapp 后端代理调用 <b>eventradar</b>（独立服务，端口待定）。
        eventradar 基于 akshare 抓取东方财富 / 巨潮 / 百度股市通 / 华尔街见闻等平台的预期事件，
        归一化为统一的 <code>ExpectedEvent</code> schema 后落 DuckDB 提供查询。
      </template>
    </el-alert>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Bell, Search } from '@element-plus/icons-vue'

const activeScope = ref('all')
const scopeOptions = [
  { label: '全部', value: 'all' },
  { label: '行业事件', value: 'industry' },
  { label: '龙头股事件', value: 'leader' },
  { label: '业绩预披露', value: 'earnings' },
  { label: 'IPO / 解禁', value: 'ipo_unlock' },
  { label: '宏观日历', value: 'macro' }
]

const dateRange = ref([])
const keyword = ref('')

const typeTagMap = {
  '业绩预告': 'success',
  '股东大会': '',
  '限售解禁': 'danger',
  '新股申购': 'warning',
  '宏观数据': 'warning',
  '行业会议': 'success',
  '分红派息': '',
  '财报预披露': 'success'
}

// 占位 mock 数据 —— 接 eventradar 之后整体替换
const mockEvents = ref([
  {
    expected_at: '2026-06-22',
    event_type: '业绩预告',
    event_name: '半导体板块多家公司将发布二季度业绩预告',
    scope: '行业',
    industries: ['半导体', '集成电路'],
    leaders: ['中芯国际', '韦尔股份'],
    source: '东方财富',
    importance: 3
  },
  {
    expected_at: '2026-06-23',
    event_type: '宏观数据',
    event_name: '5 月 LPR 利率公布',
    scope: '宏观',
    industries: ['金融', '地产'],
    leaders: [],
    source: '百度股市通',
    importance: 3
  },
  {
    expected_at: '2026-06-25',
    event_type: '行业会议',
    event_name: '2026 世界人工智能大会 (WAIC)',
    scope: '行业',
    industries: ['AI', '算力', '机器人'],
    leaders: ['寒武纪', '海光信息', '科大讯飞'],
    source: '财联社电报',
    importance: 3
  },
  {
    expected_at: '2026-06-26',
    event_type: '限售解禁',
    event_name: '宁德时代约 1.2 亿股限售股解禁',
    scope: '个股',
    industries: ['新能源', '电池'],
    leaders: ['宁德时代'],
    source: '东方财富',
    importance: 2
  },
  {
    expected_at: '2026-06-28',
    event_type: '新股申购',
    event_name: '科创板 3 只新股集中申购',
    scope: '行业',
    industries: ['IPO'],
    leaders: [],
    source: '巨潮资讯',
    importance: 1
  },
  {
    expected_at: '2026-07-01',
    event_type: '股东大会',
    event_name: '贵州茅台 2025 年度股东大会',
    scope: '个股',
    industries: ['白酒', '消费'],
    leaders: ['贵州茅台'],
    source: '东方财富',
    importance: 2
  }
])
</script>

<style scoped>
.announcements-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.announcements-hero {
  background: linear-gradient(
    135deg,
    var(--el-color-primary-light-9) 0%,
    var(--el-color-warning-light-9) 100%
  );
  border: none;
}

.hero-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.hero-subtitle {
  margin-top: 6px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.hero-status {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.announcements-toolbar {
  border: 1px solid var(--el-border-color-lighter);
}

.toolbar-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.toolbar-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.announcements-list-card {
  border: 1px solid var(--el-border-color-lighter);
}

.list-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.list-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.list-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.industry-tag {
  margin-right: 4px;
  margin-bottom: 2px;
}

.leaders {
  color: var(--el-text-color-primary);
  font-size: 13px;
}

.leaders-empty {
  color: var(--el-text-color-disabled);
}

.placeholder-note :deep(code) {
  background: var(--el-fill-color-light);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: var(--el-font-family-mono, monospace);
  font-size: 12px;
}
</style>
