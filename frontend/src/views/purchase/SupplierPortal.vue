<template>
  <div class="supplier-portal">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="4">
        <el-card class="stat-card">
          <el-statistic title="待确认订单" :value="stats.pendingConfirmation" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card class="stat-card">
          <el-statistic title="进行中订单" :value="stats.inProgress" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card class="stat-card">
          <el-statistic title="待发货" :value="stats.readyToShip" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card class="stat-card warning">
          <el-statistic title="逾期订单" :value="stats.overdue" value-style="color: #E6A23C" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card class="stat-card danger">
          <el-statistic title="质量问题" :value="stats.qualityIssues" value-style="color: #F56C6C" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card class="stat-card">
          <el-statistic title="未读消息" :value="stats.unreadMessages" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 供应商账户管理 -->
    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <span>供应商账户管理</span>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>创建账户
          </el-button>
        </div>
      </template>

      <!-- 批量操作 -->

      <div v-if="selectedRows.length > 0" class="batch-toolbar">

        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>

        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>

        <el-button size="small" @click="batchExport">导出选中</el-button>

      </div>

      <el-table :data="accounts" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="supplier_name" label="供应商" min-width="150" />
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="email" label="邮箱" width="180" />
        <el-table-column prop="mobile" label="手机" width="130" />
        <el-table-column label="权限" width="200">
          <template #default="{ row }">
            <el-tag v-if="row.can_view_orders" size="small" type="info">查看订单</el-tag>
            <el-tag v-if="row.can_confirm_orders" size="small" type="success">确认订单</el-tag>
            <el-tag v-if="row.can_update_progress" size="small">更新进度</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login" label="最后登录" width="160">
          <template #default="{ row }">
            {{ row.last_login ? formatDate(row.last_login) : '从未登录' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="resetPassword(row)">重置密码</el-button>
            <el-button size="small" :type="row.is_active ? 'warning' : 'success'" 
                       @click="toggleActive(row)">
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 订单视图列表 -->
    <el-card class="main-card" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>供应商订单视图</span>
          <el-select v-model="orderFilter.status" placeholder="状态筛选" clearable style="width: 150px">
            <el-option label="待处理" value="PENDING" />
            <el-option label="已确认" value="CONFIRMED" />
            <el-option label="生产中" value="PRODUCING" />
            <el-option label="质检中" value="QUALITY_CHECK" />
            <el-option label="待发货" value="READY" />
            <el-option label="已发货" value="SHIPPED" />
          </el-select>
        </div>
      </template>

      <el-table :data="orderViews" v-loading="orderLoading" stripe>
        <el-table-column prop="order_no" label="订单号" width="140" />
        <el-table-column prop="supplier_name" label="供应商" width="150" />
        <el-table-column prop="order_date" label="订单日期" width="110" />
        <el-table-column prop="expected_date" label="交期" width="110" />
        <el-table-column label="确认状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.confirmed ? 'success' : 'warning'">
              {{ row.confirmed ? '已确认' : '待确认' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress_status_display" label="进度状态" width="100" />
        <el-table-column label="进度" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.progress_percentage" :status="getProgressStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="total_amount" label="金额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatMoney(row.total_amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="last_update" label="最后更新" width="160">
          <template #default="{ row }">
            {{ formatDate(row.last_update) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建账户对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建供应商账户" width="500px">
      <el-form :model="accountForm" :rules="accountRules" ref="accountFormRef" label-width="100px">
        <el-form-item label="供应商" prop="supplier">
          <el-select v-model="accountForm.supplier" placeholder="选择供应商" filterable style="width: 100%">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="accountForm.username" />
        </el-form-item>
        <el-form-item label="初始密码" prop="password">
          <el-input v-model="accountForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="accountForm.email" />
        </el-form-item>
        <el-form-item label="手机" prop="mobile">
          <el-input v-model="accountForm.mobile" />
        </el-form-item>
        <el-form-item label="权限">
          <el-checkbox v-model="accountForm.can_view_orders">查看订单</el-checkbox>
          <el-checkbox v-model="accountForm.can_confirm_orders">确认订单</el-checkbox>
          <el-checkbox v-model="accountForm.can_update_progress">更新进度</el-checkbox>
          <el-checkbox v-model="accountForm.can_upload_documents">上传文档</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createAccount" :loading="submitting">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getSupplierList } from '@/api/masterdata'
import {
getSupplierPortalDashboard, getSupplierAccounts, createSupplierAccount,
  resetSupplierAccountPassword, toggleSupplierAccountActive, getSupplierOrderViews
} from '@/api/purchase'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/masterdata/')


const loading = ref(false)
const orderLoading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)

const stats = ref({
  pendingConfirmation: 0,
  inProgress: 0,
  readyToShip: 0,
  overdue: 0,
  qualityIssues: 0,
  unreadMessages: 0
})

const accounts = ref<any[]>([])
const orderViews = ref<any[]>([])
const suppliers = ref<any[]>([])

const orderFilter = reactive({
  status: ''
})

const accountForm = reactive({
  supplier: null,
  username: '',
  password: '',
  email: '',
  mobile: '',
  can_view_orders: true,
  can_confirm_orders: true,
  can_update_progress: true,
  can_upload_documents: false
})

const accountRules = {
  supplier: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入初始密码', trigger: 'blur' }]
}

const accountFormRef = ref(null)

const formatDate = (date) => {
  if (!date) return ''
  return new Date(date).toLocaleString('zh-CN')
}

const formatMoney = (val) => {
  return Number(val || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

const getProgressStatus = (row) => {
  if (row.progress_percentage >= 100) return 'success'
  if (row.progress_percentage >= 50) return ''
  return 'warning'
}

const loadDashboard = async () => {
  try {
    const res = await getSupplierPortalDashboard()
    stats.value = {
      pendingConfirmation: res.pending_confirmation || 0,
      inProgress: res.in_progress || 0,
      readyToShip: res.ready_to_ship || 0,
      overdue: res.overdue || 0,
      qualityIssues: res.quality_issues || 0,
      unreadMessages: res.unread_messages || 0
    }
  } catch (e) {
    console.error('加载看板数据失败', e)
  }
}

const loadAccounts = async () => {
  loading.value = true
  try {
    const res = await getSupplierAccounts()
    accounts.value = res.results || res
  } catch (e) {
    ElMessage.error('加载账户列表失败')
  } finally {
    loading.value = false
  }
}

const loadOrderViews = async () => {
  orderLoading.value = true
  try {
    const params = {}
    if (orderFilter.status) params.status = orderFilter.status
    const res = await getSupplierOrderViews(params)
    orderViews.value = res.results || res
  } catch (e) {
    ElMessage.error('加载订单视图失败')
  } finally {
    orderLoading.value = false
  }
}

const loadSuppliers = async () => {
  try {
    const res = await getSupplierList({ page_size: 1000 })
    suppliers.value = res.results || res
  } catch (e) {
    console.error('加载供应商列表失败')
  }
}

const createAccount = async () => {
  try {
    await accountFormRef.value.validate()
    submitting.value = true
    await createSupplierAccount(accountForm)
    ElMessage.success('账户创建成功')
    showCreateDialog.value = false
    loadAccounts()
  } catch (e) {
    if (e !== false) ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

const resetPassword = async (row) => {
  try {
    await ElMessageBox.confirm('确定要重置该账户的密码吗？', '确认')
    const res = await resetSupplierAccountPassword(row.id)
    ElMessage.success(`密码已重置为: ${res.new_password}`)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('重置失败')
  }
}

const toggleActive = async (row) => {
  try {
    await toggleSupplierAccountActive(row.id)
    ElMessage.success('状态已更新')
    loadAccounts()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

watch(() => orderFilter.status, loadOrderViews)

onMounted(() => {
  loadDashboard()
  loadAccounts()
  loadOrderViews()
  loadSuppliers()
})
</script>

<style scoped>
.supplier-portal {
  padding: 20px;
}
.stat-row {
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
}
.stat-card.warning {
  border-left: 3px solid #E6A23C;
}
.stat-card.danger {
  border-left: 3px solid #F56C6C;
}
.main-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
