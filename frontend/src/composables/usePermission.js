/**
 * 权限检查
 * Permission checking composable
 */
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

export function usePermission() {
  const userStore = useUserStore()

  /**
   * 是否是管理员
   */
  const isAdmin = computed(() => {
    return userStore.userInfo?.is_superuser === true || 
           userStore.userInfo?.is_staff === true
  })

  /**
   * 是否有删除权限
   */
  const canDelete = computed(() => {
    return isAdmin.value
  })

  /**
   * 是否有编辑权限
   */
  const canEdit = computed(() => {
    return isAdmin.value
  })

  /**
   * 检查是否有特定权限
   */
  const hasPermission = (permission) => {
    if (isAdmin.value) return true
    
    const permissions = userStore.userInfo?.permissions || []
    return permissions.includes(permission)
  }

  return {
    isAdmin,
    canDelete,
    canEdit,
    hasPermission,
  }
}
