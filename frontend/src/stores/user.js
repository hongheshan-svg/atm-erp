import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as apiLogin, getUserProfile } from '@/api/auth'
import router from '@/router'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref(null)
  const permissions = ref([])
  const menuIds = ref([])

  // Login
  async function login(username, password) {
    try {
      const response = await apiLogin(username, password)
      const data = response.data || response  // 兼容两种返回格式
      
      localStorage.setItem('access_token', data.access)
      localStorage.setItem('refresh_token', data.refresh)
      
      userInfo.value = data.user
      permissions.value = data.user.permissions || []
      menuIds.value = data.user.menu_ids || []
      
      return true
    } catch (error) {
      console.error('Login failed:', error)
      return false
    }
  }

  // Logout
  function logout() {
    userInfo.value = null
    permissions.value = []
    menuIds.value = []
    localStorage.clear()
    router.push('/login')
  }

  // Get user profile
  async function getProfile() {
    try {
      const response = await getUserProfile()
      const data = response.data || response  // 兼容两种返回格式
      userInfo.value = data
      permissions.value = data.permissions || []
      menuIds.value = data.menu_ids || []
    } catch (error) {
      console.error('Get profile failed:', error)
      logout()
    }
  }

  // Check permission
  function hasPermission(permission) {
    if (!permission) return true
    if (permissions.value.includes('*:*:*')) return true
    return permissions.value.includes(permission)
  }

  // Check menu access
  function hasMenu(menuId) {
    if (!menuId) return true
    // 超级管理员有所有权限
    if (userInfo.value?.is_superuser) return true
    // 如果有通配符权限
    if (permissions.value?.includes('*:*:*')) return true
    // 如果没有配置菜单权限，则无权限访问
    if (!menuIds.value || menuIds.value.length === 0) return false
    return menuIds.value.includes(menuId)
  }

  return {
    userInfo,
    permissions,
    menuIds,
    login,
    logout,
    getProfile,
    hasPermission,
    hasMenu
  }
})

