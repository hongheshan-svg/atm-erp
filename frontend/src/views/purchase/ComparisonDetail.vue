<template>
  <div class="comparison-detail">
    <!-- 基本信息 -->
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <div class="title-section">
            <el-button link @click="goBack">
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <h2>{{ comparison.comparison_no }}</h2>
            <el-tag :type="getStatusType(comparison.status)" size="large">
              {{ comparison.status_display }}
            </el-tag>
          </div>
          <div class="actions">
            <el-button 
              v-if="comparison.status === 'IN_PROGRESS'"
              type="primary"
              @click="handleAutoScore"
            >
              自动评分
            </el-button>
            <el-button 
              v-if="comparison.status === 'IN_PROGRESS'"
              type="success"
              @click="handleComplete"
            >
              完成比价
            </el-button>
            <el-button 
              v-if="comparison.status === 'COMPLETED'"
              type="warning"
              @click="handleApprove"
            >
              审批通过
            </el-button>
            <el-button 
              v-if="comparison.status === 'APPROVED'"
              type="primary"
              @click="handleConvertToPO"
            >
              转采购订单
            </el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic title="询价单号" :value="comparison.rfq_no" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="供应商数" :value="comparison.supplier_count || 0" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="最低报价" :value="comparison.min_price" prefix="¥" :precision="2" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="平均报价" :value="comparison.avg_price" prefix="¥" :precision="2" />
        </el-col>
      </el-row>
    </el-card>

    <!-- 权重配置 -->
    <el-card class="weight-card">
      <template #header>
        <div class="card-header">
          <span>权重配置</span>
          <el-button 
            v-if="comparison.status === 'IN_PROGRESS'"
            type="primary" size="small" 
            @click="showWeightDialog = true"
          >
            调整权重
          </el-button>
        </div>
      </template>
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="weight-item">
            <el-progress 
              type="dashboard" 
              :percentage="Number(comparison.weight_price)" 
              :width="80"
              :stroke-width="8"
              color="#67c23a"
            />
            <div class="weight-label">价格 {{ comparison.weight_price }}%</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="weight-item">
            <el-progress 
              type="dashboard" 
              :percentage="Number(comparison.weight_quality)" 
              :width="80"
              :stroke-width="8"
              color="#409eff"
            />
            <div class="weight-label">质量 {{ comparison.weight_quality }}%</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="weight-item">
            <el-progress 
              type="dashboard" 
              :percentage="Number(comparison.weight_delivery)" 
              :width="80"
              :stroke-width="8"
              color="#e6a23c"
            />
            <div class="weight-label">交期 {{ comparison.weight_delivery }}%</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="weight-item">
            <el-progress 
              type="dashboard" 
              :percentage="Number(comparison.weight_service)" 
              :width="80"
              :stroke-width="8"
              color="#909399"
            />
            <div class="weight-label">服务 {{ comparison.weight_service }}%</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 供应商比较表 -->
    <el-card>
      <template #header>
        <span>供应商报价比较</span>
      </template>
      
      <el-table :data="comparison.scores || []" stripe border>
        <el-table-column prop="ranking" label="排名" width="80" align="center">
          <template #default="{ row }">
            <el-tag 
              :type="row.ranking === 1 ? 'success' : (row.ranking === 2 ? 'warning' : 'info')"
              effect="dark"
            >
              {{ row.ranking === 1 ? '🥇' : (row.ranking === 2 ? '🥈' : (row.ranking === 3 ? '🥉' : row.ranking)) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="supplier_name" label="供应商" min-width="150">
          <template #default="{ row }">
            <span>{{ row.supplier_name }}</span>
            <el-tag v-if="row.is_recommended" type="success" size="small" style="margin-left: 8px;">
              推荐
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quotation_no" label="报价单号" width="160" />
        <el-table-column label="报价金额" width="150" align="right">
          <template #default="{ row }">
            <div class="price-amount">¥{{ formatNumber(row.total_amount) }}</div>
            <div class="price-tax">含税: ¥{{ formatNumber(row.total_with_tax) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="价格分" width="100" align="center">
          <template #default="{ row }">
            <el-progress 
              :percentage="Number(row.score_price) || 0" 
              :format="() => formatScore(row.score_price)"
              :stroke-width="6"
              :color="getScoreColor(row.score_price)"
            />
          </template>
        </el-table-column>
        <el-table-column label="质量分" width="100" align="center">
          <template #default="{ row }">
            <div v-if="comparison.status === 'IN_PROGRESS'" class="editable-score">
              <el-input-number 
                v-model="row.score_quality" 
                :min="0" :max="100" :step="5" size="small"
                @change="updateScore(row, 'score_quality', row.score_quality)"
              />
            </div>
            <el-progress 
              v-else
              :percentage="Number(row.score_quality) || 0" 
              :format="() => formatScore(row.score_quality)"
              :stroke-width="6"
              :color="getScoreColor(row.score_quality)"
            />
          </template>
        </el-table-column>
        <el-table-column label="交期分" width="100" align="center">
          <template #default="{ row }">
            <el-progress 
              :percentage="Number(row.score_delivery) || 0" 
              :format="() => formatScore(row.score_delivery)"
              :stroke-width="6"
              :color="getScoreColor(row.score_delivery)"
            />
          </template>
        </el-table-column>
        <el-table-column label="服务分" width="100" align="center">
          <template #default="{ row }">
            <div v-if="comparison.status === 'IN_PROGRESS'" class="editable-score">
              <el-input-number 
                v-model="row.score_service" 
                :min="0" :max="100" :step="5" size="small"
                @change="updateScore(row, 'score_service', row.score_service)"
              />
            </div>
            <el-progress 
              v-else
              :percentage="Number(row.score_service) || 0" 
              :format="() => formatScore(row.score_service)"
              :stroke-width="6"
              :color="getScoreColor(row.score_service)"
            />
          </template>
        </el-table-column>
        <el-table-column label="综合得分" width="120" align="center">
          <template #default="{ row }">
            <div class="total-score" :class="{ 'top-score': row.ranking === 1 }">
              {{ formatTotalScore(row.total_score) }}
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 推荐理由 -->
    <el-card v-if="comparison.recommended_supplier">
      <template #header>
        <span>推荐结果</span>
      </template>
      <el-alert
        :title="`推荐供应商：${comparison.recommended_supplier}`"
        type="success"
        :description="comparison.recommendation_reason"
        :closable="false"
        show-icon
      />
    </el-card>

    <!-- 物料明细比较 -->
    <el-card v-if="report.item_comparisons?.length">
      <template #header>
        <span>物料明细比较</span>
      </template>
      
      <el-table :data="report.item_comparisons" stripe border>
        <el-table-column prop="item_sku" label="物料编码" width="120" />
        <el-table-column prop="item_name" label="物料名称" min-width="150" />
        <el-table-column prop="required_qty" label="需求数量" width="100" align="right" />
        <el-table-column 
          v-for="(supplier, index) in getSupplierNames()" 
          :key="index"
          :label="supplier"
          width="150"
          align="right"
        >
          <template #default="{ row }">
            <div v-if="getSupplierPrice(row, supplier)">
              <div class="item-price">¥{{ formatNumber(getSupplierPrice(row, supplier).unit_price) }}</div>
              <div v-if="getSupplierPrice(row, supplier).price_change_rate" class="price-change">
                <el-tag 
                  :type="Number(getSupplierPrice(row, supplier).price_change_rate) > 0 ? 'danger' : 'success'"
                  size="small"
                >
                  {{ Number(getSupplierPrice(row, supplier).price_change_rate) > 0 ? '+' : '' }}{{ formatPriceChange(getSupplierPrice(row, supplier).price_change_rate) }}%
                </el-tag>
              </div>
            </div>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="最低价" width="100" align="right">
          <template #default="{ row }">
            <span class="price-min">¥{{ formatNumber(row.min_price) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 权重调整对话框 -->
    <el-dialog v-model="showWeightDialog" title="调整权重" width="400px">
      <el-form :model="weightForm" label-width="100px">
        <el-form-item label="价格权重">
          <el-slider v-model="weightForm.weight_price" :max="100" show-input />
        </el-form-item>
        <el-form-item label="质量权重">
          <el-slider v-model="weightForm.weight_quality" :max="100" show-input />
        </el-form-item>
        <el-form-item label="交期权重">
          <el-slider v-model="weightForm.weight_delivery" :max="100" show-input />
        </el-form-item>
        <el-form-item label="服务权重">
          <el-slider v-model="weightForm.weight_service" :max="100" show-input />
        </el-form-item>
        <el-form-item>
          <el-alert 
            v-if="weightFormTotal !== 100" 
            type="warning" 
            :title="`权重总和为 ${weightFormTotal}%，需要等于 100%`"
            :closable="false"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showWeightDialog = false">取消</el-button>
        <el-button type="primary" @click="saveWeights" :disabled="weightFormTotal !== 100">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import request from '@/utils/request'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const comparison = ref({})
const report = ref({})
const showWeightDialog = ref(false)

const weightForm = reactive({
  weight_price: 40,
  weight_quality: 25,
  weight_delivery: 20,
  weight_service: 15
})

const weightFormTotal = computed(() => {
  return weightForm.weight_price + weightForm.weight_quality + 
         weightForm.weight_delivery + weightForm.weight_service
})

// 格式化
const formatNumber = (num) => {
  return parseFloat(num || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatScore = (score) => {
  const num = parseFloat(score)
  return isNaN(num) ? '0.0' : num.toFixed(1)
}

const formatTotalScore = (score) => {
  const num = parseFloat(score)
  return isNaN(num) ? '0.00' : num.toFixed(2)
}

const formatPriceChange = (rate) => {
  const num = parseFloat(rate)
  return isNaN(num) ? '0.0' : num.toFixed(1)
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'IN_PROGRESS': 'warning',
    'COMPLETED': 'success',
    'APPROVED': 'primary'
  }
  return types[status] || 'info'
}

const getScoreColor = (score) => {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

// 获取所有供应商名称
const getSupplierNames = () => {
  if (!report.value.suppliers) return []
  return report.value.suppliers.map(s => s.supplier_name)
}

// 获取物料对应供应商的价格
const getSupplierPrice = (item, supplierName) => {
  if (!item.supplier_prices) return null
  return item.supplier_prices.find(p => p.supplier_name === supplierName)
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const id = route.params.id
    const [compRes, reportRes] = await Promise.all([
      request.get(`/purchase/comparisons/${id}/`),
      request.get(`/purchase/comparisons/${id}/report/`)
    ])
    comparison.value = compRes
    report.value = reportRes
    
    // 初始化权重表单
    weightForm.weight_price = Number(compRes.weight_price)
    weightForm.weight_quality = Number(compRes.weight_quality)
    weightForm.weight_delivery = Number(compRes.weight_delivery)
    weightForm.weight_service = Number(compRes.weight_service)
  } catch (error) {
    console.error('加载比价详情失败:', error)
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

// 返回
const goBack = () => {
  router.push('/purchase/comparisons')
}

// 自动评分
const handleAutoScore = async () => {
  try {
    await request.post(`/purchase/comparisons/${route.params.id}/auto-score/`)
    ElMessage.success('自动评分完成')
    loadData()
  } catch (error) {
    ElMessage.error('评分失败')
  }
}

// 更新单个评分
const updateScore = async (row, field, value) => {
  try {
    const data = {}
    if (field === 'score_quality') {
      data.score_quality = value
    } else if (field === 'score_service') {
      data.score_service = value
    }
    
    await request.post(`/purchase/comparisons/${route.params.id}/update-score/${row.id}/`, data)
    loadData()
  } catch (error) {
    ElMessage.error('更新评分失败')
  }
}

// 保存权重
const saveWeights = async () => {
  try {
    await request.post(`/purchase/comparisons/${route.params.id}/update-weights/`, weightForm)
    ElMessage.success('权重更新成功')
    showWeightDialog.value = false
    loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '更新失败')
  }
}

// 完成比价
const handleComplete = async () => {
  try {
    await ElMessageBox.confirm('确定完成此比价分析？', '确认')
    await request.post(`/purchase/comparisons/${route.params.id}/complete/`)
    ElMessage.success('比价分析已完成')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

// 审批
const handleApprove = async () => {
  try {
    await ElMessageBox.confirm('确定审批通过此比价分析？', '确认审批')
    await request.post(`/purchase/comparisons/${route.params.id}/approve/`)
    ElMessage.success('审批通过')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

// 转采购订单
const handleConvertToPO = async () => {
  try {
    await ElMessageBox.confirm('确定将推荐报价转换为采购订单？', '确认转换')
    const res = await request.post(`/purchase/comparisons/${route.params.id}/convert-to-po/`)
    ElMessage.success(`采购订单 ${res.order_no} 创建成功`)
    router.push(`/purchase/orders/${res.id}`)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '转换失败')
    }
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.comparison-detail {
  padding: 20px;
}

.comparison-detail > .el-card {
  margin-bottom: 20px;
}

.header-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title-section h2 {
  margin: 0;
  font-size: 20px;
}

.weight-card .weight-item {
  text-align: center;
}

.weight-label {
  margin-top: 8px;
  font-weight: 500;
  color: #303133;
}

.price-amount {
  font-weight: 600;
  color: #303133;
}

.price-tax {
  font-size: 12px;
  color: #909399;
}

.total-score {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}

.total-score.top-score {
  color: #67c23a;
}

.editable-score {
  width: 100%;
}

.editable-score :deep(.el-input-number) {
  width: 100%;
}

.item-price {
  font-weight: 500;
}

.price-change {
  margin-top: 4px;
}

.price-min {
  color: #67c23a;
  font-weight: 500;
}

.text-muted {
  color: #909399;
}
</style>

