import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
export const request = axios.create({ baseURL: '/api', timeout: 25000 })
let epoch = 0
let flight: Promise<void> | undefined
export function resetSession(access?: string, refresh?: string) {
  epoch++
  flight = undefined
  for (const [key, value] of [
    ['access_token', access],
    ['refresh_token', refresh],
  ]) {
    if (value) localStorage.setItem(key!, value)
    else localStorage.removeItem(key!)
  }
  window.dispatchEvent(new Event('erp-session'))
}
type Config = InternalAxiosRequestConfig & { epoch?: number; retried?: boolean }
request.interceptors.request.use((config: Config) => {
  config.epoch = epoch
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
request.interceptors.response.use(
  (response) => {
    if ((response.config as Config).epoch !== epoch) throw new Error('登录状态已变化，请重试。')
    return response
  },
  async (error: AxiosError) => {
    const config = error.config as Config | undefined
    if (
      !config ||
      config.epoch !== epoch ||
      error.response?.status !== 401 ||
      config.retried ||
      config.url?.startsWith('/auth/login')
    )
      throw error
    const refresh = localStorage.getItem('refresh_token')
    if (!refresh) {
      resetSession()
      throw error
    }
    const started = epoch
    if (!flight) {
      const current = axios
        .post('/api/auth/refresh/', { refresh }, { timeout: 15000 })
        .then(({ data }) => {
          if (epoch !== started) throw new Error('登录状态已变化。')
          localStorage.setItem('access_token', data.access)
        })
        .catch((e) => {
          if (epoch === started && [400, 401, 403].includes(e.response?.status)) resetSession()
          throw e
        })
        .finally(() => {
          if (flight === current) flight = undefined
        })
      flight = current
    }
    await flight
    if (epoch !== started) throw new Error('登录状态已变化。')
    config.retried = true
    return request(config)
  },
)
export function message(error: unknown): string {
  const detail = axios.isAxiosError(error) ? error.response?.data || error.message : error
  function flatten(value: any): string {
    if (value == null) return ''
    if (typeof value === 'string') return value
    if (value instanceof Error) return value.message
    if (Array.isArray(value)) return value.map(flatten).join('；')
    if (typeof value === 'object') return Object.values(value).map(flatten).join('；')
    return String(value)
  }
  return flatten(detail) || '操作失败，请重试。'
}
