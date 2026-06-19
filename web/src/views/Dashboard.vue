<script setup lang="ts">
import { useUserStore } from '@/stores/user'
import PageHeader from '@/components/PageHeader.vue'

const userStore = useUserStore()
</script>

<template>
  <div>
    <PageHeader title="工作台" subtitle="ATM-ERP 控制台" />
    <el-card>
      <p>欢迎,{{ userStore.userInfo?.name || userStore.userInfo?.username || '用户' }}。</p>
      <p>这是 Go 重写版前端基座的工作台占位页。</p>
    </el-card>
  </div>
</template>
