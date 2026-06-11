<template>
  <div class="event-search-body">
    <div class="event-search-field">
      <div class="event-search-label">事件范围</div>
      <el-date-picker
        v-model="draft.dateRange"
        type="daterange"
        unlink-panels
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        class="event-date-range"
      />
    </div>

    <div class="event-search-field">
      <div class="event-search-label">事件搜索</div>
      <div class="event-search-inline">
        <el-input
          v-model.trim="draft.keyword"
          clearable
          size="large"
          placeholder="超级电容、煤矿安全、REITs"
          class="event-keyword-input"
          @keyup.enter="onSearch"
        />

        <div class="event-search-actions">
          <el-button type="primary" :loading="loading" @click="onSearch">搜索</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'
import { createDefaultMarketEventFilters } from '../types/marketEvent'

const today = new Date()
const todayText = today.toISOString().slice(0, 10)
const monthStartText = `${todayText.slice(0, 8)}01`

const props = defineProps({
  modelValue: { type: Object, required: true },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'search', 'reset'])

const draft = reactive({
  ...createDefaultMarketEventFilters({
    date_from: monthStartText,
    date_to: todayText,
    event_type: 'all'
  }),
  dateRange: [monthStartText, todayText]
})

watch(
  () => props.modelValue,
  (value) => {
    const normalized = createDefaultMarketEventFilters({
      date_from: monthStartText,
      date_to: todayText,
      event_type: 'all',
      ...(value || {})
    })
    Object.assign(draft, normalized, {
      dateRange: buildDateRange(normalized.date_from, normalized.date_to)
    })
  },
  { immediate: true, deep: true }
)

function syncModel() {
  const [dateFrom, dateTo] = normalizeDateRange(draft.dateRange)
  emit('update:modelValue', {
    ...createDefaultMarketEventFilters({
      date_from: monthStartText,
      date_to: todayText,
      event_type: 'all'
    }),
    date_from: dateFrom,
    date_to: dateTo,
    keyword: draft.keyword || '',
    event_type: draft.event_type || 'all'
  })
}

function onSearch() {
  syncModel()
  emit('search')
}

function buildDateRange(dateFrom, dateTo) {
  if (dateFrom && dateTo) return [dateFrom, dateTo]
  if (dateFrom) return [dateFrom, dateFrom]
  if (dateTo) return [dateTo, dateTo]
  return [monthStartText, todayText]
}

function normalizeDateRange(range) {
  if (Array.isArray(range) && range.length === 2) {
    return [
      String(range[0] || monthStartText),
      String(range[1] || range[0] || todayText)
    ]
  }
  return [monthStartText, todayText]
}
</script>

<style scoped>
.event-search-body {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.event-search-field {
  display: flex;
  align-items: center;
  gap: 14px;
}

.event-search-label {
  flex: 0 0 72px;
  font-size: 13px;
  font-weight: 700;
  color: var(--el-text-color-regular);
}

.event-date-range {
  width: min(460px, 100%);
  max-width: 100%;
}

.event-search-inline {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.event-keyword-input {
  flex: 1 1 auto;
  min-width: 0;
}

.event-search-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 4px;
}

@media (max-width: 960px) {
  .event-search-field,
  .event-search-inline {
    align-items: stretch;
    flex-direction: column;
  }

  .event-search-label {
    flex: none;
  }

  .event-date-range {
    width: 100%;
  }

  .event-search-actions {
    padding-left: 0;
    justify-content: flex-end;
  }
}
</style>
