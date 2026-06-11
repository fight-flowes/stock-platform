<template>
  <div class="consecutive-board">
    <div class="board-header">
      <div class="board-title">
        <span class="fire-icon">🔥</span>
        连板榜
      </div>
      <div class="board-date">{{ tradeDate }}</div>
    </div>

    <el-skeleton v-if="loading" :rows="5" animated />
    <el-empty v-else-if="!loading && items.length === 0" description="暂无连板股" />
    
    <div v-else class="board-list">
      <div
        v-for="(item, index) in items"
        :key="item.id"
        class="board-card"
        :class="{ 'dragon-head': item.is_dragon_head }"
        @click="$emit('select', item)"
      >
        <div class="card-rank">
          <span class="rank-num" :class="'rank-' + (index + 1)">{{ index + 1 }}</span>
        </div>
        <div class="card-main">
          <div class="card-header">
            <span class="stock-name">{{ item.stock_name }}</span>
            <span class="stock-code">{{ item.stock_code }}</span>
          </div>
          <div class="card-badges">
            <el-tag :type="getConsecutiveType(item.consecutive_days)" effect="dark" size="small">
              {{ item.consecutive_days }}连板
            </el-tag>
            <div class="strength-stars">
              <span v-for="i in item.strength_level" :key="i" class="star">★</span>
            </div>
          </div>
          <div class="card-info">
            <div class="info-item">
              <span class="label">封板</span>
              <span class="value">{{ item.first_limit_time || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="label">封单</span>
              <span class="value">{{ formatAmount(item.seal_amount) }}</span>
            </div>
            <div class="info-item">
              <span class="label">开板</span>
              <span class="value">{{ item.open_count === 0 ? '一字' : item.open_count + '次' }}</span>
            </div>
          </div>
          <div v-if="item.industry || (item.concept_tags && item.concept_tags.length)" class="card-tags">
            <el-tag v-if="item.industry" size="small" type="info">{{ item.industry }}</el-tag>
            <el-tag v-for="tag in (item.concept_tags || []).slice(0, 2)" :key="tag" size="small">{{ tag }}</el-tag>
          </div>
          <div v-if="item.institution_net_buy > 0 || item.hot_money_net_buy > 0" class="card-fund">
            <span v-if="item.institution_net_buy > 0" class="fund-item inst">
              机构 +{{ formatAmount(item.institution_net_buy) }}
            </span>
            <span v-if="item.hot_money_net_buy > 0" class="fund-item youzi">
              游资 +{{ formatAmount(item.hot_money_net_buy) }}
            </span>
          </div>
        </div>
        <div v-if="item.is_dragon_head" class="dragon-badge">
          <span>🐉 龙头</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { getConsecutiveRank } from '../api/limitUp'

const props = defineProps({
  tradeDate: { type: String, required: true }
})

const emit = defineEmits(['select'])

const loading = ref(false)
const items = ref([])

function getConsecutiveType(days) {
  if (days >= 5) return 'danger'
  if (days >= 3) return 'warning'
  return 'primary'
}

function formatAmount(amount) {
  if (!amount) return '-'
  const yi = amount / 100000000
  if (yi >= 1) return `${yi.toFixed(2)}亿`
  const wan = amount / 10000
  return `${wan.toFixed(0)}万`
}

async function loadData() {
  if (!props.tradeDate) return
  loading.value = true
  try {
    const resp = await getConsecutiveRank(props.tradeDate)
    items.value = resp?.data || []
  } catch (e) {
    items.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.tradeDate, loadData, { immediate: true })
onMounted(loadData)
</script>

<style scoped>
.consecutive-board {
  background: var(--el-bg-color);
  border-radius: 12px;
  overflow: hidden;
}

.board-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.board-title {
  font-size: 18px;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 8px;
}

.fire-icon {
  font-size: 20px;
}

.board-date {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.board-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  max-height: 600px;
  overflow-y: auto;
}

.board-card {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.board-card:hover {
  background: var(--el-fill-color);
  transform: translateX(4px);
}

.board-card.dragon-head {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(239, 68, 68, 0.1) 100%);
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.card-rank {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  flex-shrink: 0;
}

.rank-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 800;
  background: var(--el-fill-color);
  color: var(--el-text-color-secondary);
}

.rank-num.rank-1 {
  background: linear-gradient(135deg, #ffd700, #ffb800);
  color: #fff;
}

.rank-num.rank-2 {
  background: linear-gradient(135deg, #c0c0c0, #a8a8a8);
  color: #fff;
}

.rank-num.rank-3 {
  background: linear-gradient(135deg, #cd7f32, #b87333);
  color: #fff;
}

.card-main {
  flex: 1;
  min-width: 0;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.stock-name {
  font-size: 15px;
  font-weight: 700;
}

.stock-code {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.card-badges {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.strength-stars {
  display: flex;
  gap: 2px;
}

.star {
  color: #f59e0b;
  font-size: 12px;
}

.card-info {
  display: flex;
  gap: 16px;
  margin-bottom: 6px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.info-item .label {
  color: var(--el-text-color-secondary);
}

.info-item .value {
  font-weight: 600;
}

.card-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.card-fund {
  display: flex;
  gap: 12px;
  font-size: 12px;
}

.fund-item {
  padding: 2px 6px;
  border-radius: 4px;
}

.fund-item.inst {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.fund-item.youzi {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.dragon-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  font-size: 11px;
  color: #f59e0b;
}
</style>