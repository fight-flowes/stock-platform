<template>
  <div v-loading="loading" class="event-review-card">
    <el-empty v-if="!loading && !review" description="暂无核查结果" :image-size="72" />

    <template v-else-if="review">
      <div class="event-review-top">
        <div class="event-review-name">{{ event?.event_name || '未命名事件' }}</div>
        <div class="event-review-time">{{ event?.event_time_text || '-' }}</div>
      </div>

      <div class="event-review-tags">
        <el-tag size="small" :type="eventTypeTagType(event)">{{ eventTypeLabel(event) }}</el-tag>
        <el-tag v-if="event?.primary_industry" size="small" type="info">{{ event.primary_industry }}</el-tag>
        <el-tag v-if="event?.primary_theme" size="small" type="success">{{ event.primary_theme }}</el-tag>
      </div>

      <div v-if="headlineText" class="event-review-summary">
        {{ headlineText }}
      </div>

      <div class="event-review-toolbar">
        <div class="review-confidence">置信度：{{ confidenceText }}</div>
        <el-button size="small" plain @click="emit('refresh')">重新核查</el-button>
      </div>

      <div class="review-grid">
        <div :class="['review-chip', `chip-${eventTruthTone}`]">
          <div class="review-chip-label">真实性</div>
          <div class="review-chip-value">{{ eventTruthLabel }}</div>
        </div>
        <div :class="['review-chip', `chip-${timeTruthTone}`]">
          <div class="review-chip-label">时间一致性</div>
          <div class="review-chip-value">{{ timeTruthLabel }}</div>
        </div>
        <div :class="['review-chip', `chip-${contentTruthTone}`]">
          <div class="review-chip-label">内容支持</div>
          <div class="review-chip-value">{{ contentTruthLabel }}</div>
        </div>
        <div :class="['review-chip', `chip-${dispositionTone}`]">
          <div class="review-chip-label">研究结论</div>
          <div class="review-chip-value">{{ dispositionLabel }}</div>
        </div>
      </div>

      <div v-if="timeDiagnostic" class="review-time-diagnostic">
        <div class="time-diagnostic-row">
          <span class="time-diagnostic-label">事件声称</span>
          <span class="time-diagnostic-value">{{ timeDiagnostic.eventDate || '—' }}</span>
        </div>
        <div class="time-diagnostic-row">
          <span class="time-diagnostic-label">证据最早</span>
          <span class="time-diagnostic-value">
            {{ timeDiagnostic.earliestDate || '—' }}
            <span v-if="timeDiagnostic.gapText" class="time-diagnostic-gap">{{ timeDiagnostic.gapText }}</span>
          </span>
        </div>
        <div v-if="timeDiagnostic.earliestTitle" class="time-diagnostic-source">
          {{ timeDiagnostic.earliestTitle }}
        </div>
        <div v-if="timeDiagnostic.hint" class="time-diagnostic-hint">
          {{ timeDiagnostic.hint }}
        </div>
      </div>

      <div class="review-section">
        <div class="review-section-title">分析摘要</div>
        <div class="review-panel">{{ summaryText }}</div>
      </div>

      <div v-if="claimEntities.length" class="review-section">
        <div class="review-section-title">事件 vs 证据 对照</div>
        <div class="review-claim-vs-evidence">
          <div class="claim-block">
            <div class="claim-label">事件原文</div>
            <div class="claim-text">{{ claimText }}</div>
            <div class="claim-entities-row">
              <span class="claim-entities-label">核心实体：</span>
              <el-tag
                v-for="entity in claimEntities"
                :key="entity"
                size="small"
                effect="dark"
                type="primary"
                class="claim-entity-tag"
              >{{ entity }}</el-tag>
            </div>
          </div>

          <div class="coverage-block">
            <div class="coverage-label">证据覆盖度</div>
            <el-empty
              v-if="!keyItems.length"
              description="暂无证据可对照"
              :image-size="48"
            />
            <table v-else class="coverage-table">
              <thead>
                <tr>
                  <th class="coverage-th-idx">#</th>
                  <th class="coverage-th-source">来源</th>
                  <th
                    v-for="entity in claimEntities"
                    :key="`th-${entity}`"
                    class="coverage-th-entity"
                  >{{ entity }}</th>
                  <th class="coverage-th-rate">命中率</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in coverageRows" :key="`row-${ri}`">
                  <td class="coverage-td-idx">{{ ri + 1 }}</td>
                  <td class="coverage-td-source">
                    <el-tag size="small" :type="sourceTypeTagType(row.source_type)">
                      {{ sourceTypeLabel(row.source_type) }}
                    </el-tag>
                  </td>
                  <td
                    v-for="entity in claimEntities"
                    :key="`cell-${ri}-${entity}`"
                    :class="['coverage-td-cell', row.hits[entity] ? 'cell-hit' : 'cell-miss']"
                  >
                    {{ row.hits[entity] ? '✓' : '✗' }}
                  </td>
                  <td :class="['coverage-td-rate', coverageRateClass(row.rate)]">
                    {{ Math.round(row.rate * 100) }}%
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="review-section">
        <div class="review-section-title">关键证据链</div>
        <el-empty v-if="!keyItems.length" description="暂无关键证据" :image-size="52" />
        <div v-else class="review-evidence-list">
          <div v-for="(item, index) in keyItems" :key="`${item.title}-${index}`" class="review-evidence-item">
            <div class="review-evidence-header">
              <div class="review-evidence-title">{{ index + 1 }}. {{ item.title || '未命名证据' }}</div>
              <div class="review-evidence-badges">
                <el-tag size="small" :type="sourceTypeTagType(item.source_type)">
                  {{ sourceTypeLabel(item.source_type) }}
                </el-tag>
                <el-tag size="small" :type="matchLevelTagType(item.match_level)" effect="plain">
                  {{ matchLevelLabel(item.match_level) }}
                </el-tag>
              </div>
            </div>
            <div class="review-evidence-source">
              <div class="review-evidence-source-row">
                <span class="review-evidence-source-label">来源机构</span>
                <span class="review-evidence-source-value">{{ item.publisher || '未知来源' }}</span>
              </div>
              <div v-if="item.published_at" class="review-evidence-source-row">
                <span class="review-evidence-source-label">发布时间</span>
                <span class="review-evidence-source-value">{{ item.published_at }}</span>
              </div>
              <div v-if="item.url" class="review-evidence-source-row">
                <span class="review-evidence-source-label">原始URL</span>
                <a :href="item.url" target="_blank" rel="noopener noreferrer" class="review-evidence-link">
                  {{ item.url }}
                </a>
              </div>
            </div>
            <div class="review-evidence-note">{{ item.note || '暂无说明' }}</div>
          </div>
        </div>
      </div>

      <div class="review-section">
        <div class="review-section-title">缺失的关键信息</div>
        <el-empty v-if="!missingItems.length" description="暂无缺失项" :image-size="52" />
        <ol v-else class="review-list">
          <li v-for="(item, index) in missingItems" :key="`${item}-${index}`">{{ item }}</li>
        </ol>
      </div>

      <div class="review-section">
        <div class="review-section-title">建议操作</div>
        <el-empty v-if="!nextActions.length" description="暂无建议操作" :image-size="52" />
        <ol v-else class="review-list">
          <li v-for="(item, index) in nextActions" :key="`${item}-${index}`">{{ item }}</li>
        </ol>
      </div>

      <el-collapse class="review-debug">
        <el-collapse-item title="调试信息" name="debug">
          <div class="review-debug-item"><strong>主查询：</strong>{{ debug.primary_query || '-' }}</div>
          <div class="review-debug-item"><strong>后备查询：</strong>{{ fallbackText }}</div>
          <div class="review-debug-item"><strong>警告：</strong>{{ warningsText }}</div>
        </el-collapse-item>
      </el-collapse>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  event: { type: Object, default: null },
  review: { type: Object, default: null },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['refresh'])

const payload = computed(() => (props.review?.review_payload && typeof props.review.review_payload === 'object'
  ? props.review.review_payload
  : {}))
const reviewBlock = computed(() => (payload.value.review && typeof payload.value.review === 'object' ? payload.value.review : {}))
const evidenceBlock = computed(() => (payload.value.evidence && typeof payload.value.evidence === 'object' ? payload.value.evidence : {}))
const debug = computed(() => (payload.value.debug && typeof payload.value.debug === 'object' ? payload.value.debug : {}))

const keyItems = computed(() => Array.isArray(evidenceBlock.value.key_items) ? evidenceBlock.value.key_items : [])
const missingItems = computed(() => Array.isArray(evidenceBlock.value.missing) ? evidenceBlock.value.missing : [])
const nextActions = computed(() => Array.isArray(payload.value.next_action) ? payload.value.next_action : [])

// === 事件 vs 证据 对照视图 ===
// claimText: 事件原文。优先用 event_content（更详细），降级到 event_name。
// claimEntities: 事件名抽出的核心实体，用跟 reviewer.py _extract_key_entities 同样的规则
// （CJK/拉丁/数字 token，长度排序，去停用词），保证视觉判定跟后端打分逻辑一致。
const claimText = computed(() => {
  const content = String(props.event?.event_content || '').trim()
  return content || String(props.event?.event_name || '').trim()
})

const claimEntities = computed(() => extractClaimEntities(props.event?.event_name || ''))

const coverageRows = computed(() => {
  const entities = claimEntities.value
  if (!entities.length) return []
  return keyItems.value.map((item) => {
    const haystack = `${item?.title || ''} ${item?.snippet || ''}`.toLowerCase()
    const hits = {}
    let hitCount = 0
    for (const ent of entities) {
      const ok = haystack.includes(ent.toLowerCase())
      hits[ent] = ok
      if (ok) hitCount += 1
    }
    return {
      source_type: item?.source_type || 'aggregator',
      hits,
      rate: entities.length > 0 ? hitCount / entities.length : 0,
    }
  })
})

const eventTruthLabel = computed(() => mapEventTruth(reviewBlock.value.event_truth || props.review?.event_truth))
const timeTruthLabel = computed(() => mapTimeTruth(reviewBlock.value.time_truth || props.review?.time_truth))
const contentTruthLabel = computed(() => mapContentTruth(reviewBlock.value.content_truth || props.review?.content_truth))
const dispositionLabel = computed(() => mapDisposition(reviewBlock.value.disposition || props.review?.disposition))

// 4 chip 的色调，用单一 tone 字段（success / warning / danger / neutral）
// 驱动 CSS 变量。比 el-tag 的 type 属性更灵活，因为 chip 是自绘块。
const eventTruthTone = computed(() => eventTruthToTone(reviewBlock.value.event_truth || props.review?.event_truth))
const timeTruthTone = computed(() => timeTruthToTone(reviewBlock.value.time_truth || props.review?.time_truth))
const contentTruthTone = computed(() => contentTruthToTone(reviewBlock.value.content_truth || props.review?.content_truth))
const dispositionTone = computed(() => dispositionToTone(reviewBlock.value.disposition || props.review?.disposition))

// 时间一致性诊断卡：只在 time_mismatch / time_dubious 时返回非空对象。
// 帮用户区分两种语义不同的"时间不一致"：
//   1) 证据日期早于事件日期（典型：旧闻新炒，技术早被报道，事件日是市场反应日）
//   2) 证据日期晚于事件日期（事件日期可能标错，或证据是事件后续报道）
// reviewer.py 的 _score_time_status 当前只输出 time_mismatch 一种，
// 没有区分这两种情况，前端这里做最小化的诊断展示让用户自己判断。
const timeDiagnostic = computed(() => {
  const tt = reviewBlock.value.time_truth || props.review?.time_truth || ''
  if (tt !== 'time_mismatch' && tt !== 'time_dubious') return null

  const eventDateRaw = props.event?.event_time_text || ''
  const eventDate = extractIsoDate(eventDateRaw)
  if (!eventDate) return null

  // 从 evidence 的 published_at 里抽所有 ISO date，按时间顺序排
  const dates = []
  for (const item of keyItems.value) {
    const d = extractIsoDate(item?.published_at || '')
    if (d) dates.push({ date: d, title: String(item?.title || '') })
  }
  if (!dates.length) {
    // 即使没拿到证据日期，仍然展示事件日期作为参考
    return {
      eventDate,
      earliestDate: '',
      earliestTitle: '',
      gapText: '',
      hint: '证据未提供明确发布日期，无法对齐。',
    }
  }
  dates.sort((a, b) => a.date.localeCompare(b.date))
  const earliest = dates[0]

  // 算天数差
  const eventTs = Date.parse(eventDate)
  const earliestTs = Date.parse(earliest.date)
  let gapText = ''
  let hint = ''
  if (Number.isFinite(eventTs) && Number.isFinite(earliestTs)) {
    const diffDays = Math.round((eventTs - earliestTs) / 86400000)
    if (diffDays > 0) {
      gapText = `(早于事件 ${diffDays} 天)`
      if (diffDays >= 60) {
        hint = '证据明显早于事件声称日期，可能是已被报道过的"旧闻新炒"——事件本身真实，事件日更可能是市场反应日。'
      } else if (diffDays >= 14) {
        hint = '证据略早于事件声称日期，事件可能在该日之前已被部分披露。'
      }
    } else if (diffDays < 0) {
      gapText = `(晚于事件 ${Math.abs(diffDays)} 天)`
      if (Math.abs(diffDays) >= 14) {
        hint = '证据晚于事件声称日期，可能是事件后续追踪报道。请确认事件原始日期是否准确。'
      }
    }
  }

  return {
    eventDate,
    earliestDate: earliest.date,
    earliestTitle: earliest.title.slice(0, 80),
    gapText,
    hint,
  }
})

// 从任意字符串里抽 YYYY-MM-DD（容忍 published_at 形如 "2025-03-03T22:00:00"
// 或 event_time_text 形如 "2026-06-17（锚点）"）。失败返回空字符串。
function extractIsoDate(value) {
  const m = String(value || '').match(/(20\d{2}-\d{2}-\d{2})/)
  return m ? m[1] : ''
}

const headlineText = computed(() => String(reviewBlock.value.headline || props.review?.headline || '暂无一句话判断'))
const summaryText = computed(() => String(reviewBlock.value.summary || props.review?.summary || '暂无分析摘要'))
const confidenceText = computed(() => {
  const value = Number(reviewBlock.value.confidence ?? props.review?.confidence ?? 0)
  return `${Math.round(value * 100)}% | ${mapConfidence(value)}`
})
const fallbackText = computed(() => {
  const items = Array.isArray(debug.value.fallback_queries) ? debug.value.fallback_queries : []
  return items.length ? items.join('；') : '-'
})
const warningsText = computed(() => {
  const items = Array.isArray(debug.value.warnings) ? debug.value.warnings : []
  return items.length ? items.join('；') : '-'
})

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

function mapEventTruth(value) {
  if (value === 'true') return '已确认'
  if (value === 'dubious') return '存疑'
  if (value === 'false') return '失实'
  return '未证实'
}

function mapTimeTruth(value) {
  if (value === 'time_aligned') return '时间一致'
  if (value === 'time_mismatch') return '时间未对齐'
  return '时间待确认'
}

function mapContentTruth(value) {
  if (value === 'accurate') return '有直接支持'
  if (value === 'mostly_accurate') return '基本支持'
  if (value === 'dubious') return '部分支持'
  return '未获直接支持'
}

function mapDisposition(value) {
  if (value === 'adopt') return '可采纳'
  if (value === 'adopt_with_caution') return '谨慎采纳'
  if (value === 'reject') return '不采纳'
  return '待复核'
}

function mapConfidence(value) {
  if (value >= 0.85) return '高'
  if (value >= 0.7) return '较高'
  if (value >= 0.5) return '中等'
  if (value >= 0.3) return '偏低'
  return '很低'
}

// === 4 chip 色调映射 ===
// tone ∈ {success, warning, danger, neutral}，映射到 .chip-* CSS 类。
// 设计原则：
//   - 真实性：true=success, dubious=warning, false=danger, unverified=neutral
//   - 时间一致性：aligned=success, dubious/mismatch=warning, unknown=neutral
//   - 内容支持：accurate=success, mostly_accurate=success, dubious=warning, unsupported=neutral
//   - 研究结论：adopt=success, adopt_with_caution=warning, reject=danger, needs_review=neutral
// 这样"全绿"的事件 = 可采纳的强证据，"全灰/警告"的事件 = 待人工复核。

function eventTruthToTone(value) {
  if (value === 'true') return 'success'
  if (value === 'dubious') return 'warning'
  if (value === 'false') return 'danger'
  return 'neutral'
}

function timeTruthToTone(value) {
  if (value === 'time_aligned') return 'success'
  if (value === 'time_mismatch' || value === 'time_dubious') return 'warning'
  return 'neutral'
}

function contentTruthToTone(value) {
  if (value === 'accurate' || value === 'mostly_accurate') return 'success'
  if (value === 'dubious') return 'warning'
  return 'neutral'
}

function dispositionToTone(value) {
  if (value === 'adopt') return 'success'
  if (value === 'adopt_with_caution') return 'warning'
  if (value === 'reject') return 'danger'
  return 'neutral'
}

// 跟 reviewer.py 的 COMMON_QUERY_WORDS 保持同步：核心实体抽取去掉这些
// 高频"骨架词"，避免它们变成虚假的"实体"污染对照表。
const CLAIM_STOPWORDS = new Set([
  '关于', '联合', '印发', '发布', '推动', '促进', '专项', '行动', '方案',
  '发展', '公司', '股份', '有限', '今日', '正式', '公告', '新闻',
])

// 在 reviewer.py _extract_key_entities + _subsplit_entity 的简化前端版：
// 1) 用 CJK / 拉丁 / 数字 token 切分
// 2) 长 token 再按 CJK↔ASCII 边界细切（"英伟达GB300" → "英伟达"+"GB300"）
// 3) 过滤停用词、长度 <2 的碎片
// 4) 按长度降序、去重，取 top-4
// 这套规则跟后端打分对齐，所以前端"显示命中"和后端"评分命中"会一致。
//
// 与 reviewer.py 的差异：在视觉对照场景，过长的"整串实体"既难放进 tag
// 也几乎不可能在搜索结果里出现，对用户没有解释力——所以前端额外把
// ≥12 字的长实体替换成它内部的 2-3 个短子片段（按 4-8 字滑动切片），
// 让对照表里的列名都是真实可命中的核心词。
function extractClaimEntities(rawName) {
  const text = String(rawName || '').replace(/\s+/g, ' ').trim()
  if (!text) return []

  const cjkOrAlnum = /[一-鿿]+|[A-Za-z0-9]+/g
  const tokens = text.match(cjkOrAlnum) || []

  const expanded = []
  for (const tok of tokens) {
    expanded.push(tok)
    if (tok.length > 6) {
      // CJK ↔ ASCII 边界细切
      const subs = tok.match(/[A-Za-z0-9]+|[一-鿿]+/g) || []
      for (const s of subs) expanded.push(s)
    }
  }

  // 在前端额外做一次"长实体瘦身"：>=12 字的 CJK token 被切成它的若干
  // 4-8 字片段（首段 + 包含主体名词的中段），让对照视图的列名都是
  // 短到能在搜索结果里出现的关键词。
  const slim = []
  for (const t of expanded) {
    if (t.length >= 12 && /^[一-鿿]+$/.test(t)) {
      // 取头部 6 字 + 尾部 6 字两个候选片段
      slim.push(t.slice(0, 6))
      slim.push(t.slice(-6))
    } else {
      slim.push(t)
    }
  }

  const filtered = slim.filter(t => t.length >= 2 && !CLAIM_STOPWORDS.has(t))
  const seen = new Set()
  const ranked = []
  for (const t of filtered.sort((a, b) => b.length - a.length)) {
    // 去掉互相是子串的（保留较长的那个），避免对照表里出现冗余列
    let dup = false
    for (const k of ranked) {
      if (k.includes(t) || t.includes(k)) { dup = true; break }
    }
    if (dup) continue
    if (seen.has(t)) continue
    seen.add(t)
    ranked.push(t)
  }
  return ranked.slice(0, 4)
}

// 把 0~1 的命中率映射到 el-tag 颜色风格的 CSS class。
function coverageRateClass(rate) {
  if (rate >= 0.75) return 'rate-high'
  if (rate >= 0.5) return 'rate-mid'
  if (rate >= 0.25) return 'rate-low'
  return 'rate-none'
}

function sourceTypeLabel(value) {
  if (value === 'official') return '🏛 官方'
  if (value === 'mainstream') return '📰 主流'
  if (value === 'industry') return '🏭 行业'
  return '📌 聚合'
}

// Map source_type to el-tag colour. Mirrors the reliability tiers used by
// the MCP reviewer (high → official, medium → mainstream/industry, low →
// aggregator), so a quick glance at the badge colour tells the user how
// trustworthy the source backing this evidence row is.
function sourceTypeTagType(value) {
  if (value === 'official') return 'success'   // 绿 — gov/exchanges/regulators
  if (value === 'mainstream') return 'primary'  // 蓝 — Reuters/Bloomberg/新华
  if (value === 'industry') return 'warning'    // 黄 — 行业垂直媒体
  return 'info'                                  // 灰 — aggregator / 其他
}

function matchLevelLabel(value) {
  if (value === 'strong') return '强匹配'
  if (value === 'partial') return '部分匹配'
  return '弱匹配'
}

// Match-level visualisation: strong (green) carries the same weight as
// "official source" — both already pass the high-confidence bar in
// _score_truth_status. Partial gets warning-yellow to signal "useful but
// not conclusive". Weak stays info-grey.
function matchLevelTagType(value) {
  if (value === 'strong') return 'success'
  if (value === 'partial') return 'warning'
  return 'info'
}
</script>

<style scoped>
.event-review-card {
  min-height: 420px;
  padding: 20px 52px 12px 8px;
  background: transparent;
}

.event-review-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.event-review-name {
  font-size: 24px;
  font-weight: 900;
  line-height: 1.45;
  color: var(--el-text-color-primary);
}

.event-review-time {
  flex-shrink: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.event-review-tags {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.event-review-summary {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--sc-event-dialog-bg, var(--el-bg-color-overlay));
  border: 1px solid var(--el-border-color-light);
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}

.event-review-toolbar {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.review-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

/* === 时间一致性诊断卡 === */
/* 仅在 time_truth ∈ {time_mismatch, time_dubious} 时显示，把"为什么时间
   未对齐"的具体原因（事件日期 vs 证据最早日期）暴露给操作员，让他能自
   己判断是"旧闻新炒"还是"事件日期错"。 */
.review-time-diagnostic {
  margin-top: 12px;
  padding: 12px 14px;
  border-left: 4px solid var(--el-color-warning);
  border-radius: 8px;
  background: var(--el-color-warning-light-9);
  font-size: 13px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.time-diagnostic-row {
  display: flex;
  gap: 8px;
  align-items: baseline;
}

.time-diagnostic-label {
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  min-width: 64px;
}

.time-diagnostic-value {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-primary);
}

.time-diagnostic-gap {
  margin-left: 8px;
  font-weight: 400;
  font-size: 12px;
  color: var(--el-color-warning);
}

.time-diagnostic-source {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
  word-break: break-word;
}

.time-diagnostic-hint {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--el-border-color-lighter);
  font-size: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}

.review-chip {
  padding: 14px 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 16px;
  background: var(--sc-event-dialog-bg, var(--el-bg-color-overlay));
  /* 色调通过 .chip-{tone} 类注入：左侧 4px 色条 + value 上色，
     总体保持中性背景避免 4 chip 全色块时视觉过载。 */
  border-left-width: 4px;
}

.review-chip.chip-success {
  border-left-color: var(--el-color-success);
}
.review-chip.chip-success .review-chip-value {
  color: var(--el-color-success);
}

.review-chip.chip-warning {
  border-left-color: var(--el-color-warning);
}
.review-chip.chip-warning .review-chip-value {
  color: var(--el-color-warning);
}

.review-chip.chip-danger {
  border-left-color: var(--el-color-danger);
}
.review-chip.chip-danger .review-chip-value {
  color: var(--el-color-danger);
}

.review-chip.chip-neutral {
  border-left-color: var(--el-border-color);
}
/* neutral 不改 value 颜色，沿用 primary text */

.review-chip-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.review-chip-value {
  margin-top: 6px;
  font-size: 16px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

.review-confidence {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.review-section {
  margin-top: 20px;
}

.review-section-title {
  margin-bottom: 10px;
  font-size: 15px;
  font-weight: 800;
  color: var(--el-text-color-primary);
}

.review-panel {
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--sc-event-dialog-bg, var(--el-bg-color-overlay));
  border: 1px solid var(--el-border-color-light);
  color: var(--el-text-color-regular);
  line-height: 1.75;
}

/* === 事件 vs 证据 对照视图 === */
.review-claim-vs-evidence {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.claim-block,
.coverage-block {
  border-radius: 12px;
  border: 1px solid var(--el-border-color-light);
  background: var(--el-fill-color-blank);
  padding: 12px 14px;
}

.claim-label,
.coverage-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
  font-weight: 600;
}

.claim-text {
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  word-break: break-word;
}

.claim-entities-row {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.claim-entities-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.claim-entity-tag {
  letter-spacing: 0.5px;
}

/* 覆盖度 table */
.coverage-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  table-layout: auto;
}

.coverage-table th,
.coverage-table td {
  padding: 6px 8px;
  text-align: center;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.coverage-table thead th {
  font-weight: 600;
  color: var(--el-text-color-regular);
  background: var(--el-fill-color-light);
}

.coverage-th-idx,
.coverage-td-idx {
  width: 32px;
  color: var(--el-text-color-secondary);
}

.coverage-th-source,
.coverage-td-source {
  width: 90px;
  text-align: left;
}

.coverage-th-entity {
  font-size: 12px;
  white-space: nowrap;
}

.coverage-td-cell {
  font-weight: 700;
  font-size: 14px;
}

.coverage-td-cell.cell-hit {
  color: var(--el-color-success);
}

.coverage-td-cell.cell-miss {
  color: var(--el-color-info-light-3);
}

.coverage-td-rate {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.coverage-td-rate.rate-high {
  color: var(--el-color-success);
}
.coverage-td-rate.rate-mid {
  color: var(--el-color-warning);
}
.coverage-td-rate.rate-low {
  color: var(--el-color-danger);
}
.coverage-td-rate.rate-none {
  color: var(--el-text-color-secondary);
}

.review-evidence-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.review-evidence-item {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--el-border-color-light);
  background: var(--sc-event-dialog-bg, var(--el-bg-color-overlay));
}

.review-evidence-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.review-evidence-badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.review-evidence-title {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.6;
  color: var(--el-text-color-primary);
}

.review-evidence-source {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--el-border-color);
}

.review-evidence-source-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-top: 6px;
}

.review-evidence-source-row:first-child {
  margin-top: 0;
}

.review-evidence-source-label {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.review-evidence-source-value {
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.review-evidence-note {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}

.review-evidence-link {
  font-size: 12px;
  color: var(--el-color-primary);
  word-break: break-all;
  text-decoration: none;
}

.review-evidence-link:hover {
  text-decoration: underline;
}

.review-list {
  margin: 0;
  padding-left: 18px;
  color: var(--el-text-color-regular);
  line-height: 1.8;
}

.review-debug {
  margin-top: 20px;
}

.review-debug-item + .review-debug-item {
  margin-top: 8px;
}

@media (max-width: 640px) {
  .event-review-card {
    padding: 18px 44px 8px 4px;
  }

  .event-review-toolbar,
  .review-evidence-header {
    flex-direction: column;
    align-items: stretch;
  }
}

@media (max-width: 768px) {
  .review-grid {
    grid-template-columns: 1fr;
  }
}
</style>
