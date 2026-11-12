import axios, { AxiosError, AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { localStore } from './storage'
// 普通接口 25 秒超时。附件上传（单个上限 20 MB）、文件导入和导出要传完整份文件或在服务端逐行处理，
// 慢速网络下 25 秒不够：客户端先报超时而服务端仍在写入，用户会去重试一项其实已经成功的操作。
export const REQUEST_TIMEOUT = 25_000
export const TRANSFER_TIMEOUT = 5 * 60_000
export const request = axios.create({ baseURL: '/api', timeout: REQUEST_TIMEOUT })
// 上传附件和导入文件走 multipart，导出、模板和附件下载按 blob 接收；导入确认只带预览令牌，但服务端要逐行写入整份文件。
const IMPORT_PATH = /import-(?:file|preview|confirm)\/$/
const transfer = (config: InternalAxiosRequestConfig) =>
  config.data instanceof FormData || config.responseType === 'blob' || IMPORT_PATH.test(config.url ?? '')
const ACCESS = 'access_token'
const REFRESH = 'refresh_token'
const CHANGED = '登录状态已变化，请重试。'
const SUPERSEDED = '其他标签页已切换为另一账号登录，请刷新页面后继续。'
let epoch = 0
let flight: Promise<void> | undefined
// 本页正在使用的登录，以登录时写入的刷新令牌标识。令牌存在各标签页共用的 localStorage 里；
// 例行续期只换访问令牌、不改刷新令牌，只有退出或重新登录（本页或其他标签页）才会改变它。
let session = localStore.get(REFRESH)
// 其他标签页已换成另一账号登录：本页界面仍属原账号，重新载入前不再发出任何请求。
let superseded = false
export function resetSession(access?: string, refresh?: string) {
  epoch++
  flight = undefined
  superseded = false
  for (const [key, value] of [
    [ACCESS, access],
    [REFRESH, refresh],
  ]) {
    if (value) localStore.set(key!, value)
    else localStore.remove(key!)
  }
  // 以实际写入结果为准：存储被禁用或写满时与共享存储保持一致，不会误判成其他标签页改了登录。
  session = localStore.get(REFRESH)
  window.dispatchEvent(new Event('erp-session'))
}
// 只用来判断两次登录是否同一账号，不作任何授权依据；解析不了按不同账号处理。
function account(token: string | null) {
  try {
    const part = token!.split('.')[1]!.replace(/-/g, '+').replace(/_/g, '/')
    const id = JSON.parse(atob(part.padEnd(Math.ceil(part.length / 4) * 4, '=')))?.user_id
    return id == null ? null : String(id)
  } catch {
    return null
  }
}
export type SessionChange = 'unchanged' | 'renewed' | 'ended' | 'superseded'
// 与共享存储里的登录对齐：storage 事件到达时、发请求前和续期前各调用一次。
// - 其他标签页例行续期只改访问令牌：不算变化，本页直接用新的访问令牌。
// - 同一账号在其他标签页重新登录：沿用新登录，不打断本页、不丢填写内容。
// - 其他标签页退出：本页按退出处理（不再改动存储），回到登录页。
// - 换成另一账号（或本页未登录时其他标签页登录）：先按退出清掉原账号的资料，再通知整页载入新账号。
export function syncSession(): SessionChange {
  if (superseded) return 'superseded'
  const stored = localStore.get(REFRESH)
  if (stored === session) return 'unchanged'
  const owner = account(stored)
  if (session && owner != null && owner === account(session)) {
    session = stored
    flight = undefined
    return 'renewed'
  }
  epoch++
  flight = undefined
  if (stored) superseded = true
  else session = null
  window.dispatchEvent(new Event('erp-session'))
  if (!superseded) return 'ended'
  window.dispatchEvent(new Event('erp-session-replaced'))
  return 'superseded'
}
window.addEventListener('storage', (event) => {
  if (event.key === REFRESH || event.key === null) syncSession()
})
// 从往返缓存恢复的页面收不到离开期间的 storage 事件。
window.addEventListener('pageshow', (event) => {
  if (event.persisted) syncSession()
})
type Config = InternalAxiosRequestConfig & { epoch?: number; retried?: boolean; throttled?: number }
// 接口限流（429）只要求等几秒时自动重发：被限流的请求在服务端未执行，写动作沿用同一操作标识，重发不会重复写入。
// 登录、导出等按分钟计的限流仍直接提示，不让用户干等。
export const THROTTLE_RETRIES = 2
export const THROTTLE_WAIT_SECONDS = 5
// 写动作统一经 api.write 发出，带 Idempotency-Key；请求到达服务端即已提交。
const isWrite = (config: Config) =>
  !['get', 'head', 'options'].includes((config.method ?? 'get').toLowerCase()) &&
  AxiosHeaders.from(config.headers).has('Idempotency-Key')
request.interceptors.request.use((config: Config) => {
  // storage 事件可能还没送到：发请求前再对齐一次，绝不让原账号的界面带着另一账号的令牌提交。
  const change = syncSession()
  if (change === 'superseded') throw new Error(SUPERSEDED)
  if (change === 'ended') throw new Error(CHANGED)
  config.epoch = epoch
  if (config.timeout === REQUEST_TIMEOUT && transfer(config)) config.timeout = TRANSFER_TIMEOUT
  const token = localStore.get(ACCESS)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
request.interceptors.response.use(
  (response) => {
    const config = response.config as Config
    // 请求期间登录已变化（退出、过期或其他标签页换了账号）：读到的是原登录的数据，不能进入当前页面。
    // 写动作到达服务端时已经提交，照常返回结果，免得用户以为失败而重复提交；
    // 界面的重新同步已由改变登录的 resetSession / syncSession 通知。
    if (config.epoch !== epoch && !isWrite(config)) throw new Error(CHANGED)
    return response
  },
  async (error: AxiosError) => {
    const config = error.config as Config | undefined
    const wait = Number(error.response?.headers?.['retry-after'])
    if (config && error.response?.status === 429 && (config.throttled ?? 0) < THROTTLE_RETRIES && wait >= 0 && wait <= THROTTLE_WAIT_SECONDS && config.epoch === epoch) {
      config.throttled = (config.throttled ?? 0) + 1
      await new Promise((resolve) => setTimeout(resolve, Math.max(wait, 1) * 1000))
      // 等待期间登录变化：不能用新登录的令牌重发原账号的请求。
      if (config.epoch !== epoch) throw error
      return request(config)
    }
    if (!config || error.response?.status !== 401 || config.retried || config.url?.startsWith('/auth/login')) throw error
    // 续期前与共享存储对齐：其他标签页已退出或换了账号时，不能拿别人的刷新令牌续期，也不能清掉别人的登录。
    syncSession()
    // 登录已变化后不重试：重试会带上新登录的令牌，把原账号的操作记到另一账号名下。
    if (config.epoch !== epoch) throw error
    const refresh = session
    if (!refresh) {
      resetSession()
      throw error
    }
    const started = epoch
    if (!flight) {
      const current = axios
        .post('/api/auth/refresh/', { refresh }, { timeout: 15000 })
        .then(({ data }) => {
          // 续期期间本页或其他标签页退出、重新登录：新令牌属于已结束的登录，不能写回共享存储。
          if (epoch !== started || localStore.get(REFRESH) !== refresh) throw new Error('登录状态已变化。')
          localStore.set(ACCESS, data.access)
        })
        .catch((e) => {
          if (epoch === started && localStore.get(REFRESH) === refresh && [400, 401, 403].includes(e.response?.status)) resetSession()
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
// 与后端、Nginx 的校验一致；格式异常的编号不展示，避免把响应内容原样塞进提示条。
const REQUEST_ID = /^[A-Za-z0-9._-]{1,64}$/
function serverErrorId(response: AxiosResponse): string {
  const headers = response.headers as { get?: (name: string) => unknown } & Record<string, unknown>
  const candidates = [
    (response.data as { request_id?: unknown } | null)?.request_id,
    typeof headers?.get === 'function' ? headers.get('x-request-id') : headers?.['x-request-id'],
  ]
  return candidates.find((value): value is string => typeof value === 'string' && REQUEST_ID.test(value)) ?? ''
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
        !['row', 'token_class', 'token_type', 'actions', 'request_id'].includes(key) &&
        !(key === 'code' && typeof detail === 'string' && /^[a-z_]+$/.test(detail)),
      ).map(([, detail]) => flatten(detail)).filter(Boolean).join('；')
      return value.row != null ? `第 ${value.row} 行：${text || '填写内容不符合要求，请检查后重试。'}` : text
    }
    return String(value)
  }
  if (!axios.isAxiosError(error)) return flatten(error) || '操作失败，请重试。'
  const data = error.response?.data
  const detail = flatten(data?.detail ?? data)
  if (!error.response) return detail || NETWORK_MESSAGES[error.code ?? ''] || '网络异常，请检查连接后重试。'
  const text = detail || STATUS_MESSAGES[error.response.status] || `请求失败（状态码 ${error.response.status}）。`
  // 只有 500 附带编号：管理员按编号在 Nginx 与后端日志里找到对应请求、操作人和异常。
  const id = error.response.status === 500 ? serverErrorId(error.response) : ''
  return id ? `${text}错误编号：${id}（请把编号告诉管理员）` : text
}
export function recoveryActions(error: unknown): { label: string; path: string }[] {
  const actions = axios.isAxiosError(error) ? error.response?.data?.actions : []
  return Array.isArray(actions) ? actions.filter(a => typeof a.label === 'string' && typeof a.path === 'string' && /^\/(projects|purchases|finance)(\/\d+)?(\?|$)/.test(a.path)) : []
}
