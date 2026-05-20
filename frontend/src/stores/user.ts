import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as apiLogin, getUserProfile } from '@/api/auth'
import { usePermissionStore } from './permission'
import router from '@/router'
import type { User } from '@/types'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref<User | null>(null)
  const profileReady = ref(false)

  async function login(username: string, password: string): Promise<boolean> {
    try {
      const response = await apiLogin(username, password)
      const data = response.data || response

      localStorage.setItem('access_token', data.access)
      localStorage.setItem('refresh_token', data.refresh)

      userInfo.value = data.user

      const permissionStore = usePermissionStore()
      permissionStore.setPermissions(data.user.permissions || [])
      permissionStore.setMenus(data.user.menus || [])
      permissionStore.setDataScopes(data.user.data_scopes || {})

      profileReady.value = true
      return true
    } catch (error) {
      console.error('Login failed:', error)
      return false
    }
  }

  function logout(): void {
    userInfo.value = null
    profileReady.value = false
    localStorage.clear()

    const permissionStore = usePermissionStore()
    permissionStore.clear()

    router.push('/login')
  }

  async function getProfile(): Promise<void> {
    const response = await getUserProfile()
    const data = response.data || response
    userInfo.value = data

    const permissionStore = usePermissionStore()
    permissionStore.setPermissions(data.permissions || [])
    permissionStore.setMenus(data.menus || [])
    permissionStore.setDataScopes(data.data_scopes || {})

    profileReady.value = true
  }

  return {
    userInfo,
    profileReady,
    login,
    logout,
    getProfile
  }
})
