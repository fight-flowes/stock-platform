export const THEME_KEY = 'sc_theme'

export function getTheme() {
  const v = localStorage.getItem(THEME_KEY)
  return v === 'dark' ? 'dark' : 'light'
}

export function applyTheme(theme) {
  const t = theme === 'dark' ? 'dark' : 'light'
  document.documentElement.classList.toggle('dark', t === 'dark')
  localStorage.setItem(THEME_KEY, t)
  return t
}

