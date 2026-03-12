import { defineStore } from 'pinia'

export const usePermissionStore = defineStore('permission', {
  state: () => ({
    permissions: new Set(),
    menus: [],
    dataScopes: {}
  }),

  actions: {
    setPermissions(perms) {
      this.permissions = new Set(perms)
    },

    setMenus(menus) {
      this.menus = menus
    },

    setDataScopes(scopes) {
      this.dataScopes = scopes
    },

    hasPermission(code) {
      if (this.permissions.has('*')) return true
      if (this.permissions.has(code)) return true

      // 父节点匹配：拥有 'purchase:order' 则自动拥有 'purchase:order:view'
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
