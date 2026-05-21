import { computed } from 'vue'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'

export function usePermission() {
  const userStore = useUserStore()
  const permissionStore = usePermissionStore()

  const isAdmin = computed(() => {
    return userStore.userInfo?.is_superuser === true
  })

  const isStaff = computed(() => {
    return userStore.userInfo?.is_staff === true || isAdmin.value
  })

  const isAuthenticated = computed(() => {
    return !!userStore.userInfo
  })

  const canDelete = computed(() => {
    if (isAdmin.value) return true
    if (!isAuthenticated.value) return false
    for (const perm of permissionStore.permissions) {
      if (perm.endsWith(':delete') || perm === '*') return true
    }
    return false
  })

  const canEdit = computed(() => {
    if (isAdmin.value) return true
    if (!isAuthenticated.value) return false
    for (const perm of permissionStore.permissions) {
      if (perm.endsWith(':edit') || perm === '*') return true
    }
    return false
  })

  const canCreate = computed(() => {
    if (isAdmin.value) return true
    if (!isAuthenticated.value) return false
    for (const perm of permissionStore.permissions) {
      if (perm.endsWith(':create') || perm === '*') return true
    }
    return false
  })

  const canView = computed(() => isAuthenticated.value)

  const hasPermission = (permission: string): boolean => {
    if (isAdmin.value) return true
    if (!permission) return true
    return permissionStore.hasPermission(permission)
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
