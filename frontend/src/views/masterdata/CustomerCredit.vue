<template>
  <div class="credit-container">
    <div class="page-header">
      <h2>客户信用管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="handleInitLevels">初始化等级</el-button>
      </div>
    </div>
    
    <el-tabs v-model="activeTab">
      <el-tab-pane label="信用列表" name="list">
        <el-card shadow="never">
          <template #header>
            <el-form :inline="true">
              <el-form-item>
                <el-input v-model="queryParams.search" placeholder="搜索客户" clearable @clear="fetchList" />
              </el-form-item>
              <el-form-item>
                <el-select v-model="queryParams.credit_level" placeholder="信用等级" clearable @change="fetchList">
                  <el-option v-for="level in creditLevels" :key="level.id" :label="level.name" :value="level.id" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchList">
                  <el-option label="正常" value="NORMAL" />
                  <el-option label="预警" value="WARNING" />
                  <el-option label="冻结" value="FROZEN" />
                  <el-option label="黑名单" value="BLACKLIST" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="fetchList">查询</el-button>
              </el-form-item>
            </el-form>
          </template>
          
          <el-table :data="creditList" v-loading="loading" border stripe>
            <el-table-column prop="customer_code" label="客户编码" width="120" />
            <el-table-column prop="customer_name" label="客户名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="level_name" label="信用等级" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.level_name">{{ row.level_name }}</el-tag>
                <span v-else class="text-muted">未评级</span>
              </template>
            </el-table-column>
            <el-table-column label="信用额度" width="140" align="right">
              <template #default="{ row }">
                <span class="amount">¥{{ formatNumber(row.credit_limit) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="已用/可用" width="180" align="right">
              <template #default="{ row }">
                <span class="text-danger">¥{{ formatNumber(row.used_amount) }}</span>
                <span> / </span>
                <span class="text-success">¥{{ formatNumber(row.available_credit) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="使用率" width="120">
              <template #default="{ row }">
                <el-progress :percentage="row.usage_rate" :status="getUsageStatus(row.usage_rate)" :stroke-width="10" />
              </template>
            </el-table-column>
            <el-table-column prop="payment_days" label="账期" width="80" align="center">
              <template #default="{ row }">
                {{ row.payment_days }}天
              </template>
            </el-table-column>
            <el-table-column prop="status_display" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleAdjust(row)">调整</el-button>
                <el-button type="warning" link size="small" @click="handleChangeStatus(row)">状态</el-button>
                <el-button type="info" link size="small" @click="handleViewDetail(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
          
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.size"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next"
            @size-change="fetchList"
            @current-change="fetchList"
            style="margin-top: 16px; justify-content: flex-end"
          />
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="信用等级" name="levels">
        <el-card shadow="never">
          <el-table :data="creditLevels" border stripe>
            <el-table-column prop="code" label="等级编码" width="100" />
            <el-table-column prop="name" label="等级名称" width="150" />
            <el-table-column label="默认额度" width="140" align="right">
              <template #default="{ row }">
                ¥{{ formatNumber(row.default_credit_limit) }}
              </template>
            </el-table-column>
            <el-table-column prop="default_payment_days" label="默认账期" width="100" align="center">
              <template #default="{ row }">
                {{ row.default_payment_days }}天
              </template>
            </el-table-column>
            <el-table-column prop="discount_rate" label="折扣率" width="100" align="center">
              <template #default="{ row }">
                {{ row.discount_rate }}%
              </template>
            </el-table-column>
            <el-table-column prop="customer_count" label="客户数" width="100" align="center" />
            <el-table-column prop="description" label="说明" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="预警客户" name="warning">
        <el-card shadow="never">
          <el-table :data="warningList" border stripe>
            <el-table-column prop="customer_name" label="客户名称" width="200" />
            <el-table-column prop="level_name" label="等级" width="100" />
            <el-table-column label="使用率" width="140">
              <template #default="{ row }">
                <el-progress :percentage="row.usage_rate" status="warning" :stroke-width="10" />
              </template>
            </el-table-column>
            <el-table-column label="额度情况" width="200">
              <template #default="{ row }">
                已用 ¥{{ formatNumber(row.used_amount) }} / 额度 ¥{{ formatNumber(row.credit_limit) }}
              </template>
            </el-table-column>
            <el-table-column prop="overdue_times" label="逾期次数" width="100" align="center" />
            <el-table-column prop="status_display" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="统计分析" name="stats">
        <el-row :gutter="16">
          <el-col :span="6" v-for="(stat, key) in statistics" :key="key">
            <el-card shadow="never" class="stat-card">
              <div class="stat-value">{{ stat.value }}</div>
              <div class="stat-label">{{ stat.label }}</div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
    
    <!-- 额度调整对话框 -->
    <el-dialog v-model="adjustDialogVisible" title="调整信用额度" width="500px">
      <el-form :model="adjustForm" label-width="100px">
        <el-form-item label="客户">
          <span>{{ currentCredit?.customer_name }}</span>
        </el-form-item>
        <el-form-item label="当前额度">
          <span class="amount">¥{{ formatNumber(currentCredit?.credit_limit || 0) }}</span>
        </el-form-item>
        <el-form-item label="调整类型">
          <el-radio-group v-model="adjustForm.adjustment_type">
            <el-radio label="INCREASE">增加</el-radio>
            <el-radio label="DECREASE">减少</el-radio>
            <el-radio label="TEMP_INCREASE">临时增加</el-radio>
            <el-radio label="RESET">重置</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="调整金额">
          <el-input-number v-model="adjustForm.amount" :min="0" :step="10000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="到期日期" v-if="adjustForm.adjustment_type === 'TEMP_INCREASE'">
          <el-date-picker v-model="adjustForm.expire_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="调整原因">
          <el-input v-model="adjustForm.reason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adjustDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAdjust" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>
    
    <!-- 状态变更对话框 -->
    <el-dialog v-model="statusDialogVisible" title="变更信用状态" width="400px">
      <el-form :model="statusForm" label-width="80px">
        <el-form-item label="客户">
          <span>{{ currentCredit?.customer_name }}</span>
        </el-form-item>
        <el-form-item label="当前状态">
          <el-tag :type="getStatusType(currentCredit?.status)">{{ currentCredit?.status_display }}</el-tag>
        </el-form-item>
        <el-form-item label="新状态">
          <el-select v-model="statusForm.status" style="width: 100%">
            <el-option label="正常" value="NORMAL" />
            <el-option label="预警" value="WARNING" />
            <el-option label="冻结" value="FROZEN" />
            <el-option label="黑名单" value="BLACKLIST" />
          </el-select>
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="statusForm.reason" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="statusDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitStatus" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 信用详情 -->
    <el-dialog v-model="creditDetailVisible" title="客户信用详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="客户">{{ creditDetail.customer_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="信用额度">¥{{ creditDetail.credit_limit?.toLocaleString() || 0 }}</el-descriptions-item>
        <el-descriptions-item label="已用额度">¥{{ creditDetail.used_amount?.toLocaleString() || 0 }}</el-descriptions-item>
        <el-descriptions-item label="剩余额度">¥{{ creditDetail.available_amount?.toLocaleString() || 0 }}</el-descriptions-item>
        <el-descriptions-item label="信用等级">{{ creditDetail.credit_grade || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ creditDetail.status_display || creditDetail.status }}</el-descriptions-item>
        <el-descriptions-item label="最后评估日期">{{ creditDetail.last_evaluation_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ creditDetail.created_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ creditDetail.remarks || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="creditDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getCreditLevelList, getCustomerCreditList, getCustomerCredit, getCreditWarningList, getCreditStatistics, initCreditLevels, adjustCredit, changeCreditStatus } from '@/api/masterdata'

const activeTab = ref('list')
const loading = ref(false)
const creditDetailVisible = ref(false)
const creditDetail = ref({})
const submitLoading = ref(false)

const creditList = ref([])
const creditLevels = ref([])
const warningList = ref([])
const statsData = ref({})

const queryParams = reactive({
  search: '',
  credit_level: null,
  status: null
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

const adjustDialogVisible = ref(false)
const statusDialogVisible = ref(false)
const currentCredit = ref(null)

const adjustForm = reactive({
  adjustment_type: 'INCREASE',
  amount: 0,
  expire_date: '',
  reason: ''
})

const statusForm = reactive({
  status: 'NORMAL',
  reason: ''
})

const statistics = computed(() => {
  if (!statsData.value) return {}
  return {
    total: { label: '客户总数', value: statsData.value.total_customers || 0 },
    limit: { label: '总信用额度', value: '¥' + formatNumber(statsData.value.total_credit_limit || 0) },
    used: { label: '已用额度', value: '¥' + formatNumber(statsData.value.total_used_amount || 0) },
    rate: { label: '整体使用率', value: (statsData.value.overall_usage_rate || 0) + '%' }
  }
})

const fetchList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.size,
      ...queryParams
    }
    const data = await getCustomerCreditList(params)
    creditList.value = data.results || data
    pagination.total = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchLevels = async () => {
  try {
    const data = await getCreditLevelList()
    creditLevels.value = data.results || data
  } catch (e) {
    console.error(e)
  }
}

const fetchWarningList = async () => {
  try {
    const data = await getCreditWarningList({ threshold: 80 })
    warningList.value = data
  } catch (e) {
    console.error(e)
  }
}

const fetchStatistics = async () => {
  try {
    const data = await getCreditStatistics()
    statsData.value = data
  } catch (e) {
    console.error(e)
  }
}

const handleInitLevels = async () => {
  try {
    const data = await initCreditLevels()
    ElMessage.success(`初始化完成，新增 ${data.created} 个等级`)
    fetchLevels()
  } catch (e) {
    ElMessage.error('初始化失败')
  }
}

const handleAdjust = (row) => {
  currentCredit.value = row
  Object.assign(adjustForm, {
    adjustment_type: 'INCREASE',
    amount: 0,
    expire_date: '',
    reason: ''
  })
  adjustDialogVisible.value = true
}

const handleChangeStatus = (row) => {
  currentCredit.value = row
  statusForm.status = row.status
  statusForm.reason = ''
  statusDialogVisible.value = true
}

const handleViewDetail = async (row) => {
  try {
    const res = await getCustomerCredit(row.id)
    creditDetail.value = res.data || res
  } catch (error) {
    console.error(error)
    creditDetail.value = row
  }
  creditDetailVisible.value = true
}

const submitAdjust = async () => {
  if (!adjustForm.amount) {
    ElMessage.warning('请输入调整金额')
    return
  }
  
  submitLoading.value = true
  try {
    await adjustCredit(currentCredit.value.id, adjustForm)
    ElMessage.success('调整成功')
    adjustDialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error('调整失败')
  } finally {
    submitLoading.value = false
  }
}

const submitStatus = async () => {
  submitLoading.value = true
  try {
    await changeCreditStatus(currentCredit.value.id, statusForm)
    ElMessage.success('状态变更成功')
    statusDialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error('状态变更失败')
  } finally {
    submitLoading.value = false
  }
}

const formatNumber = (num) => {
  if (!num) return '0'
  return parseFloat(num).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const getUsageStatus = (rate) => {
  if (rate >= 90) return 'exception'
  if (rate >= 70) return 'warning'
  return 'success'
}

const getStatusType = (status) => {
  const types = {
    NORMAL: 'success',
    WARNING: 'warning',
    FROZEN: 'danger',
    BLACKLIST: 'info'
  }
  return types[status] || ''
}

onMounted(() => {
  fetchList()
  fetchLevels()
  fetchWarningList()
  fetchStatistics()
})
</script>

<style scoped>
.credit-container {
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

.amount { font-weight: 500; }
.text-muted { color: #909399; }
.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }

.stat-card {
  text-align: center;
  padding: 20px 0;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 8px;
}
</style>
