import axios from 'axios'
import { getToken, logout } from '../utils/auth'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000'

const api = axios.create({
  baseURL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
})

// 请求拦截器：自动带上本地存的访问 Token。
// 后端 AUTH_ENABLED=false 时这个头会被忽略，本地开发零影响；
// 上公网开启后端校验后，这个头就是通行凭证。
api.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (err) => Promise.reject(err)
)

api.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const status = err?.response?.status
    // 401：token 失效 / 未授权 → 清登录态并跳登录页（带 redirect 回跳）
    if (status === 401) {
      logout()
      const here = window.location.pathname + window.location.search
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = `/login?redirect=${encodeURIComponent(here)}`
      }
    }
    const message =
      err?.response?.data?.message ||
      err?.message ||
      '请求失败'
    return Promise.reject(new Error(message))
  }
)

export default api
