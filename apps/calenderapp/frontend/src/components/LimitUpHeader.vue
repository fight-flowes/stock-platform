<template>
  <el-card shadow="never" class="card date-bar">
    <div class="date-bar-content">
      <div class="date-selector">
        <span class="label">交易日：</span>
        <el-date-picker
          :model-value="selectedDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          :clearable="false"
          @update:model-value="onDateChange($event)"
        />
      </div>
      <div class="quick-dates">
        <el-button 
          v-for="d in quickDates" 
          :key="d.value" 
          size="small" 
          :type="selectedDate === d.value ? 'primary' : 'default'" 
          @click="$emit('date-change', d.value)"
        >
          {{ d.label }}
        </el-button>
      </div>
      <div class="actions">
        <el-dropdown split-button type="success" @click="$emit('sync')" :loading="syncing">
          <el-icon><Download /></el-icon>
          同步数据
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="$emit('sync')">快速同步（仅涨停）</el-dropdown-item>
              <el-dropdown-item @click="$emit('sync-full')">完整同步（涨停+龙虎榜+概念）</el-dropdown-item>
              <el-dropdown-item divided @click="$emit('sync-batch')">批量同步日期范围</el-dropdown-item>
              <el-dropdown-item @click="$emit('identify-dragon')">重新识别龙头</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button type="primary" @click="$emit('create')" title="添加涨停记录">
          <el-icon><Plus /></el-icon>
        </el-button>
        <el-button type="warning" @click="$emit('download')" title="下载当日涨停数据">
          <el-icon><Download /></el-icon>
        </el-button>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { Plus, Download } from '@element-plus/icons-vue'

defineProps({
  selectedDate: { type: String, required: true },
  quickDates: { type: Array, default: () => [] },
  syncing: { type: Boolean, default: false }
})

const emit = defineEmits(['update:selectedDate', 'date-change', 'create', 'sync', 'sync-full', 'sync-batch', 'identify-dragon', 'download'])

function onDateChange(date) {
  emit('update:selectedDate', date)
  emit('date-change', date)
}
</script>

<style scoped>
.date-bar {
  /* 去掉 margin-bottom，由父组件控制间距 */
}

.date-bar-content {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.date-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-selector .label {
  font-weight: 600;
  white-space: nowrap;
}

.quick-dates {
  display: flex;
  gap: 4px;
}

.actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

@media (max-width: 768px) {
  .date-bar-content {
    flex-direction: column;
    align-items: stretch;
  }
  
  .actions {
    margin-left: 0;
    justify-content: flex-end;
  }
}
</style>