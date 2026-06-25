<template>
  <el-dialog
    :model-value="modelValue"
    width="640px"
    title="标签管理"
    destroy-on-close
    @close="$emit('update:modelValue', false)"
  >
    <div class="manager-create">
      <el-input v-model.trim="createForm.name" placeholder="新标签名称" class="field" />
      <el-button type="primary" :loading="saving" @click="handleCreate">新建标签</el-button>
    </div>

    <div class="tag-list">
      <div v-for="tag in tags" :key="tag.id" class="tag-row">
        <div class="tag-main">
          <el-tag effect="plain">{{ tag.name }}</el-tag>
          <span class="tag-count">{{ tag.stock_count || 0 }} 只股票</span>
        </div>
        <el-button link type="danger" @click="$emit('delete-tag', tag.id)">删除</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { reactive } from 'vue'

defineProps({
  modelValue: { type: Boolean, default: false },
  tags: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'create', 'delete-tag', 'refresh'])

const createForm = reactive({
  name: '',
})

function handleCreate() {
  emit('create', { ...createForm })
  createForm.name = ''
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
  width: 180px;
}

.tag-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tag-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
}

.tag-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tag-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
