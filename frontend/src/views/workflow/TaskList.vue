<template>
  <div class="workflow-task-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>待办审批</span>
          <div class="header-actions">
            <el-button 
              v-if="isAdmin && selectedTasks.length > 0" 
              type="danger" 
              @click="handleBatchDelete"
              :loading="deleting"
            >
              <el-icon><Delete /></el-icon>
              批量删除 ({{ selectedTasks.length }})
            </el-button>
            <el-badge :value="pendingCount" :hidden="pendingCount === 0" class="badge">
              <el-button type="primary" @click="loadTasks" :loading="loading">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </el-badge>
          </div>
        </div>
      </template>

      <el-table 
        :data="tasks" 
        v-loading="loading" 
        stripe
        @selection-change="handleSelectionChange"
      >
        <el-table-column v-if="isAdmin" type="selection" width="55" />
        <el-table-column prop="business_no" label="单据编号" width="150" />
        <el-table-column prop="business_type_display" label="业务类型" width="120" />
        <el-table-column prop="workflow_name" label="审批流程" width="150" />
        <el-table-column prop="step_name" label="当前步骤" width="120" />
        <el-table-column prop="submitter_name" label="提交人" width="100" />
        <el-table-column prop="amount" label="金额" width="120">
          <template #default="{ row }">
            <span v-if="row.amount">¥{{ Number(row.amount).toLocaleString() }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="deadline" label="截止时间" width="160">
          <template #default="{ row }">
            <span :class="{ 'text-danger': isOverdue(row.deadline) }">
              {{ formatDate(row.deadline) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="isAdmin ? 260 : 200" fixed="right">
          <template #default="{ row }">
            <el-button type="success" size="small" @click="handleApprove(row)">
              通过
            </el-button>
            <el-button type="danger" size="small" @click="handleReject(row)">
              拒绝
            </el-button>
            <el-button type="info" size="small" @click="viewDetail(row)">
              详情
            </el-button>
            <el-button 
              v-if="isAdmin" 
              type="danger" 
              size="small" 
              @click="handleDelete(row)"
              plain
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && tasks.length === 0" description="暂无待办审批" />
    </el-card>

    <!-- Approve Dialog -->
    <el-dialog v-model="approveDialogVisible" title="审批通过" width="500px">
      <el-form :model="approveForm">
        <el-form-item label="审批意见">
          <el-input
            v-model="approveForm.comment"
            type="textarea"
            :rows="3"
            placeholder="请输入审批意见（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approveDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmApprove" :loading="submitting">
          确认通过
        </el-button>
      </template>
    </el-dialog>

    <!-- Reject Dialog -->
    <el-dialog v-model="rejectDialogVisible" title="拒绝审批" width="500px">
      <el-form :model="rejectForm" :rules="rejectRules" ref="rejectFormRef">
        <el-form-item label="拒绝原因" prop="comment">
          <el-input
            v-model="rejectForm.comment"
            type="textarea"
            :rows="3"
            placeholder="请输入拒绝原因（必填）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="confirmReject" :loading="submitting">
          确认拒绝
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Delete } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { getMyPendingTasks, getPendingTaskCount, approveTask, rejectTask, deleteWorkflowTask, batchDeleteWorkflowTasks } from '@/api/workflow'

const userStore = useUserStore()
const isAdmin = computed(() => {
  const user = userStore.userInfo
  if (!user) return false
  if (user.is_superuser) return true
  // Check role_info.code (from serializer)
  const roleCode = user.role_info?.code || user.role?.code
  // Allow ADMIN, SUPER_ADMIN, 系统管理员, 总经理
  const adminRoles = ['ADMIN', 'SUPER_ADMIN', 'ROLEDC4E40', 'ROLEF8477A']
  if (roleCode && adminRoles.includes(roleCode)) return true
  return false
})

const loading = ref(false)
const submitting = ref(false)
const deleting = ref(false)
const tasks = ref([])
const pendingCount = ref(0)
const selectedTasks = ref([])

const approveDialogVisible = ref(false)
const rejectDialogVisible = ref(false)
const currentTask = ref(null)
const rejectFormRef = ref(null)

const approveForm = ref({ comment: '' })
const rejectForm = ref({ comment: '' })

const rejectRules = {
  comment: [{ required: true, message: '请输入拒绝原因', trigger: 'blur' }]
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const isOverdue = (deadline) => {
  if (!deadline) return false
  return new Date(deadline) < new Date()
}

const loadTasks = async () => {
  loading.value = true
  try {
    const [tasksRes, countRes] = await Promise.all([
      getMyPendingTasks(),
      getPendingTaskCount()
    ])
    // Handle different response formats
    tasks.value = tasksRes.results || tasksRes.data || tasksRes || []
    pendingCount.value = countRes.count || countRes.data?.count || 0
  } catch (error) {
    console.error('Failed to load tasks:', error)
    tasks.value = []
    pendingCount.value = 0
  } finally {
    loading.value = false
  }
}

const handleApprove = (row) => {
  currentTask.value = row
  approveForm.value.comment = ''
  approveDialogVisible.value = true
}

const handleReject = (row) => {
  currentTask.value = row
  rejectForm.value.comment = ''
  rejectDialogVisible.value = true
}

const confirmApprove = async () => {
  submitting.value = true
  try {
    await approveTask(currentTask.value.id, approveForm.value.comment)
    ElMessage.success('审批通过')
    approveDialogVisible.value = false
    loadTasks()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '操作失败')
  } finally {
    submitting.value = false
  }
}

const confirmReject = async () => {
  await rejectFormRef.value.validate()
  submitting.value = true
  try {
    await rejectTask(currentTask.value.id, rejectForm.value.comment)
    ElMessage.success('已拒绝')
    rejectDialogVisible.value = false
    loadTasks()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '操作失败')
  } finally {
    submitting.value = false
  }
}

const viewDetail = (row) => {
  // Navigate to business detail based on type
  const routes = {
    'PURCHASE_REQUEST': `/purchase/requests/${row.instance}`,
    'EXPENSE': `/finance/expenses/${row.instance}`,
    'SALES_ORDER': `/sales/orders/${row.instance}`,
  }
  const route = routes[row.business_type]
  if (route) {
    window.open(route, '_blank')
  }
}

const handleSelectionChange = (selection) => {
  selectedTasks.value = selection
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除此审批任务吗？删除后不可恢复', '确认删除', {
      type: 'warning'
    })
    deleting.value = true
    await deleteWorkflowTask(row.id)
    ElMessage.success('删除成功')
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '删除失败')
    }
  } finally {
    deleting.value = false
  }
}

const handleBatchDelete = async () => {
  if (selectedTasks.value.length === 0) return
  
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedTasks.value.length} 条审批任务吗？删除后不可恢复`, 
      '批量删除', 
      { type: 'warning' }
    )
    deleting.value = true
    const ids = selectedTasks.value.map(t => t.id)
    await batchDeleteWorkflowTasks(ids)
    ElMessage.success(`成功删除 ${ids.length} 条任务`)
    selectedTasks.value = []
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '批量删除失败')
    }
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  loadTasks()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.badge {
  margin-left: 10px;
}
.text-danger {
  color: #f56c6c;
}
</style>
