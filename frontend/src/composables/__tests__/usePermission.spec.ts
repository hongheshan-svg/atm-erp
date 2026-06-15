import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePermission } from '../usePermission'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'

describe('usePermission', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('isAdmin', () => {
    it('returns true for superuser', () => {
      const userStore = useUserStore()
      userStore.userInfo = { is_superuser: true, is_staff: true } as any

      const { isAdmin } = usePermission()
      expect(isAdmin.value).toBe(true)
    })

    it('returns false for non-superuser', () => {
      const userStore = useUserStore()
      userStore.userInfo = { is_superuser: false, is_staff: true } as any

      const { isAdmin } = usePermission()
      expect(isAdmin.value).toBe(false)
    })

    it('returns false when no user', () => {
      const { isAdmin } = usePermission()
      expect(isAdmin.value).toBe(false)
    })
  })

  describe('isStaff', () => {
    it('returns true for staff users', () => {
      const userStore = useUserStore()
      userStore.userInfo = { is_superuser: false, is_staff: true } as any

      const { isStaff } = usePermission()
      expect(isStaff.value).toBe(true)
    })

    it('returns true for admin even if not staff', () => {
      const userStore = useUserStore()
      userStore.userInfo = { is_superuser: true, is_staff: false } as any

      const { isStaff } = usePermission()
      expect(isStaff.value).toBe(true)
    })
  })

  describe('isAuthenticated', () => {
    it('returns true when user info exists', () => {
      const userStore = useUserStore()
      userStore.userInfo = { id: 1 } as any

      const { isAuthenticated } = usePermission()
      expect(isAuthenticated.value).toBe(true)
    })

    it('returns false when no user info', () => {
      const { isAuthenticated } = usePermission()
      expect(isAuthenticated.value).toBe(false)
    })
  })

  describe('hasPermission', () => {
    it('returns true for admin regardless of permission', () => {
      const userStore = useUserStore()
      userStore.userInfo = { is_superuser: true } as any

      const { hasPermission } = usePermission()
      expect(hasPermission('any:permission')).toBe(true)
    })

    it('returns true for empty permission string', () => {
      const userStore = useUserStore()
      userStore.userInfo = { is_superuser: false, permissions: [] } as any

      const { hasPermission } = usePermission()
      expect(hasPermission('')).toBe(true)
    })

    it('returns true for wildcard user', () => {
      const userStore = useUserStore()
      userStore.userInfo = { is_superuser: false } as any
      // permissions live in the permission store (seeded via setPermissions),
      // not on userInfo. '*' is the canonical full-access token.
      usePermissionStore().setPermissions(['*'])

      const { hasPermission } = usePermission()
      expect(hasPermission('purchase:order:view')).toBe(true)
    })

    it('returns true for exact match', () => {
      const userStore = useUserStore()
      userStore.userInfo = { is_superuser: false } as any
      usePermissionStore().setPermissions(['purchase:order:view'])

      const { hasPermission } = usePermission()
      expect(hasPermission('purchase:order:view')).toBe(true)
    })

    it('returns false for non-matching permission', () => {
      const userStore = useUserStore()
      userStore.userInfo = { is_superuser: false } as any
      usePermissionStore().setPermissions(['purchase:order:view'])

      const { hasPermission } = usePermission()
      expect(hasPermission('sales:order:view')).toBe(false)
    })
  })

  describe('canDelete', () => {
    it('returns true for admin', () => {
      const userStore = useUserStore()
      userStore.userInfo = { is_superuser: true } as any

      const { canDelete } = usePermission()
      expect(canDelete.value).toBe(true)
    })

    it('returns true when user has delete permission', () => {
      const userStore = useUserStore()
      userStore.userInfo = { is_superuser: false } as any
      // canDelete scans the permission store for a ':delete' permission
      usePermissionStore().setPermissions(['purchase:order:delete'])

      const { canDelete } = usePermission()
      expect(canDelete.value).toBe(true)
    })

    it('returns false when not authenticated', () => {
      const { canDelete } = usePermission()
      expect(canDelete.value).toBe(false)
    })
  })
})
