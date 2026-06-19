<template>
  <div class="callback-page">
    <el-icon class="spin" :size="40"><Loading /></el-icon>
    <p class="callback-msg">{{ message }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { oauthCallback } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const message = ref('正在登录,请稍候…')

onMounted(async () => {
  const platform = String(route.query.platform || '')
  const code = String(route.query.code || '')
  const state = String(route.query.state || '')

  if (!platform || !code || !state) {
    ElMessage.error('登录参数缺失,请重新扫码')
    router.replace('/login')
    return
  }

  try {
    // request 拦截器已解包为响应体:{ access, refresh, user, is_new_user }
    const data: any = await oauthCallback(platform, { code, state })
    userStore.loginWithOAuthResult(data)
    ElMessage.success(data.is_new_user ? '欢迎,已为你自动创建账号' : '登录成功')
    router.replace('/')
  } catch {
    // 错误提示已由 request.ts 拦截器统一弹出(400 显示后端 detail / 403 等有提示),此处仅回退登录页
    message.value = '登录失败,正在返回…'
    router.replace('/login')
  }
})
</script>

<style scoped>
.callback-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--text-muted, #888);
}
.callback-msg {
  font-size: 14px;
}
.spin {
  color: var(--primary, #4361ee);
  animation: callback-rot 1s linear infinite;
}
@keyframes callback-rot {
  to {
    transform: rotate(360deg);
  }
}
</style>
