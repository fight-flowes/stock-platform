<template>
  <el-card shadow="never" class="card">
    <template #header>
      <div style="font-weight: 700">筛选条件</div>
    </template>
    <el-form label-width="70px" size="small">
      <el-form-item label="连板数">
        <el-select 
          :model-value="filters.consecutive_min" 
          clearable 
          placeholder="全部" 
          style="width: 100%" 
          @update:model-value="updateFilter('consecutive_min', $event)"
        >
          <el-option v-for="n in [5, 4, 3, 2, 1]" :key="n" :label="`≥ ${n}板`" :value="n" />
        </el-select>
      </el-form-item>
      <el-form-item label="强度">
        <el-select 
          :model-value="filters.strength_min" 
          clearable 
          placeholder="全部" 
          style="width: 100%"
          @update:model-value="updateFilter('strength_min', $event)"
        >
          <el-option v-for="n in [5, 4, 3, 2, 1]" :key="n" :label="`≥ ${n}星`" :value="n" />
        </el-select>
      </el-form-item>
      <el-form-item label="行业">
        <el-input 
          :model-value="filters.industry" 
          clearable 
          placeholder="行业名称"
          @update:model-value="updateFilter('industry', $event)"
        />
      </el-form-item>
      <el-form-item label="概念">
        <el-input 
          :model-value="filters.concept" 
          clearable 
          placeholder="概念名称"
          @update:model-value="updateFilter('concept', $event)"
        />
      </el-form-item>
      <el-form-item label="关键词">
        <el-input 
          :model-value="filters.q" 
          clearable 
          placeholder="代码/名称"
          @update:model-value="updateFilter('q', $event)"
        />
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
defineProps({
  filters: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['update:filters'])

function updateFilter(key, value) {
  emit('update:filters', { ...key, [key]: value })
}
</script>

<style scoped>
.card {
  margin-bottom: 16px;
}
</style>