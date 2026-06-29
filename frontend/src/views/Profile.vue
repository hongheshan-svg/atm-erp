<template>
  <div class="profile-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>个人中心</span>
        </div>
      </template>
      
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        style="max-width: 500px;"
      >
        <el-form-item label="用户名">
          <el-input v-model="form.username" disabled />
        </el-form-item>
        
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" />
        </el-form-item>
        
        <el-form-item label="姓名" prop="first_name">
          <el-input v-model="form.first_name" placeholder="请输入姓名" />
        </el-form-item>
        
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
        
        <el-form-item label="部门">
          <el-input :value="form.department_name" disabled />
        </el-form-item>
        
        <el-form-item label="角色">
          <el-tag 
            v-for="role in form.roles" 
            :key="role.id" 
            style="margin-right: 8px;"
          >
            {{ role.name }}
          </el-tag>
          <span v-if="!form.roles?.length" style="color: #909399;">暂无角色</span>
        </el-form-item>
        
        <el-form-item label="注册时间">
          <el-input :value="form.date_joined" disabled />
        </el-form-item>
        
        <el-form-item label="上次登录">
          <el-input :value="form.last_login" disabled />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="handleSave" :loading="loading">
            保存修改
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="enabledBindings.length" shadow="never" class="bind-card">
      <template #header>
        <div class="card-header">企业 IM 绑定</div>
      </template>
      <p class="bind-tip">绑定后即可用企业微信 / 钉钉 / 飞书扫码登录本账号(更安全:由你本人登录后绑定)。</p>
      <div v-for="b in enabledBindings" :key="b.platform" class="bind-row">
        <span class="bind-name">{{ b.name }}</span>
        <el-tag :type="b.bound ? 'success' : 'info'" size="small">{{ b.bound ? '已绑定' : '未绑定' }}</el-tag>
        <el-button
          v-if="b.bound"
          type="danger"
          link
          @click="handleUnbind(b)"
        >
          解绑
        </el-button>
        <el-button
          v-else
          type="primary"
          link
          :loading="bindBusy === b.platform"
          @click="handleBind(b.platform)"
        >
          扫码绑定
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getUserProfile,
  updateProfile,
  getOAuthBindings,
  getOAuthLoginUrl,
  oauthUnbind,
  type OAuthBinding
} from '@/api/auth'

const formRef = ref(null)
const loading = ref(false)

// 企业 IM 绑定(自助:登录后扫码绑定自己的企业微信/钉钉/飞书)
const bindings = ref<OAuthBinding[]>([])
const bindBusy = ref('')
const enabledBindings = computed(() => bindings.value.filter((b) => b.enabled))

async function fetchBindings() {
  try {
    const res: any = await getOAuthBindings()
    bindings.value = Array.isArray(res) ? res : []
  } catch {
    bindings.value = []
  }
}

async function handleBind(platform: string) {
  bindBusy.value = platform
  try {
    const data: any = await getOAuthLoginUrl(platform, 'bind')
    if (data?.auth_url) {
      window.location.href = data.auth_url // 跳授权页 → 回调页(mode=bind)绑定到当前账号
    } else {
      ElMessage.error('获取绑定链接失败')
      bindBusy.value = ''
    }
  } catch {
    bindBusy.value = ''
  }
}

async function handleUnbind(b: OAuthBinding) {
  const ok = await ElMessageBox.confirm(`确认解绑${b.name}?解绑后将无法用该方式扫码登录。`, '提示', {
    type: 'warning'
  })
    .then(() => true)
    .catch(() => false)
  if (!ok) return
  try {
    await oauthUnbind(b.platform)
    ElMessage.success('已解绑')
    await fetchBindings()
  } catch {
    /* 拦截器已提示 */
  }
}

const form = reactive({
  username: '',
  email: '',
  first_name: '',
  phone: '',
  department_name: '',
  roles: [],
  date_joined: '',
  last_login: ''
})

const rules = {
  email: [
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ]
}

const fetchProfile = async () => {
  try {
    const res = await getUserProfile()
    Object.assign(form, res)
  } catch (error) {
    ElMessage.error('获取个人信息失败')
  }
}

const handleSave = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await updateProfile({
          email: form.email,
          first_name: form.first_name,
          phone: form.phone
        })
        ElMessage.success('保存成功')
        await fetchProfile()
      } catch (error) {
        ElMessage.error('保存失败')
      } finally {
        loading.value = false
      }
    }
  })
}

onMounted(() => {
  fetchProfile()
  fetchBindings()
})
</script>

<style scoped>
.profile-container {
  max-width: 800px;
}

.card-header {
  font-size: 16px;
  font-weight: 600;
}

.bind-card {
  margin-top: 16px;
}

.bind-tip {
  color: #909399;
  font-size: 13px;
  margin: 0 0 16px;
}

.bind-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-top: 1px solid var(--el-border-color-lighter);
}

.bind-name {
  width: 80px;
  font-weight: 500;
}
</style>

