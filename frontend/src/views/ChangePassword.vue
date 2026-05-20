<template>
  <div class="password-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>修改密码</span>
        </div>
      </template>
      
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        style="max-width: 450px;"
      >
        <el-form-item label="当前密码" prop="old_password">
          <el-input
            v-model="form.old_password"
            type="password"
            placeholder="请输入当前密码"
            show-password
          />
        </el-form-item>
        
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="form.new_password"
            type="password"
            placeholder="请输入新密码（至少6位）"
            show-password
          />
        </el-form-item>
        
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input
            v-model="form.confirm_password"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="loading">
            确认修改
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
      
      <el-divider />
      
      <div class="tips">
        <h4>密码要求：</h4>
        <ul>
          <li>密码长度至少6位</li>
          <li>建议包含字母、数字和特殊字符</li>
          <li>新密码不能与当前密码相同</li>
        </ul>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { changePassword } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== form.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const validateNewPassword = (rule, value, callback) => {
  if (value === form.old_password) {
    callback(new Error('新密码不能与当前密码相同'))
  } else if (value.length < 6) {
    callback(new Error('密码长度至少6位'))
  } else {
    callback()
  }
}

const rules = {
  old_password: [
    { required: true, message: '请输入当前密码', trigger: 'blur' }
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { validator: validateNewPassword, trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const handleSubmit = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await changePassword({
          old_password: form.old_password,
          new_password: form.new_password,
          new_password_confirm: form.confirm_password
        })
        
        ElMessageBox.alert(
          '密码修改成功，请重新登录',
          '提示',
          {
            confirmButtonText: '确定',
            type: 'success',
            callback: () => {
              userStore.logout()
            }
          }
        )
      } catch (error) {
        if (error.response?.data?.old_password) {
          ElMessage.error('当前密码错误')
        } else {
          ElMessage.error(error.response?.data?.detail || '修改失败')
        }
      } finally {
        loading.value = false
      }
    }
  })
}

const handleReset = () => {
  formRef.value?.resetFields()
}
</script>

<style scoped>
.password-container {
  max-width: 600px;
}

.card-header {
  font-size: 16px;
  font-weight: 600;
}

.tips {
  color: #909399;
  font-size: 13px;
}

.tips h4 {
  margin-bottom: 10px;
  color: #606266;
}

.tips ul {
  padding-left: 20px;
  margin: 0;
}

.tips li {
  line-height: 1.8;
}
</style>

