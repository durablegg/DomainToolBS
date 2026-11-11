import axios, { type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

const instance = axios.create({
  baseURL: '/api/v1',
  timeout: 20000,
})

instance.interceptors.request.use((config) => {
  // 会话级存储：关闭标签页/浏览器即失效，满足"关闭后需重新登录"
  const token = sessionStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 允许单个请求通过 config.silent = true 关闭全局错误提示（如审计员预期内的 403）
declare module 'axios' {
  export interface AxiosRequestConfig {
    silent?: boolean
  }
}

// 响应拦截：直接返回 data；统一处理鉴权与错误
instance.interceptors.response.use(
  (resp) => resp.data,
  (error) => {
    const status = error.response?.status
    const data = error.response?.data
    const silent = Boolean((error.config as AxiosRequestConfig | undefined)?.silent)
    // 后端异常时可能是 JSON（{detail}）也可能是纯文本（如 Internal Server Error）
    const detail =
      (typeof data?.detail === 'string' && data.detail) ||
      (typeof data === 'string' && data && data !== 'Internal Server Error' ? data : '')
    const fallback = status ? `请求失败（HTTP ${status}）` : '网络异常，请稍后重试'
    if (status === 401) {
      sessionStorage.removeItem('token')
      sessionStorage.removeItem('role')
      if (location.pathname !== '/login') location.href = '/login'
    } else if (!silent) {
      ElMessage.error(status === 403 ? detail || '无权限' : detail || fallback)
    }
    return Promise.reject(error)
  },
)

// 响应拦截器已在运行时返回 resp.data，这里让静态类型与之一致：
// 各方法直接返回 Promise<T>，而非 AxiosResponse<T>。
export interface Http {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  patch<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
}

export default instance as unknown as Http
