import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const service = axios.create({
  baseURL: '/api',
  timeout: 30000
})

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
    // 直接返回响应数据的 data 部分
    return response.data
  },
  async error => {
    if (error.response) {
      const { status, data } = error.response
      
      if (status === 401) {
        // Token expired or invalid
        const refreshToken = localStorage.getItem('refresh_token')
        if (refreshToken) {
          try {
            // Try to refresh token
            const response = await axios.post('/api/auth/refresh/', {
              refresh: refreshToken
            })
            
            const { access } = response.data
            localStorage.setItem('access_token', access)
            
            // Retry original request
            error.config.headers['Authorization'] = `Bearer ${access}`
            return service.request(error.config)
          } catch (refreshError) {
            // Refresh failed, redirect to login
            localStorage.clear()
            router.push('/login')
            ElMessage.error('登录已过期，请重新登录')
            return Promise.reject(refreshError)
          }
        } else {
          // No refresh token, redirect to login
          localStorage.clear()
          router.push('/login')
          ElMessage.error('请先登录')
        }
      } else if (status === 403) {
        ElMessage.error('没有权限执行此操作')
      } else if (status === 404) {
        ElMessage.error('请求的资源不存在')
      } else if (status === 500) {
        ElMessage.error('服务器错误，请稍后再试')
      } else {
        ElMessage.error(data.detail || data.error || '请求失败')
      }
    } else {
      ElMessage.error('网络错误，请检查您的网络连接')
    }
    
    return Promise.reject(error)
  }
)

export default service

