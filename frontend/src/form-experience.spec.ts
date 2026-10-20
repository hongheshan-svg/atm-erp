import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearFormDrafts, confirmFormNavigation, draftKey, loadDraft, registerFormGuard, saveDraft, savedTarget } from './form-experience'
import { fieldIssues } from './forms'
import type { Command } from './types'

const command: Command = { title: '新建采购', path: '/business/purchases/', initial: { project: 3 }, fields: [{ key: 'project', label: '项目' }, { key: 'note', label: '说明' }, { key: 'file', label: '附件', type: 'file' }] }
beforeEach(() => { sessionStorage.clear(); vi.useRealTimers() })
describe('未保存内容与操作结果', () => {
  it('暂存只恢复当前账号和相同业务上下文，不恢复文件，也不保存密码表单', () => {
    const key = draftKey(command, 1)
    expect(saveDraft(key, command, { project: 3, note: '待填写', file: new File(['x'], 'receipt.txt'), extra: '不保存' })).toBe(true)
    expect(loadDraft(key, command)).toEqual({ project: 3, note: '待填写' })
    expect(loadDraft(draftKey(command, 2), command)).toBeNull()
    expect(loadDraft(key, { ...command, initial: { project: 4 } })).toBeNull()
    expect(draftKey({ ...command, fields: [{ key: 'password', label: '密码', type: 'password' }] }, 1)).toBe('')
  })
  it('暂存过期和退出账号时清除，保留其他偏好', () => {
    vi.useFakeTimers()
    const key = draftKey(command, 1)
    saveDraft(key, command, { project: 3, note: '草稿' })
    vi.advanceTimersByTime(8 * 60 * 60 * 1000 + 1)
    expect(loadDraft(key, command)).toBeNull()
    saveDraft(key, command, { project: 3, note: '重新填写' })
    sessionStorage.setItem('module-tab-1', 'tasks')
    clearFormDrafts()
    expect(loadDraft(key, command)).toBeNull()
    expect(sessionStorage.getItem('module-tab-1')).toBe('tasks')
  })
  it('不同项目的新单草稿分别保留，不因打开另一项目而删除', () => {
    const other = { ...command, initial: { project: 4 } }
    saveDraft(draftKey(command, 1), command, { project: 3, note: '甲项目说明' })
    expect(loadDraft(draftKey(other, 1), other)).toBeNull()
    saveDraft(draftKey(other, 1), other, { project: 4, note: '乙项目说明' })
    expect(loadDraft(draftKey(command, 1), command)?.note).toBe('甲项目说明')
    expect(loadDraft(draftKey(other, 1), other)?.note).toBe('乙项目说明')
  })
  it('取消离开会阻止页签和项目切换，卸载后不留下守卫', async () => {
    const guard = vi.fn().mockResolvedValue(false)
    const remove = registerFormGuard(guard)
    expect(await confirmFormNavigation()).toBe(false)
    remove()
    expect(await confirmFormNavigation()).toBe(true)
  })
  it('保存后打开实际生成记录：付款流水、签约项目以及对账单', () => {
    expect(savedTarget({ ...command, path: '/business/entries/7/pay/' }, { id: 20 }, 7)).toEqual({ resource: 'payments', id: 20 })
    expect(savedTarget({ ...command, path: '/business/sales/9/sign/' }, { id: 9, project: 18 }, 9)).toEqual({ resource: 'projects', id: 18 })
    expect(savedTarget({ ...command, path: '/business/reconciliations/' }, { id: 25 }, 7)).toEqual({ resource: 'reconciliations', id: 25 })
  })
  it('一次列出各行填写问题，错误定位保留真实行号', () => {
    const issues = fieldIssues([{ key: 'lines', label: '收货', type: 'rows', fields: [{ key: 'quantity', label: '数量', numeric: { scale: 3, min: 0 } }] }], { lines: [{ quantity: '2' }, { quantity: '-1' }, { quantity: '2个' }] })
    expect(issues.map(i => i.path)).toEqual(['lines.1.quantity', 'lines.2.quantity'])
    expect(issues[1]?.message).toContain('第 3 行')
  })
})
