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
            <el-button type="primary" v-permission="'projects:project:create'" @click="handleAdd">创建项目</el-button>
          </div>
        </div>
      </template>

      <!-- 批量操作工具栏 - 仅管理员可见 -->
      <div class="table-toolbar" v-permission="'projects:project:delete'" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button 
          type="danger" 
          size="small" 
          @click="batchDelete"
          :loading="deleteLoading"
        >
          批量删除
        </el-button>
      </div>

      <el-table :data="projects" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <!-- 仅管理员显示选择列 -->
        <el-table-column v-permission="'projects:project:delete'" v-if="canDelete" type="selection" width="55" fixed />
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
        <el-table-column label="操作" :width="canDelete ? 400 : 340" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" v-permission="'projects:project:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="warning" @click="handleViewAttachments(row)">附件</el-button>
            <!-- 提交审批按钮 - 仅草稿/规划中/已拒绝状态可见 -->
            <el-button 
              v-if="['DRAFT', 'PLANNING', 'REJECTED'].includes(row.status)"
              size="small" 
              type="success"
              @click="handleSubmitApproval(row)"
              :loading="submitLoading === row.id"
            >
              提交审批
            </el-button>
            <!-- 查看审批流程 - 审批中状态可见 -->
            <el-button 
              v-if="row.status === 'PENDING'"
              size="small" 
              type="info"
              @click="handleViewWorkflow(row)"
            >
              审批进度
            </el-button>
            <!-- 仅管理员显示删除按钮 -->
            <el-button 
              v-if="canDelete"
              size="small" 
              type="danger" 
              @click="deleteRow(row)"
              :loading="deleteLoading"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px">
      <el-form :model="form" ref="formRef" label-width="150px">
        <el-form-item label="关联销售订单">
          <el-select 
            v-model="form.sales_order" 
            filterable 
            clearable
            placeholder="选择销售订单 (可选)"
            @change="handleSalesOrderChange"
            style="width: 100%"
          >
            <el-option 
              v-for="so in salesOrders" 
              :key="so.id" 
              :label="`${so.order_no} - ${so.customer_name} (¥${so.total_with_tax?.toLocaleString()})`" 
              :value="so.id"
            />
          </el-select>
        </el-form-item>
        
        <!-- 选中订单后显示订单详情 -->
        <el-form-item v-if="selectedOrder" label="订单详情">
          <el-card shadow="never" class="order-detail-card">
            <el-descriptions :column="3" border size="small">
              <el-descriptions-item label="订单号">{{ selectedOrder.order_no }}</el-descriptions-item>
              <el-descriptions-item label="客户订单号">{{ selectedOrder.customer_order_no || '-' }}</el-descriptions-item>
              <el-descriptions-item label="客户">{{ selectedOrder.customer_name }}</el-descriptions-item>
              <el-descriptions-item label="订单日期">{{ selectedOrder.order_date }}</el-descriptions-item>
              <el-descriptions-item label="交货日期">
                <span style="color: #E6A23C; font-weight: bold">{{ selectedOrder.delivery_date }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="含税金额">
                <span style="color: #67C23A; font-weight: bold">¥{{ selectedOrder.total_with_tax?.toLocaleString() }}</span>
              </el-descriptions-item>
            </el-descriptions>
            
            <div style="margin-top: 12px">
              <div style="font-weight: bold; margin-bottom: 8px; color: #606266">📦 产品明细</div>
              <el-table :data="selectedOrder.lines" size="small" border stripe max-height="200">
                <el-table-column prop="product_name" label="产品名称" />
                <el-table-column prop="spec" label="规格型号" width="150" />
                <el-table-column prop="qty" label="数量" width="80" align="right" />
                <el-table-column prop="unit_price" label="单价" width="100" align="right">
                  <template #default="{ row }">¥{{ row.unit_price?.toLocaleString() }}</template>
                </el-table-column>
                <el-table-column prop="line_amount" label="金额" width="120" align="right">
                  <template #default="{ row }">¥{{ row.line_amount?.toLocaleString() }}</template>
                </el-table-column>
              </el-table>
            </div>
            
            <el-alert 
              type="info" 
              :closable="false" 
              style="margin-top: 12px"
              show-icon
            >
              <template #title>
                建议：根据交货日期 <b>{{ selectedOrder.delivery_date }}</b> 设置项目结束日期，项目名称可参考产品名称
              </template>
            </el-alert>
          </el-card>
        </el-form-item>
        
        <el-divider v-if="selectedOrder" />
        
        <el-form-item label="项目编号">
          <el-input v-model="form.code" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="项目名称">
          <el-input v-model="form.name" :placeholder="selectedOrder ? `建议：${selectedOrder.customer_name} - ${selectedOrder.lines?.[0]?.product_name || '定制产品'}` : '请输入项目名称'" />
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
          <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" :placeholder="selectedOrder ? `建议：${selectedOrder.delivery_date}` : ''" />
        </el-form-item>
        <el-form-item label="总预算">
          <el-input-number v-model="form.budget_total" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" :disabled="['PENDING'].includes(form.status)">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="规划中" value="PLANNING" />
            <el-option v-if="['PENDING', 'REJECTED'].includes(form.status)" label="审批中" value="PENDING" disabled />
            <el-option v-if="form.status === 'REJECTED'" label="已拒绝" value="REJECTED" disabled />
            <el-option label="进行中" value="IN_PROGRESS" />
            <el-option label="暂停" value="PAUSED" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
          <div v-if="form.status === 'PENDING'" class="el-form-item__help">
            项目正在审批中，不可手动修改状态
          </div>
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

    <!-- 审批进度弹窗 -->
    <WorkflowProgress
      v-model="workflowDialogVisible"
      :business-type="workflowBusinessType"
      :business-id="workflowBusinessId"
    />
  </template>

<script setup>
import WorkflowProgress from '@/components/WorkflowProgress.vue'

import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { getProjectList, createProject, updateProject, submitProject } from '@/api/projects/project'
import AttachmentUpload from '@/components/AttachmentUpload.vue'
import { exportProjects } from '@/api/export'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'
import { usePermissionStore } from '@/stores/permission'
import { getUsers } from '@/api/auth'
import { getCustomerList } from '@/api/masterdata'
import { getOrdersForLinking } from '@/api/sales'

// 权限检查
const { canDelete } = usePermission()
const permissionStore = usePermissionStore()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/projects/projects/',
  {
    confirmTitle: '确认删除项目',
    confirmMessage: '此操作将永久删除选中的项目及其所有关联数据（任务、BOM、图纸等），此操作不可恢复！',
    successMessage: '删除项目成功',
    errorMessage: '删除项目失败',
    onSuccess: () => { loadProjects() }
  }
)

const router = useRouter()
const workflowDialogVisible = ref(false)
const workflowBusinessId = ref(null)
const workflowBusinessType = 'PROJECT'

const showWorkflowProgress = (row) => {
  workflowBusinessId.value = row.id
  workflowDialogVisible.value = true
}

const loading = ref(false)
const projects = ref([])
const customers = ref([])
const users = ref([])
const salesOrders = ref([])
const salesOrdersLoaded = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('创建项目')
const isEdit = ref(false)
const formRef = ref(null)
const attachmentDialogVisible = ref(false)
const currentProject = ref(null)
const submitLoading = ref(null)  // 提交审批loading状态

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
    IN_PROGRESS: 'success',
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
    IN_PROGRESS: '进行中',
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
    const response = await getProjectList()
    projects.value = response.results || response || []
  } catch (error) {
    ElMessage.error('加载项目失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const response = await getCustomerList()
    customers.value = response.results || response || []
  } catch (error) {
    console.error('Failed to load customers')
  }
}

const loadUsers = async () => {
  try {
    const response = await getUsers()
    users.value = response.results || response || []
  } catch (error) {
    console.error('Failed to load users')
  }
}

const loadSalesOrders = async () => {
  if (salesOrdersLoaded.value) {
    return true
  }

  try {
    const response = await getOrdersForLinking()
    salesOrders.value = response.data || response || []
    salesOrdersLoaded.value = true
    return true
  } catch (error) {
    if (error?.response?.status !== 403) {
      console.error('Failed to load sales orders', error)
    }
    return false
  }
}

const ensureSalesOrdersLoaded = async () => {
  if (!permissionStore.hasPermission('sales:orders')) {
    salesOrders.value = []
    salesOrdersLoaded.value = false
    return false
  }

  return loadSalesOrders()
}

// 计算选中的订单详情
const selectedOrder = computed(() => {
  if (!form.sales_order) return null
  return salesOrders.value.find(so => so.id === form.sales_order)
})

// 当选择销售订单时，自动填充相关信息
const handleSalesOrderChange = (soId) => {
  if (soId) {
    const order = salesOrders.value.find(so => so.id === soId)
    if (order) {
      // 自动填充客户
      form.customer = order.customer
      
      // 自动填充预算（使用含税金额）
      form.budget_total = order.total_with_tax || 0
      
      // 自动设置结束日期为交货日期
      if (order.delivery_date) {
        form.end_date = order.delivery_date
      }
      
      // 自动设置开始日期为今天
      if (!form.start_date) {
        const today = new Date()
        form.start_date = today.toISOString().split('T')[0]
      }
    }
  } else {
    // 清空关联时重置
    form.budget_total = 0
  }
}

const handleView = (row) => {
  router.push(`/projects/${row.id}`)
}

const handleAdd = async () => {
  dialogTitle.value = '创建项目'
  isEdit.value = false
  await ensureSalesOrdersLoaded()
  Object.assign(form, { id: null, code: '', name: '', sales_order: null, customer: null, manager: null, start_date: '', end_date: '', budget_total: 0, status: 'DRAFT' })
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑项目'
  isEdit.value = true
  await ensureSalesOrdersLoaded()
  Object.assign(form, row)
  dialogVisible.value = true
}

// 删除功能已迁移到 useBatchDelete composable

const handleSubmit = async () => {
  // 验证必填字段（项目编号可留空自动生成）
  if (!form.name || !form.customer || !form.manager || !form.start_date || !form.end_date) {
    ElMessage.warning('请填写所有必填字段（项目名称、客户、项目经理、开始日期、结束日期）')
    return
  }
  
  try {
    // 构建提交数据，只发送需要的字段
    const payload = {
      name: form.name,
      customer: form.customer,
      manager: form.manager,
      start_date: form.start_date,
      end_date: form.end_date,
      status: form.status || 'DRAFT',
      budget_total: form.budget_total || 0
    }
    
    // 项目编号（可选，留空自动生成）
    if (form.code) {
      payload.code = form.code
    }
    
    // 关联销售订单（可选）
    if (form.sales_order) {
      payload.sales_order = form.sales_order
    }
    
    if (isEdit.value) {
      payload.code = form.code  // 编辑时必须有编号
      await updateProject(form.id, payload)
      ElMessage.success('更新项目成功')
    } else {
      await createProject(payload)
      ElMessage.success('创建项目成功')
    }
    dialogVisible.value = false
    loadProjects()
    if (salesOrdersLoaded.value) {
      salesOrdersLoaded.value = false
      await ensureSalesOrdersLoaded()
    }
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

// 提交项目审批
const handleSubmitApproval = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要提交项目「${row.name}」进行审批吗？提交后将按照流程配置中的"项目立项"流程进行审批。`,
      '提交审批确认',
      { type: 'info', confirmButtonText: '确认提交', cancelButtonText: '取消' }
    )
    
    submitLoading.value = row.id
    const response = await submitProject(row.id)
    
    if (response.workflow_started) {
      ElMessage.success(response.message || '已成功提交审批，请等待审批人处理')
    } else {
      ElMessage.warning(response.message || '未配置审批流程，项目已直接启动')
    }
    
    loadProjects()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('提交审批失败:', error)
      ElMessage.error(error.response?.data?.error || error.response?.data?.detail || '提交审批失败')
    }
  } finally {
    submitLoading.value = null
  }
}

// 查看审批流程进度
const handleViewWorkflow = (row) => {
  showWorkflowProgress(row)
}

onMounted(() => {
  loadProjects()
  loadCustomers()
  loadUsers()
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
.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 10px;
  border: 1px solid #e4e7ed;
}
.table-toolbar span {
  font-size: 14px;
  color: #606266;
}
.order-detail-card {
  background-color: #fafafa;
}
.order-detail-card :deep(.el-card__body) {
  padding: 12px;
}
</style>

