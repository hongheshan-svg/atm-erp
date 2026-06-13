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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Delete } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'
import { getMyPendingTasks, getPendingTaskCount, approveTask, rejectTask, deleteWorkflowTask, batchDeleteWorkflowTasks } from '@/api/workflow'

const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
// 删除/批量删除入口：超管或持有审批中心(oa:workflow)菜单权限者可见。
// 不再硬编码随机角色 code（换库/重建角色即失效）。
const isAdmin = computed(() => {
  const user = userStore.userInfo
  if (!user) return false
  if (user.is_superuser) return true
  return permissionStore.hasPermission('oa:workflow')
})

const loading = ref(false)
const submitting = ref(false)
const deleting = ref(false)
const tasks = ref<any[]>([])
const pendingCount = ref(0)
const selectedTasks = ref<any[]>([])

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
    tasks.value = tasksRes.results || tasksRes || tasksRes || []
    pendingCount.value = countRes.count || countRes.count || 0
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
  // 用业务单据主键(business_id)而非工作流实例主键(instance)跳转；
  // 经 vue-router push 自动带上 /erp/ base。无独立详情页的模块跳列表并带 highlight 查询。
  const businessId = row.business_id
  if (!businessId) {
    ElMessage.warning('该审批关联的业务单据ID缺失，无法跳转')
    return
  }
  const targets = {
    'PURCHASE_REQUEST': { path: '/purchase/requests', query: { highlight: businessId } },
    'EXPENSE': { path: '/finance/expenses', query: { highlight: businessId } },
    'SALES_ORDER': { path: `/sales/orders/${businessId}` },
  }
  const target = targets[row.business_type]
  if (target) {
    router.push(target)
  } else {
    ElMessage.info('该业务类型暂不支持快速跳转，请到对应模块查看')
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
