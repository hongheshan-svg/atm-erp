import axios, { AxiosError, AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { message, request, requestKey, resetSession } from './request'

const adapter = request.defaults.adapter
function response(config: InternalAxiosRequestConfig, status = 200): AxiosResponse {
  return { config, status, data: { ok: true }, statusText: '', headers: new AxiosHeaders() }
}
beforeEach(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  })
  resetSession('old-token', 'refresh-token')
})
afterEach(() => { request.defaults.adapter = adapter; vi.restoreAllMocks(); resetSession() })

describe('JWT 会话与刷新', () => {
  it('并发 401 只刷新一次，重试携带新令牌', async () => {
    let finish!: (value: unknown) => void
    const refresh = vi.spyOn(axios, 'post').mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const seen: string[] = []
    request.defaults.adapter = async config => {
      const header = String(config.headers.Authorization)
      seen.push(header)
      if (header === 'Bearer old-token') throw new AxiosError('unauthorized', '401', config, {}, response(config, 401))
      return response(config)
    }
    const pending = Promise.all([request.get('/business/projects/'), request.get('/business/items/')])
    await vi.waitFor(() => expect(refresh).toHaveBeenCalledTimes(1))
    finish({ data: { access: 'new-token' } })
    await pending
    expect(seen.filter(header => header === 'Bearer new-token')).toHaveLength(2)
    expect(localStorage.getItem('access_token')).toBe('new-token')
  })

  it('退出后拒绝旧请求结果，避免旧账户数据进入新页面', async () => {
    let finish!: () => void
    request.defaults.adapter = config => new Promise(resolve => { finish = () => resolve(response(config)) })
    const pending = request.get('/business/projects/')
    const assertion = expect(pending).rejects.toThrow('登录状态已变化')
    await vi.waitFor(() => expect(finish).toBeTypeOf('function'))
    resetSession()
    finish()
    await assertion
  })

  it('退出期间到达的刷新结果不能恢复旧令牌', async () => {
    let finish!: (value: unknown) => void
    const refresh = vi.spyOn(axios, 'post').mockImplementation(() => new Promise(resolve => { finish = resolve }))
    request.defaults.adapter = async config => { throw new AxiosError('unauthorized', '401', config, {}, response(config, 401)) }
    const pending = request.get('/business/projects/')
    const assertion = expect(pending).rejects.toThrow('登录状态已变化')
    await vi.waitFor(() => expect(refresh).toHaveBeenCalledTimes(1))
    resetSession()
    finish({ data: { access: 'late-token' } })
    await assertion
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('刷新网络暂时失败保留会话，凭据失效才退出', async () => {
    vi.spyOn(axios, 'post').mockRejectedValueOnce(new AxiosError('Network Error')).mockRejectedValueOnce({ response: { status: 401 } })
    request.defaults.adapter = async config => { throw new AxiosError('unauthorized', '401', config, {}, response(config, 401)) }
    await expect(request.get('/business/projects/')).rejects.toThrow('Network Error')
    expect(localStorage.getItem('refresh_token')).toBe('refresh-token')
    await expect(request.get('/business/projects/')).rejects.toBeTruthy()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })
})

const uuidShape = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const realCrypto = globalThis.crypto

describe('操作标识生成', () => {
  // Restore explicitly instead of unstubAllGlobals, which would also drop the localStorage stub.
  afterEach(() => { Object.defineProperty(globalThis, 'crypto', { value: realCrypto, configurable: true }) })
  function withCrypto(value: unknown) {
    Object.defineProperty(globalThis, 'crypto', { value, configurable: true })
  }

  it('安全上下文直接使用浏览器的 randomUUID', () => {
    const randomUUID = vi.fn(() => '11111111-2222-4333-8444-555555555555')
    withCrypto({ randomUUID, getRandomValues: realCrypto.getRandomValues.bind(realCrypto) })
    expect(requestKey()).toBe('11111111-2222-4333-8444-555555555555')
    expect(randomUUID).toHaveBeenCalledOnce()
  })

  // Plain HTTP on a LAN address is not a secure context, so randomUUID is missing there.
  it('非安全上下文缺少 randomUUID 时仍生成合法且互不相同的标识', () => {
    withCrypto({ getRandomValues: realCrypto.getRandomValues.bind(realCrypto) })
    const keys = Array.from({ length: 200 }, () => requestKey())
    for (const key of keys) expect(key).toMatch(uuidShape)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('连 getRandomValues 都没有时退回随机数，不抛异常', () => {
    withCrypto(undefined)
    const keys = Array.from({ length: 50 }, () => requestKey())
    for (const key of keys) expect(key).toMatch(uuidShape)
    expect(new Set(keys).size).toBe(keys.length)
  })
})

describe('错误提示中文化', () => {
  const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig
  function failure(status: number, data: unknown) {
    const result: AxiosResponse = { config, status, data, statusText: '', headers: new AxiosHeaders() }
    return new AxiosError(`Request failed with status code ${status}`, 'ERR_BAD_RESPONSE', config, {}, result)
  }

  it('接口返回的提示原样展示', () => {
    expect(message(failure(400, { detail: '目标版本不高于正在运行的版本。' }))).toBe('目标版本不高于正在运行的版本。')
    expect(message(failure(400, { amount: ['金额不能为负。'], quantity: ['数量必须大于零。'] }))).toBe('金额不能为负。；数量必须大于零。')
  })

  it('连不上服务或超时改用中文说明，不显示 axios 的英文描述', () => {
    expect(message(new AxiosError('Network Error', 'ERR_NETWORK'))).toBe('无法连接服务器，请检查网络或确认服务是否已启动。')
    expect(message(new AxiosError('timeout of 25000ms exceeded', 'ECONNABORTED'))).toBe('请求超时，请检查网络后重试。')
    expect(message(new AxiosError('unknown'))).toBe('网络异常，请检查连接后重试。')
  })

  // 网关返回的是英文 HTML 错误页，直接展示既看不懂又会把整段标记塞进提示条。
  it('网关错误页按状态码给出中文提示', () => {
    expect(message(failure(502, '<html><body>502 Bad Gateway</body></html>'))).toBe('服务暂时不可用，请稍后重试。')
    expect(message(failure(403, ''))).toBe('没有执行该操作的权限。')
    expect(message(failure(418, {}))).toBe('请求失败（HTTP 418）。')
  })

  it('非请求类错误保留原有消息', () => {
    expect(message(new Error('登录状态已变化。'))).toBe('登录状态已变化。')
    expect(message(null)).toBe('操作失败，请重试。')
  })
})
