import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

interface BatchDeleteOptions {
  confirmTitle?: string
  confirmMessage?: string
  successMessage?: string
  errorMessage?: string
  idField?: string
  onSuccess?: () => void
  onError?: (error: any) => void
}

export function useBatchDelete(apiEndpoint: string, options: BatchDeleteOptions = {}) {
  const selectedRows = ref<any[]>([])
  const loading = ref(false)

  const config = {
    confirmTitle: options.confirmTitle || '确认删除',
    confirmMessage: options.confirmMessage || '此操作将永久删除选中的记录，是否继续？',
    successMessage: options.successMessage || '删除成功',
    errorMessage: options.errorMessage || '删除失败',
    idField: options.idField || 'id',
    onSuccess: options.onSuccess || (() => {}),
    onError: options.onError || (() => {}),
  }

  const handleSelectionChange = (rows: any[]) => {
    selectedRows.value = rows
  }

  const batchDelete = async (): Promise<void> => {
    if (selectedRows.value.length === 0) {
      ElMessage.warning('请至少选择一条记录')
      return
    }

    try {
      await ElMessageBox.confirm(
        `${config.confirmMessage}（已选择 ${selectedRows.value.length} 条记录）`,
        config.confirmTitle,
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )

      loading.value = true
      const ids = selectedRows.value.map(row => row[config.idField])

      const deletePromises = ids.map(id =>
        request.delete(`${apiEndpoint}${id}/`)
      )

      await Promise.all(deletePromises)

      ElMessage.success(`${config.successMessage}（共 ${ids.length} 条）`)
      selectedRows.value = []
      config.onSuccess()
    } catch (error) {
      if (error !== 'cancel') {
        console.error('批量删除失败:', error)
        ElMessage.error(config.errorMessage)
        config.onError(error)
      }
    } finally {
      loading.value = false
    }
  }

  const deleteRow = async (row: any): Promise<void> => {
    try {
      await ElMessageBox.confirm(
        config.confirmMessage,
        config.confirmTitle,
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )

      loading.value = true
      await request.delete(`${apiEndpoint}${row[config.idField]}/`)

      ElMessage.success(config.successMessage)
      config.onSuccess()
    } catch (error) {
      if (error !== 'cancel') {
        console.error('删除失败:', error)
        ElMessage.error(config.errorMessage)
        config.onError(error)
      }
    } finally {
      loading.value = false
    }
  }

  return {
    selectedRows,
    loading,
    handleSelectionChange,
    batchDelete,
    deleteRow,
  }
}
