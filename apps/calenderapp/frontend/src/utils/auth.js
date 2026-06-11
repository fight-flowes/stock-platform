/**
 * 认证工具模块
 * 
 * Token 配置：在 .env 文件中设置 VITE_AUTH_TOKEN
 * 多个 token 用逗号分隔，如: VITE_AUTH_TOKEN=token1,token2,token3
 */

// 有效的 Token 列表（从环境变量读取，支持多个）
const VALID_TOKENS = (import.meta.env.VITE_AUTH_TOKEN || 'research2024,stock123,a-stock-v5.1')
  .split(',')
  .map(t => t.trim())
  .filter(t => t)

// Token 存储 key
const TOKEN_KEY = 'a_stock_auth_token'

/**
 * 登录验证
 * @param {string} token 用户输入的 token
 * @returns {{ success: boolean, message: string }}
 */
export function login(token) {
  if (!token || !token.trim()) {
    return { success: false, message: '请输入 Token' }
  }
  
  const trimmedToken = token.trim()
  
  if (VALID_TOKENS.includes(trimmedToken)) {
    localStorage.setItem(TOKEN_KEY, trimmedToken)
    return { success: true, message: '登录成功' }
  }
  
  return { success: false, message: 'Token 无效，请检查后重试' }
}

/**
 * 退出登录
 */
export function logout() {
  localStorage.removeItem(TOKEN_KEY)
}

/**
 * 检查是否已登录
 * @returns {boolean}
 */
export function isAuthenticated() {
  const token = localStorage.getItem(TOKEN_KEY)
  if (!token) return false
  return VALID_TOKENS.includes(token)
}

/**
 * 获取当前 Token
 * @returns {string|null}
 */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

/**
 * 验证 Token 是否有效（用于后端校验）
 * @param {string} token 
 * @returns {boolean}
 */
export function validateToken(token) {
  return VALID_TOKENS.includes(token)
}
