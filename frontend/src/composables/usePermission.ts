import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

export function usePermission() {
  const userStore = useUserStore()

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

    if (isAuthenticated.value) {
      const permissions = (userStore.userInfo as any)?.permissions || []
      if (permissions.includes('*:*:*')) return true
      if (permissions.length > 0) {
        return permissions.some((p: string) => p.includes(':delete') || p.includes(':*'))
      }
      return true
    }

    return false
  })

  const canEdit = computed(() => {
    return isAuthenticated.value
  })

  const canCreate = computed(() => {
    return isAuthenticated.value
  })

  const canView = computed(() => {
    return isAuthenticated.value
  })

  const hasPermission = (permission: string): boolean => {
    if (isAdmin.value) return true
    if (!permission) return true

    const permissions = (userStore.userInfo as any)?.permissions || []
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
