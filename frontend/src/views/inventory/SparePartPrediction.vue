<template>
  <div class="spare-part-prediction">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 生命周期预测 -->
      <el-tab-pane label="寿命预测" name="lifecycle">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>备件生命周期预测</span>
              <el-button type="primary" @click="loadLifecycle" :loading="lifecycleLoading">
                <el-icon><Refresh /></el-icon>重新计算
              </el-button>
            </div>
          </template>
          <!-- 批量操作 -->
          <div v-if="selectedRows.length > 0" class="batch-toolbar">
            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
            <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
            <el-button size="small" @click="batchExport">导出选中</el-button>
          </div>
          <el-table :data="lifecycleData" v-loading="lifecycleLoading" stripe @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="spare_part_name" label="备件名称" min-width="180" />
            <el-table-column prop="equipment_name" label="关联设备" min-width="150" />
            <el-table-column prop="predicted_life_hours" label="预测寿命(h)" width="120" align="right" />
            <el-table-column prop="current_usage_hours" label="已使用(h)" width="110" align="right" />
            <el-table-column label="剩余寿命" width="150">
              <template #default="{ row }">
                <el-progress :percentage="Math.max(0, Math.min(100, ((row.remaining_hours || 0) / (row.predicted_life_hours || 1)) * 100))"
                  :status="(row.remaining_hours || 0) < 200 ? 'exception' : ((row.remaining_hours || 0) < 500 ? 'warning' : '')" />
                <span style="font-size:12px;color:#909399;">{{ row.remaining_hours }}h</span>
              </template>
            </el-table-column>
            <el-table-column prop="confidence" label="置信度" width="100" align="center">
              <template #default="{ row }">{{ row.confidence }}%</template>
            </el-table-column>
            <el-table-column label="建议" width="150">
              <template #default="{ row }">
                <el-tag v-if="(row.remaining_hours || 0) < 200" type="danger" size="small">立即更换</el-tag>
                <el-tag v-else-if="(row.remaining_hours || 0) < 500" type="warning" size="small">计划采购</el-tag>
                <el-tag v-else type="success" size="small">正常使用</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 采购建议 -->
      <el-tab-pane label="采购建议" name="purchase">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>智能采购建议</span>
              <el-button type="primary" @click="loadPurchaseSuggestions" :loading="purchaseLoading">
                <el-icon><Refresh /></el-icon>重新生成
              </el-button>
            </div>
          </template>
          <el-table :data="purchaseSuggestions" v-loading="purchaseLoading" stripe>
            <el-table-column prop="spare_part_name" label="备件名称" min-width="180" />
            <el-table-column prop="current_stock" label="当前库存" width="100" align="center" />
            <el-table-column prop="suggested_quantity" label="建议采购" width="100" align="center">
              <template #default="{ row }">
                <span style="font-weight:bold;color:#409eff">{{ row.suggested_quantity }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="suggested_date" label="建议日期" width="120" />
            <el-table-column prop="estimated_cost" label="预估金额" width="120" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.estimated_cost) }}</template>
            </el-table-column>
            <el-table-column prop="reason" label="建议原因" min-width="250" show-overflow-tooltip />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="sugStatusType(row.status)" size="small">{{ sugStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link type="primary" v-if="row.status === 'pending'" @click="acceptSuggestion(row)">接受</el-button>
                <el-button size="small" link type="info" v-if="row.status === 'pending'" @click="rejectSuggestion(row)">忽略</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 成本分析 -->
      <el-tab-pane label="备件成本" name="cost">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>备件消耗成本分析</span>
              <el-button type="primary" @click="loadCostAnalysis" :loading="costLoading">分析</el-button>
            </div>
          </template>

          <el-row :gutter="16" v-if="costAnalysis" style="margin-bottom: 16px">
            <el-col :span="8">
              <el-card class="stat-card">
                <el-statistic title="月均消耗金额" :value="costAnalysis.avg_monthly_cost" prefix="¥" :precision="2" />
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card class="stat-card">
                <el-statistic title="年度预测总额" :value="costAnalysis.yearly_forecast" prefix="¥" :precision="2" />
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card class="stat-card">
                <el-statistic title="同比变化" :value="costAnalysis.yoy_change" suffix="%" />
              </el-card>
            </el-col>
          </el-row>

          <!-- Top消耗 -->
          <el-row :gutter="16">
            <el-col :span="12">
              <h4 style="margin-bottom: 12px">消耗金额 Top 10</h4>
              <el-table :data="costAnalysis?.top_cost_parts || []" size="small" stripe>
                <el-table-column type="index" width="50" />
                <el-table-column prop="name" label="备件" min-width="150" />
                <el-table-column prop="total_cost" label="总金额" width="120" align="right">
                  <template #default="{ row }">¥{{ formatMoney(row.total_cost) }}</template>
                </el-table-column>
              </el-table>
            </el-col>
            <el-col :span="12">
              <h4 style="margin-bottom: 12px">消耗频次 Top 10</h4>
              <el-table :data="costAnalysis?.top_frequency_parts || []" size="small" stripe>
                <el-table-column type="index" width="50" />
                <el-table-column prop="name" label="备件" min-width="150" />
                <el-table-column prop="consumption_count" label="频次" width="80" align="center" />
                <el-table-column prop="total_quantity" label="总数量" width="80" align="center" />
              </el-table>
            </el-col>
          </el-row>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import {
getSparePartLifecyclePrediction, getSparePartPurchaseSuggestions,
  getSparePartCostAnalysis
} from '@/api/inventory'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/inventory/')


const activeTab = ref('lifecycle')
const lifecycleLoading = ref(false)
const purchaseLoading = ref(false)
const costLoading = ref(false)

const lifecycleData = ref([])
const purchaseSuggestions = ref([])
const costAnalysis = ref(null)

const formatMoney = (v) => v ? Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'
const sugStatusType = (s) => ({ pending: 'warning', accepted: 'success', rejected: 'info', ordered: '' }[s] || 'info')
const sugStatusLabel = (s) => ({ pending: '待处理', accepted: '已接受', rejected: '已忽略', ordered: '已下单' }[s] || s)

const loadLifecycle = async () => {
  lifecycleLoading.value = true
  try {
    const res = await getSparePartLifecyclePrediction()
    lifecycleData.value = res.data?.results || res.data || res || []
  } finally { lifecycleLoading.value = false }
}

const loadPurchaseSuggestions = async () => {
  purchaseLoading.value = true
  try {
    const res = await getSparePartPurchaseSuggestions()
    purchaseSuggestions.value = res.data?.results || res.data || res || []
  } finally { purchaseLoading.value = false }
}

const loadCostAnalysis = async () => {
  costLoading.value = true
  try {
    const res = await getSparePartCostAnalysis()
    costAnalysis.value = res.data || res
  } finally { costLoading.value = false }
}

const acceptSuggestion = (row) => {
  row.status = 'accepted'
  ElMessage.success('已接受采购建议')
}

const rejectSuggestion = (row) => {
  row.status = 'rejected'
  ElMessage.info('已忽略')
}

onMounted(() => {
  loadLifecycle()
  loadPurchaseSuggestions()
  loadCostAnalysis()
})
</script>

<style scoped>
.spare-part-prediction { padding: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.stat-card { text-align: center; }
</style>
