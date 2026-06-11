import { Solar } from 'lunar-javascript'

const cache = new Map()

function keyFromYmd(y, m, d) {
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

export function getLunarDayText(date) {
  const y = date.getFullYear()
  const m = date.getMonth() + 1
  const d = date.getDate()
  const key = keyFromYmd(y, m, d)
  if (cache.has(key)) return cache.get(key)
  const lunar = Solar.fromYmd(y, m, d).getLunar()
  const text = lunar.getDayInChinese()
  cache.set(key, text)
  return text
}

