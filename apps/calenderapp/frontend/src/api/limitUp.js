import axios from 'axios'
import { getHolidayStatus } from '../utils/holiday'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000'

function isFallbackTradingDay(dateText) {
  const date = new Date(`${dateText}T00:00:00`)
  if (Number.isNaN(date.getTime())) return false
  const weekday = date.getDay()
  if (weekday === 0 || weekday === 6) return false
  const holiday = getHolidayStatus(date)
  return holiday.type !== 'rest'
}

function buildFallbackTradingDays(startDate, endDate) {
  const result = []
  const cursor = new Date(`${startDate}T00:00:00`)
  const end = new Date(`${endDate}T00:00:00`)
  if (Number.isNaN(cursor.getTime()) || Number.isNaN(end.getTime()) || cursor > end) {
    return result
  }

  while (cursor <= end) {
    const y = cursor.getFullYear()
    const m = String(cursor.getMonth() + 1).padStart(2, '0')
    const d = String(cursor.getDate()).padStart(2, '0')
    const dateText = `${y}-${m}-${d}`
    if (isFallbackTradingDay(dateText)) {
      result.push(dateText)
    }
    cursor.setDate(cursor.getDate() + 1)
  }

  return result.reverse()
}

/**
 * 获取交易日历（交易日列表）
 * 优先从涨停数据推断；若区间内暂无涨停记录，则回退为工作日近似。
 */
export async function getTradingDays(startDate, endDate) {
  try {
    const limitUpResp = await axios.get(`${API_BASE}/api/limit-up/`, {
      params: { start_date: startDate, end_date: endDate, page_size: 500 }
    })
    const limitUpItems = limitUpResp.data?.data?.items || []
    const dates = [...new Set(limitUpItems.map(item => item.limit_up_date))]
    if (dates.length > 0) {
      return dates.sort().reverse()
    }
    return buildFallbackTradingDays(startDate, endDate)
  } catch (e) {
    console.error('获取交易日失败:', e)
    return buildFallbackTradingDays(startDate, endDate)
  }
}

/**
 * 涨停股列表
 */
export async function listLimitUps(params) {
  const resp = await axios.get(`${API_BASE}/api/limit-up/`, { params })
  return resp.data
}

/**
 * 涨停详情
 */
export async function getLimitUpDetail(id) {
  const resp = await axios.get(`${API_BASE}/api/limit-up/${id}`)
  return resp.data
}

/**
 * 创建涨停记录
 */
export async function createLimitUp(data) {
  const resp = await axios.post(`${API_BASE}/api/limit-up/`, data)
  return resp.data
}

/**
 * 更新涨停记录
 */
export async function updateLimitUp(id, data) {
  const resp = await axios.put(`${API_BASE}/api/limit-up/${id}`, data)
  return resp.data
}

/**
 * 批量更新涨停记录
 */
export async function batchUpdateLimitUps(items, updates = null) {
  const resp = await axios.put(`${API_BASE}/api/limit-up/batch-update`, {
    items,
    updates
  })
  return resp.data
}

/**
 * 删除涨停记录
 */
export async function deleteLimitUp(id) {
  const resp = await axios.delete(`${API_BASE}/api/limit-up/${id}`)
  return resp.data
}

/**
 * 连板榜排名
 */
export async function getConsecutiveRank(date) {
  const resp = await axios.get(`${API_BASE}/api/limit-up/consecutive`, { params: { date } })
  return resp.data
}

/**
 * 龙头股列表
 */
export async function getDragonHeads(date) {
  const resp = await axios.get(`${API_BASE}/api/limit-up/dragon-head`, { params: { date } })
  return resp.data
}

/**
 * 区间统计
 */
export async function getStatistics(startDate, endDate) {
  const resp = await axios.get(`${API_BASE}/api/limit-up/statistics`, {
    params: { start_date: startDate, end_date: endDate }
  })
  return resp.data
}

/**
 * 资金流向排行
 */
export async function getFundFlowRank(startDate, endDate, top = 20) {
  const resp = await axios.get(`${API_BASE}/api/limit-up/fund-flow`, {
    params: { start_date: startDate, end_date: endDate, top }
  })
  return resp.data
}

/**
 * 概念热度统计
 */
export async function getConceptHot(startDate, endDate, top = 20) {
  const resp = await axios.get(`${API_BASE}/api/limit-up/concept-hot`, {
    params: { start_date: startDate, end_date: endDate, top }
  })
  return resp.data
}

/**
 * 下载导入模板
 */
export function downloadTemplate() {
  window.open(`${API_BASE}/api/limit-up/template.csv`, '_blank')
}

/**
 * CSV批量导入
 */
export async function importLimitUpsCsv(file) {
  const formData = new FormData()
  formData.append('file', file)
  const resp = await axios.post(`${API_BASE}/api/limit-up/import`, formData)
  return resp.data
}

/**
 * 从 Tushare 同步涨停数据
 */
export async function syncFromTushare(date) {
  const resp = await axios.post(`${API_BASE}/api/limit-up/sync-tushare?date=${date}`, null, {
    timeout: 120000  // 2分钟超时
  })
  return resp.data
}

/**
 * 完整同步（涨停+龙虎榜+概念板块+龙头识别）
 */
export async function syncFullFromTushare(date) {
  const resp = await axios.post(`${API_BASE}/api/limit-up/sync-full?date=${date}`, null, {
    timeout: 180000  // 3分钟超时（完整同步需要更长时间）
  })
  return resp.data
}

/**
 * 批量同步日期范围
 */
export async function syncDateRange(startDate, endDate) {
  const resp = await axios.post(`${API_BASE}/api/limit-up/sync-range?start_date=${startDate}&end_date=${endDate}`, null, {
    timeout: 300000  // 5分钟超时（批量同步可能需要很长时间）
  })
  return resp.data
}

/**
 * 获取热门概念板块
 */
export async function getHotConcepts(date) {
  const resp = await axios.get(`${API_BASE}/api/limit-up/hot-concepts?date=${date}`)
  return resp.data
}

/**
 * 获取股票所属概念
 */
export async function getStockConcepts(stockCode) {
  const resp = await axios.get(`${API_BASE}/api/limit-up/stock-concepts/${stockCode}`)
  return resp.data
}

/**
 * 重新识别龙头股
 */
export async function identifyDragon(date) {
  const resp = await axios.post(`${API_BASE}/api/limit-up/identify-dragon?date=${date}`)
  return resp.data
}

/**
 * 获取涨停股K线数据
 */
/**
 * 获取涨停股K线数据
 * @param {number} id - 涨停记录ID
 * @param {string} date - 涨停日期（分区表复合主键需要）
 * @param {number} days - 查询天数
 */
export async function getLimitUpKline(id, date, days = 60) {
  const params = new URLSearchParams({ days })
  if (date) {
    params.append('date', date)
  }
  const resp = await axios.get(`${API_BASE}/api/limit-up/${id}/kline?${params}`)
  return resp.data
}

/**
 * 获取涨停股分时线数据
 */
/**
 * 获取涨停股分时线数据
 * @param {number} id - 涨停记录ID
 * @param {string} date - 涨停日期（分区表复合主键需要）
 */
export async function getLimitUpIntraday(id, date) {
  const params = date ? `?date=${date}` : ''
  const resp = await axios.get(`${API_BASE}/api/limit-up/${id}/intraday${params}`)
  return resp.data
}

/**
 * 导出涨停数据
 * @param {string} startDate - 开始日期
 * @param {string} endDate - 结束日期
 * @param {string} format - 导出格式 csv/json
 */
export function exportLimitUps(startDate, endDate, format = 'csv') {
  const params = new URLSearchParams()
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)
  params.append('format', format)
  window.open(`${API_BASE}/api/limit-up/export?${params}`, '_blank')
}

/**
 * 导出当日涨停解析事件
 * @param {string} date - 交易日期
 * @param {object} filters - 当前筛选条件
 */
export async function exportLimitUpEvents(date, filters = {}) {
  const params = new URLSearchParams()
  if (date) params.append('date', date)
  Object.entries(filters || {}).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') return
    params.append(key, value)
  })
  return axios.get(`${API_BASE}/api/limit-up/events-export`, {
    params,
    responseType: 'blob'
  })
}

/**
 * 分析涨停股票
 */
export async function analyzeLimitUp(stockCode, date, force = false) {
  const resp = await axios.post(`${API_BASE}/api/limit-up/analyze?stock_code=${stockCode}&date=${date}&force=${force}`)
  return resp.data
}

/**
 * 获取涨停股分析结果
 */
export async function getLimitUpAnalysis(stockCode, date) {
  const resp = await axios.get(`${API_BASE}/api/limit-up/analysis/${stockCode}?date=${date}`)
  return resp.data
}
