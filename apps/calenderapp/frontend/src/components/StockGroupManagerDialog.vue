<template>
  <el-dialog
    :model-value="modelValue"
    width="720px"
    title="分组管理"
    destroy-on-close
    @close="$emit('update:modelValue', false)"
  >
    <div class="manager-create">
      <el-input v-model.trim="createForm.name" placeholder="新分组名称" class="field" />
      <el-input v-model.trim="createForm.description" placeholder="描述（可选）" class="field field--wide" />
      <el-button type="primary" :loading="saving" @click="handleCreate">新建分组</el-button>
    </div>

    <div class="manager-tip">拖动左侧手柄可调整顶部按钮顺序</div>

    <div class="manager-list">
      <div
        v-for="row in localGroups"
        :key="row.id"
        class="manager-row"
        :class="{
          'is-dragging': draggingGroupId === row.id,
          'is-over': overGroupId === row.id && draggingGroupId !== row.id,
          'is-editing': editingGroupId === row.id,
        }"
        :draggable="!saving && editingGroupId !== row.id"
        @dragstart="handleDragStart(row.id)"
        @dragend="handleDragEnd"
        @dragover.prevent="handleDragOver(row.id)"
        @drop.prevent="handleDrop(row.id)"
      >
        <div class="manager-row-grip" :class="{ 'is-disabled': saving || editingGroupId === row.id }">::</div>
        <div class="manager-row-main">
          <div v-if="editingGroupId === row.id" class="manager-row-edit">
            <el-input
              v-model.trim="editingForm.name"
              size="small"
              class="manager-edit-name"
            />
            <el-input
              v-model.trim="editingForm.description"
              size="small"
              placeholder="描述（可选）"
              class="manager-edit-desc"
            />
          </div>
          <div v-else class="manager-row-meta">
            <div class="manager-row-title">{{ row.name }}</div>
            <div class="manager-row-desc">{{ row.description || '暂无描述' }}</div>
            <div class="manager-row-count">{{ row.stock_count || 0 }} 只股票</div>
          </div>
        </div>
        <div class="manager-row-actions">
          <template v-if="editingGroupId === row.id">
            <el-button link type="primary" @click="handleSaveEdit(row.id)">保存</el-button>
            <el-button link @click="cancelEdit">取消</el-button>
          </template>
          <template v-else>
            <el-button link type="primary" @click="startEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="$emit('delete-group', row.id)">删除</el-button>
          </template>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  groups: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'create', 'update-group', 'delete-group', 'reorder-groups', 'refresh'])

const createForm = reactive({
  name: '',
  description: '',
})

const localGroups = ref([])
const editingGroupId = ref(null)
const editingForm = reactive({
  name: '',
  description: '',
})
const draggingGroupId = ref(null)
const overGroupId = ref(null)

watch(
  () => props.groups,
  (value) => {
    localGroups.value = Array.isArray(value) ? value.map(group => ({ ...group })) : []
  },
  { immediate: true, deep: true }
)

function handleCreate() {
  emit('create', { ...createForm })
  createForm.name = ''
  createForm.description = ''
}

function startEdit(row) {
  editingGroupId.value = row.id
  editingForm.name = row.name || ''
  editingForm.description = row.description || ''
}

function cancelEdit() {
  editingGroupId.value = null
  editingForm.name = ''
  editingForm.description = ''
}

function handleSaveEdit(groupId) {
  emit('update-group', {
    groupId,
    payload: {
      name: editingForm.name,
      description: editingForm.description,
    },
  })
  cancelEdit()
}

function handleDragStart(groupId) {
  if (props.saving || editingGroupId.value) return
  draggingGroupId.value = groupId
}

function handleDragOver(groupId) {
  if (!draggingGroupId.value || draggingGroupId.value === groupId) return
  overGroupId.value = groupId
}

function handleDrop(groupId) {
  if (!draggingGroupId.value || draggingGroupId.value === groupId) {
    handleDragEnd()
    return
  }

  const currentIndex = localGroups.value.findIndex(group => group.id === draggingGroupId.value)
  const targetIndex = localGroups.value.findIndex(group => group.id === groupId)
  if (currentIndex < 0 || targetIndex < 0) {
    handleDragEnd()
    return
  }

  const reorderedGroups = [...localGroups.value]
  const [movedGroup] = reorderedGroups.splice(currentIndex, 1)
  reorderedGroups.splice(targetIndex, 0, movedGroup)
  localGroups.value = reorderedGroups
  emit('reorder-groups', reorderedGroups.map(group => group.id))
  handleDragEnd()
}

function handleDragEnd() {
  draggingGroupId.value = null
  overGroupId.value = null
}
</script>

<style scoped>
.manager-create {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.field {
  width: 160px;
}

.field--wide {
  width: 220px;
}

.manager-tip {
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.manager-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.manager-row {
  display: flex;
  align-items: stretch;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
  background: var(--el-bg-color);
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.manager-row.is-over {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 10px 24px rgba(59, 130, 246, 0.12);
}

.manager-row.is-dragging {
  opacity: 0.72;
}

.manager-row.is-editing {
  border-color: var(--el-color-primary-light-5);
}

.manager-row-grip {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  flex: 0 0 24px;
  color: var(--el-text-color-secondary);
  cursor: grab;
  user-select: none;
  font-weight: 700;
  letter-spacing: 1px;
}

.manager-row-grip.is-disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.manager-row-main {
  flex: 1;
  min-width: 0;
}

.manager-row-meta,
.manager-row-edit {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.manager-row-title {
  flex: 0 0 108px;
  font-size: 14px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.manager-row-desc {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.manager-row-count {
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.manager-edit-name {
  flex: 0 0 140px;
}

.manager-edit-desc {
  flex: 1;
  min-width: 180px;
}

.manager-row-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}

@media (max-width: 760px) {
  .manager-row {
    flex-wrap: wrap;
  }

  .manager-row-meta,
  .manager-row-edit {
    flex-wrap: wrap;
    align-items: flex-start;
  }

  .manager-row-title,
  .manager-edit-name,
  .manager-edit-desc {
    flex: 1 1 100%;
  }

  .manager-row-desc {
    white-space: normal;
  }

  .manager-row-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
