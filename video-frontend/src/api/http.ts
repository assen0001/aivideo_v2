/** Axios 实例 + 拦截器（token / 401 全局登出 / 错误 toast） */
import axios, { type AxiosRequestConfig } from 'axios'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'

declare module 'axios' {
  export interface AxiosRequestConfig {
    /** 跳过全局错误 toast（登录页等自行处理内联错误） */
    skipToast?: boolean
  }
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 30000,
})

// 请求拦截：注入 token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：成功直接返回数据体；错误统一 toast（401 → 全局登出）
http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const toast = useToastStore()
    const status = err.response?.status
    const message = err.response?.data?.message || err.message || '请求失败'
    const skip = (err.config as AxiosRequestConfig)?.skipToast === true

    if (status === 401) {
      const auth = useAuthStore()
      auth.handle401()
    } else if (!skip) {
      toast.show('error', message)
    }
    return Promise.reject(err)
  },
)

export default http
