import { defineStore } from 'pinia'

const normalizeDataScope = (scope: string): string => {
  const normalized: Record<string, string> = {
    ALL: 'all',
    all: 'all',
    GLOBAL: 'all',
    global: 'all',
    DEPARTMENT: 'dept_tree',
    department_and_below: 'dept_tree',
    DEPT_TREE: 'dept_tree',
    dept_tree: 'dept_tree',
    DEPT: 'dept',
    dept: 'dept',
    department: 'dept',
    SELF: 'self',
    self: 'self',
    CUSTOM: 'custom',
    custom: 'custom'
  }

  return normalized[scope] || scope
}

export const usePermissionStore = defineStore('permission', {
  state: () => ({
    permissions: new Set<string>(),
    menus: [] as string[],
    dataScopes: {} as Record<string, string>
  }),

  actions: {
    setPermissions(perms: string[]) {
      this.permissions = new Set(perms)
    },

    setMenus(menus: string[]) {
      this.menus = menus
    },

    setDataScopes(scopes: Record<string, string>) {
      this.dataScopes = Object.fromEntries(
        Object.entries(scopes || {}).map(([module, scope]) => [module, normalizeDataScope(scope)])
      )
    },

    hasPermission(code: string): boolean {
      if (this.permissions.has('*')) return true
      if (this.permissions.has(code)) return true

      const parts = code.split(':')
      for (let i = parts.length - 1; i > 0; i--) {
        const parentCode = parts.slice(0, i).join(':')
        if (this.permissions.has(parentCode)) return true
      }

      return false
    },

    clear() {
      this.permissions.clear()
      this.menus = []
      this.dataScopes = {}
    }
  }
})
