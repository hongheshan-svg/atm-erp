<template>
  <div class="quote-estimation-detail">
    <el-page-header @back="goBack" :content="pageTitle" />
    
    <el-card class="detail-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>基本信息</span>
          <div class="actions">
            <el-button v-if="canEdit" type="primary" @click="handleEdit">编辑</el-button>
            <el-button v-if="canCalculate" @click="handleCalculate">重新核算</el-button>
            <el-button v-if="canSubmit" type="success" @click="handleSubmit">提交审核</el-button>
          </div>
        </div>
      </template>
      
      <el-descriptions :column="3" border>
        <el-descriptions-item label="估算编号">{{ estimation.estimation_no }}</el-descriptions-item>
        <el-descriptions-item label="项目名称">{{ estimation.project_name }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ estimation.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(estimation.status)">{{ estimation.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建日期">{{ estimation.created_at }}</el-descriptions-item>
        <el-descriptions-item label="创建人">{{ estimation.created_by_name }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
    
    <el-card class="cost-summary" v-if="estimation.id">
      <template #header>
        <span>成本汇总</span>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="cost-item">
            <div class="label">材料成本</div>
            <div class="value">¥ {{ formatMoney(estimation.material_cost) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="cost-item">
            <div class="label">人工成本</div>
            <div class="value">¥ {{ formatMoney(estimation.labor_cost) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="cost-item">
            <div class="label">外协成本</div>
            <div class="value">¥ {{ formatMoney(estimation.outsource_cost) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="cost-item primary">
            <div class="label">总成本</div>
            <div class="value">¥ {{ formatMoney(estimation.total_cost) }}</div>
          </div>
        </el-col>
      </el-row>
      
      <el-divider />
      
      <el-row :gutter="20">
        <el-col :span="8">
          <div class="cost-item success">
            <div class="label">建议报价</div>
            <div class="value">¥ {{ formatMoney(estimation.suggested_price) }}</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="cost-item" :class="getProfitClass(estimation.profit_rate)">
            <div class="label">预计利润率</div>
            <div class="value">{{ formatPercent(estimation.profit_rate) }}%</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="cost-item">
            <div class="label">预计交付周期</div>
            <div class="value">{{ estimation.estimated_lead_time }} 天</div>
          </div>
        </el-col>
      </el-row>
    </el-card>
    
    <!-- 成本明细 -->
    <el-card class="cost-details" v-if="estimation.id">
      <template #header>
        <span>成本明细</span>
      </template>
      
      <el-tabs v-model="activeTab">
        <el-tab-pane label="材料明细" name="material">
          <el-table :data="estimation.material_items || []" stripe>
            <el-table-column prop="item_name" label="物料名称" />
            <el-table-column prop="specification" label="规格" />
            <el-table-column prop="quantity" label="数量" align="right" />
            <el-table-column prop="unit" label="单位" width="80" />
            <el-table-column prop="unit_price" label="单价" align="right">
              <template #default="{ row }">¥ {{ formatMoney(row.unit_price) }}</template>
            </el-table-column>
            <el-table-column prop="subtotal" label="小计" align="right">
              <template #default="{ row }">¥ {{ formatMoney(row.subtotal) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        
        <el-tab-pane label="人工明细" name="labor">
          <el-table :data="estimation.labor_items || []" stripe>
            <el-table-column prop="work_type_display" label="工种" />
            <el-table-column prop="skill_level_display" label="技能级别" />
            <el-table-column prop="hours" label="工时" align="right" />
            <el-table-column prop="hourly_rate" label="时薪" align="right">
              <template #default="{ row }">¥ {{ formatMoney(row.hourly_rate) }}</template>
            </el-table-column>
            <el-table-column prop="subtotal" label="小计" align="right">
              <template #default="{ row }">¥ {{ formatMoney(row.subtotal) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        
        <el-tab-pane label="外协明细" name="outsource">
          <el-table :data="estimation.outsource_items || []" stripe>
            <el-table-column prop="process_name" label="工序名称" />
            <el-table-column prop="supplier_name" label="供应商" />
            <el-table-column prop="quantity" label="数量" align="right" />
            <el-table-column prop="unit_price" label="单价" align="right">
              <template #default="{ row }">¥ {{ formatMoney(row.unit_price) }}</template>
            </el-table-column>
            <el-table-column prop="subtotal" label="小计" align="right">
              <template #default="{ row }">¥ {{ formatMoney(row.subtotal) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        
        <el-tab-pane label="其他成本" name="other">
          <el-table :data="estimation.other_costs || []" stripe>
            <el-table-column prop="cost_type_display" label="成本类型" />
            <el-table-column prop="description" label="说明" />
            <el-table-column prop="amount" label="金额" align="right">
              <template #default="{ row }">¥ {{ formatMoney(row.amount) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getQuoteEstimation, calculateQuoteEstimation, submitQuoteEstimation } from '@/api/sales'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const estimation = ref<Record<string, any>>({})
const activeTab = ref('material')

const pageTitle = computed(() => {
  return estimation.value.estimation_no ? `估算详情 - ${estimation.value.estimation_no}` : '估算详情'
})

const canEdit = computed(() => estimation.value.status === 'DRAFT')
const canCalculate = computed(() => ['DRAFT', 'CALCULATED'].includes(estimation.value.status))
const canSubmit = computed(() => estimation.value.status === 'CALCULATED')

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'CALCULATED': 'warning',
    'PENDING': 'primary',
    'APPROVED': 'success',
    'REJECTED': 'danger'
  }
  return types[status] || 'info'
}

const getProfitClass = (rate) => {
  if (rate >= 0.3) return 'success'
  if (rate >= 0.15) return 'warning'
  return 'danger'
}

const formatMoney = (value) => {
  if (!value) return '0.00'
  return parseFloat(value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

const formatPercent = (value) => {
  if (!value) return '0.00'
  return (parseFloat(value) * 100).toFixed(2)
}

const loadEstimation = async () => {
  loading.value = true
  try {
    const res = await getQuoteEstimation(route.params.id)
    estimation.value = res
  } catch (error) {
    ElMessage.error('加载估算详情失败')
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push({ name: 'QuoteEstimationList' })
}

const handleEdit = () => {
  router.push({ name: 'QuoteEstimationEdit', params: { id: route.params.id } })
}

const handleCalculate = async () => {
  try {
    await calculateQuoteEstimation(route.params.id)
    ElMessage.success('重新核算成功')
    loadEstimation()
  } catch (error) {
    ElMessage.error('核算失败')
  }
}

const handleSubmit = async () => {
  try {
    await submitQuoteEstimation(route.params.id)
    ElMessage.success('提交审核成功')
    loadEstimation()
  } catch (error) {
    ElMessage.error('提交失败')
  }
}

onMounted(() => {
  loadEstimation()
})
</script>

<style scoped>
.quote-estimation-detail {
  padding: 20px;
}

.el-page-header {
  margin-bottom: 20px;
}

.detail-card,
.cost-summary,
.cost-details {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.cost-item {
  text-align: center;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.cost-item .label {
  color: #909399;
  margin-bottom: 8px;
}

.cost-item .value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.cost-item.primary .value {
  color: #409eff;
}

.cost-item.success .value {
  color: #67c23a;
}

.cost-item.warning .value {
  color: #e6a23c;
}

.cost-item.danger .value {
  color: #f56c6c;
}
</style>
