import axios, { AxiosError, AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, afterEach, describe, expect, it, onTestFinished, vi } from 'vitest'
import { download, readBlob, write } from '../api'
import { downloadBOM } from '../api/bom'
import { message, request, requestKey, resetSession, REQUEST_TIMEOUT, TRANSFER_TIMEOUT } from './request'

const adapter = request.defaults.adapter
function response(config: InternalAxiosRequestConfig, status = 200): AxiosResponse {
  return { config, status, data: { ok: true }, statusText: '', headers: new AxiosHeaders() }
}
// 浏览器共用的 localStorage；直接改这里就是「其他标签页」写入，本页不会收到自己写入的 storage 事件。
let shared = new Map<string, string>()
beforeEach(() => {
  shared = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => shared.get(key) ?? null,
    setItem: (key: string, value: string) => shared.set(key, value),
    removeItem: (key: string) => shared.delete(key),
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

// 挂起每个请求，由测试决定何时返回；记录每次实际发出的请求。
function deferredAdapter() {
  const sent: { config: InternalAxiosRequestConfig; finish: (status?: number) => void }[] = []
  request.defaults.adapter = config => new Promise((resolve, reject) => {
    sent.push({ config, finish: (status = 200) => status < 400 ? resolve(response(config, status)) : reject(new AxiosError('failed', String(status), config, {}, response(config, status))) })
  })
  return sent
}
function sessionEvents() {
  const seen: string[] = []
  const record = (event: Event) => { seen.push(event.type) }
  window.addEventListener('erp-session', record)
  window.addEventListener('erp-session-replaced', record)
  onTestFinished(() => {
    window.removeEventListener('erp-session', record)
    window.removeEventListener('erp-session-replaced', record)
  })
  return seen
}

describe('请求期间登录变化', () => {
  it('已提交的写动作照常返回结果，读取和导出结果仍作废', async () => {
    const sent = deferredAdapter()
    const saved = write('/business/purchases/', { supplier: 1 }, 'key-1')
    const listed = request.get('/business/projects/')
    const exported = request.post('/business/bom/export/', { project: 7 }, { responseType: 'blob' })
    const listedAssertion = expect(listed).rejects.toThrow('登录状态已变化')
    const exportedAssertion = expect(exported).rejects.toThrow('登录状态已变化')
    await vi.waitFor(() => expect(sent).toHaveLength(3))
    resetSession()
    for (const entry of sent) entry.finish()
    await expect(saved).resolves.toEqual({ ok: true })
    await listedAssertion
    await exportedAssertion
  })

  it('写动作遇到 401 时登录已变化：不续期也不重试，不会以新登录的身份重新提交', async () => {
    const refresh = vi.spyOn(axios, 'post')
    const sent = deferredAdapter()
    const saved = write('/business/purchases/', { supplier: 1 }, 'key-1')
    const assertion = expect(saved).rejects.toMatchObject({ response: { status: 401 } })
    await vi.waitFor(() => expect(sent).toHaveLength(1))
    resetSession('second-access', 'second-refresh')
    sent[0]!.finish(401)
    await assertion
    expect(refresh).not.toHaveBeenCalled()
    expect(sent).toHaveLength(1)
  })
})

// JWT 里只有 user_id 用于判断是否同一账号；签名不参与。
function jwt(user: number, id: string) {
  const payload = btoa(JSON.stringify({ token_type: 'refresh', user_id: user, jti: id })).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `eyJhbGciOiJIUzI1NiJ9.${payload}.signature`
}
// 其他标签页登录、续期或退出：只改共享存储，随后（可能稍晚）收到 storage 事件。
function otherTab(access: string | null, refresh: string | null, notify = true) {
  for (const [key, value] of [['access_token', access], ['refresh_token', refresh]] as const) {
    if (value == null) shared.delete(key)
    else shared.set(key, value)
  }
  if (notify) window.dispatchEvent(new StorageEvent('storage', { key: 'refresh_token', newValue: refresh }))
}

describe('跨标签页登录同步', () => {
  it('其他标签页例行续期只换访问令牌：本页不重新载入、不退出，后续请求用新令牌', async () => {
    resetSession('access-1', jwt(1, 'a'))
    const seen = sessionEvents()
    const sent = deferredAdapter()
    const pending = request.get('/business/projects/')
    await vi.waitFor(() => expect(sent).toHaveLength(1))
    shared.set('access_token', 'access-1-renewed')
    window.dispatchEvent(new StorageEvent('storage', { key: 'access_token', newValue: 'access-1-renewed' }))
    sent[0]!.finish()
    await expect(pending).resolves.toMatchObject({ data: { ok: true } })
    const next = request.get('/business/items/')
    await vi.waitFor(() => expect(sent).toHaveLength(2))
    expect(sent[1]!.config.headers.Authorization).toBe('Bearer access-1-renewed')
    sent[1]!.finish()
    await next
    expect(seen).toEqual([])
  })

  it('其他标签页退出：本页按退出处理，进行中的读取作废，不再带旧令牌', async () => {
    resetSession('access-1', jwt(1, 'a'))
    const seen = sessionEvents()
    const sent = deferredAdapter()
    const pending = request.get('/business/projects/')
    const assertion = expect(pending).rejects.toThrow('登录状态已变化')
    await vi.waitFor(() => expect(sent).toHaveLength(1))
    otherTab(null, null)
    expect(seen).toEqual(['erp-session'])
    sent[0]!.finish()
    await assertion
    const next = request.get('/auth/me/')
    await vi.waitFor(() => expect(sent).toHaveLength(2))
    expect(sent[1]!.config.headers.Authorization).toBeUndefined()
    sent[1]!.finish()
    await next
  })

  it('其他标签页换成另一账号：本页清空原账号并整页载入，载入前不带新账号令牌发出任何请求', async () => {
    resetSession('access-1', jwt(1, 'a'))
    const seen = sessionEvents()
    const sent = deferredAdapter()
    const pending = request.get('/business/projects/')
    const assertion = expect(pending).rejects.toThrow('登录状态已变化')
    await vi.waitFor(() => expect(sent).toHaveLength(1))
    otherTab('access-2', jwt(2, 'b'))
    expect(seen).toEqual(['erp-session', 'erp-session-replaced'])
    sent[0]!.finish()
    await assertion
    await expect(write('/business/purchases/', { supplier: 1 }, 'key-1')).rejects.toThrow('其他标签页已切换为另一账号登录')
    await expect(request.get('/auth/me/')).rejects.toThrow('其他标签页已切换为另一账号登录')
    expect(sent).toHaveLength(1)
    // 只通知一次；本页不改动另一账号的令牌。
    otherTab('access-2', jwt(2, 'b'))
    expect(seen).toEqual(['erp-session', 'erp-session-replaced'])
    expect(shared.get('access_token')).toBe('access-2')
    expect(shared.get('refresh_token')).toBe(jwt(2, 'b'))
  })

  it('本页重新登录后恢复正常请求', async () => {
    resetSession('access-1', jwt(1, 'a'))
    otherTab('access-2', jwt(2, 'b'))
    await expect(request.get('/auth/me/')).rejects.toThrow('其他标签页已切换为另一账号登录')
    resetSession('access-3', jwt(3, 'c'))
    const sent = deferredAdapter()
    const next = request.get('/auth/me/')
    await vi.waitFor(() => expect(sent).toHaveLength(1))
    expect(sent[0]!.config.headers.Authorization).toBe('Bearer access-3')
    sent[0]!.finish()
    await next
  })

  it('同一账号在其他标签页重新登录：沿用新登录，进行中的请求和页面不受影响', async () => {
    resetSession('access-1', jwt(1, 'a'))
    const seen = sessionEvents()
    const sent = deferredAdapter()
    const pending = request.get('/business/projects/')
    await vi.waitFor(() => expect(sent).toHaveLength(1))
    otherTab('access-1b', jwt(1, 'c'))
    sent[0]!.finish()
    await expect(pending).resolves.toMatchObject({ data: { ok: true } })
    const next = request.get('/business/items/')
    await vi.waitFor(() => expect(sent).toHaveLength(2))
    expect(sent[1]!.config.headers.Authorization).toBe('Bearer access-1b')
    sent[1]!.finish()
    await next
    expect(seen).toEqual([])
  })

  it('storage 事件尚未送到时，发请求前也能发现换号，不会带着新账号令牌提交', async () => {
    resetSession('access-1', jwt(1, 'a'))
    const seen = sessionEvents()
    const sent = deferredAdapter()
    otherTab('access-2', jwt(2, 'b'), false)
    await expect(write('/business/purchases/', { supplier: 1 }, 'key-1')).rejects.toThrow('其他标签页已切换为另一账号登录')
    expect(sent).toHaveLength(0)
    expect(seen).toEqual(['erp-session', 'erp-session-replaced'])
  })

  it('续期期间其他标签页换号：续期结果不覆盖新账号令牌，也不重试原请求', async () => {
    resetSession('access-1', jwt(1, 'a'))
    let finish!: (value: unknown) => void
    const refresh = vi.spyOn(axios, 'post').mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const sent = deferredAdapter()
    const pending = request.get('/business/projects/')
    const assertion = expect(pending).rejects.toThrow('登录状态已变化')
    await vi.waitFor(() => expect(sent).toHaveLength(1))
    sent[0]!.finish(401)
    await vi.waitFor(() => expect(refresh).toHaveBeenCalledTimes(1))
    otherTab('access-2', jwt(2, 'b'), false)
    finish({ data: { access: 'late-access-1' } })
    await assertion
    expect(shared.get('access_token')).toBe('access-2')
    expect(sent).toHaveLength(1)
  })

  it('其他标签页换号后本页续期失败：不清除另一账号的登录', async () => {
    resetSession('access-1', jwt(1, 'a'))
    let fail!: (reason: unknown) => void
    vi.spyOn(axios, 'post').mockImplementation(() => new Promise((_resolve, reject) => { fail = reject }))
    const sent = deferredAdapter()
    const pending = request.get('/business/projects/')
    const assertion = expect(pending).rejects.toBeTruthy()
    await vi.waitFor(() => expect(sent).toHaveLength(1))
    sent[0]!.finish(401)
    await vi.waitFor(() => expect(fail).toBeTypeOf('function'))
    otherTab('access-2', jwt(2, 'b'), false)
    fail({ response: { status: 401 } })
    await assertion
    expect(shared.get('access_token')).toBe('access-2')
    expect(shared.get('refresh_token')).toBe(jwt(2, 'b'))
  })
})

describe('上传、导入与导出超时', () => {
  it('普通请求保持 25 秒，附件上传、文件导入与各类下载放宽到数分钟', async () => {
    const seen: [string, number | undefined][] = []
    request.defaults.adapter = async config => {
      seen.push([`${config.method} ${config.url}`, config.timeout])
      return { ...response(config), data: config.responseType === 'blob' ? new Blob(['x']) : { ok: true } }
    }
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:file')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const file = () => { const body = new FormData(); body.append('file', new Blob(['x']), 'a.xlsx'); return body }
    await request.get('/business/projects/')
    await write('/business/purchases/', { supplier: 1 }, 'key-1')
    await write('/business/documents/', file(), 'key-2')
    await write('/business/tasks/import-file/', file(), 'key-3')
    await write('/business/tasks/import-confirm/', { token: 't' }, 'key-4')
    await write('/business/projects/3/import-preview/', file(), 'key-5')
    await write('/business/projects/3/bom-import-confirm/', { token: 't' }, 'key-6')
    await download('/business/tasks/export/', '任务.xlsx')
    await readBlob('/api/business/documents/1/file/')
    await downloadBOM(7, [1], 'xlsx', 'BOM.xlsx')
    await request.get('/business/projects/', { timeout: 1000 })
    expect(seen).toEqual([
      ['get /business/projects/', REQUEST_TIMEOUT],
      ['post /business/purchases/', REQUEST_TIMEOUT],
      ['post /business/documents/', TRANSFER_TIMEOUT],
      ['post /business/tasks/import-file/', TRANSFER_TIMEOUT],
      ['post /business/tasks/import-confirm/', TRANSFER_TIMEOUT],
      ['post /business/projects/3/import-preview/', TRANSFER_TIMEOUT],
      ['post /business/projects/3/bom-import-confirm/', TRANSFER_TIMEOUT],
      ['get /business/tasks/export/', TRANSFER_TIMEOUT],
      ['get /business/documents/1/file/', TRANSFER_TIMEOUT],
      ['post /business/bom/export/', TRANSFER_TIMEOUT],
      ['get /business/projects/', 1000],
    ])
    expect(REQUEST_TIMEOUT).toBe(25000)
    expect(TRANSFER_TIMEOUT).toBeGreaterThanOrEqual(3 * 60_000)
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
    expect(message(failure(418, {}))).toBe('请求失败（状态码 418）。')
  })

  it('非请求类错误保留原有消息', () => {
    expect(message(new Error('登录状态已变化。'))).toBe('登录状态已变化。')
    expect(message(null)).toBe('操作失败，请重试。')
  })

  it('英文接口、登录凭据和未知错误使用中文，内部状态与恢复链接不混入提示', () => {
    expect(message(failure(400, { name: ['This field is required.'] }))).toBe('此项为必填项。')
    expect(message(failure(400, { code: ['此值已存在，请修改。'] }))).toBe('此值已存在，请修改。')
    expect(message(failure(401, {
      detail: 'Given token not valid for any token type', code: 'token_not_valid',
      messages: [{ token_class: 'AccessToken', token_type: 'access', message: 'Token is expired' }],
    }))).toBe('登录状态已失效，请重新登录。')
    expect(message(failure(502, 'Bad Gateway'))).toBe('服务暂时不可用，请稍后重试。')
    expect(message(new Error('Failed to fetch dynamically imported module: https://example.test/app.js'))).toBe('页面资源加载失败，请刷新页面后重试。')
    expect(message(new Error('Unexpected internal exception'))).toBe('操作失败，请重试。')
    expect(message(failure(409, { reason: '请核对原单据。', actions: [{ label: '打开单据', path: '/finance?focus=1' }] }))).toBe('请核对原单据。')
  })

  describe('服务器处理失败附带错误编号', () => {
    function serverError(data: unknown, headers: Record<string, string> = {}) {
      const result: AxiosResponse = { config, status: 500, data, statusText: '', headers: new AxiosHeaders(headers) }
      return new AxiosError('Request failed with status code 500', 'ERR_BAD_RESPONSE', config, {}, result)
    }
    const suffix = (id: string) => `错误编号：${id}（请把编号告诉管理员）`

    it('优先使用响应体中的编号，原中文提示不变', () => {
      const data = { detail: '服务器处理失败，请稍后重试或联系管理员。', request_id: '0f3a9c' }
      expect(message(serverError(data, { 'X-Request-ID': 'header-id' }))).toBe(`服务器处理失败，请稍后重试或联系管理员。${suffix('0f3a9c')}`)
    })

    it('错误页没有响应体编号时取响应头', () => {
      expect(message(serverError('<html>Server Error (500)</html>', { 'X-Request-ID': 'nginx-7d1e' })))
        .toBe(`服务器处理失败，请稍后重试或联系管理员。${suffix('nginx-7d1e')}`)
    })

    it('没有编号或编号格式异常时只显示原提示', () => {
      expect(message(serverError({}))).toBe('服务器处理失败，请稍后重试或联系管理员。')
      expect(message(serverError({ request_id: '<img src=x>' }, { 'X-Request-ID': 'x'.repeat(65) })))
        .toBe('服务器处理失败，请稍后重试或联系管理员。')
    })

    it('其他状态码即使带编号也不改文案', () => {
      const headers = new AxiosHeaders({ 'X-Request-ID': 'abc' })
      for (const [status, data, text] of [
        [400, { detail: '金额不能为负。', request_id: 'abc' }, '金额不能为负。'],
        [502, '', '服务暂时不可用，请稍后重试。'],
      ] as const) {
        const result: AxiosResponse = { config, status, data, statusText: '', headers }
        expect(message(new AxiosError('failed', 'ERR_BAD_RESPONSE', config, {}, result))).toBe(text)
      }
    })
  })

  it('导入错误保留文件行号与实际账号，不显示原始字段名', () => {
    expect(message({ row: 3, message: '执行人账号：未找到登录用户名“wuxingguang”。' })).toBe('第 3 行：执行人账号：未找到登录用户名“wuxingguang”。')
    expect(message({ row: 4, message: 'This field may not be blank.' })).toBe('第 4 行：此项不能为空。')
    expect(message({ row: 5, message: 'Unknown error' })).toBe('第 5 行：填写内容不符合要求，请检查后重试。')
    expect(message(failure(400, { detail: '"中文错误选项" is not a valid choice.' }))).toBe('请选择列表中的有效选项。')
  })
})

describe('接口限流自动重发', () => {
  function throttled(config: InternalAxiosRequestConfig, seconds?: string): never {
    const headers = new AxiosHeaders(seconds === undefined ? {} : { 'retry-after': seconds })
    throw new AxiosError('throttled', '429', config, {}, { ...response(config, 429), headers })
  }

  it('只需等几秒的 429 等待后用同一操作标识重发，成功后照常返回', async () => {
    vi.useFakeTimers()
    onTestFinished(() => { vi.useRealTimers() })
    const keys: string[] = []
    request.defaults.adapter = async config => {
      keys.push(String(config.headers['Idempotency-Key']))
      return keys.length === 1 ? throttled(config, '2') : response(config)
    }
    const pending = request.post('/business/items/', { name: '滑块' }, { headers: { 'Idempotency-Key': 'key-1' } })
    await vi.advanceTimersByTimeAsync(1999)
    expect(keys).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(1)
    await expect(pending).resolves.toMatchObject({ status: 200 })
    expect(keys).toEqual(['key-1', 'key-1'])
  })

  it('最多重发两次，仍被限流时把 429 交给调用方', async () => {
    vi.useFakeTimers()
    onTestFinished(() => { vi.useRealTimers() })
    let calls = 0
    request.defaults.adapter = async config => { calls++; return throttled(config, '1') }
    const pending = request.get('/business/projects/')
    const failed = expect(pending).rejects.toMatchObject({ response: { status: 429 } })
    await vi.advanceTimersByTimeAsync(2000)
    await failed
    expect(calls).toBe(3)
  })

  it('需要长时间等待或未给出等待时间的 429 不重发', async () => {
    for (const seconds of ['42', undefined]) {
      let calls = 0
      request.defaults.adapter = async config => { calls++; return throttled(config, seconds) }
      await expect(request.post('/auth/login/', {})).rejects.toMatchObject({ response: { status: 429 } })
      expect(calls).toBe(1)
    }
  })
})
