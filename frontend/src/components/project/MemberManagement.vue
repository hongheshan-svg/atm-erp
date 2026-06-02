<template>
  <div class="member-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>项目成员</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            添加成员
          </el-button>
        </div>
      </template>

      <el-table :data="memberList" v-loading="loading" border>
        <el-table-column prop="user_name" label="成员姓名" width="120" />
        <el-table-column prop="user_email" label="邮箱" width="200" />
        <el-table-column prop="role" label="项目角色" width="150" />
        <el-table-column prop="hourly_rate" label="时薪（元/小时）" width="130" align="right">
          <template #default="{ row }">
            ¥{{ toFixedSafe(row.hourly_rate) }}
          </template>
        </el-table-column>
        <el-table-column prop="allocated_hours" label="分配工时" width="100" align="right">
          <template #default="{ row }">
            {{ row.allocated_hours || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="actual_hours" label="实际工时" width="100" align="right">
          <template #default="{ row }">
            {{ row.actual_hours || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '活跃' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 20px;">
        <el-statistic title="总分配工时" :value="totalAllocatedHours" suffix="小时" />
        <el-statistic title="总实际工时" :value="totalActualHours" suffix="小时" style="margin-top: 10px;" />
        <el-statistic
          title="预计人工成本"
          :value="estimatedLaborCost"
          prefix="¥"
          :precision="2"
          style="margin-top: 10px;"
        />
      </div>
    </el-card>

    <!-- 成员编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
      @close="resetForm"
    >
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="成员" prop="user">
          <el-select
            v-model="formData.user"
            placeholder="请选择成员"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="user in userOptions"
              :key="user.id"
              :label="`${user.username} - ${user.first_name}${user.last_name}`"
              :value="user.id"
            >
              <div style="display: flex; justify-content: space-between;">
                <span>{{ user.username }} - {{ user.first_name }}{{ user.last_name }}</span>
                <span style="color: #8492a6; font-size: 13px">{{ user.department_name }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="项目角色" prop="role">
          <el-input v-model="formData.role" placeholder="例如：前端开发工程师" />
        </el-form-item>
        <el-form-item label="时薪（元/小时）" prop="hourly_rate">
          <el-input-number
            v-model="formData.hourly_rate"
            :min="0"
            :step="10"
            :precision="2"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="分配工时" prop="allocated_hours">
          <el-input-number
            v-model="formData.allocated_hours"
            :min="0"
            :step="1"
            :precision="1"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="实际工时" prop="actual_hours">
          <el-input-number
            v-model="formData.actual_hours"
            :min="0"
            :step="1"
            :precision="1"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch
            v-model="formData.is_active"
            active-text="活跃"
            inactive-text="停用"
          />
        </el-form-item>
        <el-form-item label="备注" prop="notes">
          <el-input
            v-model="formData.notes"
            type="textarea"
            :rows="3"
            placeholder="请输入备注"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { toFixedSafe } from '@/utils/number'

const props = defineProps({
  projectId: {
    type: [Number, String],
    required: true
  }
})

const emit = defineEmits(['refresh'])

const loading = ref(false)
const memberList = ref<any[]>([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const formRef = ref(null)
const submitting = ref(false)
const isEdit = ref(false)
const currentMemberId = ref(null)

const userOptions = ref<any[]>([])

const formData = ref({
  user: null,
  role: '',
  hourly_rate: 0,
  allocated_hours: 0,
  actual_hours: 0,
  is_active: true,
  notes: ''
})

const rules = {
  user: [{ required: true, message: '请选择成员', trigger: 'change' }],
  role: [{ required: true, message: '请输入项目角色', trigger: 'blur' }],
  hourly_rate: [{ required: true, message: '请输入时薪', trigger: 'blur' }]
}

const totalAllocatedHours = computed(() => {
  return memberList.value.reduce((sum, member) => sum + (member.allocated_hours || 0), 0)
})

const totalActualHours = computed(() => {
  return memberList.value.reduce((sum, member) => sum + (member.actual_hours || 0), 0)
})

const estimatedLaborCost = computed(() => {
  return memberList.value.reduce((sum, member) => {
    return sum + ((member.actual_hours || 0) * (member.hourly_rate || 0))
  }, 0)
})

const loadMemberList = async () => {
  loading.value = true
  try {
    const response = await request.get(`/projects/members/`, {
      params: { project: props.projectId }
    })
    const data = response.data || response
    memberList.value = data.results || data
  } catch (error) {
    console.error('加载成员失败:', error)
    ElMessage.error('加载成员失败')
  } finally {
    loading.value = false
  }
}

const loadUsers = async () => {
  try {
    const response = await request.get('/auth/users/', {
      params: { is_active: true, page_size: 100 }
    })
    const data = response.data || response
    userOptions.value = data.results || data
  } catch (error) {
    console.error('加载用户失败:', error)
  }
}

const handleAdd = () => {
  isEdit.value = false
  dialogTitle.value = '添加成员'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  currentMemberId.value = row.id
  dialogTitle.value = '编辑成员'
  formData.value = {
    user: row.user,
    role: row.role || '',
    hourly_rate: row.hourly_rate || 0,
    allocated_hours: row.allocated_hours || 0,
    actual_hours: row.actual_hours || 0,
    is_active: row.is_active !== false,
    notes: row.notes || ''
  }
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该成员吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await request.delete(`/projects/members/${row.id}/`)
    ElMessage.success('删除成功')
    loadMemberList()
    emit('refresh')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除成员失败:', error)
      ElMessage.error('删除成员失败')
    }
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      const payload = {
        ...formData.value,
        project: props.projectId
      }

      if (isEdit.value) {
        await request.put(`/projects/members/${currentMemberId.value}/`, payload)
        ElMessage.success('更新成功')
      } else {
        await request.post('/projects/members/', payload)
        ElMessage.success('添加成功')
      }

      dialogVisible.value = false
      loadMemberList()
      emit('refresh')
    } catch (error) {
      console.error('保存成员失败:', error)
      ElMessage.error(isEdit.value ? '更新成员失败' : '添加成员失败')
    } finally {
      submitting.value = false
    }
  })
}

const resetForm = () => {
  formData.value = {
    user: null,
    role: '',
    hourly_rate: 0,
    allocated_hours: 0,
    actual_hours: 0,
    is_active: true,
    notes: ''
  }
  currentMemberId.value = null
  if (formRef.value) {
    formRef.value.clearValidate()
  }
}

onMounted(() => {
  loadMemberList()
  loadUsers()
})

defineExpose({
  loadMemberList
})
</script>

<style scoped>
.member-management {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
