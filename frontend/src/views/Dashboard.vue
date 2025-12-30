<template>
  <div class="dashboard">
    <!-- 第一行：核心财务指标 -->
    <el-row :gutter="16">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card income">
          <div class="kpi-header">
            <el-icon class="kpi-icon"><TrendCharts /></el-icon>
            <span class="kpi-trend up" v-if="kpis.financial.revenue_growth > 0">
              +{{ kpis.financial.revenue_growth }}%
            </span>
          </div>
          <div class="kpi-value">{{ formatCurrency(kpis.financial.revenue.total) }}</div>
          <div class="kpi-label">本月收入</div>
          <div class="kpi-footer">
            <span>{{ kpis.financial.revenue.orders }} 笔订单</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card expense">
          <div class="kpi-header">
            <el-icon class="kpi-icon"><Coin /></el-icon>
          </div>
          <div class="kpi-value">{{ formatCurrency(kpis.financial.expenses) }}</div>
          <div class="kpi-label">本月支出</div>
          <div class="kpi-footer">
            <span>{{ kpis.financial.purchase_orders }} 笔采购</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card total-ar">
          <div class="kpi-header">
            <el-icon class="kpi-icon"><Money /></el-icon>
          </div>
          <div class="kpi-value">{{ formatCurrency(kpis.financial.total_receivables) }}</div>
          <div class="kpi-label">总应收账款</div>
          <div class="kpi-footer">
            <span>已收 {{ formatCurrency(kpis.financial.total_received) }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card total-ap">
          <div class="kpi-header">
            <el-icon class="kpi-icon"><Tickets /></el-icon>
          </div>
          <div class="kpi-value">{{ formatCurrency(kpis.financial.total_payables) }}</div>
          <div class="kpi-label">总应付账款</div>
          <div class="kpi-footer">
            <span>已付 {{ formatCurrency(kpis.financial.total_paid) }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 第二行：待收待付 -->
    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card receivable">
          <div class="kpi-header">
            <el-icon class="kpi-icon"><Wallet /></el-icon>
            <span class="kpi-alert" v-if="kpis.financial.overdue_receivables > 0">
              {{ kpis.financial.overdue_receivables }} 笔逾期
            </span>
          </div>
          <div class="kpi-value">{{ formatCurrency(kpis.financial.receivables) }}</div>
          <div class="kpi-label">待收款</div>
          <div class="kpi-footer">
            <span>回款率 {{ kpis.financial.collection_rate }}%</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card payable">
          <div class="kpi-header">
            <el-icon class="kpi-icon"><CreditCard /></el-icon>
            <span class="kpi-alert" v-if="kpis.financial.overdue_payables > 0">
              {{ kpis.financial.overdue_payables }} 笔逾期
            </span>
          </div>
          <div class="kpi-value">{{ formatCurrency(kpis.financial.payables) }}</div>
          <div class="kpi-label">待付款</div>
          <div class="kpi-footer">
            <span>付款率 {{ kpis.financial.payment_rate }}%</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card project">
          <div class="kpi-header">
            <el-icon class="kpi-icon"><Folder /></el-icon>
          </div>
          <div class="kpi-value">{{ kpis.projects.active_count }}</div>
          <div class="kpi-label">进行中项目</div>
          <div class="kpi-footer">
            <span>总预算 {{ formatCurrency(kpis.projects.total_budget) }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card sales">
          <div class="kpi-header">
            <el-icon class="kpi-icon"><Sell /></el-icon>
          </div>
          <div class="kpi-value">{{ kpis.sales.pending_orders }}</div>
          <div class="kpi-label">待处理销售单</div>
          <div class="kpi-footer">
            <span>本月 {{ kpis.sales.monthly_orders }} 单</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card purchase">
          <div class="kpi-header">
            <el-icon class="kpi-icon"><ShoppingCart /></el-icon>
          </div>
          <div class="kpi-value">{{ kpis.purchase.pending_orders }}</div>
          <div class="kpi-label">待处理采购单</div>
          <div class="kpi-footer">
            <span>本月 {{ kpis.purchase.monthly_orders }} 单</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card inventory">
          <div class="kpi-header">
            <el-icon class="kpi-icon"><Box /></el-icon>
            <span class="kpi-alert" v-if="kpis.inventory.low_stock > 0">
              {{ kpis.inventory.low_stock }} 低库存
            </span>
          </div>
          <div class="kpi-value">{{ formatCurrency(kpis.inventory.value) }}</div>
          <div class="kpi-label">库存价值</div>
          <div class="kpi-footer">
            <span>{{ kpis.inventory.total_items }} 种物料</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 第三行：图表和表格 -->
    <el-row :gutter="16" style="margin-top: 16px;">
      <!-- 收支趋势图 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>收支趋势（近6个月）</span>
            </div>
          </template>
          <div ref="trendChart" style="height: 300px;"></div>
        </el-card>
      </el-col>

      <!-- 应收账款账龄分析 -->
      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>应收账款账龄</span>
            </div>
          </template>
          <div ref="agingChart" style="height: 300px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 第四行：待办事项 -->
    <el-row :gutter="16" style="margin-top: 16px;">
      <!-- 收款提醒 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="hover" class="alert-card">
          <template #header>
            <div class="card-header">
              <span>⚠️ 收款提醒</span>
              <el-tag type="danger" size="small">{{ overdueReceivables.length }}</el-tag>
            </div>
          </template>
          <div class="alert-list" v-if="overdueReceivables.length > 0">
            <div class="alert-item" v-for="item in overdueReceivables.slice(0, 5)" :key="item.id">
              <div class="alert-info">
                <div class="alert-title">{{ item.customer_name }}</div>
                <div class="alert-desc">{{ item.ar_no }} · 逾期{{ item.overdue_days }}天</div>
              </div>
              <div class="alert-amount text-danger">¥{{ formatNumber(item.amount_remaining) }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无逾期应收" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 付款提醒 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="hover" class="alert-card">
          <template #header>
            <div class="card-header">
              <span>📅 付款提醒</span>
              <el-tag type="warning" size="small">{{ upcomingPayables.length }}</el-tag>
            </div>
          </template>
          <div class="alert-list" v-if="upcomingPayables.length > 0">
            <div class="alert-item" v-for="item in upcomingPayables.slice(0, 5)" :key="item.id">
              <div class="alert-info">
                <div class="alert-title">{{ item.supplier_name }}</div>
                <div class="alert-desc">{{ item.ap_no }} · {{ item.days_until_due > 0 ? item.days_until_due + '天后到期' : '已逾期' }}</div>
              </div>
              <div class="alert-amount text-warning">¥{{ formatNumber(item.amount_remaining) }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无待付款项" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 项目进度 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="hover" class="alert-card">
          <template #header>
            <div class="card-header">
              <span>📊 项目进度</span>
            </div>
          </template>
          <div class="project-list" v-if="activeProjects.length > 0">
            <div class="project-item" v-for="project in activeProjects.slice(0, 5)" :key="project.id">
              <div class="project-info">
                <div class="project-name">{{ project.name }}</div>
                <div class="project-customer">{{ project.customer_name }}</div>
              </div>
              <el-progress 
                :percentage="project.progress || 0" 
                :color="getProgressColor(project.progress)"
                :stroke-width="8"
              />
            </div>
          </div>
          <el-empty v-else description="暂无进行中项目" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 第五行：Top客户和供应商 -->
    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>🏆 Top 5 客户（本月销售额）</span>
            </div>
          </template>
          <el-table :data="topCustomers" size="small" stripe>
            <el-table-column type="index" label="#" width="40" />
            <el-table-column prop="name" label="客户" show-overflow-tooltip />
            <el-table-column prop="amount" label="销售额" width="120" align="right">
              <template #default="{ row }">
                <span class="text-success">¥{{ formatNumber(row.amount) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="orders" label="订单" width="60" align="center" />
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>📦 Top 5 供应商（本月采购额）</span>
            </div>
          </template>
          <el-table :data="topSuppliers" size="small" stripe>
            <el-table-column type="index" label="#" width="40" />
            <el-table-column prop="name" label="供应商" show-overflow-tooltip />
            <el-table-column prop="amount" label="采购额" width="120" align="right">
              <template #default="{ row }">
                <span class="text-primary">¥{{ formatNumber(row.amount) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="orders" label="订单" width="60" align="center" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { TrendCharts, Coin, Wallet, CreditCard, Folder, Sell, ShoppingCart, Box, Money, Tickets } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import request from '@/utils/request'

// 数据
const kpis = ref({
  financial: {
    revenue: { total: 0, orders: 0 },
    expenses: 0,
    purchase_orders: 0,
    total_receivables: 0,
    total_received: 0,
    total_payables: 0,
    total_paid: 0,
    receivables: 0,
    payables: 0,
    overdue_receivables: 0,
    overdue_payables: 0,
    collection_rate: 0,
    payment_rate: 0,
    revenue_growth: 0
  },
  projects: {
    active_count: 0,
    total_budget: 0
  },
  sales: {
    pending_orders: 0,
    monthly_orders: 0
  },
  purchase: {
    pending_orders: 0,
    monthly_orders: 0
  },
  inventory: {
    value: 0,
    total_items: 0,
    low_stock: 0
  }
})

const overdueReceivables = ref([])
const upcomingPayables = ref([])
const activeProjects = ref([])
const topCustomers = ref([])
const topSuppliers = ref([])
const trendData = ref({ months: [], income: [], expense: [] })
const agingData = ref([])

const trendChart = ref(null)
const agingChart = ref(null)
let trendChartInstance = null
let agingChartInstance = null

// 格式化
const formatCurrency = (value) => {
  const num = Number(value) || 0
  if (num >= 10000) {
    return '¥' + (num / 10000).toFixed(1) + '万'
  }
  return '¥' + num.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

const formatNumber = (value) => {
  return Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const getProgressColor = (progress) => {
  if (progress >= 80) return '#67c23a'
  if (progress >= 50) return '#409eff'
  if (progress >= 20) return '#e6a23c'
  return '#f56c6c'
}

// 加载数据
const loadDashboardData = async () => {
  try {
    const res = await request.get('/analytics/management_dashboard/')
    const data = res.data || res
    
    kpis.value = {
      financial: {
        revenue: data.financial?.revenue || { total: 0, orders: 0 },
        expenses: data.financial?.expenses || 0,
        purchase_orders: data.financial?.purchase_orders || 0,
        total_receivables: data.financial?.total_receivables || 0,
        total_received: data.financial?.total_received || 0,
        total_payables: data.financial?.total_payables || 0,
        total_paid: data.financial?.total_paid || 0,
        receivables: data.financial?.receivables || 0,
        payables: data.financial?.payables || 0,
        overdue_receivables: data.financial?.overdue_receivables || 0,
        overdue_payables: data.financial?.overdue_payables || 0,
        collection_rate: data.financial?.collection_rate || 0,
        payment_rate: data.financial?.payment_rate || 0,
        revenue_growth: data.financial?.revenue_growth || 0
      },
      projects: data.projects || { active_count: 0, total_budget: 0 },
      sales: data.sales || { pending_orders: 0, monthly_orders: 0 },
      purchase: data.purchase || { pending_orders: 0, monthly_orders: 0 },
      inventory: data.inventory || { value: 0, total_items: 0, low_stock: 0 }
    }
    
    overdueReceivables.value = data.overdue_receivables || []
    upcomingPayables.value = data.upcoming_payables || []
    activeProjects.value = data.active_projects || []
    topCustomers.value = data.top_customers || []
    topSuppliers.value = data.top_suppliers || []
    trendData.value = data.trend_data || { months: [], income: [], expense: [] }
    agingData.value = data.aging_data || []
    
    renderCharts()
  } catch (error) {
    console.error('加载仪表盘数据失败:', error)
  }
}

// 渲染图表
const renderCharts = () => {
  renderTrendChart()
  renderAgingChart()
}

const renderTrendChart = () => {
  if (!trendChart.value) return
  
  if (!trendChartInstance) {
    trendChartInstance = echarts.init(trendChart.value)
  }
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    legend: {
      data: ['收入', '支出', '利润'],
      top: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: trendData.value.months || ['1月', '2月', '3月', '4月', '5月', '6月']
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (val) => val >= 10000 ? (val / 10000) + '万' : val
      }
    },
    series: [
      {
        name: '收入',
        type: 'bar',
        data: trendData.value.income || [0, 0, 0, 0, 0, 0],
        itemStyle: { color: '#67c23a' }
      },
      {
        name: '支出',
        type: 'bar',
        data: trendData.value.expense || [0, 0, 0, 0, 0, 0],
        itemStyle: { color: '#f56c6c' }
      },
      {
        name: '利润',
        type: 'line',
        data: (trendData.value.income || []).map((v, i) => v - (trendData.value.expense?.[i] || 0)),
        itemStyle: { color: '#409eff' },
        smooth: true
      }
    ]
  }
  
  trendChartInstance.setOption(option)
}

const renderAgingChart = () => {
  if (!agingChart.value) return
  
  if (!agingChartInstance) {
    agingChartInstance = echarts.init(agingChart.value)
  }
  
  const defaultData = [
    { name: '0-30天', value: 0 },
    { name: '31-60天', value: 0 },
    { name: '61-90天', value: 0 },
    { name: '90天以上', value: 0 }
  ]
  
  const data = agingData.value.length > 0 ? agingData.value : defaultData
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      top: 'center'
    },
    series: [
      {
        name: '账龄分布',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['60%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false
        },
        emphasis: {
          label: {
            show: true,
            fontSize: '14',
            fontWeight: 'bold'
          }
        },
        data: data.map((item, index) => ({
          ...item,
          itemStyle: {
            color: ['#67c23a', '#409eff', '#e6a23c', '#f56c6c'][index]
          }
        }))
      }
    ]
  }
  
  agingChartInstance.setOption(option)
}

// 窗口大小变化时重新渲染图表
const handleResize = () => {
  trendChartInstance?.resize()
  agingChartInstance?.resize()
}

onMounted(() => {
  loadDashboardData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChartInstance?.dispose()
  agingChartInstance?.dispose()
})
</script>

<style scoped>
.dashboard {
  padding: 16px;
  background: #f5f7fa;
  min-height: calc(100vh - 60px);
}

.kpi-card {
  border-radius: 12px;
  border: none;
  margin-bottom: 16px;
  transition: transform 0.2s, box-shadow 0.2s;
}

.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.kpi-card.income { border-top: 3px solid #67c23a; }
.kpi-card.expense { border-top: 3px solid #f56c6c; }
.kpi-card.total-ar { border-top: 3px solid #2ecc71; }
.kpi-card.total-ap { border-top: 3px solid #9b59b6; }
.kpi-card.receivable { border-top: 3px solid #409eff; }
.kpi-card.payable { border-top: 3px solid #e6a23c; }
.kpi-card.project { border-top: 3px solid #8e44ad; }
.kpi-card.sales { border-top: 3px solid #3498db; }
.kpi-card.purchase { border-top: 3px solid #1abc9c; }
.kpi-card.inventory { border-top: 3px solid #34495e; }

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.kpi-icon {
  font-size: 24px;
  color: #909399;
}

.kpi-trend {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
}

.kpi-trend.up {
  background: #e8f5e9;
  color: #4caf50;
}

.kpi-alert {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  background: #fff3e0;
  color: #ff9800;
}

.kpi-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}

.kpi-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.kpi-footer {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.alert-card {
  height: 320px;
}

.alert-list {
  max-height: 240px;
  overflow-y: auto;
}

.alert-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}

.alert-item:last-child {
  border-bottom: none;
}

.alert-info {
  flex: 1;
  min-width: 0;
}

.alert-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alert-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.alert-amount {
  font-size: 14px;
  font-weight: 600;
  margin-left: 12px;
  white-space: nowrap;
}

.project-list {
  max-height: 240px;
  overflow-y: auto;
}

.project-item {
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}

.project-item:last-child {
  border-bottom: none;
}

.project-info {
  margin-bottom: 8px;
}

.project-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.project-customer {
  font-size: 12px;
  color: #909399;
}

.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }
.text-warning { color: #e6a23c; }
.text-primary { color: #409eff; }

@media (max-width: 768px) {
  .dashboard { padding: 10px; }
  .kpi-value { font-size: 22px; }
  .alert-card { height: auto; min-height: 200px; }
}
</style>
