<template>
  <div class="fund-flow">
    <div class="flow-header">
      <div class="flow-title">资金流向</div>
      <el-radio-group v-model="activeTab" size="small">
        <el-radio-button value="institution">机构</el-radio-button>
        <el-radio-button value="hotMoney">游资</el-radio-button>
      </el-radio-group>
    </div>

    <el-skeleton v-if="loading" :rows="5" animated />
    <el-empty v-else-if="!loading && currentList.length === 0" description="暂无数据" />
    
    <div v-else class="flow-list">
      <div
        v-for="(item, index) in currentList"
        :key="item.id"
        class="flow-item"
        @click="$emit('select', item)"
      >
        <div class="item-rank">{{ index + 1 }}</div>
        <div class="item-main">
          <div class="item-header">
            <span class="item-name">{{ item.stock_name }}</span>
            <el-tag size="small" :type="getConsecutiveType(item.consecutive_days)">
              {{ item.consecutive_days }}板
            </el-tag>
          </div>
          <div class="item-info">
            <span class="item-code">{{ item.stock_code }}</span>
            <span class="item-industry" v-if="item.industry">{{ item.industry }}</span>
          </div>
        </div>
        <div class="item-amount" :class="{ positive: currentAmount(item) > 0 }">
          {{ formatAmount(currentAmount(item)) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getFundFlowRank } from '../api/limitUp'

const props = defineProps({
  startDate: { type: String, default: '' },
  endDate: { type: String, default: '' }
})

const emit = defineEmits(['select'])

const loading = ref(false)
const activeTab = ref('institution')
const institutionTop = ref([])
const hotMoneyTop = ref([])

const currentList = computed(() => {
  return activeTab.value === 'institution' ? institutionTop.value : hotMoneyTop.value
})

function currentAmount(item) {
  return activeTab.value === 'institution' ? item.institution_net_buy : item.hot_money_net_buy
}

function getConsecutiveType(days) {
  if (days >= 5) return 'danger'
  if (days >= 3) return 'warning'
  return 'primary'
}

function formatAmount(amount) {
  if (!amount) return '-'
  const yi = amount / 100000000
  if (Math.abs(yi) >= 1) return `${yi > 0 ? '+' : ''}${yi.toFixed(2)}亿`
  const wan = amount / 10000
  return `${wan > 0 ? '+' : ''}${wan.toFixed(0)}万`
}

async function loadData() {
  if (!props.startDate || !props.endDate) return
  loading.value = true
  try {
    const resp = await getFundFlowRank(props.startDate, props.endDate, 20)
    institutionTop.value = resp?.data?.institution_top || []
    hotMoneyTop.value = resp?.data?.hot_money_top || []
  } catch (e) {
    institutionTop.value = []
    hotMoneyTop.value = []
  } finally {
    loading.value = false
  }
}

watch(() => [props.startDate, props.endDate], loadData, { immediate: true })
onMounted(loadData)
</script>

<style scoped>
.fund-flow {
  background: var(--el-bg-color);
  border-radius: 12px;
  overflow: hidden;
}

.flow-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.flow-title {
  font-size: 16px;
  font-weight: 700;
}

.flow-list {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 400px;
  overflow-y: auto;
}

.flow-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.flow-item:hover {
  background: var(--el-fill-color-lighter);
}

.item-rank {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--el-fill-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.item-main {
  flex: 1;
  min-width: 0;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.item-name {
  font-size: 14px;
  font-weight: 600;
}

.item-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.item-amount {
  font-size: 14px;
  font-weight: 700;
  color: var(--el-text-color-secondary);
}

.item-amount.positive {
  color: #ef4444;
}
</style>