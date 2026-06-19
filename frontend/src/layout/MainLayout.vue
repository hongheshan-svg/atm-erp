<template>
  <el-container v-if="userStore.profileReady" class="layout-container">
    <el-aside :width="isCollapse ? '64px' : '240px'" class="sidebar">
      <div class="logo" @click="$router.push('/')">
        <div class="logo-icon">
          <svg :width="isCollapse ? 24 : 20" :height="isCollapse ? 24 : 20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="5" y="7" width="14" height="12" rx="2" stroke="currentColor" stroke-width="1.8" fill="none"/>
            <rect x="9" y="3" width="6" height="4" rx="1" stroke="currentColor" stroke-width="1.8" fill="none"/>
            <circle cx="9.5" cy="12" r="1.5" fill="currentColor"/>
            <circle cx="14.5" cy="12" r="1.5" fill="currentColor"/>
            <path d="M10 16h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <path d="M2 11v4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <path d="M22 11v4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
            <path d="M12 1v2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
        </div>
        <transition name="logo-text">
          <span v-if="!isCollapse" class="logo-title">{{ companyShortName || 'ERP' }}</span>
        </transition>
      </div>

      <div class="version-badge-wrap">
        <VersionBadge :collapsed="isCollapse" />
      </div>

      <el-menu
        :default-active="$route.path"
        class="sidebar-menu"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
      >
        <DynamicMenu :menus="permissionStore.menus" />
      </el-menu>

      <div class="sidebar-footer" @click="toggleCollapse">
        <el-icon :size="16">
          <Fold v-if="!isCollapse" />
          <Expand v-else />
        </el-icon>
        <span v-if="!isCollapse" class="collapse-label">收起菜单</span>
      </div>
    </el-aside>

    <el-container class="main-container">
      <el-header class="header" height="56px">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="$route.meta.title">{{ $route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <el-tooltip content="全屏" placement="bottom">
            <el-icon class="header-action" @click="toggleFullscreen"><FullScreen /></el-icon>
          </el-tooltip>
          <el-dropdown @command="handleCommand" trigger="click">
            <div class="user-block">
              <el-avatar :size="30" class="user-avatar">
                {{ (userStore.userInfo?.username || 'U').charAt(0).toUpperCase() }}
              </el-avatar>
              <span class="username">{{ userStore.userInfo?.username || '用户' }}</span>
              <el-icon :size="12"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>个人中心
                </el-dropdown-item>
                <el-dropdown-item command="password">
                  <el-icon><Lock /></el-icon>修改密码
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>

      <el-footer class="footer" height="36px">
        <span>© {{ new Date().getFullYear() }} {{ companyName || '深圳市奥特迈智能装备有限公司' }}</span>
        <span class="version">v{{ appVersion }}</span>
      </el-footer>
    </el-container>
  </el-container>
  <div v-else class="app-loading">
    <div class="app-loading-spinner"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Fold, Expand, User, Lock, SwitchButton, FullScreen, ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'
import { APP_VERSION } from '@/config/version'
import { useCompanyConfig } from '@/stores/companyConfig'
import DynamicMenu from '@/components/DynamicMenu.vue'
import VersionBadge from '@/components/VersionBadge.vue'

const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
const { companyName, companyShortName, loadCompanyConfig } = useCompanyConfig()

const isCollapse = ref(false)
const appVersion = APP_VERSION

const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

const handleCommand = (command) => {
  if (command === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      userStore.logout()
    })
  } else if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'password') {
    router.push('/change-password')
  }
}

onMounted(async () => {
  await loadCompanyConfig()
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
  overflow: hidden;
}

/* ---- Sidebar ---- */
.sidebar {
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  transition: width 0.28s var(--transition);
  border-right: none;
  overflow: hidden;
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  cursor: pointer;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.logo-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--primary);
  border-radius: var(--radius-sm);
  color: #fff;
  flex-shrink: 0;
}

.logo-title {
  font-size: 15px;
  font-weight: 600;
  color: #f1f5f9;
  white-space: nowrap;
  letter-spacing: 0.02em;
}

.logo-text-enter-active,
.logo-text-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.logo-text-enter-from,
.logo-text-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}

/* Sidebar Menu */
.sidebar-menu {
  border-right: none !important;
  background: transparent !important;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 0;
}

.sidebar-menu :deep(.el-menu) {
  background-color: transparent !important;
  border: none !important;
}

.sidebar-menu :deep(.el-menu-item),
.sidebar-menu :deep(.el-sub-menu__title) {
  height: 40px;
  line-height: 40px;
  color: rgba(255, 255, 255, 0.6) !important;
  font-size: 13px;
  margin: 1px 8px;
  border-radius: var(--radius-sm);
  padding-right: 12px !important;
  transition: all 0.2s;
}

.sidebar-menu :deep(.el-menu-item .el-icon),
.sidebar-menu :deep(.el-sub-menu__title .el-icon) {
  font-size: 16px;
  margin-right: 8px;
  width: 16px;
}

.sidebar-menu :deep(.el-menu-item:hover),
.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background-color: rgba(255, 255, 255, 0.06) !important;
  color: #fff !important;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: var(--primary) !important;
  color: #fff !important;
  font-weight: 500;
}

.sidebar-menu :deep(.el-sub-menu.is-opened > .el-sub-menu__title) {
  color: #fff !important;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item) {
  background-color: transparent !important;
  padding-left: 48px !important;
  height: 36px;
  line-height: 36px;
  font-size: 13px;
  margin: 0 8px;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.06) !important;
  color: #fff !important;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item.is-active) {
  background: rgba(67, 97, 238, 0.15) !important;
  color: var(--primary-light) !important;
  font-weight: 500;
}

/* ── 三级菜单：二级分组标题 ── */
.sidebar-menu :deep(.el-sub-menu .el-sub-menu > .el-sub-menu__title) {
  height: 30px;
  line-height: 30px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.38) !important;
  padding-left: 44px !important;
  margin: 6px 8px 2px;
  border-radius: var(--radius-sm);
  font-weight: 600;
  letter-spacing: 0.04em;
}

.sidebar-menu :deep(.el-sub-menu .el-sub-menu > .el-sub-menu__title:hover) {
  color: rgba(255, 255, 255, 0.65) !important;
  background-color: rgba(255, 255, 255, 0.04) !important;
}

.sidebar-menu :deep(.el-sub-menu .el-sub-menu.is-opened > .el-sub-menu__title) {
  color: rgba(255, 255, 255, 0.55) !important;
}

/* ── 三级菜单：叶子项 ── */
.sidebar-menu :deep(.el-sub-menu .el-sub-menu .el-menu-item) {
  padding-left: 56px !important;
  height: 34px;
  line-height: 34px;
  font-size: 13px;
  margin: 0 8px;
}

.sidebar-menu :deep(.el-sub-menu .el-sub-menu .el-menu-item.is-active) {
  background: rgba(67, 97, 238, 0.15) !important;
  color: var(--primary-light) !important;
  font-weight: 500;
}

/* ── 分组箭头图标 ── */
.sidebar-menu :deep(.el-sub-menu .el-sub-menu .el-sub-menu__icon-arrow) {
  color: rgba(255, 255, 255, 0.2);
  font-size: 10px;
}

.sidebar-menu :deep(.el-sub-menu__icon-arrow) {
  color: rgba(255, 255, 255, 0.3);
  font-size: 12px;
}

/* Sidebar scrollbar */
.sidebar-menu::-webkit-scrollbar {
  width: 3px;
}
.sidebar-menu::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}
.sidebar-menu::-webkit-scrollbar-track {
  background: transparent;
}

/* Sidebar collapse toggle */
.sidebar-footer {
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.35);
  font-size: 12px;
  cursor: pointer;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
  transition: color 0.2s;
}
.sidebar-footer:hover {
  color: rgba(255, 255, 255, 0.7);
}
.collapse-label {
  white-space: nowrap;
}

/* ---- Header ---- */
.header {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-action {
  font-size: 18px;
  color: var(--text-muted);
  cursor: pointer;
  padding: 6px;
  border-radius: var(--radius-sm);
  transition: all 0.2s;
}
.header-action:hover {
  color: var(--primary);
  background: #f0f5ff;
}

.user-block {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  transition: background 0.2s;
}
.user-block:hover {
  background: var(--border-light);
}

.user-avatar {
  background: var(--primary) !important;
  color: #fff !important;
  font-size: 13px;
  font-weight: 600;
}

.username {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

/* ---- Main Content ---- */
.main-container {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-content {
  background: var(--bg-page);
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

/* ---- Footer ---- */
.footer {
  background: var(--bg-card);
  border-top: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--text-muted);
  font-size: 11px;
  flex-shrink: 0;
}
.footer .version {
  color: #cbd5e1;
}

/* ---- Page Transition ---- */
.page-enter-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.page-leave-active {
  transition: opacity 0.18s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
}

/* ---- App Loading ---- */
.app-loading {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-page);
}
.app-loading-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
