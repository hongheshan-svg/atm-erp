<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../session'
import { message } from '../utils/request'
const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)
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
    <section class="login-card">
      <div class="brand-mark">P</div>
      <h1>项目 ERP</h1>
      <p class="muted">连接需求、采购、交付与售后</p>
      <el-alert v-if="route.query.setup === 'complete'" title="首次配置完成，请使用新密码登录。" type="success" :closable="false" />
      <form @submit.prevent="submit">
        <el-alert v-if="error" :title="error" type="error" role="alert" :closable="false" /><label
          class="field"
          ><span>用户名</span><input v-model="username" required autocomplete="username" /></label
        ><label class="field"
          ><span>密码</span
          ><input
            v-model="password"
            required
            type="password"
            autocomplete="current-password" /></label
        ><el-button type="primary" native-type="submit" :loading="busy">登录</el-button>
      </form>
    </section>
  </main>
</template>
