import { defineStore } from 'pinia'
import { ref } from 'vue'
import { usePermissionStore } from './permission'
import { login as apiLogin, getProfile as apiGetProfile } from '@/api/auth'
import type { UserProfile } from '@/types'

export const useUserStore = defineStore('user', () => {
  const userInfo = ref<UserProfile | null>(null)
  const profileReady = ref(false)

  // 用 profile 回灌权限相关 store(登录/拉档案共用)。
  function applyProfile(profile: UserProfile) {
    userInfo.value = profile
    const permissionStore = usePermissionStore()
    permissionStore.setPermissions(profile.permissions || [])
    permissionStore.setMenus(profile.menus || [])
    permissionStore.setDataScopes(profile.data_scopes || {})
    profileReady.value = true
  }

  async function login(username: string, password: string): Promise<boolean> {
    try {
      const data = await apiLogin(username, password)
      localStorage.setItem('access_token', data.access)
      localStorage.setItem('refresh_token', data.refresh)
      applyProfile(data.user)
      return true
    } catch (error) {
      console.error('登录失败:', error)
      return false
    }
  }

  function logout(): void {
    userInfo.value = null
    profileReady.value = false
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    usePermissionStore().clear()
  }

  async function fetchProfile(): Promise<void> {
    const profile = await apiGetProfile()
    applyProfile(profile)
  }

  return {
    userInfo,
    profileReady,
    login,
    logout,
    fetchProfile,
    applyProfile
  }
})
