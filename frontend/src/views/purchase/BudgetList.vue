<template>
  <div class="budget-list-container">
    <div class="page-header">
      <h2>采购预算管理</h2>
      <el-button type="primary" v-permission="'purchase:request:create'" @click="handleAdd">
        <el-icon><Plus /></el-icon> 新增预算
      </el-button>
    </div>
    
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">￥{{ formatAmount(stats.total_budget) }}</div>
          <div class="stat-label">预算总额</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-primary">
          <div class="stat-value">￥{{ formatAmount(stats.total_used) }}</div>
          <div class="stat-label">已使用</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-success">
          <div class="stat-value">￥{{ formatAmount(stats.total_available) }}</div>
          <div class="stat-label">可用余额</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.usage_rate || 0 }}%</div>
          <div class="stat-label">使用率</div>
          <el-progress :percentage="stats.usage_rate || 0" :show-text="false" :stroke-width="6" 
            :color="getProgressColor(stats.usage_rate)" />
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 过滤条件 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="queryParams">
        <el-form-item label="年度">
          <el-select v-model="queryParams.year" clearable>
            <el-option v-for="y in yearOptions" :key="y" :label="y + '年'" :value="y" />
          </el-select>
        </el-form-item>
        <el-form-item label="预算类型">
          <el-select v-model="queryParams.budget_type" clearable placeholder="全部">
            <el-option v-for="t in budgetTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" clearable placeholder="全部">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="待审批" value="PENDING" />
            <el-option label="已审批" value="APPROVED" />
            <el-option label="执行中" value="ACTIVE" />
            <el-option label="已关闭" value="CLOSED" />
            <el-option label="已超支" value="EXCEEDED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <!-- 数据表格 -->
    <el-card shadow="never">
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" border stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="budget_no" label="预算编号" width="140" />
        <el-table-column prop="name" label="预算名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="budget_type_display" label="类型" width="100" />
        <el-table-column prop="year" label="年度" width="80" />
        <el-table-column label="预算期间" width="200">
          <template #default="{ row }">
            {{ row.start_date }} ~ {{ row.end_date }}
          </template>
        </el-table-column>
        <el-table-column label="预算金额" width="130" align="right">
          <template #default="{ row }">
            <span class="amount">￥{{ formatAmount(row.total_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="已使用" width="130" align="right">
          <template #default="{ row }">
            <span class="amount used">￥{{ formatAmount(row.used_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="使用率" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.usage_rate || 0" :stroke-width="10"
              :color="getProgressColor(row.usage_rate)" :format="(p) => p.toFixed(1) + '%'" />
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="getStatusTag(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">查看</el-button>
            <el-button type="primary" link size="small" v-permission="'purchase:request:edit'" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button type="success" link size="small" @click="handleApprove(row)" v-if="row.status === 'PENDING'">审批</el-button>
            <el-button type="warning" link size="small" @click="handleActivate(row)" v-if="row.status === 'APPROVED'">激活</el-button>
            <el-button type="danger" link size="small" v-permission="'purchase:request:delete'" @click="handleDelete(row)" v-if="row.status === 'DRAFT'">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        class="pagination"
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :page-sizes="[10, 20, 50]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>
    
    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="预算编号" prop="budget_no">
              <el-input v-model="form.budget_no" placeholder="自动生成" :disabled="isEdit" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预算名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入预算名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="预算类型" prop="budget_type">
              <el-select v-model="form.budget_type" style="width: 100%">
                <el-option v-for="t in budgetTypes" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预算年度" prop="year">
              <el-select v-model="form.year" style="width: 100%">
                <el-option v-for="y in yearOptions" :key="y" :label="y + '年'" :value="y" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始日期" prop="start_date">
              <el-date-picker v-model="form.start_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="end_date">
              <el-date-picker v-model="form.end_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="预算总额" prop="total_amount">
              <el-input-number v-model="form.total_amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预警阈值(%)">
              <el-input-number v-model="form.warning_threshold" :min="0" :max="100" :precision="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注说明">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 查看详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="预算详情" width="900px">
      <template v-if="currentBudget">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="预算编号">{{ currentBudget.budget_no }}</el-descriptions-item>
          <el-descriptions-item label="预算名称">{{ currentBudget.name }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ currentBudget.budget_type_display }}</el-descriptions-item>
          <el-descriptions-item label="年度">{{ currentBudget.year }}</el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ currentBudget.start_date }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">{{ currentBudget.end_date }}</el-descriptions-item>
          <el-descriptions-item label="预算总额">￥{{ formatAmount(currentBudget.total_amount) }}</el-descriptions-item>
          <el-descriptions-item label="已使用">￥{{ formatAmount(currentBudget.used_amount) }}</el-descriptions-item>
          <el-descriptions-item label="可用余额">￥{{ formatAmount(currentBudget.available_amount) }}</el-descriptions-item>
          <el-descriptions-item label="使用率">
            <el-progress :percentage="currentBudget.usage_rate || 0" :stroke-width="16"
              :color="getProgressColor(currentBudget.usage_rate)" />
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTag(currentBudget.status)">{{ currentBudget.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="预警阈值">{{ currentBudget.warning_threshold }}%</el-descriptions-item>
        </el-descriptions>
        
        <el-divider>预算使用记录</el-divider>
        <el-table :data="usageRecords" border stripe max-height="300">
          <el-table-column prop="created_at" label="时间" width="160" />
          <el-table-column prop="usage_type_display" label="类型" width="100" />
          <el-table-column prop="reference_no" label="参考单号" width="140" />
          <el-table-column label="金额" width="120" align="right">
            <template #default="{ row }">
              <span :class="row.amount > 0 ? 'text-danger' : 'text-success'">
                {{ row.amount > 0 ? '+' : '' }}{{ formatAmount(row.amount) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="说明" />
        </el-table>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
getPurchaseBudgets, getPurchaseBudget, createPurchaseBudget, updatePurchaseBudget,
  deletePurchaseBudget, getPurchaseBudgetStatistics, getPurchaseBudgetUsageRecords,
  approvePurchaseBudget, activatePurchaseBudget
} from '@/api/purchase'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/purchase/budgets/', { onSuccess: () => fetchData() })


const loading = ref(false)
const submitLoading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const dialogTitle = ref('新增预算')
const isEdit = ref(false)
const currentBudget = ref(null)
const usageRecords = ref<any[]>([])
const formRef = ref(null)
const stats = ref<Record<string, any>>({})

const budgetTypes = ref([
  { value: 'ANNUAL', label: '年度预算' },
  { value: 'PROJECT', label: '项目预算' },
  { value: 'DEPARTMENT', label: '部门预算' },
  { value: 'CATEGORY', label: '品类预算' }
])

const currentYear = new Date().getFullYear()
const yearOptions = computed(() => {
  return Array.from({ length: 5 }, (_, i) => currentYear - 2 + i)
})

const queryParams = reactive({
  page: 1,
  page_size: 10,
  year: currentYear,
  budget_type: null,
  status: null
})

const form = reactive({
  budget_no: '',
  name: '',
  budget_type: 'ANNUAL',
  year: currentYear,
  start_date: `${currentYear}-01-01`,
  end_date: `${currentYear}-12-31`,
  total_amount: 0,
  warning_threshold: 80,
  description: ''
})

const rules = {
  budget_no: [{ required: true, message: '请输入预算编号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入预算名称', trigger: 'blur' }],
  budget_type: [{ required: true, message: '请选择预算类型', trigger: 'change' }],
  year: [{ required: true, message: '请选择预算年度', trigger: 'change' }],
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }],
  total_amount: [{ required: true, message: '请输入预算总额', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await getPurchaseBudgets(queryParams)
    tableData.value = data.results || data
    total.value = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    const data = await getPurchaseBudgetStatistics({ 
      year: queryParams.year 
    })
    stats.value = data
  } catch (e) {
    console.error(e)
  }
}

const resetQuery = () => {
  queryParams.year = currentYear
  queryParams.budget_type = null
  queryParams.status = null
  queryParams.page = 1
  fetchData()
  fetchStats()
}

const handleAdd = () => {
  isEdit.value = false
  dialogTitle.value = '新增预算'
  Object.assign(form, {
    budget_no: `BG-${currentYear}-${String(Date.now()).slice(-4)}`,
    name: '',
    budget_type: 'ANNUAL',
    year: currentYear,
    start_date: `${currentYear}-01-01`,
    end_date: `${currentYear}-12-31`,
    total_amount: 0,
    warning_threshold: 80,
    description: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  dialogTitle.value = '编辑预算'
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const data = await getPurchaseBudget(row.id)
    currentBudget.value = data
    
    const usageRes = await getPurchaseBudgetUsageRecords(row.id)
    usageRecords.value = usageRes
    
    viewDialogVisible.value = true
  } catch (e) {
    ElMessage.error('获取详情失败')
  }
}

const handleSubmit = async () => {
  const valid = await formRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updatePurchaseBudget(form.id, form)
      ElMessage.success('修改成功')
    } else {
      await createPurchaseBudget(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
    fetchStats()
  } catch (e) {
    console.error(e)
    ElMessage.error('操作失败')
  } finally {
    submitLoading.value = false
  }
}

const handleApprove = (row) => {
  ElMessageBox.confirm('确定要审批通过此预算吗？', '提示', { type: 'warning' })
    .then(async () => {
      await approvePurchaseBudget(row.id)
      ElMessage.success('审批成功')
      fetchData()
    })
}

const handleActivate = (row) => {
  ElMessageBox.confirm('确定要激活此预算吗？激活后可开始使用。', '提示', { type: 'warning' })
    .then(async () => {
      await activatePurchaseBudget(row.id)
      ElMessage.success('激活成功')
      fetchData()
    })
}

const handleDelete = (row) => {
  ElMessageBox.confirm('确定要删除此预算吗？', '提示', { type: 'warning' })
    .then(async () => {
      await deletePurchaseBudget(row.id)
      ElMessage.success('删除成功')
      fetchData()
      fetchStats()
    })
}

const formatAmount = (val) => {
  if (!val) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

const getProgressColor = (rate) => {
  if (rate >= 90) return '#f56c6c'
  if (rate >= 80) return '#e6a23c'
  if (rate >= 60) return '#409eff'
  return '#67c23a'
}

const getStatusTag = (status) => {
  const tags = {
    DRAFT: 'info',
    PENDING: 'warning',
    APPROVED: 'primary',
    ACTIVE: 'success',
    CLOSED: '',
    EXCEEDED: 'danger'
  }
  return tags[status] || ''
}

onMounted(() => {
  fetchData()
  fetchStats()
})
</script>

<style scoped>
.budget-list-container {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 16px 0;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.stat-primary .stat-value {
  color: #409eff;
}

.stat-success .stat-value {
  color: #67c23a;
}

.filter-card {
  margin-bottom: 16px;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

.amount {
  font-weight: 500;
}

.amount.used {
  color: #f56c6c;
}

.text-danger {
  color: #f56c6c;
}

.text-success {
  color: #67c23a;
}
</style>
