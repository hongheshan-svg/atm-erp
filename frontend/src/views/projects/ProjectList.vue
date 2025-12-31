<template>
  <div class="project-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>项目管理</span>
          <div class="header-actions">
            <el-button type="success" @click="handleExport">
              <el-icon><Download /></el-icon>
              导出Excel
            </el-button>
            <el-button type="primary" @click="handleAdd">创建项目</el-button>
          </div>
        </div>
      </template>

      <el-table :data="projects" v-loading="loading" stripe border>
        <el-table-column prop="code" label="项目编号" width="150" />
        <el-table-column prop="name" label="项目名称" />
        <el-table-column prop="sales_order_no" label="关联订单" width="140">
          <template #default="{ row }">
            <el-tag v-if="row.sales_order_no" type="success" size="small">{{ row.sales_order_no }}</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="customer_name" label="客户" />
        <el-table-column prop="manager_name" label="负责人" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120" />
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="warning" @click="handleViewAttachments(row)">附件</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px">
      <el-form :model="form" ref="formRef" label-width="150px">
        <el-form-item label="关联销售订单">
          <el-select 
            v-model="form.sales_order" 
            filterable 
            clearable
            placeholder="选择销售订单 (可选)"
            @change="handleSalesOrderChange"
          >
            <el-option 
              v-for="so in salesOrders" 
              :key="so.id" 
              :label="`${so.order_no} - ${so.customer_name}`" 
              :value="so.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="项目编号">
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item label="项目名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="客户">
          <el-select v-model="form.customer" filterable placeholder="请选择客户">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目经理">
          <el-select v-model="form.manager" filterable placeholder="请选择项目经理">
            <el-option v-for="u in users" :key="u.id" :label="getUserDisplayName(u)" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="总预算">
          <el-input-number v-model="form.budget_total" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="规划中" value="PLANNING" />
            <el-option label="进行中" value="ACTIVE" />
            <el-option label="暂停" value="PAUSED" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">提交</el-button>
      </template>
    </el-dialog>
    
    <!-- 附件管理对话框 -->
    <el-dialog v-model="attachmentDialogVisible" :title="`项目 ${currentProject?.name || ''} - 附件管理`" width="900px" destroy-on-close>
      <AttachmentUpload
        v-if="currentProject"
        related-model="Project"
        :related-id="currentProject.id"
        title="项目相关资料（合同、文档等）"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'
import AttachmentUpload from '@/components/AttachmentUpload.vue'
import { exportProjects } from '@/api/export'

const router = useRouter()
const loading = ref(false)
const projects = ref([])
const customers = ref([])
const users = ref([])
const salesOrders = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('创建项目')
const isEdit = ref(false)
const formRef = ref(null)
const attachmentDialogVisible = ref(false)
const currentProject = ref(null)

const form = reactive({
  id: null,
  code: '',
  name: '',
  sales_order: null,
  customer: null,
  manager: null,
  start_date: '',
  end_date: '',
  budget_total: 0,
  status: 'DRAFT'
})

const getStatusType = (status) => {
  const types = {
    DRAFT: 'info',
    PENDING: 'warning',
    REJECTED: 'danger',
    PLANNING: 'info',
    ACTIVE: 'success',
    PAUSED: 'warning',
    COMPLETED: '',
    CANCELLED: 'danger',
    ARCHIVED: 'info'
  }
  return types[status] || ''
}

const getStatusLabel = (status) => {
  const labels = {
    DRAFT: '草稿',
    PENDING: '审批中',
    REJECTED: '已拒绝',
    PLANNING: '规划中',
    ACTIVE: '进行中',
    PAUSED: '暂停',
    COMPLETED: '已完成',
    CANCELLED: '已取消',
    ARCHIVED: '已归档'
  }
  return labels[status] || status
}

const getUserDisplayName = (user) => {
  // 优先显示姓名，如果没有则显示用户名
  const fullName = (user.last_name || '') + (user.first_name || '')
  if (fullName.trim() && fullName !== user.username) {
    return fullName
  }
  return user.username
}

const loadProjects = async () => {
  loading.value = true
  try {
    const response = await request.get('/projects/projects/')
    projects.value = response.results || response || []
  } catch (error) {
    ElMessage.error('加载项目失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const response = await request.get('/masterdata/customers/')
    customers.value = response.results || response || []
  } catch (error) {
    console.error('Failed to load customers')
  }
}

const loadUsers = async () => {
  try {
    const response = await request.get('/auth/users/')
    users.value = response.results || response || []
  } catch (error) {
    console.error('Failed to load users')
  }
}

const loadSalesOrders = async () => {
  try {
    // 只加载未关联项目的销售订单，或者当前编辑项目已关联的订单
    const response = await request.get('/sales/orders/')
    salesOrders.value = response.results || response || []
  } catch (error) {
    console.error('Failed to load sales orders')
  }
}

// 当选择销售订单时，自动填充客户
const handleSalesOrderChange = (soId) => {
  if (soId) {
    const selectedOrder = salesOrders.value.find(so => so.id === soId)
    if (selectedOrder) {
      form.customer = selectedOrder.customer
    }
  }
}

const handleView = (row) => {
  router.push(`/projects/${row.id}`)
}

const handleAdd = () => {
  dialogTitle.value = '创建项目'
  isEdit.value = false
  Object.assign(form, { id: null, code: '', name: '', sales_order: null, customer: null, manager: null, start_date: '', end_date: '', budget_total: 0, status: 'DRAFT' })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑项目'
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该项目吗？', '警告', { type: 'warning' })
    await request.delete(`/projects/projects/${row.id}/`)
    ElMessage.success('删除项目成功')
    loadProjects()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除项目失败')
  }
}

const handleSubmit = async () => {
  // 验证必填字段
  if (!form.code || !form.name || !form.customer || !form.manager || !form.start_date || !form.end_date) {
    ElMessage.warning('请填写所有必填字段（项目编号、名称、客户、项目经理、开始日期、结束日期）')
    return
  }
  
  try {
    // 构建提交数据，只发送需要的字段
    const payload = {
      code: form.code,
      name: form.name,
      customer: form.customer,
      manager: form.manager,
      start_date: form.start_date,
      end_date: form.end_date,
      status: form.status || 'DRAFT',
      budget_total: form.budget_total || 0
    }
    
    // 可选字段
    if (form.sales_order) {
      payload.sales_order = form.sales_order
    }
    
    if (isEdit.value) {
      await request.put(`/projects/projects/${form.id}/`, payload)
      ElMessage.success('更新项目成功')
    } else {
      await request.post('/projects/projects/', payload)
      ElMessage.success('创建项目成功')
    }
    dialogVisible.value = false
    loadProjects()
  } catch (error) {
    console.error('保存项目失败:', error)
    ElMessage.error(error.response?.data?.detail || '保存项目失败')
  }
}

const handleViewAttachments = (row) => {
  currentProject.value = row
  attachmentDialogVisible.value = true
}

const handleExport = async () => {
  try {
    ElMessage.info('正在导出...')
    await exportProjects()
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

onMounted(() => {
  loadProjects()
  loadCustomers()
  loadUsers()
  loadSalesOrders()
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
  gap: 10px;
}
</style>

