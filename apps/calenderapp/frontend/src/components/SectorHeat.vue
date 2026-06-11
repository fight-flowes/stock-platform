<template>
  <div class="sector-heat">
    <div class="heat-header">
      <div class="heat-title">板块热度</div>
      <el-radio-group v-model="activeTab" size="small">
        <el-radio-button value="industry">行业</el-radio-button>
        <el-radio-button value="concept">概念</el-radio-button>
      </el-radio-group>
    </div>

    <el-skeleton v-if="loading" :rows="5" animated />
    <el-empty v-else-if="!loading && (!data || Object.keys(data).length === 0)" description="暂无数据" />
    
    <div v-else class="heat-list">
      <div
        v-for="(count, name) in sortedData"
        :key="name"
        class="heat-item"
        @click="$emit('select', activeTab, name)"
      >
        <div class="heat-name">{{ name }}</div>
        <div class="heat-bar-wrap">
          <div class="heat-bar" :style="{ width: getBarWidth(count) + '%' }"></div>
        </div>
        <div class="heat-count">{{ count }}只</div>
      </div>
    </div>

    <div v-if="showMore && totalItems > displayLimit" class="heat-more">
      <el-button text @click="expanded = !expanded">
        {{ expanded ? '收起' : `查看全部 ${totalItems} 项` }}
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'

const props = defineProps({
  industryData: { type: Object, default: () => ({}) },
  conceptData: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  showMore: { type: Boolean, default: true },
  displayLimit: { type: Number, default: 10 }
})

const emit = defineEmits(['select'])

const activeTab = ref('industry')
const expanded = ref(false)

const data = computed(() => {
  return activeTab.value === 'industry' ? props.industryData : props.conceptData
})

const sortedData = computed(() => {
  const entries = Object.entries(data.value || {}).sort((a, b) => b[1] - a[1])
  const limited = expanded.value ? entries : entries.slice(0, props.displayLimit)
  return Object.fromEntries(limited)
})

const totalItems = computed(() => Object.keys(data.value || {}).length)

const maxCount = computed(() => {
  const values = Object.values(data.value || {})
  return Math.max(...values, 1)
})

function getBarWidth(count) {
  return (count / maxCount.value) * 100
}
</script>

<style scoped>
.sector-heat {
  background: var(--el-bg-color);
  border-radius: 12px;
  overflow: hidden;
}

.heat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.heat-title {
  font-size: 16px;
  font-weight: 700;
}

.heat-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.heat-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.heat-item:hover {
  background: var(--el-fill-color-lighter);
}

.heat-name {
  width: 100px;
  font-size: 13px;
  font-weight: 500;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.heat-bar-wrap {
  flex: 1;
  height: 8px;
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
  overflow: hidden;
}

.heat-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--el-color-primary), var(--el-color-primary-light-3));
  border-radius: 4px;
  transition: width 0.3s;
}

.heat-count {
  width: 50px;
  text-align: right;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-color-primary);
  flex-shrink: 0;
}

.heat-more {
  padding: 8px;
  text-align: center;
  border-top: 1px solid var(--el-border-color-lighter);
}
</style>