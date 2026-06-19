<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'
import { useCompanyConfigStore } from '@/stores/companyConfig'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
const companyConfig = useCompanyConfigStore()

// 菜单定义。permission 为空表示对所有登录用户可见。
interface MenuItem {
  index: string
  title: string
  permission?: string
}

const allMenus: MenuItem[] = [
  { index: '/dashboard', title: '工作台' },
  { index: '/masterdata/items', title: '物料管理', permission: 'masterdata:item:view' }
]

// 按权限裁剪侧边菜单(父码通配由 store 处理)。
const visibleMenus = computed(() =>
  allMenus.filter(m => !m.permission || permissionStore.hasPermission(m.permission))
)

const activeMenu = computed(() => route.path)

const displayName = computed(() => userStore.userInfo?.name || userStore.userInfo?.username || '未登录')

function handleSelect(index: string) {
  router.push(index)
}

async function handleLogout() {
  const confirmed = await ElMessageBox.confirm('确认退出登录?', '提示', { type: 'warning' })
    .then(() => true)
    .catch(() => false)
  if (!confirmed) return
  userStore.logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="210px" class="layout__aside">
      <div class="layout__brand">{{ companyConfig.companyName }}</div>
      <el-menu :default-active="activeMenu" @select="handleSelect">
        <el-menu-item v-for="m in visibleMenus" :key="m.index" :index="m.index">
          {{ m.title }}
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="layout__header">
        <span class="layout__title">{{ (route.meta.title as string) || '' }}</span>
        <el-dropdown @command="handleLogout">
          <span class="layout__user">{{ displayName }}</span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
}

.layout__aside {
  border-right: 1px solid var(--el-border-color);
}

.layout__brand {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  font-size: 16px;
  font-weight: 700;
}

.layout__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color);
}

.layout__title {
  font-size: 16px;
  font-weight: 600;
}

.layout__user {
  cursor: pointer;
  color: var(--el-color-primary);
}
</style>
