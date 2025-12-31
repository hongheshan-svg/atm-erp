<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <h1>ERP管理系统</h1>
        <p>企业资源计划 · 项目管理 · 进销存 · 成本管控</p>
      </div>
      
      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        class="login-form"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="用户名"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="login-button"
            :loading="loading"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </div>
    
    <div class="login-footer">
      Copyright © {{ new Date().getFullYear() }} 深圳市奥特迈智能装备有限公司 版权所有
      <span class="version">v{{ appVersion }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { APP_VERSION } from '@/config/version'

const router = useRouter()
const userStore = useUserStore()
const appVersion = APP_VERSION

const loginFormRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

// 页面加载时读取上次的用户名
onMounted(() => {
  const lastUsername = localStorage.getItem('last_username')
  if (lastUsername) {
    loginForm.username = lastUsername
  }
})

const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        const success = await userStore.login(loginForm.username, loginForm.password)
        
        if (success) {
          // 登录成功后保存用户名
          localStorage.setItem('last_username', loginForm.username)
          ElMessage.success('登录成功')
          router.push('/')
        } else {
          ElMessage.error('用户名或密码错误')
        }
      } catch (error) {
        ElMessage.error('登录失败，请稍后再试')
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
  position: relative;
}

.login-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 50%;
  background: linear-gradient(135deg, #304156 0%, #409eff 100%);
  clip-path: polygon(0 0, 100% 0, 100% 70%, 0 100%);
}

.login-box {
  width: 420px;
  padding: 40px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  position: relative;
  z-index: 1;
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-header h1 {
  font-size: 26px;
  color: #303133;
  margin-bottom: 10px;
  font-weight: 600;
}

.login-header p {
  color: #909399;
  font-size: 13px;
}

.login-form {
  margin-top: 20px;
}

.login-button {
  width: 100%;
}

.login-footer {
  position: absolute;
  bottom: 20px;
  left: 0;
  right: 0;
  text-align: center;
  color: #909399;
  font-size: 12px;
  z-index: 1;
}

.login-footer .version {
  margin-left: 15px;
  color: #c0c4cc;
  font-size: 11px;
}
</style>

