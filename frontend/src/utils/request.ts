import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { localStore } from './storage'
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
    if (value) localStore.set(key!, value)
    else localStore.remove(key!)
  }
  window.dispatchEvent(new Event('erp-session'))
}
type Config = InternalAxiosRequestConfig & { epoch?: number; retried?: boolean }
request.interceptors.request.use((config: Config) => {
  config.epoch = epoch
  const token = localStore.get('access_token')
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
    const refresh = localStore.get('refresh_token')
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
          localStore.set('access_token', data.access)
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
// crypto.randomUUID() exists only in secure contexts, and a LAN install is served over plain
// HTTP, so build the operation key from getRandomValues (available everywhere) when it is missing.
export function requestKey(): string {
  const source = globalThis.crypto
  if (typeof source?.randomUUID === 'function') return source.randomUUID()
  const bytes = new Uint8Array(16)
  if (typeof source?.getRandomValues === 'function') source.getRandomValues(bytes)
  else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256)
  bytes[6] = (bytes[6]! & 0x0f) | 0x40
  bytes[8] = (bytes[8]! & 0x3f) | 0x80
  const hex = [...bytes].map(byte => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
// axios 自带的描述和网关返回的 HTML 错误页都是英文，一律换成按错误类型给出的中文说明。
const NETWORK_MESSAGES: Record<string, string> = {
  ECONNABORTED: '请求超时，请检查网络后重试。',
  ETIMEDOUT: '请求超时，请检查网络后重试。',
  ERR_NETWORK: '无法连接服务器，请检查网络或确认服务是否已启动。',
  ERR_CANCELED: '请求已取消。',
}
const STATUS_MESSAGES: Record<number, string> = {
  400: '填写内容或提交格式不正确，请检查后重试。',
  401: '登录状态已失效，请重新登录。',
  403: '没有执行该操作的权限。',
  404: '请求的数据不存在或已被删除。',
  405: '不支持此操作方式，请刷新页面后重试。',
  408: '请求超时，请检查网络后重试。',
  413: '提交内容过大，请缩减后重试。',
  415: '不支持此提交格式，请按页面要求重新提交。',
  422: '填写内容不符合要求，请检查后重试。',
  429: '操作过于频繁，请稍后再试。',
  500: '服务器处理失败，请稍后重试或联系管理员。',
  502: '服务暂时不可用，请稍后重试。',
  503: '服务暂时不可用，请稍后重试。',
  504: '服务响应超时，请稍后重试。',
}
const ERROR_TEXT: Record<string, string> = {
  'Network Error': NETWORK_MESSAGES.ERR_NETWORK!,
  'Failed to fetch': NETWORK_MESSAGES.ERR_NETWORK!,
  'Load failed': NETWORK_MESSAGES.ERR_NETWORK!,
  'This field is required.': '此项为必填项。',
  'This field may not be blank.': '此项不能为空。',
  'This field may not be null.': '此项不能为空。',
  'A valid integer is required.': '请填写有效整数。',
  'A valid number is required.': '请填写有效数字。',
  'Not found.': STATUS_MESSAGES[404]!,
  'Authentication credentials were not provided.': '请先登录后再操作。',
  'You do not have permission to perform this action.': STATUS_MESSAGES[403]!,
  'No active account found with the given credentials': '用户名或密码不正确，或账号已停用。',
  'Given token not valid for any token type': STATUS_MESSAGES[401]!,
  'Token is invalid': STATUS_MESSAGES[401]!,
  'Token is expired': '登录凭据已过期，请重新登录。',
}
function chineseMessage(value: string): string {
  const text = value.trim()
  if (!text || text.startsWith('<')) return ''
  if (ERROR_TEXT[text]) return ERROR_TEXT[text]!
  if (/^timeout of \d+ms exceeded$/.test(text)) return NETWORK_MESSAGES.ETIMEDOUT!
  if (/^(Failed to fetch dynamically imported module|Importing a module script failed|Loading chunk)/.test(text)) return '页面资源加载失败，请刷新页面后重试。'
  if (/^JSON parse error/.test(text)) return '提交内容格式不正确，请检查后重新提交。'
  if (/is not a valid choice\.?$/.test(text)) return '请选择列表中的有效选项。'
  if (/^Ensure this field has no more than \d+ characters/.test(text)) return `此项不能超过 ${text.match(/\d+/)![0]} 个字符。`
  return /[\u4e00-\u9fff]/.test(text) ? text : ''
}
export function message(error: unknown): string {
  function flatten(value: any): string {
    if (value == null) return ''
    // 响应体是错误页而不是接口返回时，原样展示只会得到一段英文 HTML。
    if (typeof value === 'string') return chineseMessage(value)
    if (value instanceof Error) return chineseMessage(value.message)
    if (Array.isArray(value)) return value.map(flatten).filter(Boolean).join('；')
    if (typeof value === 'object') {
      const text = Object.entries(value).filter(([key, detail]) =>
        !['row', 'token_class', 'token_type', 'actions'].includes(key) &&
        !(key === 'code' && typeof detail === 'string' && /^[a-z_]+$/.test(detail)),
      ).map(([, detail]) => flatten(detail)).filter(Boolean).join('；')
      return value.row != null ? `第 ${value.row} 行：${text || '填写内容不符合要求，请检查后重试。'}` : text
    }
    return String(value)
  }
  if (!axios.isAxiosError(error)) return flatten(error) || '操作失败，请重试。'
  const data = error.response?.data
  const detail = flatten(data?.detail ?? data)
  if (detail) return detail
  if (!error.response) return NETWORK_MESSAGES[error.code ?? ''] || '网络异常，请检查连接后重试。'
  return STATUS_MESSAGES[error.response.status] || `请求失败（状态码 ${error.response.status}）。`
}
export function recoveryActions(error: unknown): { label: string; path: string }[] {
  const actions = axios.isAxiosError(error) ? error.response?.data?.actions : []
  return Array.isArray(actions) ? actions.filter(a => typeof a.label === 'string' && typeof a.path === 'string' && /^\/(projects|purchases|finance)(\/\d+)?(\?|$)/.test(a.path)) : []
}
