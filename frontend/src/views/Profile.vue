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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getUserProfile, updateProfile } from '@/api/auth'

const formRef = ref(null)
const loading = ref(false)

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
</style>

