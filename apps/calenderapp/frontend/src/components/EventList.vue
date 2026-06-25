<template>
  <el-card shadow="never" class="event-board-card">
    <template #header>
      <div class="event-board-header">
        <div class="event-board-title-group">
          <div class="event-board-title">{{ cardTitle }}</div>
          <slot name="header-extra"></slot>
        </div>
        <el-tag size="small" effect="plain">{{ totalCount }}</el-tag>
      </div>
    </template>

    <div v-loading="loading" class="event-board-body">
      <el-empty v-if="!loading && totalCount === 0" description="暂无事件" :image-size="72" />

      <template v-else>
        <div v-for="section in sections" :key="section.key" class="timeline-section">
          <div
            v-if="!hideSectionHeader && (section.title || section.summary)"
            class="timeline-section-header"
          >
            <div class="timeline-section-title">{{ section.title }}</div>
            <div v-if="section.summary" class="timeline-section-summary">{{ section.summary }}</div>
          </div>

          <el-empty
            v-if="!section.groups.length"
            :description="section.emptyText"
            :image-size="56"
          />

          <el-timeline v-else>
            <el-timeline-item
              v-for="group in section.groups"
              :key="`${section.key}-${group.dateKey}`"
              :timestamp="group.dateLabel"
              placement="top"
              :type="section.key === 'future' ? 'primary' : 'success'"
            >
              <div class="timeline-date-card">
                <div class="timeline-date-summary">
                  <span v-if="showIndustrySummary(group)">行业事件 {{ group.industryEvents.length }}</span>
                  <span v-if="showStockSummary(group)">个股事件 {{ group.stockEvents.length }}</span>
                  <span>合计 {{ group.totalCount }}</span>
                </div>

                <div v-if="group.industryEvents.length" class="timeline-block">
                  <div class="timeline-block-title">{{ industryBlockTitle }}</div>
                  <div class="timeline-event-list">
                    <div
                      v-for="item in group.industryEvents"
                      :key="item.event_key"
                      :class="['timeline-event-card', { active: item.event_key === selectedEventKey }]"
                      @click="emit('select', item)"
                    >
                      <div class="timeline-event-top">
                        <div class="timeline-event-title">{{ item.event_name || '未命名事件' }}</div>
                        <div class="timeline-event-actions">
                          <el-button
                            size="small"
                            :type="getReviewButtonType(item)"
                            plain
                            :loading="isReviewLoading(item)"
                            @click.stop="emit('review', item)"
                          >
                            {{ getReviewButtonText(item) }}
                          </el-button>
                          <el-tag size="small" :type="eventTruthTagType(item)">{{ eventTruthTagText(item) }}</el-tag>
                          <el-button
                            link
                            size="small"
                            class="timeline-event-remove"
                            title="从我的关注列表中移除"
                            @click.stop="emit('unfavorite', item)"
                          >
                            ✕
                          </el-button>
                        </div>
                      </div>
                      <div class="timeline-event-summary">{{ previewText(item) }}</div>
                      <div class="timeline-event-meta">
                        <span v-if="item.primary_industry">{{ item.primary_industry }}</span>
                        <span v-if="item.primary_theme">{{ item.primary_theme }}</span>
                        <span>影响 {{ item.affected_stock_count || 0 }} 只股票</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="group.stockEvents.length" class="timeline-block">
                  <div class="timeline-block-title">{{ stockBlockTitle }}</div>
                  <div class="timeline-event-list">
                    <div
                      v-for="item in group.stockEvents"
                      :key="item.event_key"
                      :class="['timeline-event-card', { active: item.event_key === selectedEventKey }]"
                      @click="emit('select', item)"
                    >
                      <div class="timeline-event-top">
                        <div class="timeline-event-title">{{ item.event_name || '未命名事件' }}</div>
                        <div class="timeline-event-actions">
                          <el-button
                            size="small"
                            :type="getReviewButtonType(item)"
                            plain
                            :loading="isReviewLoading(item)"
                            @click.stop="emit('review', item)"
                          >
                            {{ getReviewButtonText(item) }}
                          </el-button>
                          <el-tag size="small" :type="eventTruthTagType(item)">{{ eventTruthTagText(item) }}</el-tag>
                          <el-button
                            link
                            size="small"
                            class="timeline-event-remove"
                            title="从我的关注列表中移除"
                            @click.stop="emit('unfavorite', item)"
                          >
                            ✕
                          </el-button>
                        </div>
                      </div>
                      <div class="timeline-event-summary">{{ previewText(item) }}</div>
                      <div class="timeline-event-meta">
                        <span v-if="item.primary_theme">{{ item.primary_theme }}</span>
                        <span v-if="item.primary_industry">{{ item.primary_industry }}</span>
                        <span>来源报告 {{ item.source_report_count || 0 }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </template>
    </div>
  </el-card>
</template>

<script setup>
const props = defineProps({
  sections: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  selectedEventKey: { type: String, default: '' },
  totalCount: { type: Number, default: 0 },
  cardTitle: { type: String, default: '事件列表' },
  hideSectionHeader: { type: Boolean, default: false },
  scopeFilter: { type: String, default: 'all' },
  reviewStatusMap: { type: Object, default: () => ({}) },
  reviewLoadingMap: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['select', 'review', 'unfavorite'])

const industryBlockTitle = '行业事件'
const stockBlockTitle = '个股事件'

function previewText(item) {
  const content = String(item?.event_content || '').trim()
  if (!content) {
    if (item?.primary_theme && item?.primary_industry) {
      return `${item.primary_industry} / ${item.primary_theme}`
    }
    return item?.primary_theme || item?.primary_industry || '暂无事件摘要'
  }
  return content
}

function showIndustrySummary(group) {
  if (props.scopeFilter === 'stock') return false
  if (props.scopeFilter === 'industry') return true
  return group.industryEvents.length > 0
}

function showStockSummary(group) {
  if (props.scopeFilter === 'industry') return false
  if (props.scopeFilter === 'stock') return true
  return group.stockEvents.length > 0
}

function getReviewState(item) {
  const eventKey = String(item?.event_key || '')
  const cached = props.reviewStatusMap?.[eventKey]
  if (cached) {
    return cached
  }
  const listStatus = String(item?.review_status || '').trim()
  if (!listStatus) {
    return null
  }
  return {
    review_status: listStatus,
    updated_at: String(item?.review_updated_at || '')
  }
}

function isReviewLoading(item) {
  const eventKey = String(item?.event_key || '')
  return Boolean(props.reviewLoadingMap?.[eventKey])
}

function getReviewButtonText(item) {
  if (isReviewLoading(item)) return '核查中'
  const review = getReviewState(item)
  const status = String(review?.review_status || '')
  if (status === 'completed') return '查看核查'
  if (status === 'failed') return '重试核查'
  if (status === 'pending') return '核查中'
  return '核查'
}

function getReviewButtonType(item) {
  const review = getReviewState(item)
  const status = String(review?.review_status || '')
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'pending') return 'primary'
  return 'info'
}

// 核查真实性标签：仅当核查完成时按 event_truth 显示，否则统一显示“未核查”
function eventTruthTagText(item) {
  const review = getReviewState(item)
  const status = String(review?.review_status || '')
  if (status !== 'completed') return '未核查'
  const truth = String(item?.event_truth || review?.event_truth || '').trim()
  if (truth === 'true') return '已确认'
  if (truth === 'dubious') return '存疑'
  if (truth === 'false') return '失实'
  return '未证实'
}

function eventTruthTagType(item) {
  const review = getReviewState(item)
  const status = String(review?.review_status || '')
  if (status !== 'completed') return 'info'
  const truth = String(item?.event_truth || review?.event_truth || '').trim()
  if (truth === 'true') return 'success'
  if (truth === 'dubious') return 'warning'
  if (truth === 'false') return 'danger'
  return 'info'
}
</script>

<style scoped>
.event-board-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.event-board-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.event-board-title {
  font-size: 18px;
  font-weight: 900;
  color: var(--el-text-color-primary);
}

.event-board-body {
  min-height: 640px;
}

.timeline-section + .timeline-section {
  margin-top: 24px;
}

.timeline-section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.timeline-section-title {
  font-size: 16px;
  font-weight: 900;
  color: var(--el-text-color-primary);
}

.timeline-section-summary {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.timeline-date-card {
  padding: 16px 18px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 18px;
  background: linear-gradient(180deg, var(--el-bg-color-overlay) 0%, var(--el-fill-color-blank) 100%);
}

.timeline-date-summary {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.timeline-date-summary span {
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-light);
}

.timeline-block + .timeline-block {
  margin-top: 16px;
}

.timeline-block-title {
  margin: 14px 0 10px;
  font-size: 13px;
  font-weight: 800;
  color: var(--el-text-color-regular);
}

.timeline-event-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.timeline-event-card {
  padding: 13px 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 16px;
  background: var(--el-bg-color-overlay);
  cursor: pointer;
  transition: all 0.2s ease;
}

.timeline-event-card:hover,
.timeline-event-card.active {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
  box-shadow: 0 10px 24px rgba(59, 130, 246, 0.12);
}

.timeline-event-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.timeline-event-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* "从关注列表移除" 按钮：低对比度叉号，悬浮时变红，避免抢占核查按钮的视觉权重。 */
.timeline-event-remove {
  margin-left: 4px;
  padding: 0 6px !important;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  line-height: 1;
}

.timeline-event-remove:hover {
  color: var(--el-color-danger);
}

.timeline-event-title {
  font-weight: 800;
  line-height: 1.55;
  color: var(--el-text-color-primary);
}

.timeline-stock-preview {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: right;
}

.timeline-event-summary {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.timeline-event-meta {
  margin-top: 10px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
