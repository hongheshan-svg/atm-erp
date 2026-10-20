import { afterEach, describe, expect, it } from 'vitest'
import { options, recentReferences, referenceLabel, rememberReference } from './catalog'
import { user } from './session'

afterEach(() => { user.value = null })
describe('选择器名称与最近使用', () => {
  it('名称优先、编号辅助，保留规格与重名账号', () => {
    expect(options([{ id: 7, name: '伺服电机', code: 'M007', specification: '750W', brand: '品牌甲', unit: '台' }])).toEqual([
      { value: 7, label: '伺服电机 · M007 · 750W · 品牌甲 · 台' },
    ])
    expect(referenceLabel({ id: 1, display_name: '王工', username: 'wang1' })).toEqual({ name: '王工', detail: 'wang1' })
    expect(options([{ id: 1, display_name: '王工', username: 'wang1' }, { id: 2, display_name: '王工', username: 'wang2' }])).toEqual([
      { value: 1, label: '王工（wang1）' }, { value: 2, label: '王工（wang2）' },
    ])
  })
  it('最近使用仅记本次会话的ID，名称与可见性重新取自授权结果', () => {
    user.value = { id: 1, roles: ['manager'] }
    rememberReference('/business/projects/', 2)
    rememberReference('/business/projects/', 3)
    rememberReference('/business/projects/', 2)
    expect(recentReferences('/business/projects/', [{ id: 2, name: '改名后的授权项目' }, { id: 4, name: '其他项目' }])).toEqual([{ id: 2, name: '改名后的授权项目' }])
    expect(recentReferences('/business/projects/', [])).toEqual([])
    expect(recentReferences('/business/items/', [{ id: 2 }])).toEqual([])
    user.value = { id: 2, roles: ['manager'] }
    expect(recentReferences('/business/projects/', [{ id: 2 }])).toEqual([])
    user.value = { id: 1, roles: ['manager'] }
    expect(recentReferences('/business/projects/', [{ id: 2 }])).toEqual([])
  })
  it('退出和撤换岗位立即清空最近使用，不向未登录会话提供历史', () => {
    user.value = { id: 1, roles: ['admin'] }
    rememberReference('/business/items/', 1)
    user.value.roles = ['member']
    expect(recentReferences('/business/items/', [{ id: 1 }])).toEqual([])
    rememberReference('/business/items/', 1)
    window.dispatchEvent(new Event('erp-session'))
    expect(recentReferences('/business/items/', [{ id: 1 }])).toEqual([])
    rememberReference('/business/items/', 1)
    user.value = { id: 1, roles: ['admin'] }
    expect(recentReferences('/business/items/', [{ id: 1 }])).toEqual([])
  })
})
