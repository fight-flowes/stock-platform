<template>
  <el-card shadow="never" class="workbench-card">
    <div class="workbench-row">
      <div class="workbench-filters">
        <el-select
          :model-value="selectedTagIds"
          multiple
          collapse-tags
          collapse-tags-tooltip
          clearable
          filterable
          placeholder="按标签筛选"
          class="filter-select filter-select--wide"
          @change="$emit('update:selectedTagIds', $event || [])"
        >
          <el-option
            v-for="tag in tags"
            :key="tag.id"
            :label="tag.name"
            :value="tag.id"
          />
        </el-select>

      </div>

      <div class="workbench-actions">
        <el-button v-if="selectedGroupId" type="primary" plain @click="$emit('add-group-stocks')">添加股票</el-button>
        <el-button @click="$emit('manage-groups')">管理分组</el-button>
        <el-button @click="$emit('manage-tags')">管理标签</el-button>
      </div>
    </div>

    <div class="group-row">
      <div class="filter-caption">分组视角</div>
      <div class="group-buttons">
        <el-button
          size="small"
          :type="!selectedGroupId && !ungroupedOnly ? 'primary' : 'default'"
          @click="showAll"
        >
          全部
        </el-button>
        <el-tooltip
          v-for="group in groups"
          :key="group.id"
          :content="group.description"
          placement="top"
          :disabled="!group.description"
        >
          <el-button
            size="small"
            :type="selectedGroupId === group.id && !ungroupedOnly ? 'primary' : 'default'"
            @click="selectGroup(group.id)"
          >
            {{ group.name }}
            <span v-if="group.stock_count !== undefined" class="group-count">{{ group.stock_count }}</span>
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <div v-if="selectedCount > 0" class="batch-row">
      <div class="batch-title">已选 {{ selectedCount }} 只股票</div>

      <el-select
        v-model="batchGroupId"
        clearable
        placeholder="选择分组"
        class="filter-select"
      >
        <el-option
          v-for="group in groups"
          :key="group.id"
          :label="group.name"
          :value="group.id"
        />
      </el-select>
      <el-button :disabled="!batchGroupId" :loading="batchGroupLoading" type="primary" plain @click="applyBatchGroup">
        批量加入分组
      </el-button>

      <el-select
        v-model="batchTagId"
        clearable
        placeholder="选择标签"
        class="filter-select"
      >
        <el-option
          v-for="tag in tags"
          :key="tag.id"
          :label="tag.name"
          :value="tag.id"
        />
      </el-select>
      <el-button :disabled="!batchTagId" :loading="batchTagLoading" type="primary" plain @click="applyBatchTag">
        批量添加标签
      </el-button>
    </div>
  </el-card>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  groups: { type: Array, default: () => [] },
  tags: { type: Array, default: () => [] },
  selectedGroupId: { type: [Number, String, null], default: null },
  selectedTagIds: { type: Array, default: () => [] },
  ungroupedOnly: { type: Boolean, default: false },
  selectedCount: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
  batchGroupLoading: { type: Boolean, default: false },
  batchTagLoading: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:selectedTagIds',
  'change-group-scope',
  'manage-groups',
  'manage-tags',
  'add-group-stocks',
  'batch-add-group',
  'batch-add-tag',
])

const batchGroupId = ref(null)
const batchTagId = ref(null)

function applyBatchGroup() {
  if (!batchGroupId.value) return
  emit('batch-add-group', batchGroupId.value)
  batchGroupId.value = null
}

function applyBatchTag() {
  if (!batchTagId.value) return
  emit('batch-add-tag', batchTagId.value)
  batchTagId.value = null
}

function selectGroup(groupId) {
  emit('change-group-scope', { groupId, ungroupedOnly: false })
}

function showAll() {
  emit('change-group-scope', { groupId: null, ungroupedOnly: false })
}
</script>

<style scoped>
.workbench-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 22px;
  background: linear-gradient(180deg, var(--el-bg-color) 0%, var(--el-fill-color-blank) 100%);
  box-shadow: 0 18px 42px rgba(148, 163, 184, 0.08);
}

.workbench-card :deep(.el-card__body) {
  padding: 18px 18px 16px;
}

.workbench-row,
.batch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.batch-row {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--el-border-color-lighter);
  justify-content: flex-start;
}

.workbench-filters,
.workbench-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.group-row {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.group-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.filter-caption {
  font-size: 13px;
  font-weight: 700;
  color: var(--el-text-color-regular);
}

.filter-select {
  width: 180px;
}

.filter-select--wide {
  width: 260px;
}

.batch-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.group-count {
  margin-left: 4px;
  font-size: 11px;
  opacity: 0.7;
}
</style>
