<script setup lang="ts">
import { computed, watch } from 'vue'
import { ElConfigProvider } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { useRoute, useRouter } from 'vue-router'
import { user, logout } from './session'
import { navigation } from './navigation'
const route = useRoute()
const router = useRouter()
const currentModule = computed(() => navigation().find(item => route.path.startsWith('/' + item.key))?.label || '工作台')
watch(user, (value) => {
  if (!value && route.path !== '/login') void router.replace('/login')
})
</script>
<template>
  <ElConfigProvider :locale="zhCn">
    <router-view v-if="route.path === '/login'" />
    <div v-else class="shell">
      <aside class="sidebar">
        <div class="brand">
          <span class="brand-mark">P</span>
          <div>项目 ERP<small>从需求到交付</small></div>
        </div>
        <nav aria-label="主导航">
          <router-link
            v-for="item in navigation()"
            :key="item.key"
            :to="'/' + item.key"
            :class="{ selected: route.path.startsWith('/' + item.key) }"
            ><el-icon><component :is="item.icon" /></el-icon>{{ item.label }}</router-link
          >
        </nav>
        <div class="sidebar-note">以项目为中心<br />让协作简单一些</div>
      </aside>
      <main>
        <header class="topbar">
          <div class="breadcrumb"><span>工作空间</span><span aria-hidden="true">/</span><strong>{{ currentModule }}</strong></div>
          <div class="account-menu">
            <span class="account-avatar" aria-hidden="true">{{ (user?.display_name || user?.username || 'P').slice(0, 1).toUpperCase() }}</span>
            <span class="account-name">{{ user?.display_name || user?.username }}</span><el-button text @click="logout">退出登录</el-button>
          </div>
        </header>
        <div class="content"><router-view :key="route.path" /></div>
      </main>
    </div>
  </ElConfigProvider>
</template>
