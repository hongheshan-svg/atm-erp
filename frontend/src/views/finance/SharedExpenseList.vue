<template>
  <div class="shared-expense-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>公共费用分摊</span>
          <el-button type="primary" :icon="Plus" v-permission="'finance:shared_expense:create'" @click="handleAdd">新增公共费用</el-button>
        </div>
      </template>

      <!-- Search Form -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="费用类别">
          <el-select v-model="searchForm.category" placeholder="费用类别" clearable style="width: 120px;">
            <el-option label="房租" value="RENT" />
            <el-option label="水电费" value="UTILITIES" />
            <el-option label="设备折旧" value="EQUIPMENT" />
            <el-option label="IT服务" value="IT" />
            <el-option label="行政费用" value="ADMIN" />
            <el-option label="保险费" value="INSURANCE" />
            <el-option label="折旧" value="DEPRECIATION" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="状态" clearable style="width: 120px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="待分摊" value="PENDING" />
            <el-option label="已分摊" value="ALLOCATED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-permission="'finance:shared_expense:delete'" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" v-permission="'finance:shared_expense:delete'" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <!-- Data Table -->
      <el-table :data="expenses" border v-loading="loading" @selection-change="handleSelectionChange">
        <el-table-column v-permission="'finance:shared_expense:delete'" v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="expense_no" label="费用编号" width="140" />
        <el-table-column prop="name" label="费用名称" min-width="150" />
        <el-table-column prop="category_display" label="类别" width="100" />
        <el-table-column prop="expense_date" label="费用日期" width="110" />
        <el-table-column prop="amount" label="金额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ Number(row.amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}
          </template>
        </el-table-column>
        <el-table-column prop="allocation_method_display" label="分摊方式" width="100" />
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分摊期间" width="180">
          <template #default="{ row }">
            {{ row.period_start }} ~ {{ row.period_end }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleView(row)">详情</el-button>
            <el-button v-if="row.status === 'DRAFT' || row.status === 'PENDING'" type="success" link @click="handleAllocate(row)">分摊</el-button>
            <el-button v-if="row.status === 'ALLOCATED'" type="warning" link @click="handleCancelAllocation(row)">撤销</el-button>
            <el-button v-if="canDelete && row.status === 'DRAFT'" type="danger" link @click="deleteRow(row)" :loading="deleteLoading">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 20px;"
      />
    </el-card>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑公共费用' : '新增公共费用'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="费用名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入费用名称" />
        </el-form-item>
        <el-form-item label="费用类别" prop="category">
          <el-select v-model="form.category" style="width: 100%;">
            <el-option label="房租" value="RENT" />
            <el-option label="水电费" value="UTILITIES" />
            <el-option label="设备折旧" value="EQUIPMENT" />
            <el-option label="IT服务" value="IT" />
            <el-option label="行政费用" value="ADMIN" />
            <el-option label="保险费" value="INSURANCE" />
            <el-option label="折旧" value="DEPRECIATION" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="费用金额" prop="amount">
          <el-input-number v-model="form.amount" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="费用日期" prop="expense_date">
          <el-date-picker v-model="form.expense_date" type="date" placeholder="选择日期" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="分摊期间" prop="period">
          <el-date-picker v-model="form.period" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="分摊方式" prop="allocation_method">
          <el-select v-model="form.allocation_method" style="width: 100%;">
            <el-option label="平均分摊" value="EQUAL" />
            <el-option label="按收入比例" value="REVENUE" />
            <el-option label="按人员数量" value="HEADCOUNT" />
            <el-option label="按工时比例" value="LABOR_HOURS" />
            <el-option label="按预算比例" value="BUDGET" />
            <el-option label="自定义比例" value="CUSTOM" />
          </el-select>
        </el-form-item>
        <el-form-item label="费用说明">
          <el-input v-model="form.description" type="textarea" rows="2" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- Allocation Dialog -->
    <el-dialog v-model="allocateDialogVisible" title="费用分摊" width="800px">
      <div v-if="currentExpense">
        <el-descriptions :column="2" border class="mb-20">
          <el-descriptions-item label="费用编号">{{ currentExpense.expense_no }}</el-descriptions-item>
          <el-descriptions-item label="费用名称">{{ currentExpense.name }}</el-descriptions-item>
          <el-descriptions-item label="费用金额">¥{{ Number(currentExpense.amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}</el-descriptions-item>
          <el-descriptions-item label="分摊方式">{{ currentExpense.allocation_method_display }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">选择分摊项目</el-divider>
        
        <el-checkbox-group v-model="selectedProjectIds" class="project-select">
          <el-checkbox v-for="project in projects" :key="project.id" :value="project.id">
            {{ project.code }} - {{ project.name }}
          </el-checkbox>
        </el-checkbox-group>

        <!-- Custom ratios for CUSTOM method -->
        <template v-if="currentExpense.allocation_method === 'CUSTOM' && selectedProjectIds.length > 0">
          <el-divider content-position="left">自定义分摊比例</el-divider>
          <el-form label-width="200px">
            <el-form-item v-for="pid in selectedProjectIds" :key="pid" :label="getProjectLabel(pid)">
              <el-input-number v-model="customRatios[pid]" :min="0" :max="100" :precision="2" />
              <span class="unit-label">%</span>
            </el-form-item>
          </el-form>
        </template>

        <!-- Preview -->
        <template v-if="allocationPreview.length > 0">
          <el-divider content-position="left">分摊预览</el-divider>
          <el-table :data="allocationPreview" border size="small">
            <el-table-column prop="project_code" label="项目编号" width="120" />
            <el-table-column prop="project_name" label="项目名称" />
            <el-table-column prop="ratio" label="分摊比例" width="100" align="right">
              <template #default="{ row }">
                {{ (row.ratio * 100).toFixed(2) }}%
              </template>
            </el-table-column>
            <el-table-column prop="amount" label="分摊金额" width="120" align="right">
              <template #default="{ row }">
                ¥{{ Number(row.amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
      <template #footer>
        <el-button @click="allocateDialogVisible = false">取消</el-button>
        <el-button type="info" @click="handlePreviewAllocation" :disabled="selectedProjectIds.length === 0">预览分摊</el-button>
        <el-button type="primary" @click="handleConfirmAllocation" :disabled="allocationPreview.length === 0" :loading="submitting">确认分摊</el-button>
      </template>
    </el-dialog>

    <!-- Detail Dialog -->
    <el-dialog v-model="detailDialogVisible" title="费用详情" width="800px">
      <div v-if="currentExpense">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="费用编号">{{ currentExpense.expense_no }}</el-descriptions-item>
          <el-descriptions-item label="费用名称">{{ currentExpense.name }}</el-descriptions-item>
          <el-descriptions-item label="费用类别">{{ currentExpense.category_display }}</el-descriptions-item>
          <el-descriptions-item label="费用金额">¥{{ Number(currentExpense.amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}</el-descriptions-item>
          <el-descriptions-item label="费用日期">{{ currentExpense.expense_date }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentExpense.status)">{{ currentExpense.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="分摊期间">{{ currentExpense.period_start }} ~ {{ currentExpense.period_end }}</el-descriptions-item>
          <el-descriptions-item label="分摊方式">{{ currentExpense.allocation_method_display }}</el-descriptions-item>
          <el-descriptions-item label="费用说明" :span="2">{{ currentExpense.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ currentExpense.notes || '-' }}</el-descriptions-item>
        </el-descriptions>

        <template v-if="currentExpense.allocations && currentExpense.allocations.length > 0">
          <el-divider content-position="left">分摊明细</el-divider>
          <el-table :data="currentExpense.allocations" border size="small">
            <el-table-column prop="project_code" label="项目编号" width="120" />
            <el-table-column prop="project_name" label="项目名称" />
            <el-table-column prop="allocation_ratio" label="分摊比例" width="100" align="right">
              <template #default="{ row }">
                {{ (Number(row.allocation_ratio) * 100).toFixed(2) }}%
              </template>
            </el-table-column>
            <el-table-column prop="allocated_amount" label="分摊金额" width="120" align="right">
              <template #default="{ row }">
                ¥{{ Number(row.allocated_amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSharedExpenses, getSharedExpense, createSharedExpense, patchSharedExpense, calculateSharedExpenseAllocation, allocateSharedExpense, cancelSharedExpenseAllocation } from '@/api/finance'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'
import { usePermissionStore } from '@/stores/permission'
import { getProjectList } from '@/api/projects/project'

// 权限检查
const { canDelete } = usePermission()
const permissionStore = usePermissionStore()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/finance/shared-expenses/',
  { onSuccess: () => loadData(), confirmTitle: '删除公共费用', confirmMessage: '确定要删除该公共费用吗？' }
)

const loading = ref(false)
const expenses = ref([])
const projects = ref([])
const projectsLoaded = ref(false)

const searchForm = reactive({
  category: null,
  status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// Dialog states
const dialogVisible = ref(false)
const allocateDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const isEdit = ref(false)
const currentExpense = ref(null)
const selectedProjectIds = ref([])
const customRatios = ref({})
const allocationPreview = ref([])

const form = reactive({
  id: null,
  name: '',
  category: 'OTHER',
  amount: 0,
  expense_date: null,
  period: null,
  allocation_method: 'EQUAL',
  description: '',
  notes: ''
})

const rules = {
  name: [{ required: true, message: '请输入费用名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择费用类别', trigger: 'change' }],
  amount: [{ required: true, message: '请输入费用金额', trigger: 'blur' }],
  expense_date: [{ required: true, message: '请选择费用日期', trigger: 'change' }],
  period: [{ required: true, message: '请选择分摊期间', trigger: 'change' }],
  allocation_method: [{ required: true, message: '请选择分摊方式', trigger: 'change' }]
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'PENDING': 'warning',
    'ALLOCATED': 'success',
    'CANCELLED': 'danger'
  }
  return types[status] || 'info'
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const response = await getSharedExpenses(params)
    expenses.value = response.results || []
    pagination.total = response.count || 0
  } catch (error) {
    console.error('加载数据失败:', error)
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  if (projectsLoaded.value) {
    return true
  }

  try {
    const response = await getProjectList({ is_deleted: false, page_size: 100 })
    projects.value = response.results || response || [] || []
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

const resetSearch = () => {
  searchForm.category = null
  searchForm.status = null
  loadData()
}

const handleAdd = () => {
  isEdit.value = false
  form.id = null
  form.name = ''
  form.category = 'OTHER'
  form.amount = 0
  form.expense_date = null
  form.period = null
  form.allocation_method = 'EQUAL'
  form.description = ''
  form.notes = ''
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value?.validate()
  
  submitting.value = true
  try {
    const payload = {
      name: form.name,
      category: form.category,
      amount: form.amount,
      expense_date: form.expense_date,
      period_start: form.period?.[0],
      period_end: form.period?.[1],
      allocation_method: form.allocation_method,
      description: form.description,
      notes: form.notes,
      status: 'PENDING'
    }
    
    if (isEdit.value) {
      await patchSharedExpense(form.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createSharedExpense(payload)
      ElMessage.success('创建成功')
    }
    
    dialogVisible.value = false
    loadData()
  } catch (error) {
    console.error('保存失败:', error)
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

const handleView = async (expense) => {
  try {
    const response = await getSharedExpense(expense.id)
    currentExpense.value = response
    detailDialogVisible.value = true
  } catch (error) {
    console.error('加载详情失败:', error)
  }
}

const handleAllocate = async (expense) => {
  await ensureProjectsLoaded()
  currentExpense.value = expense
  selectedProjectIds.value = []
  customRatios.value = {}
  allocationPreview.value = []
  allocateDialogVisible.value = true
}

const getProjectLabel = (pid) => {
  const project = projects.value.find(p => p.id === pid)
  return project ? `${project.code} - ${project.name}` : pid
}

const handlePreviewAllocation = async () => {
  if (selectedProjectIds.value.length === 0) {
    ElMessage.warning('请选择至少一个项目')
    return
  }
  
  try {
    const payload = {
      project_ids: selectedProjectIds.value
    }
    
    if (currentExpense.value.allocation_method === 'CUSTOM') {
      payload.custom_ratios = customRatios.value
    }
    
    const response = await calculateSharedExpenseAllocation(currentExpense.value.id, payload)
    allocationPreview.value = response.allocations || []
  } catch (error) {
    console.error('计算分摊失败:', error)
    ElMessage.error('计算分摊失败')
  }
}

const handleConfirmAllocation = async () => {
  submitting.value = true
  try {
    const payload = {
      project_ids: selectedProjectIds.value
    }
    
    if (currentExpense.value.allocation_method === 'CUSTOM') {
      payload.custom_ratios = customRatios.value
    }
    
    await allocateSharedExpense(currentExpense.value.id, payload)
    
    ElMessage.success('分摊成功')
    allocateDialogVisible.value = false
    loadData()
  } catch (error) {
    console.error('分摊失败:', error)
    ElMessage.error(error.response?.data?.error || '分摊失败')
  } finally {
    submitting.value = false
  }
}

const handleCancelAllocation = async (expense) => {
  try {
    await ElMessageBox.confirm('确定要撤销该费用的分摊吗？', '确认撤销', { type: 'warning' })
    
    await cancelSharedExpenseAllocation(expense.id)
    ElMessage.success('撤销成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('撤销失败:', error)
      ElMessage.error('撤销失败')
    }
  }
}

// handleDelete 已被 useBatchDelete 的 deleteRow 替代

// Reset preview when project selection changes
watch(selectedProjectIds, () => {
  allocationPreview.value = []
})

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.shared-expense-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 10px;
}

.mb-20 {
  margin-bottom: 20px;
}

.project-select {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.project-select .el-checkbox {
  margin-right: 0;
  width: 250px;
}

.unit-label {
  margin-left: 8px;
  color: #999;
}
</style>

