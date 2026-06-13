<template>
  <div class="expense-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>费用报销</span>
          <el-button type="primary" v-permission="'finance:expense:create'" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            提交报销
          </el-button>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="项目">
          <el-select v-model="searchForm.project" placeholder="选择项目" clearable filterable style="width: 180px;">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="searchForm.category" placeholder="选择分类" clearable style="width: 120px;">
            <el-option label="差旅费" value="TRAVEL" />
            <el-option label="餐饮费" value="MEAL" />
            <el-option label="办公用品" value="OFFICE" />
            <el-option label="通讯费" value="COMMUNICATION" />
            <el-option label="培训费" value="TRAINING" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 120px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已提交" value="SUBMITTED" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已拒绝" value="REJECTED" />
            <el-option label="已报销" value="PAID" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadExpenses">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-permission="'finance:expense:delete'" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" v-permission="'finance:expense:delete'" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <el-table :data="expenses" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column v-permission="'finance:expense:delete'" v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="expense_no" label="费用编号" width="150" />
        <el-table-column prop="user_name" label="提交人" width="100" />
        <el-table-column prop="project_name" label="项目" />
        <el-table-column prop="category" label="分类" width="100">
          <template #default="{ row }">
            {{ getCategoryLabel(row.category) }}
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.amount || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="expense_date" label="费用日期" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" show-overflow-tooltip />
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" v-permission="'finance:expense:edit'" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="info" @click="handleAttachments(row)">附件</el-button>
            <el-button size="small" type="warning" @click="handleSubmit(row)" v-if="row.status === 'DRAFT'">提交</el-button>
            <el-button size="small" type="success" @click="handleApprove(row)" v-if="row.status === 'SUBMITTED'">批准</el-button>
            <el-button size="small" type="danger" @click="handleReject(row)" v-if="row.status === 'SUBMITTED'">拒绝</el-button>
            <el-button size="small" type="primary" @click="handleReimburse(row)" v-if="row.status === 'APPROVED'">报销</el-button>
            <el-button v-if="canDelete" size="small" type="danger" @click="deleteRow(row)" :loading="deleteLoading">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadExpenses"
        @current-change="loadExpenses"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="费用分类" prop="category">
              <el-select v-model="form.category" placeholder="选择分类" style="width: 100%;">
                <el-option label="差旅费" value="TRAVEL" />
                <el-option label="餐饮费" value="MEAL" />
                <el-option label="办公用品" value="OFFICE" />
                <el-option label="通讯费" value="COMMUNICATION" />
                <el-option label="培训费" value="TRAINING" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="费用日期" prop="expense_date">
              <el-date-picker v-model="form.expense_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="关联项目">
              <el-select v-model="form.project" placeholder="选择项目" filterable clearable style="width: 100%;">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联部门">
              <el-select v-model="form.department" placeholder="选择部门" filterable clearable style="width: 100%;">
                <el-option v-for="d in departments" :key="d.id" :label="d.name" :value="d.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="费用金额" prop="amount">
          <el-input-number v-model="form.amount" :min="0" :precision="2" :step="100" style="width: 200px;" />
          <span style="margin-left: 10px; color: #909399;">元</span>
        </el-form-item>
        <el-form-item label="费用说明" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请详细描述费用用途" />
        </el-form-item>
        
        <!-- 附件上传 -->
        <el-form-item label="报销凭证">
          <!-- 编辑时使用完整附件组件 -->
          <AttachmentUpload
            v-if="isEdit && form.id"
            ref="attachmentRef"
            related-model="Expense"
            :related-id="form.id"
            title="报销凭证"
            accept=".pdf,.jpg,.jpeg,.png,.gif"
          />
          <!-- 新增时使用简化的文件选择 -->
          <div v-else class="temp-upload">
            <el-upload
              ref="tempUploadRef"
              :auto-upload="false"
              :file-list="tempFiles"
              :on-change="handleTempFileChange"
              :on-remove="handleTempFileRemove"
              multiple
              accept=".pdf,.jpg,.jpeg,.png,.gif"
              list-type="picture"
            >
              <el-button type="primary">
                <el-icon><Upload /></el-icon>
                上传发票/行程单
              </el-button>
              <template #tip>
                <div class="el-upload__tip">
                  支持发票、行程单、收据等凭证（PDF/图片），单个文件不超过10MB
                </div>
              </template>
            </el-upload>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 查看详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="费用报销详情" width="600px">
      <el-descriptions :column="2" border v-if="currentExpense">
        <el-descriptions-item label="费用编号">{{ currentExpense.expense_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentExpense.status)">{{ getStatusLabel(currentExpense.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="费用分类">{{ getCategoryLabel(currentExpense.category) }}</el-descriptions-item>
        <el-descriptions-item label="费用金额">¥{{ parseFloat(currentExpense.amount || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="费用日期">{{ currentExpense.expense_date }}</el-descriptions-item>
        <el-descriptions-item label="提交人">{{ currentExpense.user_name }}</el-descriptions-item>
        <el-descriptions-item label="关联项目">{{ currentExpense.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关联部门">{{ currentExpense.department_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="费用说明" :span="2">{{ currentExpense.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ currentExpense.created_at }}</el-descriptions-item>
        <el-descriptions-item label="报销日期" v-if="currentExpense.reimbursement_date">{{ currentExpense.reimbursement_date }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 附件管理对话框 -->
    <el-dialog v-model="attachmentDialogVisible" :title="`费用报销 ${currentExpense?.expense_no || ''} - 附件管理`" width="900px" destroy-on-close>
      <AttachmentUpload
        v-if="currentExpense"
        related-model="Expense"
        :related-id="currentExpense.id"
        title="报销凭证（发票、收据等）"
        :disabled="currentExpense.status === 'PAID'"
      />
      <div v-if="currentExpense?.status === 'DRAFT'" class="attachment-tip">
        <el-alert 
          title="请上传报销相关凭证，如发票、收据、付款截图等"
          type="info"
          :closable="false"
          show-icon
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload } from '@element-plus/icons-vue'
import { getExpenses, createExpense, updateExpense, submitExpense, approveExpense, rejectExpense, reimburseExpense } from '@/api/finance'
import AttachmentUpload from '@/components/AttachmentUpload.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'
import { usePermissionStore } from '@/stores/permission'
import { getDepartments } from '@/api/auth'
import { batchUploadAttachments } from '@/api/core'
import { getProjectList } from '@/api/projects/project'

// 权限检查
const { canDelete } = usePermission()
const permissionStore = usePermissionStore()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/finance/expenses/',
  { onSuccess: () => loadExpenses(), confirmTitle: '删除费用', confirmMessage: '确定要删除该费用报销吗？' }
)

const attachmentRef = ref(null)
const tempUploadRef = ref(null)
const tempFiles = ref<any[]>([])

const loading = ref(false)
const saving = ref(false)
const expenses = ref<any[]>([])
const projects = ref<any[]>([])
const projectsLoaded = ref(false)
const departments = ref<any[]>([])
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const attachmentDialogVisible = ref(false)
const dialogTitle = ref('提交报销')
const isEdit = ref(false)
const formRef = ref(null)
const currentExpense = ref(null)

const searchForm = reactive({
  project: null,
  category: null,
  status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  category: 'TRAVEL',
  expense_date: '',
  project: null,
  department: null,
  amount: 0,
  description: ''
})

const rules = {
  category: [{ required: true, message: '请选择费用分类', trigger: 'change' }],
  expense_date: [{ required: true, message: '请选择费用日期', trigger: 'change' }],
  amount: [{ required: true, message: '请输入费用金额', trigger: 'blur' }],
  description: [{ required: true, message: '请输入费用说明', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const types = {
    DRAFT: 'info',
    SUBMITTED: 'warning',
    APPROVED: 'success',
    REJECTED: 'danger',
    PAID: ''
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    DRAFT: '草稿',
    SUBMITTED: '已提交',
    APPROVED: '已批准',
    REJECTED: '已拒绝',
    PAID: '已报销'
  }
  return labels[status] || status
}

const getCategoryLabel = (category) => {
  const labels = { 
    TRAVEL: '差旅费', 
    MEAL: '餐饮费', 
    OFFICE: '办公用品', 
    COMMUNICATION: '通讯费',
    TRAINING: '培训费',
    OTHER: '其他' 
  }
  return labels[category] || category
}

const loadExpenses = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.project) params.project = searchForm.project
    if (searchForm.category) params.category = searchForm.category
    if (searchForm.status) params.status = searchForm.status
    
    const res = await getExpenses(params)
    expenses.value = res.results || res.results || res || []
    pagination.total = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载费用列表失败')
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  if (projectsLoaded.value) {
    return true
  }

  try {
    const res = await getProjectList()
    projects.value = res.results || res.results || res || []
    projectsLoaded.value = true
    return true
  } catch (error) {
    if (error?.response?.status !== 403) {
      console.error('加载项目失败:', error)
    }
    return false
  }
}

const ensureProjectsLoaded = async () => {
  if (!permissionStore.hasPermission('projects:list')) {
    projects.value = []
    projectsLoaded.value = false
    return false
  }

  return loadProjects()
}

const loadDepartments = async () => {
  try {
    const res = await getDepartments()
    departments.value = res.results || res.results || res || []
  } catch (error) {
    console.error('加载部门失败:', error)
  }
}

const resetSearch = () => {
  searchForm.project = null
  searchForm.category = null
  searchForm.status = null
  pagination.page = 1
  loadExpenses()
}

const handleTempFileChange = (file, fileList) => {
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning(`文件 "${file.name}" 超过10MB限制`)
    fileList.pop()
    return
  }
  tempFiles.value = fileList
}

const handleTempFileRemove = (file, fileList) => {
  tempFiles.value = fileList
}

const uploadTempFiles = async (expenseId) => {
  if (!tempFiles.value.length) return
  
  const formData = new FormData()
  formData.append('related_model', 'Expense')
  formData.append('related_id', expenseId)
  formData.append('category', 'INVOICE')
  
  for (const file of tempFiles.value) {
    formData.append('files', file.raw)
  }
  
  try {
    await batchUploadAttachments(formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  } catch (error) {
    console.error('附件上传失败:', error)
    ElMessage.warning('报销已保存，但部分附件上传失败')
  }
}

const handleAdd = async () => {
  await ensureProjectsLoaded()
  dialogTitle.value = '提交报销'
  isEdit.value = false
  tempFiles.value = []
  Object.assign(form, {
    id: null,
    category: 'TRAVEL',
    expense_date: new Date().toISOString().split('T')[0],
    project: null,
    department: null,
    amount: 0,
    description: ''
  })
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  await ensureProjectsLoaded()
  dialogTitle.value = '编辑报销'
  isEdit.value = true
  
  Object.assign(form, {
    id: row.id,
    category: row.category,
    expense_date: row.expense_date,
    project: row.project,
    department: row.department,
    amount: parseFloat(row.amount || 0),
    description: row.description || ''
  })
  
  dialogVisible.value = true
}

const handleView = (row) => {
  currentExpense.value = row
  viewDialogVisible.value = true
}

const handleAttachments = (row) => {
  currentExpense.value = row
  attachmentDialogVisible.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    
    if (!form.project && !form.department) {
      ElMessage.warning('请至少选择一个关联项目或部门')
      return
    }
    
    saving.value = true
    
    const payload = {
      category: form.category,
      expense_date: form.expense_date,
      project: form.project,
      department: form.department,
      amount: form.amount,
      description: form.description
    }
    
    if (isEdit.value) {
      await updateExpense(form.id, payload)
      ElMessage.success('更新费用报销成功')
    } else {
      const response = await createExpense(payload)
      // 上传附件
      if (tempFiles.value.length && response.id) {
        await uploadTempFiles(response.id)
      }
      ElMessage.success('创建费用报销成功')
    }
    
    dialogVisible.value = false
    tempFiles.value = []
    loadExpenses()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('保存费用报销失败')
      console.error(error)
    }
  } finally {
    saving.value = false
  }
}

const handleSubmit = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交该费用报销吗？提交后将进入审批流程。', '提交确认', { type: 'warning' })
    await submitExpense(row.id)
    ElMessage.success('提交成功')
    loadExpenses()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('提交失败')
    }
  }
}

const handleApprove = async (row) => {
  try {
    await ElMessageBox.confirm('确定要批准该费用报销吗？', '批准确认', { type: 'warning' })
    await approveExpense(row.id)
    ElMessage.success('批准成功')
    loadExpenses()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('批准失败')
    }
  }
}

const handleReject = async (row) => {
  try {
    await ElMessageBox.confirm('确定要拒绝该费用报销吗？', '拒绝确认', { type: 'warning' })
    await rejectExpense(row.id)
    ElMessage.success('已拒绝')
    loadExpenses()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const handleReimburse = async (row) => {
  try {
    await ElMessageBox.confirm('确定要标记该费用为已报销吗？', '报销确认', { type: 'warning' })
    await reimburseExpense(row.id)
    ElMessage.success('已报销')
    loadExpenses()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

// handleDelete 已被 useBatchDelete 的 deleteRow 替代

onMounted(() => {
  loadExpenses()
  loadDepartments()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.attachment-tip {
  margin-top: 20px;
}

.temp-upload {
  width: 100%;
}

.temp-upload .el-upload__tip {
  color: #909399;
  font-size: 12px;
  margin-top: 5px;
}
</style>
