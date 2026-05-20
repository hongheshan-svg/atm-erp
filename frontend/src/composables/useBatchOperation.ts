import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

interface BatchOperationOptions {
  confirmTitle?: string
  confirmMessage?: string
  successMessage?: string
  errorMessage?: string
  idField?: string
  onSuccess?: () => void
  onError?: (error: any) => void
}

export function useBatchOperation(apiEndpoint: string, options: BatchOperationOptions = {}) {
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

  const selectedCount = computed(() => selectedRows.value.length)

  const handleSelectionChange = (rows: any[]) => {
    selectedRows.value = rows
  }

  const clearSelection = () => {
    selectedRows.value = []
  }

  const getSelectedIds = (): (string | number)[] => {
    return selectedRows.value.map(row => row[config.idField])
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
        { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
      )
      loading.value = true
      const ids = getSelectedIds()
      await Promise.all(ids.map(id => request.delete(`${apiEndpoint}${id}/`)))
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
      await ElMessageBox.confirm(config.confirmMessage, config.confirmTitle, {
        confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning',
      })
      loading.value = true
      await request.delete(`${apiEndpoint}${row[config.idField]}/`)
      ElMessage.success(config.successMessage)
      config.onSuccess()
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error(config.errorMessage)
        config.onError(error)
      }
    } finally {
      loading.value = false
    }
  }

  const batchExport = (): void => {
    if (selectedRows.value.length === 0) {
      ElMessage.warning('请至少选择一条记录')
      return
    }
    const data = selectedRows.value
    const headers = Object.keys(data[0] || {})
    const csvRows = [headers.join(',')]
    data.forEach(row => {
      csvRows.push(headers.map(h => {
        const val = row[h] == null ? '' : String(row[h]).replace(/,/g, '，')
        return val
      }).join(','))
    })
    const BOM = '﻿'
    const blob = new Blob([BOM + csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `export_${Date.now()}.csv`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出 ${data.length} 条记录`)
  }

  const batchUpdateStatus = async (newStatus: string, statusField = 'status'): Promise<void> => {
    if (selectedRows.value.length === 0) {
      ElMessage.warning('请至少选择一条记录')
      return
    }
    try {
      await ElMessageBox.confirm(
        `确定要将选中的 ${selectedRows.value.length} 条记录更新状态吗？`,
        '确认操作',
        { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
      )
      loading.value = true
      const ids = getSelectedIds()
      await Promise.all(ids.map(id =>
        request.patch(`${apiEndpoint}${id}/`, { [statusField]: newStatus })
      ))
      ElMessage.success(`已更新 ${ids.length} 条记录`)
      selectedRows.value = []
      config.onSuccess()
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error('批量更新失败')
        config.onError(error)
      }
    } finally {
      loading.value = false
    }
  }

  return {
    selectedRows,
    selectedCount,
    loading,
    handleSelectionChange,
    clearSelection,
    getSelectedIds,
    batchDelete,
    deleteRow,
    batchExport,
    batchUpdateStatus,
  }
}
