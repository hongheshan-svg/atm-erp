import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const service = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// JWT refresh state management - prevents concurrent refresh attempts
let isRefreshing = false
let failedQueue = []

const syncUserProfile = async (accessToken) => {
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

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

// Request interceptor
service.interceptors.request.use(
  config => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor
service.interceptors.response.use(
  response => {
    // 对于blob类型的响应，返回完整响应对象
    if (response.config.responseType === 'blob') {
      return response
    }
    // 其他情况直接返回响应数据的 data 部分
    return response.data
  },
  async error => {
    const originalRequest = error.config

    if (error.response) {
      const { status, data } = error.response
      
      if (status === 401 && !originalRequest._retry) {
        // Token expired or invalid
        const refreshToken = localStorage.getItem('refresh_token')
        
        if (!refreshToken) {
          localStorage.clear()
          router.push('/login')
          ElMessage.error('请先登录')
          return Promise.reject(error)
        }

        // If already refreshing, queue this request
        if (isRefreshing) {
          return new Promise((resolve, reject) => {
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
          
          // Process queued requests with new token
          processQueue(null, access)
          
          // Retry original request
          originalRequest.headers['Authorization'] = `Bearer ${access}`
          return service.request(originalRequest)
        } catch (refreshError) {
          processQueue(refreshError, null)
          localStorage.clear()
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

export default service
