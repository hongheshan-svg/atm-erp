import axios, { type AxiosRequestConfig, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

// 失败队列项:401 刷新期间被挂起的请求。
interface QueueItem {
  resolve: (token: string) => void
  reject: (error: unknown) => void
}

// 原始请求需要携带 _retry 标记防止无限重试。
type RetryableRequest = InternalAxiosRequestConfig & { _retry?: boolean }

const service = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// 单飞刷新:isRefreshing 标志 + failedQueue 排队重放。
let isRefreshing = false
let failedQueue: QueueItem[] = []

// 刷新成功后用新 token 拉取档案并回灌 permission/user store。
const syncUserProfile = async (accessToken: string): Promise<void> => {
  try {
    const response = await axios.get('/api/auth/profile', {
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
    console.warn('刷新 token 后同步用户档案失败:', syncError)
  }
}

// 重放/拒绝所有排队请求。
const processQueue = (error: unknown, token: string | null = null): void => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token as string)
    }
  })
  failedQueue = []
}

// 请求拦截器:注入 Bearer token。
service.interceptors.request.use(
  config => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器:解包 response.data;blob 透传;401 单飞刷新 + 排队重放。
service.interceptors.response.use(
  (response: AxiosResponse) => {
    if (response.config.responseType === 'blob') {
      return response
    }
    return response.data
  },
  async error => {
    const originalRequest = error.config as RetryableRequest

    if (error.response) {
      const { status, data } = error.response

      if (status === 401 && originalRequest && !originalRequest._retry) {
        const refreshToken = localStorage.getItem('refresh_token')

        if (!refreshToken) {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          router.push('/login')
          ElMessage.error('请先登录')
          return Promise.reject(error)
        }

        // 刷新进行中:挂起当前请求,待新 token 重放。
        if (isRefreshing) {
          return new Promise<string>((resolve, reject) => {
            failedQueue.push({ resolve, reject })
          })
            .then(token => {
              originalRequest.headers.Authorization = `Bearer ${token}`
              return service.request(originalRequest)
            })
            .catch(err => Promise.reject(err))
        }

        originalRequest._retry = true
        isRefreshing = true

        try {
          const response = await axios.post('/api/auth/refresh', {
            refresh: refreshToken
          })

          const { access } = response.data
          localStorage.setItem('access_token', access)
          await syncUserProfile(access)

          processQueue(null, access)

          originalRequest.headers.Authorization = `Bearer ${access}`
          return service.request(originalRequest)
        } catch (refreshError) {
          processQueue(refreshError, null)
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          router.push('/login')
          ElMessage.error('登录已过期,请重新登录')
          return Promise.reject(refreshError)
        } finally {
          isRefreshing = false
        }
      } else if (status === 403) {
        ElMessage.error('没有权限执行此操作')
      } else if (status === 404) {
        ElMessage.error('请求的资源不存在')
      } else if (status === 500) {
        ElMessage.error('服务器错误,请稍后再试')
      } else {
        ElMessage.error(data?.detail || data?.error || '请求失败')
      }
    } else {
      ElMessage.error('网络错误,请检查您的网络连接')
    }

    return Promise.reject(error)
  }
)

/**
 * 响应拦截器在 `return response.data` 处对响应做了解包,因此运行时 `request({...})` /
 * `request.get(...)` 实际 resolve 的是「业务数据」而非 `AxiosResponse`。这里用一个可调用接口
 * 把默认导出重新声明为「返回解包后数据」的客户端,使类型与运行时一致。
 * (blob 下载分支返回完整 response,调用点按需指定 T 或访问 .data。)
 */
export interface RequestClient {
  <T = unknown>(config: AxiosRequestConfig): Promise<T>
  request<T = unknown>(config: AxiosRequestConfig): Promise<T>
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  head<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  options<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  patch<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
}

const client = service as unknown as RequestClient

export default client

export function request<T = unknown>(config: AxiosRequestConfig): Promise<T> {
  return service(config) as unknown as Promise<T>
}

/**
 * blob 下载专用:响应拦截器对 responseType==='blob' 返回完整 AxiosResponse(含 .data/.headers),
 * 故此处如实声明为 Promise<AxiosResponse<Blob>>,避免被 RequestClient 的「解包」统一签名误描述。
 */
export function requestBlob(config: AxiosRequestConfig): Promise<AxiosResponse<Blob>> {
  return service({ ...config, responseType: 'blob' }) as unknown as Promise<AxiosResponse<Blob>>
}
