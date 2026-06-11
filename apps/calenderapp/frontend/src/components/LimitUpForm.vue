<template>
  <el-form ref="formRef" :model="form" :rules="rules" label-width="92px" @submit.prevent>
    <el-row :gutter="12">
      <el-col :xs="24" :sm="12">
        <el-form-item label="股票代码" prop="stock_code">
          <el-input v-model.trim="form.stock_code" placeholder="如：002361.SZ" />
        </el-form-item>
      </el-col>
      <el-col :xs="24" :sm="12">
        <el-form-item label="股票名称" prop="stock_name">
          <el-input v-model.trim="form.stock_name" placeholder="如：神剑股份" />
        </el-form-item>
      </el-col>

      <el-col :xs="24" :sm="12">
        <el-form-item label="涨停日期" prop="limit_up_date">
          <el-date-picker v-model="form.limit_up_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :xs="24" :sm="12">
        <el-form-item label="连板数" prop="consecutive_days">
          <el-input-number v-model="form.consecutive_days" :min="1" :max="20" style="width: 100%" />
        </el-form-item>
      </el-col>

      <el-col :xs="24" :sm="12">
        <el-form-item label="封单金额">
          <el-input-number v-model="form.seal_amount" :min="0" :precision="2" style="width: 100%" placeholder="万元" />
        </el-form-item>
      </el-col>
      <el-col :xs="24" :sm="12">
        <el-form-item label="封板时间">
          <el-time-picker v-model="form.first_limit_time" format="HH:mm:ss" value-format="HH:mm:ss" style="width: 100%" placeholder="首次封板" />
        </el-form-item>
      </el-col>

      <el-col :xs="24" :sm="12">
        <el-form-item label="开板次数">
          <el-input-number v-model="form.open_count" :min="0" :max="20" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :xs="24" :sm="12">
        <el-form-item label="所属行业">
          <el-input v-model.trim="form.industry" placeholder="如：航天军工" />
        </el-form-item>
      </el-col>

      <el-col :xs="24" :sm="24">
        <el-form-item label="概念标签">
          <el-select
            v-model="form.concept_tags"
            multiple
            filterable
            allow-create
            default-first-option
            clearable
            placeholder="输入概念，回车添加"
            style="width: 100%"
          />
        </el-form-item>
      </el-col>

      <el-col :xs="24" :sm="12">
        <el-form-item label="机构净买">
          <el-input-number v-model="form.institution_net_buy" :precision="2" style="width: 100%" placeholder="万元" />
        </el-form-item>
      </el-col>
      <el-col :xs="24" :sm="12">
        <el-form-item label="游资净买">
          <el-input-number v-model="form.hot_money_net_buy" :precision="2" style="width: 100%" placeholder="万元" />
        </el-form-item>
      </el-col>

      <el-col :xs="24" :sm="24">
        <el-form-item label="涨停原因">
          <el-input v-model="form.reason_detail" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="简述涨停原因" />
        </el-form-item>
      </el-col>
    </el-row>

    <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 8px">
      <el-button @click="emit('cancel')">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="onSubmit">保存</el-button>
    </div>
  </el-form>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Object, default: null }
})

const emit = defineEmits(['submit', 'cancel'])

const blank = () => ({
  stock_code: '',
  stock_name: '',
  limit_up_date: new Date().toISOString().slice(0, 10),
  consecutive_days: 1,
  limit_up_type: 'first_board',
  seal_amount: 0,
  seal_ratio: 0,
  turnover_rate: 0,
  first_limit_time: '',
  last_limit_time: '',
  open_count: 0,
  industry: '',
  concept_tags: [],
  institution_net_buy: 0,
  hot_money_net_buy: 0,
  north_net_buy: 0,
  total_net_buy: 0,
  reason_category: '',
  reason_detail: ''
})

const form = reactive(blank())
const formRef = ref()
const submitting = ref(false)

const rules = {
  stock_code: [{ required: true, message: '请输入股票代码', trigger: 'blur' }],
  stock_name: [{ required: true, message: '请输入股票名称', trigger: 'blur' }],
  limit_up_date: [{ required: true, message: '请选择涨停日期', trigger: 'change' }],
  consecutive_days: [{ required: true, message: '请输入连板数', trigger: 'change' }]
}

watch(
  () => props.modelValue,
  (val) => {
    Object.assign(form, blank())
    if (!val) return
    form.stock_code = val.stock_code || ''
    form.stock_name = val.stock_name || ''
    form.limit_up_date = val.limit_up_date || form.limit_up_date
    form.consecutive_days = Number(val.consecutive_days || 1)
    form.limit_up_type = val.limit_up_type || 'first_board'
    form.seal_amount = Number(val.seal_amount || 0)
    form.seal_ratio = Number(val.seal_ratio || 0)
    form.turnover_rate = Number(val.turnover_rate || 0)
    form.first_limit_time = val.first_limit_time || ''
    form.last_limit_time = val.last_limit_time || ''
    form.open_count = Number(val.open_count || 0)
    form.industry = val.industry || ''
    form.concept_tags = Array.isArray(val.concept_tags) ? [...val.concept_tags] : []
    form.institution_net_buy = Number(val.institution_net_buy || 0)
    form.hot_money_net_buy = Number(val.hot_money_net_buy || 0)
    form.north_net_buy = Number(val.north_net_buy || 0)
    form.total_net_buy = Number(val.total_net_buy || 0)
    form.reason_category = val.reason_category || ''
    form.reason_detail = val.reason_detail || ''
  },
  { immediate: true }
)

async function onSubmit() {
  if (!formRef.value) return
  submitting.value = true
  try {
    await formRef.value.validate()
    emit('submit', {
      stock_code: form.stock_code,
      stock_name: form.stock_name,
      limit_up_date: form.limit_up_date,
      consecutive_days: form.consecutive_days,
      limit_up_type: form.consecutive_days >= 2 ? 'multi_board' : 'first_board',
      seal_amount: form.seal_amount,
      seal_ratio: form.seal_ratio,
      turnover_rate: form.turnover_rate,
      first_limit_time: form.first_limit_time || null,
      last_limit_time: form.last_limit_time || null,
      open_count: form.open_count,
      industry: form.industry || null,
      concept_tags: form.concept_tags,
      institution_net_buy: form.institution_net_buy,
      hot_money_net_buy: form.hot_money_net_buy,
      north_net_buy: form.north_net_buy,
      total_net_buy: form.total_net_buy,
      reason_category: form.reason_category || null,
      reason_detail: form.reason_detail || null
    })
  } finally {
    submitting.value = false
  }
}
</script>