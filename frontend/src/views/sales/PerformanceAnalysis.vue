<template>
  <div class="performance-container">
    <div class="page-header">
      <h2>销售业绩分析</h2>
      <div class="header-actions">
        <el-select v-model="queryYear" style="width: 120px" @change="fetchAllData">
          <el-option v-for="y in yearOptions" :key="y" :label="y + '年'" :value="y" />
        </el-select>
        <el-select v-model="queryMonth" placeholder="全年" clearable style="width: 100px" @change="fetchAllData">
          <el-option v-for="m in 12" :key="m" :label="m + '月'" :value="m" />
        </el-select>
      </div>
    </div>
    
    <el-tabs v-model="activeTab">
      <el-tab-pane label="业绩概览" name="overview">
        <!-- 核心指标 -->
        <el-row :gutter="16" class="stats-row">
          <el-col :span="6">
            <el-card shadow="never" class="stat-card">
              <div class="stat-value">￥{{ formatAmount(myPerformance.order_amount) }}</div>
              <div class="stat-label">我的订单额</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never" class="stat-card stat-primary">
              <div class="stat-value">{{ myPerformance.order_count || 0 }}</div>
              <div class="stat-label">订单数</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never" class="stat-card stat-success">
              <div class="stat-value">{{ myPerformance.conversion_rate || 0 }}%</div>
              <div class="stat-label">转化率</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never" class="stat-card stat-warning">
              <div class="stat-value">{{ myPerformance.new_customers || 0 }}</div>
              <div class="stat-label">新客户</div>
            </el-card>
          </el-col>
        </el-row>
        
        <!-- 图表 -->
        <el-row :gutter="16">
          <el-col :span="12">
            <el-card shadow="never" header="月度趋势">
              <div ref="trendChart" style="height: 300px"></div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never" header="团队排名">
              <el-table :data="teamRanking" border stripe max-height="300">
                <el-table-column label="排名" width="60" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.rank <= 3" :type="['danger', 'warning', 'info'][row.rank - 1]" size="small">
                      {{ row.rank }}
                    </el-tag>
                    <span v-else>{{ row.rank }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="销售人员" />
                <el-table-column prop="order_count" label="订单数" width="80" align="right" />
                <el-table-column label="订单额" align="right" width="140">
                  <template #default="{ row }">
                    ￥{{ formatAmount(row.total_amount) }}
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
        </el-row>
        
        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :span="12">
            <el-card shadow="never" header="客户贡献Top10">
              <el-table :data="customerAnalysis.top_customers" border stripe max-height="280">
                <el-table-column prop="customer__name" label="客户" show-overflow-tooltip />
                <el-table-column prop="order_count" label="订单数" width="80" align="right" />
                <el-table-column label="金额" align="right" width="140">
                  <template #default="{ row }">
                    ￥{{ formatAmount(row.total_amount) }}
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never" header="销售漏斗">
              <div ref="funnelChart" style="height: 280px"></div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
      
      <el-tab-pane label="销售目标" name="targets">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>我的销售目标</span>
              <el-button type="primary" size="small" @click="handleRefreshTargets">刷新数据</el-button>
            </div>
          </template>
          <el-table :data="myTargets" border stripe>
            <el-table-column label="期间" width="120">
              <template #default="{ row }">
                {{ row.year }}年{{ row.month ? row.month + '月' : (row.quarter ? 'Q' + row.quarter : '全年') }}
              </template>
            </el-table-column>
            <el-table-column label="订单目标" align="right" width="140">
              <template #default="{ row }">
                ￥{{ formatAmount(row.order_target) }}
              </template>
            </el-table-column>
            <el-table-column label="订单实际" align="right" width="140">
              <template #default="{ row }">
                ￥{{ formatAmount(row.order_actual) }}
              </template>
            </el-table-column>
            <el-table-column label="完成率" width="180">
              <template #default="{ row }">
                <el-progress :percentage="Math.min(row.order_rate || 0, 100)" 
                  :color="getTargetColor(row.order_rate)"
                  :format="() => (row.order_rate || 0).toFixed(1) + '%'" />
              </template>
            </el-table-column>
            <el-table-column label="回款目标" align="right" width="140">
              <template #default="{ row }">
                ￥{{ formatAmount(row.collection_target) }}
              </template>
            </el-table-column>
            <el-table-column label="回款实际" align="right" width="140">
              <template #default="{ row }">
                ￥{{ formatAmount(row.collection_actual) }}
              </template>
            </el-table-column>
            <el-table-column label="回款完成率" width="180">
              <template #default="{ row }">
                <el-progress :percentage="Math.min(row.collection_rate || 0, 100)" 
                  :color="getTargetColor(row.collection_rate)" 
                  :format="() => (row.collection_rate || 0).toFixed(1) + '%'" />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="提成明细" name="commissions">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>我的提成明细</span>
              <span class="total-commission">
                累计提成: <b>￥{{ formatAmount(totalCommission) }}</b>
              </span>
            </div>
          </template>
          <el-table :data="myCommissions" border stripe>
            <el-table-column label="期间" width="100">
              <template #default="{ row }">
                {{ row.year }}.{{ row.month }}
              </template>
            </el-table-column>
            <el-table-column prop="commission_type_display" label="类型" width="100" />
            <el-table-column prop="order_no" label="关联订单" width="140" />
            <el-table-column label="基数金额" align="right" width="140">
              <template #default="{ row }">
                ￥{{ formatAmount(row.base_amount) }}
              </template>
            </el-table-column>
            <el-table-column label="提成比例" align="right" width="100">
              <template #default="{ row }">
                {{ row.commission_rate }}%
              </template>
            </el-table-column>
            <el-table-column label="提成金额" align="right" width="120">
              <template #default="{ row }">
                <span class="commission-amount">￥{{ formatAmount(row.commission_amount) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status_display" label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="getCommissionStatusTag(row.status)">
                  {{ row.status_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="remarks" label="备注" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import * as echarts from 'echarts'

const activeTab = ref('overview')
const trendChart = ref(null)
const funnelChart = ref(null)
let trendChartInstance = null
let funnelChartInstance = null

const currentYear = new Date().getFullYear()
const queryYear = ref(currentYear)
const queryMonth = ref(null)

const yearOptions = Array.from({ length: 3 }, (_, i) => currentYear - i)

const myPerformance = ref({})
const teamRanking = ref([])
const monthlyTrend = ref([])
const customerAnalysis = ref({ top_customers: [], new_customers_trend: [] })
const pipelineAnalysis = ref({ stages: [] })
const myTargets = ref([])
const myCommissions = ref([])

const totalCommission = computed(() => {
  return myCommissions.value
    .filter(c => c.status !== 'CANCELLED')
    .reduce((sum, c) => sum + Number(c.commission_amount || 0), 0)
})

const fetchMyPerformance = async () => {
  try {
    const params = { year: queryYear.value }
    if (queryMonth.value) params.month = queryMonth.value
    
    const { data } = await request.get('/sales/performance/my_performance/', { params })
    myPerformance.value = data
  } catch (e) {
    console.error(e)
  }
}

const fetchTeamRanking = async () => {
  try {
    const params = { year: queryYear.value, limit: 10 }
    if (queryMonth.value) params.month = queryMonth.value
    
    const { data } = await request.get('/sales/performance/team_ranking/', { params })
    teamRanking.value = data
  } catch (e) {
    console.error(e)
  }
}

const fetchMonthlyTrend = async () => {
  try {
    const { data } = await request.get('/sales/performance/monthly_trend/', {
      params: { year: queryYear.value }
    })
    monthlyTrend.value = data
    nextTick(() => renderTrendChart())
  } catch (e) {
    console.error(e)
  }
}

const fetchCustomerAnalysis = async () => {
  try {
    const { data } = await request.get('/sales/performance/customer_analysis/', {
      params: { year: queryYear.value }
    })
    customerAnalysis.value = data
  } catch (e) {
    console.error(e)
  }
}

const fetchPipelineAnalysis = async () => {
  try {
    const { data } = await request.get('/sales/performance/pipeline_analysis/', {
      params: { year: queryYear.value }
    })
    pipelineAnalysis.value = data
    nextTick(() => renderFunnelChart())
  } catch (e) {
    console.error(e)
  }
}

const fetchMyTargets = async () => {
  try {
    const { data } = await request.get('/sales/targets/my_targets/')
    myTargets.value = data
  } catch (e) {
    console.error(e)
  }
}

const fetchMyCommissions = async () => {
  try {
    const { data } = await request.get('/sales/commissions/my_commissions/')
    myCommissions.value = data
  } catch (e) {
    console.error(e)
  }
}

const fetchAllData = () => {
  fetchMyPerformance()
  fetchTeamRanking()
  fetchMonthlyTrend()
  fetchCustomerAnalysis()
  fetchPipelineAnalysis()
}

const handleRefreshTargets = async () => {
  for (const target of myTargets.value) {
    try {
      await request.post(`/sales/targets/${target.id}/refresh/`)
    } catch (e) {
      console.error(e)
    }
  }
  ElMessage.success('数据已刷新')
  fetchMyTargets()
}

const renderTrendChart = () => {
  if (!trendChart.value) return
  
  if (!trendChartInstance) {
    trendChartInstance = echarts.init(trendChart.value)
  }
  
  const months = monthlyTrend.value.map(d => {
    const date = new Date(d.month)
    return `${date.getMonth() + 1}月`
  })
  const amounts = monthlyTrend.value.map(d => Number(d.total_amount || 0))
  const counts = monthlyTrend.value.map(d => d.order_count || 0)
  
  trendChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['订单额', '订单数'] },
    xAxis: { type: 'category', data: months },
    yAxis: [
      { type: 'value', name: '金额(万)', axisLabel: { formatter: v => (v / 10000).toFixed(0) } },
      { type: 'value', name: '数量' }
    ],
    series: [
      {
        name: '订单额',
        type: 'bar',
        data: amounts,
        itemStyle: { color: '#409eff' }
      },
      {
        name: '订单数',
        type: 'line',
        yAxisIndex: 1,
        data: counts,
        itemStyle: { color: '#67c23a' }
      }
    ]
  })
}

const renderFunnelChart = () => {
  if (!funnelChart.value) return
  
  if (!funnelChartInstance) {
    funnelChartInstance = echarts.init(funnelChart.value)
  }
  
  const statusMap = {
    DRAFT: '草稿',
    PENDING: '待审批',
    APPROVED: '已审批',
    SENT: '已发送',
    WON: '已成交',
    LOST: '已失败'
  }
  
  const funnelData = (pipelineAnalysis.value.stages || []).map(s => ({
    name: statusMap[s.status] || s.status,
    value: s.count
  }))
  
  funnelChartInstance.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}' },
    series: [{
      type: 'funnel',
      left: '10%',
      width: '80%',
      label: { show: true, position: 'inside' },
      data: funnelData.sort((a, b) => b.value - a.value)
    }]
  })
}

const formatAmount = (val) => {
  if (!val) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

const getTargetColor = (rate) => {
  if (rate >= 100) return '#67c23a'
  if (rate >= 80) return '#409eff'
  if (rate >= 60) return '#e6a23c'
  return '#f56c6c'
}

const getCommissionStatusTag = (status) => {
  const tags = {
    PENDING: 'warning',
    CONFIRMED: 'primary',
    PAID: 'success',
    CANCELLED: 'info'
  }
  return tags[status] || ''
}

onMounted(() => {
  fetchAllData()
  fetchMyTargets()
  fetchMyCommissions()
})
</script>

<style scoped>
.performance-container {
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

.header-actions {
  display: flex;
  gap: 10px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 20px 0;
}

.stat-value {
  font-size: 26px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 6px;
}

.stat-primary .stat-value { color: #409eff; }
.stat-success .stat-value { color: #67c23a; }
.stat-warning .stat-value { color: #e6a23c; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.total-commission {
  color: #409eff;
}

.total-commission b {
  font-size: 18px;
  color: #67c23a;
}

.commission-amount {
  color: #67c23a;
  font-weight: 500;
}
</style>
