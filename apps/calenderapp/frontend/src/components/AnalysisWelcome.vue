<template>
  <div class="analysis-welcome">
    <div class="analysis-welcome-hero">
      <div class="analysis-welcome-icon">
        <VibeTradingIcon />
      </div>
      <div class="analysis-welcome-title">Eventra-Trading</div>
      <div class="analysis-welcome-desc">
        使用 Eventra-Trading 的会话能力，围绕市场、事件和个股进行连续追问。
      </div>
    </div>

    <div class="analysis-welcome-chips">
      <span v-for="item in capabilityChips" :key="item" class="analysis-chip">{{ item }}</span>
    </div>

    <div class="analysis-welcome-section">
      <div class="analysis-welcome-section-title">试试这些提问</div>
      <div class="analysis-example-grid">
        <button
          v-for="item in examples"
          :key="item.title"
          type="button"
          class="analysis-example-card"
          @click="$emit('select-example', item.prompt)"
        >
          <div class="analysis-example-header">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </div>
          <div class="analysis-example-desc">{{ item.desc }}</div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { DataAnalysis, Histogram, Opportunity, TrendCharts } from '@element-plus/icons-vue'
import VibeTradingIcon from './VibeTradingIcon.vue'

defineEmits(['select-example'])

const capabilityChips = [
  '流式输出',
  '多轮追问',
  '市场研判',
  '个股分析',
  '交易思路',
]

const examples = [
  {
    title: '复盘市场',
    desc: '概括今天 A 股盘面的主线、分歧和情绪变化',
    prompt: '请帮我复盘今天 A 股市场的主线、分歧和情绪变化，给出简明结论。',
    icon: TrendCharts,
  },
  {
    title: '分析个股',
    desc: '从题材、资金和预期角度分析一只股票',
    prompt: '请从题材逻辑、资金表现和预期差三个角度分析一只股票的交易价值。',
    icon: DataAnalysis,
  },
  {
    title: '拆解逻辑',
    desc: '把一个热点事件拆成受益方向和风险点',
    prompt: '请把一个热点事件拆解成受益方向、受损方向、核心变量和风险点。',
    icon: Opportunity,
  },
  {
    title: '生成问法',
    desc: '不知道怎么问时，先让 AI 帮你展开问题',
    prompt: '如果我要分析一个市场热点，你建议我从哪些问题开始问？请给我一个提问清单。',
    icon: Histogram,
  },
]
</script>

<style scoped>
.analysis-welcome {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px 8px 8px;
}

.analysis-welcome-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-align: center;
}

.analysis-welcome-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
}

.analysis-welcome-title {
  font-size: 21px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

.analysis-welcome-desc {
  max-width: 420px;
  line-height: 1.65;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.analysis-welcome-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.analysis-chip {
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid var(--el-border-color-light);
  background: var(--el-fill-color-blank);
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.analysis-welcome-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.analysis-welcome-section-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--el-text-color-secondary);
}

.analysis-example-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.analysis-example-card {
  padding: 12px;
  border-radius: 16px;
  border: 1px solid var(--el-border-color-light);
  background: var(--el-fill-color-blank);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

.analysis-example-card:hover {
  border-color: var(--el-color-primary-light-5);
  transform: translateY(-1px);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

.analysis-example-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.analysis-example-desc {
  margin-top: 8px;
  font-size: 11px;
  line-height: 1.55;
  color: var(--el-text-color-secondary);
}

@media (max-width: 640px) {
  .analysis-example-grid {
    grid-template-columns: 1fr;
  }
}
</style>
