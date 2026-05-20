import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useBatchDelete } from '../useBatchDelete'
import { ElMessage, ElMessageBox } from 'element-plus'

vi.mock('@/utils/request', () => ({
  default: {
    delete: vi.fn().mockResolvedValue({}),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
  }
}))

describe('useBatchDelete', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('initializes with empty selection', () => {
    const { selectedRows, loading } = useBatchDelete('/api/test/')

    expect(selectedRows.value).toEqual([])
    expect(loading.value).toBe(false)
  })

  describe('handleSelectionChange', () => {
    it('updates selectedRows', () => {
      const { selectedRows, handleSelectionChange } = useBatchDelete('/api/test/')

      handleSelectionChange([{ id: 1 }, { id: 2 }])

      expect(selectedRows.value).toHaveLength(2)
    })
  })

  describe('batchDelete', () => {
    it('shows warning if no rows selected', async () => {
      const { batchDelete } = useBatchDelete('/api/test/')

      await batchDelete()

      expect(ElMessage.warning).toHaveBeenCalledWith('请至少选择一条记录')
    })

    it('calls delete API for each selected row', async () => {
      const onSuccess = vi.fn()
      const { handleSelectionChange, batchDelete } = useBatchDelete('/api/test/', { onSuccess })
      const request = await import('@/utils/request')

      handleSelectionChange([{ id: 1 }, { id: 2 }, { id: 3 }])
      await batchDelete()

      expect(request.default.delete).toHaveBeenCalledTimes(3)
      expect(request.default.delete).toHaveBeenCalledWith('/api/test/1/')
      expect(request.default.delete).toHaveBeenCalledWith('/api/test/2/')
      expect(request.default.delete).toHaveBeenCalledWith('/api/test/3/')
      expect(onSuccess).toHaveBeenCalled()
    })

    it('uses custom idField', async () => {
      const { handleSelectionChange, batchDelete } = useBatchDelete('/api/items/', { idField: 'uid' })
      const request = await import('@/utils/request')

      handleSelectionChange([{ uid: 'abc' }, { uid: 'def' }])
      await batchDelete()

      expect(request.default.delete).toHaveBeenCalledWith('/api/items/abc/')
      expect(request.default.delete).toHaveBeenCalledWith('/api/items/def/')
    })

    it('clears selection after successful delete', async () => {
      const { selectedRows, handleSelectionChange, batchDelete } = useBatchDelete('/api/test/')

      handleSelectionChange([{ id: 1 }])
      await batchDelete()

      expect(selectedRows.value).toEqual([])
    })

    it('calls onError when delete fails', async () => {
      const onError = vi.fn()
      const { handleSelectionChange, batchDelete } = useBatchDelete('/api/test/', { onError })
      const request = await import('@/utils/request')
      ;(request.default.delete as any).mockRejectedValue(new Error('Server error'))

      handleSelectionChange([{ id: 1 }])
      await batchDelete()

      expect(onError).toHaveBeenCalled()
      expect(ElMessage.error).toHaveBeenCalled()
    })
  })

  describe('deleteRow', () => {
    it('deletes a single row', async () => {
      const onSuccess = vi.fn()
      const { deleteRow } = useBatchDelete('/api/test/', { onSuccess })
      const request = await import('@/utils/request')
      ;(request.default.delete as any).mockResolvedValue({})

      await deleteRow({ id: 42 })

      expect(request.default.delete).toHaveBeenCalledWith('/api/test/42/')
      expect(onSuccess).toHaveBeenCalled()
    })
  })
})
