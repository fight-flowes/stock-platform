import { HolidayUtil } from 'lunar-javascript'

const cache = new Map()

function keyFromYmd(y, m, d) {
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

export function getHolidayStatus(date) {
  const y = date.getFullYear()
  const m = date.getMonth() + 1
  const d = date.getDate()
  const key = keyFromYmd(y, m, d)
  if (cache.has(key)) return cache.get(key)

  const h = HolidayUtil.getHoliday(y, m, d)
  if (!h) {
    const v = { type: 'none' }
    cache.set(key, v)
    return v
  }

  if (h.isWork()) {
    const v = { type: 'work' }
    cache.set(key, v)
    return v
  }

  const v = { type: 'rest', name: h.getName() }
  cache.set(key, v)
  return v
}

