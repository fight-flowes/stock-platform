import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000'

const api = axios.create({
  baseURL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
})

api.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const message =
      err?.response?.data?.message ||
      err?.message ||
      '请求失败'
    return Promise.reject(new Error(message))
  }
)

export default api
