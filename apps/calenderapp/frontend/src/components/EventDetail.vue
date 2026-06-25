<template>
  <div v-loading="loading" class="event-detail-card">
    <el-empty v-if="!loading && !event" description="暂无事件详情" :image-size="72" />

    <template v-else-if="event">
      <div class="event-detail-top">
        <div class="event-detail-name">{{ event.event_name || '未命名事件' }}</div>
        <div class="event-detail-time">{{ event.event_time_text || '-' }}</div>
      </div>

      <div class="event-detail-tags">
        <el-tag size="small" :type="eventTypeTagType(event)">{{ eventTypeLabel(event) }}</el-tag>
        <el-tag v-if="event.primary_industry" size="small" type="info">{{ event.primary_industry }}</el-tag>
        <el-tag v-if="event.primary_theme" size="small" type="success">{{ event.primary_theme }}</el-tag>
        <el-tag v-if="event.is_cross_stock" size="small" type="warning">跨股票</el-tag>
      </div>

      <div v-if="event.scope_reason" class="event-scope-reason">
        {{ event.scope_reason }}
      </div>

      <div class="event-detail-grid">
        <div class="detail-chip">
          <div class="detail-chip-label">首次出现</div>
          <div class="detail-chip-value">{{ event.first_seen_date || '-' }}</div>
        </div>
        <div class="detail-chip">
          <div class="detail-chip-label">最近活跃</div>
          <div class="detail-chip-value">{{ event.latest_active_date || '-' }}</div>
        </div>
        <div class="detail-chip">
          <div class="detail-chip-label">影响股票</div>
          <div class="detail-chip-value">{{ event.affected_stocks?.length || 0 }}</div>
        </div>
        <div class="detail-chip">
          <div class="detail-chip-label">事件来源</div>
          <div class="detail-chip-value">{{ event.source_reports?.length || 0 }}</div>
        </div>
      </div>

      <div class="detail-section">
        <div class="detail-section-title">事件内容</div>
        <div class="detail-panel">{{ event.event_content || '暂无事件内容' }}</div>
      </div>

      <div class="detail-section">
        <div class="detail-section-title">影响个股</div>
        <div v-if="event.affected_stocks?.length" class="stock-tag-list">
          <el-tag
            v-for="item in event.affected_stocks"
            :key="`${item.stock_code}-${item.stock_name}`"
            size="small"
            @click="emit('open-stock', item)"
          >
            {{ item.stock_name || '-' }}<span v-if="item.stock_code"> {{ item.stock_code }}</span>
          </el-tag>
        </div>
        <el-empty v-else description="暂无明确影响个股" :image-size="52" />
      </div>

      <div class="detail-section">
        <div class="detail-section-title">事件来源</div>
        <div v-if="event.source_reports?.length" class="source-report-list">
          <div
            v-for="report in event.source_reports"
            :key="report.report_id"
            class="source-report-item"
          >
            <div class="source-report-header">
              <span class="source-report-heading">事件来源</span>
              <el-button size="small" plain @click="emit('open-report', report)">查看原报告</el-button>
            </div>

            <div v-if="hasSourceInfo(report)" class="source-report-source">
              <div v-if="report.source_name" class="source-report-source-row">
                <span class="source-report-source-label">来源平台</span>
                <span class="source-report-source-value">{{ report.source_name }}</span>
              </div>
              <div v-if="report.source_url" class="source-report-source-row">
                <span class="source-report-source-label">原始URL</span>
                <a
                  class="source-report-link"
                  :href="report.source_url"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {{ report.source_url }}
                </a>
              </div>
            </div>
            <div v-else class="source-report-empty">暂无来源信息</div>
          </div>
        </div>
        <el-empty v-else description="暂无事件来源" :image-size="52" />
      </div>
    </template>
  </div>
</template>

<script setup>
defineProps({
  event: { type: Object, default: null },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['open-report', 'open-stock'])

function eventTypeLabel(event) {
  const eventType = String(event?.event_type || '').toLowerCase()
  if (eventType === 'industry') return '行业事件'
  if (eventType === 'stock') return '个股事件'

  const scope = String(event?.event_scope || '').toLowerCase()
  if (scope === 'industry') return '行业事件'
  if (scope === 'mixed') return '行业事件'
  if (scope === 'macro') return '行业事件'
  return '个股事件'
}

function eventTypeTagType(event) {
  const eventType = String(event?.event_type || '').toLowerCase()
  if (eventType === 'industry') return 'warning'
  if (eventType === 'stock') return ''

  const scope = String(event?.event_scope || '').toLowerCase()
  if (scope === 'industry') return 'warning'
  if (scope === 'mixed') return 'warning'
  if (scope === 'macro') return 'warning'
  return ''
}

function hasSourceInfo(report) {
  return Boolean(String(report?.source_name || '').trim() || String(report?.source_url || '').trim())
}
</script>

<style scoped>
.event-detail-card {
  min-height: 420px;
  padding: 20px 52px 12px 8px;
  background: transparent;
}

.event-detail-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.event-detail-name {
  font-size: 24px;
  font-weight: 900;
  line-height: 1.45;
  color: var(--el-text-color-primary);
}

.event-detail-time {
  flex-shrink: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.event-detail-tags {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.event-detail-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.event-scope-reason {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--sc-event-dialog-bg, var(--el-bg-color-overlay));
  border: 1px solid var(--el-border-color-light);
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}

.detail-chip {
  padding: 14px 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 16px;
  background: var(--sc-event-dialog-bg, var(--el-bg-color-overlay));
}

.detail-chip-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.detail-chip-value {
  margin-top: 6px;
  font-size: 16px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

.detail-section {
  margin-top: 20px;
}

.detail-section-title {
  margin-bottom: 10px;
  font-size: 15px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

.detail-panel {
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--sc-event-dialog-bg, var(--el-bg-color-overlay));
  border: 1px solid var(--el-border-color-light);
  color: var(--el-text-color-regular);
  line-height: 1.8;
}

.stock-tag-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.source-report-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.source-report-item {
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
  background: var(--sc-event-dialog-bg, var(--el-bg-color-overlay));
}

.source-report-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.source-report-heading {
  font-size: 14px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.source-report-source {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--el-border-color);
}

.source-report-source-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-top: 6px;
}

.source-report-source-row:first-child {
  margin-top: 0;
}

.source-report-source-label {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.source-report-source-value {
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.source-report-link {
  font-size: 12px;
  color: var(--el-color-primary);
  word-break: break-all;
  text-decoration: none;
}

.source-report-link:hover {
  text-decoration: underline;
}

.source-report-empty {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--el-border-color);
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

@media (max-width: 640px) {
  .source-report-header {
    flex-direction: column;
    align-items: stretch;
  }
}

@media (max-width: 1080px) {
  .event-detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .event-detail-card {
    padding: 18px 44px 8px 4px;
  }

  .event-detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
