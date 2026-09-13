import { afterEach, describe, expect, it, vi } from 'vitest'
import { localStore, sessionStore } from './storage'

afterEach(() => vi.unstubAllGlobals())

describe('浏览器存储降级', () => {
  it('存储被策略禁用时读写不抛异常，读取返回空', () => {
    const blocked = () => { throw new DOMException('blocked', 'SecurityError') }
    vi.stubGlobal('localStorage', { get getItem() { return blocked() }, get setItem() { return blocked() }, get removeItem() { return blocked() } })
    expect(localStore.get('access_token')).toBeNull()
    expect(() => localStore.set('access_token', 'x')).not.toThrow()
    expect(() => localStore.remove('access_token')).not.toThrow()
  })

  it('配额写满时写入静默降级，不影响后续读取', () => {
    const values = new Map<string, string>([['erp.page-size', '20']])
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: () => { throw new DOMException('quota', 'QuotaExceededError') },
      removeItem: (key: string) => values.delete(key),
    })
    expect(() => localStore.set('erp.page-size', '50')).not.toThrow()
    expect(localStore.get('erp.page-size')).toBe('20')
  })

  it('stub 缺少 removeItem 时也不抛异常', () => {
    vi.stubGlobal('sessionStorage', { getItem: () => null, setItem: () => undefined })
    expect(() => sessionStore.remove('module-project-1-采购')).not.toThrow()
  })

  it('存储可用时正常读写', () => {
    const values = new Map<string, string>()
    vi.stubGlobal('sessionStorage', {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    })
    sessionStore.set('project-overview', 'collapsed')
    expect(sessionStore.get('project-overview')).toBe('collapsed')
    sessionStore.remove('project-overview')
    expect(sessionStore.get('project-overview')).toBeNull()
  })
})
