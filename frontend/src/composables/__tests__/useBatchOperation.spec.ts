import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useBatchOperation } from '../useBatchOperation'
import { ElMessage, ElMessageBox } from 'element-plus'

vi.mock('@/utils/request', () => ({
  default: {
    delete: vi.fn().mockResolvedValue({}),
    patch: vi.fn().mockResolvedValue({}),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  }
}))

describe('useBatchOperation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('initializes with empty state', () => {
    const { selectedRows, selectedCount, loading } = useBatchOperation('/api/orders/')

    expect(selectedRows.value).toEqual([])
    expect(selectedCount.value).toBe(0)
    expect(loading.value).toBe(false)
  })

  describe('handleSelectionChange', () => {
    it('updates rows and count', () => {
      const { handleSelectionChange, selectedCount } = useBatchOperation('/api/orders/')

      handleSelectionChange([{ id: 1 }, { id: 2 }])

      expect(selectedCount.value).toBe(2)
    })
  })

  describe('clearSelection', () => {
    it('empties the selection', () => {
      const { handleSelectionChange, clearSelection, selectedRows } = useBatchOperation('/api/orders/')

      handleSelectionChange([{ id: 1 }])
      clearSelection()

      expect(selectedRows.value).toEqual([])
    })
  })

  describe('getSelectedIds', () => {
    it('returns array of ids', () => {
      const { handleSelectionChange, getSelectedIds } = useBatchOperation('/api/orders/')

      handleSelectionChange([{ id: 10 }, { id: 20 }, { id: 30 }])

      expect(getSelectedIds()).toEqual([10, 20, 30])
    })

    it('uses custom idField', () => {
      const { handleSelectionChange, getSelectedIds } = useBatchOperation('/api/items/', { idField: 'code' })

      handleSelectionChange([{ code: 'A' }, { code: 'B' }])

      expect(getSelectedIds()).toEqual(['A', 'B'])
    })
  })

  describe('batchExport', () => {
    it('warns when nothing selected', () => {
      const { batchExport } = useBatchOperation('/api/orders/')

      batchExport()

      expect(ElMessage.warning).toHaveBeenCalledWith('请至少选择一条记录')
    })

    it('creates CSV and downloads', () => {
      const createObjectURL = vi.fn(() => 'blob:url')
      const revokeObjectURL = vi.fn()
      Object.defineProperty(window, 'URL', {
        value: { createObjectURL, revokeObjectURL },
        writable: true
      })

      const clickMock = vi.fn()
      vi.spyOn(document, 'createElement').mockReturnValue({
        href: '',
        download: '',
        click: clickMock,
      } as any)

      const { handleSelectionChange, batchExport } = useBatchOperation('/api/orders/')
      handleSelectionChange([{ id: 1, name: 'Order 1' }, { id: 2, name: 'Order 2' }])

      batchExport()

      expect(createObjectURL).toHaveBeenCalled()
      expect(clickMock).toHaveBeenCalled()
      expect(ElMessage.success).toHaveBeenCalled()
    })
  })

  describe('batchUpdateStatus', () => {
    it('warns when nothing selected', async () => {
      const { batchUpdateStatus } = useBatchOperation('/api/orders/')

      await batchUpdateStatus('APPROVED')

      expect(ElMessage.warning).toHaveBeenCalledWith('请至少选择一条记录')
    })

    it('patches each selected row', async () => {
      const onSuccess = vi.fn()
      const { handleSelectionChange, batchUpdateStatus } = useBatchOperation('/api/orders/', { onSuccess })
      const request = await import('@/utils/request')

      handleSelectionChange([{ id: 1 }, { id: 2 }])
      await batchUpdateStatus('APPROVED')

      // request has baseURL '/api', so the composable strips the '/api' prefix
      expect(request.default.patch).toHaveBeenCalledWith('/orders/1/', { status: 'APPROVED' })
      expect(request.default.patch).toHaveBeenCalledWith('/orders/2/', { status: 'APPROVED' })
      expect(onSuccess).toHaveBeenCalled()
    })
  })

  describe('batchDelete', () => {
    it('deletes selected rows', async () => {
      const { handleSelectionChange, batchDelete } = useBatchOperation('/api/orders/')
      const request = await import('@/utils/request')

      handleSelectionChange([{ id: 5 }])
      await batchDelete()

      expect(request.default.delete).toHaveBeenCalledWith('/orders/5/')
    })
  })
})
