import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

interface QueueItem {
  resolve: (token: string) => void
  reject: (error: any) => void
}

const service = axios.create({
  baseURL: '/api',
  timeout: 30000
})

let isRefreshing = false
let failedQueue: QueueItem[] = []

const syncUserProfile = async (accessToken: string): Promise<void> => {
  try {
    const response = await axios.get('/api/auth/users/profile/', {
      headers: {
        Authorization: `Bearer ${accessToken}`
      }
    })
    const profile = response.data?.data || response.data
    const [{ useUserStore }, { usePermissionStore }] = await Promise.all([
      import('@/stores/user'),
      import('@/stores/permission')
    ])
    const userStore = useUserStore()
    const permissionStore = usePermissionStore()

    userStore.userInfo = profile
    permissionStore.setPermissions(profile.permissions || [])
    permissionStore.setMenus(profile.menus || [])
    permissionStore.setDataScopes(profile.data_scopes || {})
    userStore.profileReady = true
  } catch (syncError) {
    console.warn('Failed to sync user profile after token refresh:', syncError)
  }
}

const processQueue = (error: any, token: string | null = null): void => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token!)
    }
  })
  failedQueue = []
}

service.interceptors.request.use(
  config => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

service.interceptors.response.use(
  (response: AxiosResponse) => {
    if (response.config.responseType === 'blob') {
      return response
    }
    return response.data
  },
  async error => {
    const originalRequest = error.config

    if (error.response) {
      const { status, data } = error.response

      if (status === 401 && !originalRequest._retry) {
        const refreshToken = localStorage.getItem('refresh_token')

        if (!refreshToken) {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          router.push('/login')
          ElMessage.error('请先登录')
          return Promise.reject(error)
        }

        if (isRefreshing) {
          return new Promise<string>((resolve, reject) => {
            failedQueue.push({ resolve, reject })
          }).then(token => {
            originalRequest.headers['Authorization'] = `Bearer ${token}`
            return service.request(originalRequest)
          }).catch(err => Promise.reject(err))
        }

        originalRequest._retry = true
        isRefreshing = true

        try {
          const response = await axios.post('/api/accounts/refresh/', {
            refresh: refreshToken
          })

          const { access } = response.data
          localStorage.setItem('access_token', access)
          await syncUserProfile(access)

          processQueue(null, access)

          originalRequest.headers['Authorization'] = `Bearer ${access}`
          return service.request(originalRequest)
        } catch (refreshError) {
          processQueue(refreshError, null)
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          router.push('/login')
          ElMessage.error('登录已过期，请重新登录')
          return Promise.reject(refreshError)
        } finally {
          isRefreshing = false
        }
      } else if (status === 403) {
        ElMessage.error('没有权限执行此操作')
      } else if (status === 404) {
        ElMessage.error('请求的资源不存在')
      } else if (status === 500) {
        ElMessage.error('服务器错误，请稍后再试')
      } else {
        ElMessage.error(data?.detail || data?.error || '请求失败')
      }
    } else {
      ElMessage.error('网络错误，请检查您的网络连接')
    }

    return Promise.reject(error)
  }
)

/**
 * 响应拦截器在上方 `return response.data` 处对响应做了解包，因此运行时 `request({...})` /
 * `request.get(...)` 实际 resolve 的是「业务数据」而非 `AxiosResponse`。但 axios 实例的方法签名
 * 返回的是 `Promise<AxiosResponse<T>>`，与运行时不符——这会让全站调用点把解包后的数据当作
 * AxiosResponse 使用而触发大量 TS2339（属性不存在于 AxiosResponse）。这里用一个可调用接口把
 * 默认导出重新声明为「返回解包后数据」的客户端，使类型与运行时一致。
 * （blob 下载分支返回完整 response，调用点按需指定 T 或访问 .data。）
 */
export interface RequestClient {
  <T = any>(config: AxiosRequestConfig): Promise<T>
  request<T = any>(config: AxiosRequestConfig): Promise<T>
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  head<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  options<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>
}

const client = service as unknown as RequestClient

export default client

export function request<T = any>(config: AxiosRequestConfig): Promise<T> {
  return service(config) as unknown as Promise<T>
}
