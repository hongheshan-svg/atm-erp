import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as apiLogin, getUserProfile } from '@/api/auth'
import { usePermissionStore } from './permission'
import router from '@/router'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref(null)

  // Login
  async function login(username, password) {
    try {
      const response = await apiLogin(username, password)
      const data = response.data || response

      localStorage.setItem('access_token', data.access)
      localStorage.setItem('refresh_token', data.refresh)

      userInfo.value = data.user

      // 设置权限数据到 Permission Store
      const permissionStore = usePermissionStore()
      permissionStore.setPermissions(data.user.permissions || [])
      permissionStore.setMenus(data.user.menus || [])
      permissionStore.setDataScopes(data.user.data_scopes || {})

      return true
    } catch (error) {
      console.error('Login failed:', error)
      return false
    }
  }

  // Logout
  function logout() {
    userInfo.value = null
    localStorage.clear()

    const permissionStore = usePermissionStore()
    permissionStore.clear()

    router.push('/login')
  }

  // Get user profile
  async function getProfile() {
    try {
      const response = await getUserProfile()
      const data = response.data || response
      userInfo.value = data

      // 设置权限数据到 Permission Store
      const permissionStore = usePermissionStore()
      permissionStore.setPermissions(data.permissions || [])
      permissionStore.setMenus(data.menus || [])
      permissionStore.setDataScopes(data.data_scopes || {})
    } catch (error) {
      console.error('Get profile failed:', error)
      logout()
    }
  }

  return {
    userInfo,
    login,
    logout,
    getProfile
  }
})

