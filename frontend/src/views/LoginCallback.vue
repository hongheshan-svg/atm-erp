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
import { oauthBind, oauthCallback } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isBind = String(route.query.mode || '') === 'bind'
const message = ref(isBind ? '正在绑定企业 IM,请稍候…' : '正在登录,请稍候…')

onMounted(async () => {
  const platform = String(route.query.platform || '')
  const code = String(route.query.code || '')
  const state = String(route.query.state || '')

  if (!platform || !code || !state) {
    ElMessage.error('参数缺失,请重新扫码')
    router.replace(isBind ? '/profile' : '/login')
    return
  }

  try {
    if (isBind) {
      // 鉴权态自助绑定:当前已登录用户把自己的 IM 身份绑定到本账号
      await oauthBind(platform, { code, state })
      ElMessage.success('企业 IM 绑定成功')
      router.replace('/profile')
      return
    }
    // 登录:request 拦截器已解包为响应体 { access, refresh, user, is_new_user }
    const data: any = await oauthCallback(platform, { code, state })
    userStore.loginWithOAuthResult(data)
    ElMessage.success(data.is_new_user ? '欢迎,已为你自动创建账号' : '登录成功')
    router.replace('/')
  } catch {
    // 错误提示已由 request.ts 拦截器统一弹出;此处仅回退
    message.value = isBind ? '绑定失败,正在返回…' : '登录失败,正在返回…'
    router.replace(isBind ? '/profile' : '/login')
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
