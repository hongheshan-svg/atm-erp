import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePermissionStore } from '../permission'

describe('usePermissionStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('setPermissions', () => {
    it('stores permissions as a Set', () => {
      const store = usePermissionStore()
      store.setPermissions(['purchase:order:view', 'purchase:order:edit'])

      expect(store.permissions.has('purchase:order:view')).toBe(true)
      expect(store.permissions.has('purchase:order:edit')).toBe(true)
    })

    it('replaces previous permissions', () => {
      const store = usePermissionStore()
      store.setPermissions(['old:perm'])
      store.setPermissions(['new:perm'])

      expect(store.permissions.has('old:perm')).toBe(false)
      expect(store.permissions.has('new:perm')).toBe(true)
    })
  })

  describe('setMenus', () => {
    it('stores menu list', () => {
      const store = usePermissionStore()
      store.setMenus(['purchase', 'sales', 'inventory'])

      expect(store.menus).toEqual(['purchase', 'sales', 'inventory'])
    })
  })

  describe('setDataScopes', () => {
    it('normalizes data scope values', () => {
      const store = usePermissionStore()
      store.setDataScopes({
        purchase: 'ALL',
        sales: 'DEPARTMENT',
        finance: 'SELF',
      })

      expect(store.dataScopes.purchase).toBe('all')
      expect(store.dataScopes.sales).toBe('dept_tree')
      expect(store.dataScopes.finance).toBe('self')
    })

    it('handles null scopes', () => {
      const store = usePermissionStore()
      store.setDataScopes(null as any)

      expect(store.dataScopes).toEqual({})
    })
  })

  describe('hasPermission', () => {
    it('returns true for exact match', () => {
      const store = usePermissionStore()
      store.setPermissions(['purchase:order:view'])

      expect(store.hasPermission('purchase:order:view')).toBe(true)
    })

    it('returns false for no match', () => {
      const store = usePermissionStore()
      store.setPermissions(['purchase:order:view'])

      expect(store.hasPermission('sales:order:view')).toBe(false)
    })

    it('returns true for wildcard *', () => {
      const store = usePermissionStore()
      store.setPermissions(['*'])

      expect(store.hasPermission('any:permission:here')).toBe(true)
    })

    it('returns true for parent permission (hierarchical)', () => {
      const store = usePermissionStore()
      store.setPermissions(['purchase:order'])

      expect(store.hasPermission('purchase:order:view')).toBe(true)
      expect(store.hasPermission('purchase:order:edit')).toBe(true)
      expect(store.hasPermission('purchase:order:delete')).toBe(true)
    })

    it('does not match sibling permissions', () => {
      const store = usePermissionStore()
      store.setPermissions(['purchase:order:view'])

      expect(store.hasPermission('purchase:order:edit')).toBe(false)
    })

    it('parent purchase matches purchase:order:view', () => {
      const store = usePermissionStore()
      store.setPermissions(['purchase'])

      expect(store.hasPermission('purchase:order:view')).toBe(true)
    })
  })

  describe('clear', () => {
    it('clears all state', () => {
      const store = usePermissionStore()
      store.setPermissions(['test'])
      store.setMenus(['menu1'])
      store.setDataScopes({ mod: 'all' })

      store.clear()

      expect(store.permissions.size).toBe(0)
      expect(store.menus).toEqual([])
      expect(store.dataScopes).toEqual({})
    })
  })
})
