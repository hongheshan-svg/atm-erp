<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../session'
import { message } from '../utils/request'
import { View, Hide } from '@element-plus/icons-vue'
import automation from '../assets/login-automation.png'
import { version } from '../../package.json'
const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)
const passwordVisible = ref(false)
async function submit() {
  busy.value = true
  error.value = ''
  try {
    await login(username.value, password.value)
    await router.replace('/workbench')
  } catch (e) {
    error.value = message(e)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <main class="login-page">
    <section class="login-brand" aria-label="项目 ERP">
      <div class="brand"><span class="brand-mark">P</span><div>项目 ERP<small>v{{ version }}</small></div></div>
      <h1>以项目为中心，<br /><span>让协作简单一些</span></h1>
      <p>从需求到交付，协作有序。</p>
      <img :src="automation" alt="自动化装配工作站线稿" width="720" height="460" />
    </section>
    <section class="login-card">
      <h1>欢迎登录</h1>
      <p class="muted">使用管理员分配的账号登录</p>
      <el-alert v-if="route.query.setup === 'complete'" title="首次配置完成，请使用新密码登录。" type="success" :closable="false" />
      <form @submit.prevent="submit">
        <el-alert v-if="error" :title="error" type="error" role="alert" :closable="false" /><label
          class="field"
          ><span>用户名</span><input v-model="username" required autocomplete="username" placeholder="请输入用户名" /></label
        ><label class="field"
          ><span>密码</span
          ><span class="password-control"><input
            v-model="password"
            aria-label="密码"
            required
            :type="passwordVisible ? 'text' : 'password'"
            placeholder="请输入密码"
            autocomplete="current-password" /><button type="button" :aria-label="passwordVisible ? '隐藏密码' : '显示密码'" :aria-pressed="passwordVisible" @click="passwordVisible = !passwordVisible"><el-icon><component :is="passwordVisible ? Hide : View" /></el-icon></button></span></label
        ><el-button type="primary" native-type="submit" :loading="busy">登录</el-button>
      </form>
      <p class="login-help">账号由管理员分配，如需帮助请联系管理员。</p>
    </section>
  </main>
</template>
<style scoped>
.login-page { grid-template-columns: minmax(380px, 47%) 1fr; background: #fff; }
.login-brand { background: #142a3e; color: #fff; align-self: stretch; padding: clamp(32px, 6vw, 86px); display: flex; flex-direction: column; justify-content: flex-start; overflow: hidden; }
.login-brand .brand { padding: 0; font-size: 26px; margin-bottom: 64px; }
.login-brand .brand-mark { width: 60px; height: 60px; font-size: 34px; }
.login-brand h1 { font-size: clamp(30px, 4.2vw, 64px); line-height: 1.35; letter-spacing: 0; }
.login-brand h1 span { color: #a9cff8; }
.login-brand > p { color: #bfd0e3; font-size: 18px; }
.login-brand img { display: block; width: calc(100% + 160px); height: auto; margin: 20px -80px -20px; mix-blend-mode: lighten; mask-image: radial-gradient(ellipse 60% 60%, #000 60%, transparent 100%); }
.login-card { width: min(460px, 80%); border: 0; padding: 24px 0; border-radius: 0; box-shadow: none; }
.login-card h1 { font-size: clamp(34px, 3.3vw, 50px); }
.login-card > .muted { font-size: 16px; margin-bottom: 48px; }
.login-card .field { margin: 28px 0; font-size: 15px; gap: 12px; }
.login-card input { min-height: 56px; }
.login-card form > .el-button { height: 56px; font-size: 18px; }
.login-help { margin-top: 22px; text-align: center; font-size: 13px; color: #64748b; line-height: 1.8; }
.password-control { position: relative; display: block; }
.password-control input { padding-right: 48px; }
.password-control button { position: absolute; right: 4px; top: 8px; width: 40px; height: 40px; border: 0; background: transparent; color: #64748b; cursor: pointer; }
@media (max-width: 760px) {
  .login-page { display: flex; flex-direction: column; }
  .login-brand { padding: 24px; width: 100%; }
  .login-brand .brand { margin-bottom: 18px; font-size: 20px; }
  .login-brand .brand-mark { width: 40px; height: 40px; font-size: 26px; }
  .login-brand h1 { font-size: 24px; }
  .login-brand > p { font-size: 14px; margin-bottom: 0; }
  .login-brand img { display: none; }
  .login-card { width: min(460px, calc(100% - 48px)); margin: 12px auto; }
  .login-card h1 { font-size: 28px; }
  .login-card > .muted { margin-bottom: 24px; }
}
</style>
