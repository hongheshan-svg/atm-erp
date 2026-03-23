<template>
  <div class="login-page">
    <div class="login-left">
      <div class="brand-area">
        <div class="brand-icon">
          <el-icon :size="36"><Cpu /></el-icon>
        </div>
        <h1 class="brand-title">{{ companyName || 'ERP管理系统' }}</h1>
        <p class="brand-desc">非标自动化 · 项目管理 · 供应链 · 智能制造</p>
        <div class="feature-list">
          <div class="feature-item">
            <el-icon><Folder /></el-icon>
            <span>项目全生命周期管理</span>
          </div>
          <div class="feature-item">
            <el-icon><DataAnalysis /></el-icon>
            <span>BOM · 采购 · 生产一体化</span>
          </div>
          <div class="feature-item">
            <el-icon><TrendCharts /></el-icon>
            <span>实时成本与利润分析</span>
          </div>
        </div>
      </div>
    </div>

    <div class="login-right">
      <div class="login-form-wrapper">
        <h2 class="form-title">登录</h2>
        <p class="form-subtitle">欢迎回来，请输入您的账号信息</p>

        <el-form
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          class="login-form"
          @keyup.enter="handleLogin"
          size="large"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="用户名"
              :prefix-icon="User"
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="密码"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              class="login-btn"
              :loading="loading"
              @click="handleLogin"
            >
              {{ loading ? '登录中...' : '登 录' }}
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <div class="login-footer">
        © {{ new Date().getFullYear() }} {{ companyName || '深圳市奥特迈智能装备有限公司' }}
        <span class="version">v{{ appVersion }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Cpu, Folder, DataAnalysis, TrendCharts } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { APP_VERSION } from '@/config/version'
import { useCompanyConfig } from '@/stores/companyConfig'

const router = useRouter()
const userStore = useUserStore()
const appVersion = APP_VERSION
const { companyName, loadCompanyConfig } = useCompanyConfig()

const loginFormRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

onMounted(async () => {
  const lastUsername = localStorage.getItem('last_username')
  if (lastUsername) {
    loginForm.username = lastUsername
  }
  await loadCompanyConfig()
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
.login-page {
  min-height: 100vh;
  display: flex;
}

/* ---- Left Panel ---- */
.login-left {
  flex: 1;
  background: linear-gradient(135deg, var(--bg-sidebar) 0%, #1a365d 50%, var(--primary) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px;
  position: relative;
  overflow: hidden;
}

.login-left::before {
  content: '';
  position: absolute;
  width: 400px;
  height: 400px;
  border-radius: 50%;
  background: rgba(67, 97, 238, 0.12);
  top: -100px;
  right: -100px;
}

.login-left::after {
  content: '';
  position: absolute;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: rgba(6, 214, 160, 0.08);
  bottom: -80px;
  left: -60px;
}

.brand-area {
  position: relative;
  z-index: 1;
  max-width: 400px;
}

.brand-icon {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  color: #fff;
  margin-bottom: 28px;
  backdrop-filter: blur(8px);
}

.brand-title {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 12px;
  letter-spacing: 0.01em;
}

.brand-desc {
  font-size: 15px;
  color: rgba(255, 255, 255, 0.6);
  margin-bottom: 48px;
  line-height: 1.6;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 14px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
}

.feature-item .el-icon {
  font-size: 20px;
  color: var(--accent);
}

/* ---- Right Panel ---- */
.login-right {
  width: 480px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  background: #fff;
}

.login-form-wrapper {
  width: 100%;
  max-width: 360px;
}

.form-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.form-subtitle {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 36px;
}

.login-form :deep(.el-input__wrapper) {
  border-radius: var(--radius-sm);
  padding: 4px 12px;
  box-shadow: 0 0 0 1px var(--border) inset !important;
  transition: box-shadow 0.2s;
}

.login-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #b4c4d9 inset !important;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px var(--primary) inset !important;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  border-radius: var(--radius-sm);
  letter-spacing: 0.05em;
  margin-top: 8px;
}

.login-footer {
  position: absolute;
  bottom: 24px;
  font-size: 11px;
  color: var(--text-muted);
}

.login-footer .version {
  margin-left: 12px;
  color: #cbd5e1;
}

/* ---- Responsive ---- */
@media (max-width: 900px) {
  .login-left {
    display: none;
  }
  .login-right {
    width: 100%;
  }
}
</style>
