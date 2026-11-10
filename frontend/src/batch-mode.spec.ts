import { beforeEach, describe, expect, it, vi } from 'vitest'

describe('批量管理开关', () => {
  beforeEach(() => { localStorage.clear(); vi.resetModules() })
  it('默认收起删除入口', async () => {
    const { batchMode } = await import('./batch-mode')
    expect(batchMode.value).toBe(false)
  })
  it('开启后跨页面保持，退出后清除', async () => {
    const first = await import('./batch-mode')
    first.setBatchMode(true)
    vi.resetModules()
    const second = await import('./batch-mode')
    expect(second.batchMode.value).toBe(true)
    second.setBatchMode(false)
    vi.resetModules()
    expect((await import('./batch-mode')).batchMode.value).toBe(false)
  })
})
