import axios, { AxiosError, AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { request, resetSession } from './request'

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
