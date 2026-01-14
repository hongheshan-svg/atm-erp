/**
 * 权限检查
 * Permission checking composable
 */
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

export function usePermission() {
  const userStore = useUserStore()

  /**
   * 是否是管理员（超级管理员）
   */
  const isAdmin = computed(() => {
    return userStore.userInfo?.is_superuser === true
  })

  /**
   * 是否是员工（有基本操作权限）
   */
  const isStaff = computed(() => {
    return userStore.userInfo?.is_staff === true || isAdmin.value
  })

  /**
   * 是否已登录
   */
  const isAuthenticated = computed(() => {
    return !!userStore.userInfo
  })

  /**
   * 是否有删除权限
   * - 管理员始终有删除权限
   * - 普通用户根据角色权限判断（如果角色有配置权限则检查，否则默认允许）
   */
  const canDelete = computed(() => {
    // 管理员始终可以删除
    if (isAdmin.value) return true
    
    // 已登录用户检查角色权限
    if (isAuthenticated.value) {
      const permissions = userStore.permissions || []
      // 如果有通配符权限
      if (permissions.includes('*:*:*')) return true
      // 如果角色有配置权限，检查是否包含删除权限
      if (permissions.length > 0) {
        return permissions.some(p => p.includes(':delete') || p.includes(':*'))
      }
      // 如果没有配置具体权限，默认允许（由后端控制）
      return true
    }
    
    return false
  })

  /**
   * 是否有编辑权限
   * - 所有已登录用户都有编辑权限
   */
  const canEdit = computed(() => {
    return isAuthenticated.value
  })

  /**
   * 是否有创建权限
   * - 所有已登录用户都有创建权限
   */
  const canCreate = computed(() => {
    return isAuthenticated.value
  })

  /**
   * 是否有查看权限
   * - 所有已登录用户都有查看权限
   */
  const canView = computed(() => {
    return isAuthenticated.value
  })

  /**
   * 检查是否有特定权限
   */
  const hasPermission = (permission) => {
    if (isAdmin.value) return true
    if (!permission) return true
    
    const permissions = userStore.permissions || []
    if (permissions.includes('*:*:*')) return true
    return permissions.includes(permission)
  }

  return {
    isAdmin,
    isStaff,
    isAuthenticated,
    canDelete,
    canEdit,
    canCreate,
    canView,
    hasPermission,
  }
}
