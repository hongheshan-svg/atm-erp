import { afterEach, expect, it, vi } from 'vitest'
import { read } from '../api'
import { documentPreview, closeDocumentPreview } from '../document-preview'
import { actionCommand as financeCommand } from './finance'
import { actionCommand as settlementCommand } from './settlement'
import { salesCommand } from './sales'
vi.mock('../api', () => ({ read: vi.fn(), all: vi.fn(), download: vi.fn() }))
afterEach(() => { vi.resetAllMocks(); closeDocumentPreview() })
it('凭证列表按各条原始附件打开预览，保留下载', async () => {
  vi.mocked(read).mockResolvedValue({ evidence: [{ document: 17, name: '银行回单.pdf' }, { document: 22, name: '补充凭证.png' }] })
  const command = await financeCommand('payments', { id: 1 }, '查看凭证')
  command.actions!.find(action => action.label === '预览 补充凭证.png')!.run()
  expect(documentPreview.value).toEqual({ id: 22, name: '补充凭证.png' })
  expect(command.actions!.map(action => action.label)).toContain('下载 银行回单.pdf')
})
it('补充协议只为服务端允许返回的附件提供预览', async () => {
  vi.mocked(read).mockResolvedValue([{ document: 31, document__original_name: '补充协议.docx', before: {}, after: {} }, { document: null, before: {}, after: {} }])
  const command = await salesCommand({ id: 3 }, '补充协议记录')
  expect(command.actions!.filter(action => action.label.startsWith('预览'))).toHaveLength(1)
  command.actions![0]!.run()
  expect(documentPreview.value?.id).toBe(31)
})
it('已确认的对账单打开所关联附件，不从其他单据推测文件', async () => {
  vi.mocked(read).mockResolvedValue({ document: 41, snapshot: { project: {}, entry: {}, payments: [] } })
  const command = await settlementCommand('reconciliations', { id: 5 }, '查看对账明细')
  command.actions!.find(action => action.label === '预览 对账附件')!.run()
  expect(documentPreview.value?.id).toBe(41)
})
