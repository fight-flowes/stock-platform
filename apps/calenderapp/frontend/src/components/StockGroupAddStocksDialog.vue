<template>
  <el-dialog
    :model-value="modelValue"
    width="720px"
    :title="`添加股票到分组：${groupName || '未选择分组'}`"
    destroy-on-close
    @close="$emit('update:modelValue', false)"
  >
    <div class="search-row">
      <el-input
        v-model.trim="keyword"
        clearable
        placeholder="输入股票代码或名称进行搜索"
        @keyup.enter="emitSearch"
      >
        <template #append>
          <el-button :loading="searching" @click="emitSearch">搜索</el-button>
        </template>
      </el-input>
    </div>

    <div v-if="results.length > 0" class="results-block">
      <div class="results-head">
        <span>搜索结果（{{ results.length }}）</span>
        <span class="results-tip">勾选后可直接加入当前分组</span>
      </div>
      <el-checkbox-group v-model="localSelectedCodes" class="result-list">
        <label v-for="item in results" :key="item.code" class="result-item">
          <el-checkbox :label="item.code">
            <span class="result-code">{{ item.code }}</span>
            <span class="result-name">{{ item.name }}</span>
            <el-tag v-if="item.exchange" size="small" effect="plain">{{ item.exchange }}</el-tag>
          </el-checkbox>
        </label>
      </el-checkbox-group>
    </div>

    <el-empty v-else description="搜索股票后即可添加到当前分组" :image-size="70" />

    <template #footer>
      <div class="dialog-footer">
        <div class="selected-tip">已选 {{ localSelectedCodes.length }} 只</div>
        <div class="dialog-actions">
          <el-button @click="$emit('update:modelValue', false)">取消</el-button>
          <el-button type="primary" :disabled="localSelectedCodes.length === 0" :loading="submitting" @click="emitSubmit">
            加入分组
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  groupName: { type: String, default: '' },
  results: { type: Array, default: () => [] },
  selectedCodes: { type: Array, default: () => [] },
  searching: { type: Boolean, default: false },
  submitting: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'search', 'submit'])

const keyword = ref('')
const localSelectedCodes = ref([])

watch(
  () => props.selectedCodes,
  (value) => {
    localSelectedCodes.value = Array.isArray(value) ? [...value] : []
  },
  { immediate: true, deep: true }
)

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) {
      keyword.value = ''
      localSelectedCodes.value = []
    }
  }
)

function emitSearch() {
  emit('search', keyword.value)
}

function emitSubmit() {
  emit('submit', localSelectedCodes.value)
}
</script>

<style scoped>
.search-row {
  margin-bottom: 16px;
}

.results-block {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
  overflow: hidden;
}

.results-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  background: var(--el-fill-color-light);
  font-size: 13px;
  font-weight: 600;
}

.results-tip {
  font-size: 12px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
}

.result-list {
  display: flex;
  flex-direction: column;
}

.result-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.result-item:first-child {
  border-top: none;
}

.result-code {
  margin-right: 10px;
  font-weight: 700;
  color: var(--el-color-primary);
}

.result-name {
  margin-right: 10px;
  color: var(--el-text-color-primary);
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.selected-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.dialog-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
