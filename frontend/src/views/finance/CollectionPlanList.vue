<template>
  <div class="collection-container">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon primary"><el-icon><Money /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">¥{{ formatNumber(statistics.total_amount) }}</div>
              <div class="stat-label">合同总额</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon success"><el-icon><Check /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">¥{{ formatNumber(statistics.collected_amount) }}</div>
              <div class="stat-label">已回款</div>
            </div>
          </div>
          <el-progress :percentage="statistics.collection_rate" :stroke-width="4" style="margin-top: 8px" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card warning">
          <div class="stat-content">
            <div class="stat-icon warning"><el-icon><Clock /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ statistics.upcoming_count }}</div>
              <div class="stat-label">即将到期</div>
            </div>
          </div>
          <div class="stat-sub">金额: ¥{{ formatNumber(statistics.upcoming_amount) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card danger">
          <div class="stat-content">
            <div class="stat-icon danger"><el-icon><Warning /></el-icon></div>
            <div class="stat-info">
              <div class="stat-value">{{ statistics.overdue_count }}</div>
              <div class="stat-label">已逾期</div>
            </div>
          </div>
          <div class="stat-sub">金额: ¥{{ formatNumber(statistics.overdue_amount) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>
        <div class="card-header">
          <el-tabs v-model="activeTab" @tab-change="handleTabChange">
            <el-tab-pane label="全部计划" name="all" />
            <el-tab-pane label="即将到期" name="upcoming" />
            <el-tab-pane label="已逾期" name="overdue" />
          </el-tabs>
          <el-button type="primary" @click="handleCreate"><el-icon><Plus /></el-icon> 新建计划</el-button>
        </div>
      </template>

      <!-- 筛选 -->
      <div class="filter-area">
        <el-input v-model="queryParams.search" placeholder="搜索计划编号/名称/客户" style="width: 240px" clearable @keyup.enter="handleSearch">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="queryParams.status" placeholder="状态" clearable @change="handleSearch">
          <el-option label="草稿" value="DRAFT" />
          <el-option label="已确认" value="CONFIRMED" />
          <el-option label="执行中" value="IN_PROGRESS" />
          <el-option label="已完成" value="COMPLETED" />
        </el-select>
      </div>

      <!-- 表格 -->
      <el-table :data="plans" v-loading="loading" stripe style="width: 100%; margin-top: 16px">
        <el-table-column prop="plan_no" label="计划编号" width="140" />
        <el-table-column prop="name" label="计划名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="customer_name" label="客户" width="150" />
        <el-table-column prop="project_name" label="项目" width="150" show-overflow-tooltip />
        <el-table-column label="合同金额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatNumber(row.total_amount) }}
          </template>
        </el-table-column>
        <el-table-column label="已回款" width="120" align="right">
          <template #default="{ row }">
            <span :class="{ 'text-success': row.collected_amount > 0 }">¥{{ formatNumber(row.collected_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="回款率" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.collection_rate" :stroke-width="6" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="节点/逾期" width="100">
          <template #default="{ row }">
            <span>{{ row.milestone_count }}个</span>
            <span v-if="row.overdue_count > 0" class="text-danger">({{ row.overdue_count }}逾期)</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" type="primary" @click="handleEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" destroy-on-close>
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="计划名称" prop="name">
              <el-input v-model="formData.name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户" prop="customer">
              <el-select v-model="formData.customer" filterable placeholder="选择客户" style="width: 100%">
                <el-option v-for="c in customerOptions" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="关联项目">
              <el-select v-model="formData.project" filterable clearable placeholder="选择项目" style="width: 100%">
                <el-option v-for="p in projectOptions" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="合同总金额" prop="total_amount">
              <el-input-number v-model="formData.total_amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="formData.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="回款计划详情" size="60%">
      <div v-if="currentPlan" class="detail-content">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="计划编号">{{ currentPlan.plan_no }}</el-descriptions-item>
          <el-descriptions-item label="计划名称">{{ currentPlan.name }}</el-descriptions-item>
          <el-descriptions-item label="客户">{{ currentPlan.customer_name }}</el-descriptions-item>
          <el-descriptions-item label="项目">{{ currentPlan.project_name }}</el-descriptions-item>
          <el-descriptions-item label="合同金额">¥{{ formatNumber(currentPlan.total_amount) }}</el-descriptions-item>
          <el-descriptions-item label="已回款">¥{{ formatNumber(currentPlan.collected_amount) }}</el-descriptions-item>
          <el-descriptions-item label="回款率">
            <el-progress :percentage="currentPlan.collection_rate" :stroke-width="8" style="width: 200px" />
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentPlan.status)">{{ currentPlan.status_display }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <h4 style="margin: 20px 0 10px">回款节点</h4>
        <el-table :data="currentPlan.milestones || []" stripe>
          <el-table-column prop="name" label="节点名称" />
          <el-table-column label="类型">
            <template #default="{ row }">{{ row.milestone_type_display }}</template>
          </el-table-column>
          <el-table-column label="计划金额" align="right">
            <template #default="{ row }">¥{{ formatNumber(row.planned_amount) }}</template>
          </el-table-column>
          <el-table-column label="已收金额" align="right">
            <template #default="{ row }">
              <span :class="{ 'text-success': row.collected_amount > 0 }">¥{{ formatNumber(row.collected_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="planned_date" label="计划日期" />
          <el-table-column label="状态">
            <template #default="{ row }">
              <el-tag :type="getMilestoneStatusType(row.status, row.is_overdue)">
                {{ row.is_overdue ? '已逾期' : row.status_display }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button size="small" @click="handleAddRecord(row)">收款</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>

    <!-- 收款对话框 -->
    <el-dialog v-model="recordDialogVisible" title="添加收款记录" width="500px">
      <el-form :model="recordData" label-width="100px">
        <el-form-item label="收款金额">
          <el-input-number v-model="recordData.amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="收款日期">
          <el-date-picker v-model="recordData.collection_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="付款方式">
          <el-select v-model="recordData.payment_method" style="width: 100%">
            <el-option label="银行转账" value="BANK" />
            <el-option label="支票" value="CHECK" />
            <el-option label="现金" value="CASH" />
            <el-option label="承兑汇票" value="ACCEPTANCE" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="交易流水号">
          <el-input v-model="recordData.transaction_no" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="recordData.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="recordDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRecord" :loading="recording">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search, Money, Check, Clock, Warning } from '@element-plus/icons-vue'
import {
  getCollectionPlanList,
  getCollectionPlan,
  getCollectionPlanStatistics,
  getOverdueCollections,
  getUpcomingCollections,
  createCollectionPlan,
  updateCollectionPlan,
  addCollectionRecord
} from '@/api/finance/collection'
import { getCustomerList } from '@/api/masterdata/customer'
import { getProjectList } from '@/api/projects/project'

const loading = ref(false)
const submitting = ref(false)
const recording = ref(false)
const dialogVisible = ref(false)
const detailVisible = ref(false)
const recordDialogVisible = ref(false)
const dialogTitle = ref('新建回款计划')
const activeTab = ref('all')
const plans = ref([])
const total = ref(0)
const customerOptions = ref([])
const projectOptions = ref([])
const currentPlan = ref(null)
const currentMilestone = ref(null)

const statistics = reactive({
  total_amount: 0,
  collected_amount: 0,
  remaining_amount: 0,
  collection_rate: 0,
  overdue_count: 0,
  overdue_amount: 0,
  upcoming_count: 0,
  upcoming_amount: 0
})

const queryParams = reactive({
  search: '',
  status: '',
  page: 1,
  page_size: 20
})

const formRef = ref(null)
const formData = reactive({
  id: null,
  name: '',
  customer: null,
  project: null,
  total_amount: 0,
  notes: ''
})

const recordData = reactive({
  milestone_id: null,
  amount: 0,
  collection_date: '',
  payment_method: 'BANK',
  transaction_no: '',
  notes: ''
})

const formRules = {
  name: [{ required: true, message: '请输入计划名称', trigger: 'blur' }],
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  total_amount: [{ required: true, message: '请输入合同总金额', trigger: 'blur' }]
}

const formatNumber = (num) => {
  return num ? Number(num).toLocaleString() : '0'
}

const getStatusType = (status) => {
  const map = { DRAFT: 'info', CONFIRMED: '', IN_PROGRESS: 'warning', COMPLETED: 'success', CANCELLED: 'danger' }
  return map[status] || ''
}

const getMilestoneStatusType = (status, isOverdue) => {
  if (isOverdue) return 'danger'
  const map = { PENDING: 'info', PARTIAL: 'warning', COLLECTED: 'success', CANCELLED: 'info' }
  return map[status] || ''
}

const fetchData = async () => {
  loading.value = true
  try {
    let res
    if (activeTab.value === 'overdue') {
      res = await getOverdueCollections()
      // 需要转换数据格式
      plans.value = []
    } else if (activeTab.value === 'upcoming') {
      res = await getUpcomingCollections()
      plans.value = []
    } else {
      res = await getCollectionPlanList(queryParams)
      plans.value = res.results || res || []
      total.value = res.count || plans.value.length
    }
  } catch (error) {
    console.error('获取数据失败', error)
  } finally {
    loading.value = false
  }
}

const fetchStatistics = async () => {
  try {
    const res = await getCollectionPlanStatistics()
    Object.assign(statistics, res || {})
  } catch (error) {
    console.error('获取统计失败', error)
  }
}

const fetchOptions = async () => {
  try {
    const [customerRes, projectRes] = await Promise.all([
      getCustomerList({ page_size: 500 }),
      getProjectList({ page_size: 500 })
    ])
    customerOptions.value = customerRes.results || customerRes || []
    projectOptions.value = projectRes.results || projectRes || []
  } catch (error) {
    console.error('获取选项失败', error)
  }
}

const handleSearch = () => {
  queryParams.page = 1
  fetchData()
}

const handleTabChange = () => {
  fetchData()
}

const handleCreate = () => {
  dialogTitle.value = '新建回款计划'
  Object.assign(formData, { id: null, name: '', customer: null, project: null, total_amount: 0, notes: '' })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑回款计划'
  Object.assign(formData, row)
  dialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const res = await getCollectionPlan(row.id)
    currentPlan.value = res
    detailVisible.value = true
  } catch (error) {
    ElMessage.error('获取详情失败')
  }
}

const handleSubmit = async () => {
  const valid = await formRef.value.validate()
  if (!valid) return

  submitting.value = true
  try {
    if (formData.id) {
      await updateCollectionPlan(formData.id, formData)
      ElMessage.success('更新成功')
    } else {
      await createCollectionPlan(formData)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
    fetchStatistics()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

const handleAddRecord = (milestone) => {
  currentMilestone.value = milestone
  recordData.milestone_id = milestone.id
  recordData.amount = milestone.planned_amount - milestone.collected_amount
  recordData.collection_date = new Date().toISOString().split('T')[0]
  recordData.payment_method = 'BANK'
  recordData.transaction_no = ''
  recordData.notes = ''
  recordDialogVisible.value = true
}

const submitRecord = async () => {
  recording.value = true
  try {
    await addCollectionRecord(recordData.milestone_id, recordData)
    ElMessage.success('收款记录添加成功')
    recordDialogVisible.value = false
    // 刷新详情
    if (currentPlan.value) {
      const res = await getCollectionPlan(currentPlan.value.id)
      currentPlan.value = res
    }
    fetchStatistics()
  } catch (error) {
    ElMessage.error('添加失败')
  } finally {
    recording.value = false
  }
}

onMounted(() => {
  fetchData()
  fetchStatistics()
  fetchOptions()
})
</script>

<style scoped lang="scss">
.collection-container {
  padding: 20px;
}

.stat-cards {
  margin-bottom: 20px;
}

.stat-card {
  border-radius: 8px;
  
  &.warning { border-left: 4px solid #E6A23C; }
  &.danger { border-left: 4px solid #F56C6C; }
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  
  &.primary { background: #ecf5ff; color: #409EFF; }
  &.success { background: #f0f9eb; color: #67C23A; }
  &.warning { background: #fdf6ec; color: #E6A23C; }
  &.danger { background: #fef0f0; color: #F56C6C; }
}

.stat-info {
  .stat-value {
    font-size: 24px;
    font-weight: 600;
    color: #303133;
  }
  
  .stat-label {
    font-size: 13px;
    color: #909399;
  }
}

.stat-sub {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-area {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.text-success { color: #67C23A; }
.text-danger { color: #F56C6C; }

.detail-content {
  padding: 0 20px;
}
</style>
