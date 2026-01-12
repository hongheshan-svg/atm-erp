<template>
  <div class="analysis-container">
    <div class="page-header">
      <h2>销售分析</h2>
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        @change="fetchData"
        style="width: 280px"
      />
    </div>
    
    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <!-- 销售漏斗 -->
      <el-tab-pane label="销售漏斗" name="funnel">
        <el-row :gutter="16">
          <el-col :span="14">
            <el-card shadow="never" header="销售漏斗">
              <div class="funnel-chart">
                <div v-for="(stage, idx) in funnelData" :key="stage.stage" class="funnel-stage"
                  :style="{ width: (100 - idx * 15) + '%', background: getStageColor(stage.stage) }">
                  <div class="stage-content">
                    <span class="stage-name">{{ stage.stage_name }}</span>
                    <span class="stage-count">{{ stage.count }} 个</span>
                    <span class="stage-amount">¥{{ formatNumber(stage.amount) }}</span>
                  </div>
                  <div class="conversion-arrow" v-if="idx < funnelData.length - 1">
                    ↓ {{ stage.conversion_rate }}%
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="10">
            <el-card shadow="never" header="漏斗统计">
              <el-descriptions :column="1" border>
                <el-descriptions-item label="总线索数">{{ funnelSummary.total_leads }}</el-descriptions-item>
                <el-descriptions-item label="总成交数">{{ funnelSummary.total_orders }}</el-descriptions-item>
                <el-descriptions-item label="成交金额">¥{{ formatNumber(funnelSummary.total_order_amount) }}</el-descriptions-item>
                <el-descriptions-item label="整体转化率">
                  <span class="highlight">{{ funnelSummary.overall_conversion }}%</span>
                </el-descriptions-item>
              </el-descriptions>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
      
      <!-- 客户分析 -->
      <el-tab-pane label="客户分析" name="customer">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-card shadow="never">
              <template #header>
                <div class="card-header">
                  <span>客户RFM分析</span>
                  <el-button type="primary" size="small" @click="handleRFMAnalyze">执行分析</el-button>
                </div>
              </template>
              
              <el-row :gutter="16" class="segment-cards">
                <el-col :span="4" v-for="seg in customerSegments" :key="seg.customer_segment">
                  <div class="segment-card" :style="{ borderColor: getSegmentColor(seg.customer_segment) }">
                    <div class="segment-name">{{ seg.customer_segment }}</div>
                    <div class="segment-count">{{ seg.count }} 家</div>
                    <div class="segment-amount">¥{{ formatNumber(seg.total_monetary) }}</div>
                  </div>
                </el-col>
              </el-row>
              
              <el-divider />
              
              <el-table :data="topCustomers" border stripe max-height="300">
                <el-table-column type="index" label="排名" width="60" />
                <el-table-column prop="customer_code" label="客户编码" width="120" />
                <el-table-column prop="customer_name" label="客户名称" min-width="180" />
                <el-table-column prop="r_score" label="R分" width="60" align="center" />
                <el-table-column prop="f_score" label="F分" width="60" align="center" />
                <el-table-column prop="m_score" label="M分" width="60" align="center" />
                <el-table-column prop="rfm_score" label="综合分" width="80" align="center" />
                <el-table-column label="累计金额" width="140" align="right">
                  <template #default="{ row }">
                    ¥{{ formatNumber(row.monetary) }}
                  </template>
                </el-table-column>
                <el-table-column prop="customer_segment" label="客户分层" width="120" />
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
      
      <!-- 销售趋势 -->
      <el-tab-pane label="销售趋势" name="trend">
        <el-card shadow="never" header="销售趋势">
          <div ref="trendChartRef" style="height: 400px"></div>
        </el-card>
      </el-tab-pane>
      
      <!-- 销售排名 -->
      <el-tab-pane label="销售排名" name="ranking">
        <el-card shadow="never" header="销售人员排名">
          <el-table :data="ranking" border stripe>
            <el-table-column prop="rank" label="排名" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.rank <= 3" :type="row.rank === 1 ? 'danger' : row.rank === 2 ? 'warning' : ''">
                  {{ row.rank }}
                </el-tag>
                <span v-else>{{ row.rank }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="销售人员" min-width="150" />
            <el-table-column prop="order_count" label="订单数" width="100" align="center" />
            <el-table-column label="销售金额" width="160" align="right">
              <template #default="{ row }">
                <span class="amount">¥{{ formatNumber(row.total_amount) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="占比" width="150">
              <template #default="{ row }">
                <el-progress :percentage="getPercentage(row.total_amount)" :stroke-width="10" />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, computed } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import * as echarts from 'echarts'

const activeTab = ref('funnel')
const trendChartRef = ref(null)
let trendChart = null

const dateRange = ref([])

const funnelData = ref([])
const funnelSummary = ref({})
const customerSegments = ref([])
const topCustomers = ref([])
const trendData = ref([])
const ranking = ref([])

const maxAmount = computed(() => {
  if (!ranking.value.length) return 1
  return Math.max(...ranking.value.map(r => r.total_amount))
})

const getPercentage = (amount) => {
  return Math.round(amount / maxAmount.value * 100)
}

const fetchFunnel = async () => {
  try {
    const params = {}
    if (dateRange.value?.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const data = await request.get('/sales/analysis/funnel/', { params })
    funnelData.value = data.funnel || []
    funnelSummary.value = {
      total_leads: data.total_leads,
      total_orders: data.total_orders,
      total_order_amount: data.total_order_amount,
      overall_conversion: data.overall_conversion
    }
  } catch (e) {
    console.error(e)
  }
}

const fetchCustomerAnalysis = async () => {
  try {
    const segData = await request.get('/sales/customer-rfm/segment_summary/')
    customerSegments.value = segData?.segments || []
    
    const topData = await request.get('/sales/customer-rfm/top_customers/')
    topCustomers.value = topData?.customers || topData || []
  } catch (e) {
    console.error(e)
  }
}

const handleRFMAnalyze = async () => {
  try {
    ElMessage.info('正在执行RFM分析...')
    const data = await request.post('/sales/customer-rfm/analyze/')
    ElMessage.success(`分析完成，共分析 ${data.analyzed_count} 个客户`)
    fetchCustomerAnalysis()
  } catch (e) {
    ElMessage.error('分析失败')
  }
}

const fetchTrend = async () => {
  try {
    const data = await request.get('/sales/analysis/trend/', {
      params: { period: 'month', months: 12 }
    })
    trendData.value = data.trend || []
    renderTrendChart()
  } catch (e) {
    console.error(e)
  }
}

const renderTrendChart = async () => {
  await nextTick()
  if (!trendChartRef.value) return
  
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['订单数', '销售额']
    },
    xAxis: {
      type: 'category',
      data: trendData.value.map(d => d.date?.substring(0, 7) || '')
    },
    yAxis: [
      { type: 'value', name: '订单数' },
      { type: 'value', name: '销售额', axisLabel: { formatter: '{value}' } }
    ],
    series: [
      {
        name: '订单数',
        type: 'bar',
        data: trendData.value.map(d => d.count),
        itemStyle: { color: '#409eff' }
      },
      {
        name: '销售额',
        type: 'line',
        yAxisIndex: 1,
        data: trendData.value.map(d => d.amount),
        itemStyle: { color: '#67c23a' }
      }
    ]
  }
  
  trendChart.setOption(option)
}

const fetchRanking = async () => {
  try {
    const params = {}
    if (dateRange.value?.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const data = await request.get('/sales/analysis/ranking/', { params })
    ranking.value = data.ranking || []
  } catch (e) {
    console.error(e)
  }
}

const fetchData = () => {
  if (activeTab.value === 'funnel') fetchFunnel()
  else if (activeTab.value === 'customer') fetchCustomerAnalysis()
  else if (activeTab.value === 'trend') fetchTrend()
  else if (activeTab.value === 'ranking') fetchRanking()
}

const handleTabChange = () => {
  fetchData()
}

const formatNumber = (num) => {
  if (!num) return '0'
  return parseFloat(num).toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

const getStageColor = (stage) => {
  const colors = {
    LEAD: '#409eff',
    OPPORTUNITY: '#67c23a',
    QUOTATION: '#e6a23c',
    ORDER: '#f56c6c'
  }
  return colors[stage] || '#909399'
}

const getSegmentColor = (segment) => {
  const colors = {
    '重要价值客户': '#67c23a',
    '潜力客户': '#409eff',
    '忠诚客户': '#e6a23c',
    '新客户': '#909399',
    '沉睡客户': '#f56c6c',
    '流失客户': '#909399'
  }
  return colors[segment] || '#409eff'
}

onMounted(() => {
  // 设置默认日期范围：本月
  const today = new Date()
  const start = new Date(today.getFullYear(), today.getMonth(), 1)
  dateRange.value = [
    start.toISOString().slice(0, 10),
    today.toISOString().slice(0, 10)
  ]
  
  fetchFunnel()
  fetchCustomerAnalysis()
})
</script>

<style scoped>
.analysis-container {
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.funnel-chart {
  padding: 20px;
}

.funnel-stage {
  margin: 0 auto 16px;
  padding: 16px 20px;
  border-radius: 4px;
  color: #fff;
  text-align: center;
  position: relative;
}

.stage-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stage-name { font-weight: bold; }
.stage-count { font-size: 16px; }
.stage-amount { font-size: 14px; opacity: 0.9; }

.conversion-arrow {
  position: absolute;
  bottom: -20px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 12px;
  color: #666;
}

.highlight {
  font-size: 24px;
  font-weight: bold;
  color: #67c23a;
}

.segment-cards {
  margin-bottom: 20px;
}

.segment-card {
  border: 2px solid;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}

.segment-name {
  font-weight: bold;
  margin-bottom: 8px;
}

.segment-count {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.segment-amount {
  font-size: 12px;
  color: #909399;
}

.amount {
  font-weight: 500;
}
</style>
