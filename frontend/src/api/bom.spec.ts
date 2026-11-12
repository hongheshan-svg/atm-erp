import { afterEach, expect, it, vi } from 'vitest'
import { request } from '../utils/request'
import { downloadBOM } from './bom'

vi.mock('../utils/request', () => ({ request: { get: vi.fn(), post: vi.fn() } }))
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); vi.clearAllMocks() })

it('大量跨页BOM行号通过POST正文发送，下载后释放文件', async () => {
  vi.useFakeTimers()
  const data = new Blob(['表格'])
  vi.mocked(request.post).mockResolvedValue({ data })
  const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:bom')
  const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  const ids = Array.from({ length: 20000 }, (_, i) => i + 1)
  await downloadBOM(7, ids, 'xlsx', 'BOM已选.xlsx')
  expect(request.post).toHaveBeenCalledWith('/business/bom/export/', { project: 7, ids, file_format: 'xlsx' }, { responseType: 'blob' })
  expect(create).toHaveBeenCalledWith(data)
  expect(click).toHaveBeenCalledOnce()
  vi.runAllTimers()
  expect(revoke).toHaveBeenCalledWith('blob:bom')
})

it('权限或过期明细错误显示原中文原因，不生成空白下载', async () => {
  const error = { response: { data: new Blob([JSON.stringify({ detail: '所选明细已变化，请刷新。' })]) } }
  vi.mocked(request.post).mockRejectedValue(error)
  const create = vi.spyOn(URL, 'createObjectURL')
  await expect(downloadBOM(7, [1], 'csv', 'BOM.csv')).rejects.toMatchObject({ response: { data: { detail: '所选明细已变化，请刷新。' } } })
  expect(create).not.toHaveBeenCalled()
})

it('缺料清单和可回导模板通过 layout 区分导出格式', async () => {
  vi.mocked(request.post).mockResolvedValue({ data: new Blob(['表格']) })
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:bom')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  await downloadBOM(7, [1, 2], 'xlsx', '缺料清单.xlsx', 'purchase')
  expect(request.post).toHaveBeenLastCalledWith('/business/bom/export/', { project: 7, ids: [1, 2], file_format: 'xlsx', layout: 'purchase' }, { responseType: 'blob' })
  await downloadBOM(7, [1], 'xlsx', 'BOM回导模板.xlsx', 'import')
  expect(request.post).toHaveBeenLastCalledWith('/business/bom/export/', { project: 7, ids: [1], file_format: 'xlsx', layout: 'import' }, { responseType: 'blob' })
})

it('普通下载与预览读取共用同一出错解析：JSON 错误转回对象，非 JSON 保留原错误', async () => {
  const { download, readBlob } = await import('./index')
  const failure = { response: { data: new Blob([JSON.stringify({ detail: '无权下载' })]) } }
  vi.mocked(request.get).mockRejectedValueOnce(failure)
  await expect(download('/api/business/tasks/export/', '任务.xlsx')).rejects.toMatchObject({ response: { data: { detail: '无权下载' } } })
  expect(request.get).toHaveBeenLastCalledWith('/business/tasks/export/', { responseType: 'blob', params: {} })
  const raw = new Blob(['<html>bad gateway</html>'])
  vi.mocked(request.get).mockRejectedValueOnce({ response: { data: raw } })
  await expect(readBlob('/api/business/documents/1/file/')).rejects.toMatchObject({ response: { data: raw } })
  const file = new Blob(['pdf'])
  vi.mocked(request.get).mockResolvedValueOnce({ data: file })
  await expect(readBlob('/business/documents/1/file/')).resolves.toBe(file)
})
