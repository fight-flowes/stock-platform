<template>
  <el-form ref="formRef" :model="form" :rules="rules" label-width="92px" @submit.prevent>
    <el-row :gutter="12">
      <el-col :xs="24" :sm="10">
        <el-form-item label="日期" prop="event_date">
          <el-date-picker v-model="form.event_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :xs="24" :sm="14">
        <el-form-item label="标题" prop="title">
          <el-input v-model.trim="form.title" placeholder="例如：财报发布 / 分红预案" />
        </el-form-item>
      </el-col>

      <el-col :xs="24" :sm="10">
        <el-form-item label="重要性" prop="importance">
          <div style="display: flex; align-items: center; gap: 10px; width: 100%">
            <el-rate v-model="form.importance" :max="5" />
            <el-tag type="info"> {{ form.importance }} </el-tag>
          </div>
        </el-form-item>
      </el-col>
      <el-col :xs="24" :sm="14">
        <el-form-item label="类型">
          <el-select v-model="form.event_type" clearable filterable placeholder="未指定" style="width: 100%">
            <el-option v-for="opt in typeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
      </el-col>

      <el-col :xs="24" :sm="24">
        <el-form-item label="相关股票">
          <el-select
            v-model="form.stock_list"
            multiple
            filterable
            remote
            clearable
            reserve-keyword
            :remote-method="onStockSearch"
            :loading="stockLoading"
            placeholder="输入代码/名称搜索，支持多选"
            style="width: 100%"
          >
            <el-option
              v-for="s in stockOptions"
              :key="s.code"
              :label="`${s.code} ${s.name || ''}`.trim()"
              :value="s.code"
            />
          </el-select>
        </el-form-item>
      </el-col>

      <el-col :xs="24" :sm="12">
        <el-form-item label="来源">
          <el-input v-model.trim="form.source" placeholder="例如：公告 / 研报 / 手工整理" />
        </el-form-item>
      </el-col>
      <el-col :xs="24" :sm="12">
        <el-form-item label="来源链接">
          <el-input v-model.trim="form.source_url" placeholder="https://..." />
        </el-form-item>
      </el-col>

      <el-col :xs="24" :sm="12">
        <el-form-item label="可信度">
          <div style="display: flex; align-items: center; gap: 10px; width: 100%">
            <el-input v-model.trim="form.credibility" placeholder="⭐⭐⭐⭐⭐" style="flex: 1" />
            <el-tooltip content="从 event-extractor 抽取的事件自动标注可信度" placement="top">
              <el-icon><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
        </el-form-item>
      </el-col>
      <el-col :xs="24" :sm="12">
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" />
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
import { computed, reactive, ref, watch } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import { searchStocks } from '../api/stocks'

const props = defineProps({
  modelValue: { type: Object, default: null },
  eventTypes: { type: Object, default: null }
})

const emit = defineEmits(['submit', 'cancel'])

const blank = () => ({
  event_date: new Date().toISOString().slice(0, 10),
  title: '',
  importance: 3,
  event_type: '',
  source: '',
  source_url: '',  // 新增
  description: '',
  stock_list: [],
  credibility: ''  // 新增
})

const form = reactive(blank())
const formRef = ref()
const submitting = ref(false)

const rules = {
  event_date: [{ required: true, message: '请选择日期', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  importance: [{ required: true, message: '请选择重要性', trigger: 'change' }]
}

watch(
  () => props.modelValue,
  (val) => {
    Object.assign(form, blank())
    if (!val) return
    form.event_date = val.event_date || form.event_date
    form.title = val.title || ''
    form.importance = Number(val.importance || 3)
    form.event_type = val.event_type || ''
    form.source = val.source || ''
    form.source_url = val.source_url || ''  // 新增
    form.description = val.description || ''
    form.stock_list = Array.isArray(val.stock_list) ? [...val.stock_list] : []
    form.credibility = val.credibility || ''  // 新增
  },
  { immediate: true }
)

const payload = computed(() => {
  return {
    event_date: form.event_date,
    title: form.title,
    importance: form.importance,
    event_type: form.event_type || null,
    source: form.source || null,
    source_url: form.source_url || null,  // 新增
    description: form.description || null,
    stock_list: Array.isArray(form.stock_list) ? form.stock_list.filter(Boolean) : [],
    credibility: form.credibility || null  // 新增
  }
})

const typeOptions = computed(() => {
  const map = props.eventTypes || {}
  const opts = Object.keys(map).map((k) => ({ value: k, label: map[k] }))
  if (opts.length) return opts
  // 默认类型列表（包含新增类型）
  return [
    { value: 'earnings', label: '财报发布' },
    { value: 'dividend', label: '分红派息' },
    { value: 'shareholder_meeting', label: '股东大会' },
    { value: 'listing_status', label: '上市/退市' },
    { value: 'financing', label: '融资事件' },
    { value: 'm_and_a', label: '并购重组' },
    { value: 'regulatory', label: '监管事件' },
    { value: 'policy', label: '政策利好' },      // 新增
    { value: 'announcement', label: '公司公告' }, // 新增
    { value: 'industry', label: '行业动态' },    // 新增
    { value: 'fund_flow', label: '资金动向' },   // 新增
    { value: 'other', label: '其他事件' }
  ]
})

const stockLoading = ref(false)
const stockOptions = ref([])

async function onStockSearch(q) {
  const query = String(q || '').trim()
  if (!query) return
  stockLoading.value = true
  try {
    const resp = await searchStocks(query, 10)
    stockOptions.value = resp?.data || []
  } finally {
    stockLoading.value = false
  }
}

async function onSubmit() {
  if (!formRef.value) return
  submitting.value = true
  try {
    await formRef.value.validate()
    emit('submit', payload.value)
  } finally {
    submitting.value = false
  }
}
</script>