/**
 * 通用批量删除功能
 * Composition API for batch delete operations
 */
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

export function useBatchDelete(apiEndpoint, options = {}) {
  const selectedRows = ref([])
  const loading = ref(false)

  // 配置选项
  const config = {
    confirmTitle: options.confirmTitle || '确认删除',
    confirmMessage: options.confirmMessage || '此操作将永久删除选中的记录，是否继续？',
    successMessage: options.successMessage || '删除成功',
    errorMessage: options.errorMessage || '删除失败',
    idField: options.idField || 'id',
    // 回调函数
    onSuccess: options.onSuccess || (() => {}),
    onError: options.onError || (() => {}),
  }

  /**
   * 处理选择变化
   */
  const handleSelectionChange = (rows) => {
    selectedRows.value = rows
  }

  /**
   * 批量删除
   */
  const batchDelete = async () => {
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
      
      // 批量删除API调用
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

  /**
   * 单条删除
   */
  const deleteRow = async (row) => {
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
