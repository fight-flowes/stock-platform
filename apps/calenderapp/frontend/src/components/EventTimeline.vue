<template>
  <el-card shadow="never" class="event-timeline-card">
    <template #header>
      <div class="event-timeline-header">
        <div class="event-timeline-title">发酵轨迹</div>
        <el-tag size="small" effect="plain">{{ timeline.length }}</el-tag>
      </div>
    </template>

    <div v-loading="loading" class="event-timeline-body">
      <el-empty v-if="!loading && timeline.length === 0" description="暂无发酵轨迹" :image-size="56" />

      <div v-else class="timeline-list">
        <div v-for="point in timeline" :key="point.date" class="timeline-item">
          <div class="timeline-date">{{ point.date || '-' }}</div>
          <div class="timeline-stats">
            <span>影响股票 {{ point.affected_stock_count || 0 }}</span>
            <span>来源报告 {{ point.source_report_count || 0 }}</span>
          </div>
          <div class="timeline-stocks">
            <el-tag
              v-for="stock in point.stocks || []"
              :key="`${stock.stock_code}-${stock.stock_name}`"
              size="small"
              @click="emit('select-stock', stock)"
            >
              {{ stock.stock_name || '-' }}<span v-if="stock.stock_code"> {{ stock.stock_code }}</span>
            </el-tag>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
defineProps({
  timeline: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['select-stock'])
</script>

<style scoped>
.event-timeline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.event-timeline-title {
  font-weight: 800;
  color: #0f172a;
}

.event-timeline-body {
  min-height: 180px;
}

.timeline-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.timeline-item {
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fcfdff;
}

.timeline-date {
  font-weight: 800;
  color: #0f172a;
}

.timeline-stats {
  margin-top: 6px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #64748b;
}

.timeline-stocks {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
