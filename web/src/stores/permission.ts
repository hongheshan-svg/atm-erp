import { defineStore } from 'pinia'

// 数据范围标准化:后端可能返回多种大小写/枚举,统一为前端约定值。
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

interface PermissionState {
  permissions: Set<string>
  menus: string[]
  dataScopes: Record<string, string>
  // 用于在 hasPermission 计算中建立响应式依赖(Set 变更不被深度追踪)。
  _version: number
}

export const usePermissionStore = defineStore('permission', {
  state: (): PermissionState => ({
    permissions: new Set<string>(),
    menus: [],
    dataScopes: {},
    _version: 0
  }),

  actions: {
    setPermissions(perms: string[]) {
      this.permissions = new Set(perms)
      this._version++
    },

    setMenus(menus: string[]) {
      this.menus = menus
    },

    setDataScopes(scopes: Record<string, string>) {
      this.dataScopes = Object.fromEntries(
        Object.entries(scopes || {}).map(([module, scope]) => [module, normalizeDataScope(scope)])
      )
    },

    // 权限判断:* 通配 -> 精确命中 -> 父码通配(a:b:c -> a:b -> a)。
    hasPermission(code: string): boolean {
      void this._version
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
      this.permissions = new Set<string>()
      this.menus = []
      this.dataScopes = {}
      this._version++
    }
  }
})
