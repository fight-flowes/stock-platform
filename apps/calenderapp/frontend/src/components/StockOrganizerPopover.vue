<template>
  <el-dialog
    :model-value="modelValue"
    width="560px"
    title="股票归类"
    destroy-on-close
    @close="$emit('update:modelValue', false)"
  >
    <div class="organizer-header">
      <div class="stock-name">{{ stockName || stockCode }}</div>
      <div class="stock-code">{{ stockCode }}</div>
    </div>

    <div class="organizer-section">
      <div class="section-title">所属分组</div>
      <el-checkbox-group v-model="localGroupIds" class="check-grid">
        <el-checkbox v-for="group in groups" :key="group.id" :label="group.id">
          {{ group.name }}
        </el-checkbox>
      </el-checkbox-group>
      <el-empty v-if="groups.length === 0" description="暂无分组" :image-size="56" />
    </div>

    <div class="organizer-section">
      <div class="section-title">标签</div>
      <el-checkbox-group v-model="localTagIds" class="check-grid">
        <el-checkbox v-for="tag in tags" :key="tag.id" :label="tag.id">
          {{ tag.name }}
        </el-checkbox>
      </el-checkbox-group>
      <el-empty v-if="tags.length === 0" description="暂无标签" :image-size="56" />
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="$emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  stockCode: { type: String, default: '' },
  stockName: { type: String, default: '' },
  modelValue: { type: Boolean, default: false },
  groupIds: { type: Array, default: () => [] },
  tagIds: { type: Array, default: () => [] },
  groups: { type: Array, default: () => [] },
  tags: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'save'])

const localGroupIds = ref([])
const localTagIds = ref([])

watch(
  () => [props.groupIds, props.tagIds, props.modelValue],
  () => {
    localGroupIds.value = Array.isArray(props.groupIds) ? [...props.groupIds] : []
    localTagIds.value = Array.isArray(props.tagIds) ? [...props.tagIds] : []
  },
  { immediate: true, deep: true }
)

function handleSave() {
  emit('save', {
    stockCode: props.stockCode,
    group_ids: localGroupIds.value,
    tag_ids: localTagIds.value,
  })
}
</script>

<style scoped>
.organizer-header {
  margin-bottom: 18px;
}

.stock-name {
  font-size: 18px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

.stock-code {
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.organizer-section + .organizer-section {
  margin-top: 20px;
}

.section-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 700;
}

.check-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
