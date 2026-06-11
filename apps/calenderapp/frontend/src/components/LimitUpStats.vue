<template>
  <el-row :gutter="16">
    <el-col :xs="24" :lg="6">
      <el-card shadow="never" class="card stat-card">
        <div class="stat-value">{{ stats.total || 0 }}</div>
        <div class="stat-label">涨停总数</div>
      </el-card>
    </el-col>
    <el-col :xs="24" :lg="6">
      <el-card shadow="never" class="card stat-card highlight">
        <div class="stat-value">{{ highConsecutiveCount }}</div>
        <div class="stat-label">连板股 (≥2)</div>
      </el-card>
    </el-col>
    <el-col :xs="24" :lg="6">
      <el-card shadow="never" class="card stat-card">
        <div class="stat-value">{{ stats.by_consecutive?.['3'] || 0 }}</div>
        <div class="stat-label">三连板</div>
      </el-card>
    </el-col>
    <el-col :xs="24" :lg="6">
      <el-card shadow="never" class="card stat-card dragon">
        <div class="stat-value">{{ dragonHeadCount }}</div>
        <div class="stat-label">龙头股</div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  stats: { type: Object, default: () => ({}) },
  rows: { type: Array, default: () => [] }
})

// 连板股数量
const highConsecutiveCount = computed(() => {
  return props.rows.filter(r => r.consecutive_days >= 2).length
})

// 龙头股数量
const dragonHeadCount = computed(() => {
  return props.rows.filter(r => r.is_dragon_head).length
})
</script>

<style scoped>
.stat-card {
  text-align: center;
  padding: 16px 0;
}

.stat-value {
  font-size: 32px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

.stat-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-top: 8px;
}

.stat-card.highlight .stat-value {
  color: #f59e0b;
}

.stat-card.dragon .stat-value {
  color: #ef4444;
}

.stat-card.dragon {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(245, 158, 11, 0.1) 100%);
}
</style>