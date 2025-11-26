<template>
  <div class="project-analytics">
    <el-row :gutter="20">
      <!-- Summary Cards -->
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="card-content">
            <div class="icon projects">
              <el-icon><Management /></el-icon>
            </div>
            <div class="info">
              <div class="value">{{ summary.total_projects }}</div>
              <div class="label">总项目数</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="card-content">
            <div class="icon revenue">
              <el-icon><Money /></el-icon>
            </div>
            <div class="info">
              <div class="value">{{ formatCurrency(summary.total_revenue) }}</div>
              <div class="label">总收入</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="card-content">
            <div class="icon profit">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="info">
              <div class="value">{{ formatCurrency(summary.total_profit) }}</div>
              <div class="label">总利润</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>项目状态分布</span>
          </template>
          <div ref="statusChart" style="height: 350px;"></div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>项目利润率分布</span>
          </template>
          <div ref="profitChart" style="height: 350px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <span>项目成本结构分析</span>
          </template>
          <div ref="costChart" style="height: 350px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Project Performance Table -->
    <el-row style="margin-top: 20px;">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>项目绩效排行</span>
              <el-select v-model="sortBy" @change="loadProjectPerformance">
                <el-option label="按利润率" value="margin" />
                <el-option label="按收入" value="revenue" />
                <el-option label="按利润" value="profit" />
              </el-select>
            </div>
          </template>

          <el-table :data="topProjects" stripe border>
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="name" label="项目名称" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="revenue" label="收入" width="120">
              <template #default="{ row }">
                {{ formatCurrency(row.revenue) }}
              </template>
            </el-table-column>
            <el-table-column prop="total_cost" label="总成本" width="120">
              <template #default="{ row }">
                {{ formatCurrency(row.total_cost) }}
              </template>
            </el-table-column>
            <el-table-column prop="profit" label="利润" width="120">
              <template #default="{ row }">
                {{ formatCurrency(row.profit) }}
              </template>
            </el-table-column>
            <el-table-column prop="profit_margin" label="利润率" width="100">
              <template #default="{ row }">
                <el-tag :type="getMarginType(row.profit_margin)">
                  {{ (row.profit_margin || 0).toFixed(2) }}%
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Management, Money, TrendCharts } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'

const summary = reactive({
  total_projects: 0,
  total_revenue: 0,
  total_profit: 0
})

const topProjects = ref([])
const sortBy = ref('margin')

const statusChart = ref(null)
const profitChart = ref(null)
const costChart = ref(null)

const formatCurrency = (value) => {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY'
  }).format(value || 0)
}

const getStatusLabel = (status) => {
  const labels = {
    'DRAFT': '草稿',
    'PLANNING': '规划中',
    'ACTIVE': '进行中',
    'PAUSED': '暂停',
    'COMPLETED': '已完成',
    'CANCELLED': '已取消',
    'ARCHIVED': '已归档'
  }
  return labels[status] || status
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'PLANNING': 'info',
    'ACTIVE': 'success',
    'PAUSED': 'warning',
    'COMPLETED': 'primary',
    'CANCELLED': 'danger',
    'ARCHIVED': 'info'
  }
  return types[status] || 'info'
}

const getMarginType = (margin) => {
  if (margin < 0) return 'danger'
  if (margin < 10) return 'warning'
  if (margin < 20) return 'info'
  return 'success'
}

const loadProjectPerformance = async () => {
  try {
    const res = await request.get('/reports/profitability/')
    // 后端返回的是数组或者 {data: [...]} 格式
    let data = []
    if (Array.isArray(res)) {
      data = res
    } else if (res.data) {
      data = Array.isArray(res.data) ? res.data : (res.data.results || [])
    } else if (res.results) {
      data = res.results
    }
    
    // Calculate summary
    summary.total_projects = data.length
    summary.total_revenue = data.reduce((sum, p) => sum + (parseFloat(p.revenue) || 0), 0)
    summary.total_profit = data.reduce((sum, p) => sum + (parseFloat(p.profit) || 0), 0)
    
    // 标准化数据格式 - 后端返回 margin_percent，前端需要 profit_margin
    const normalizedData = data.map(p => ({
      ...p,
      profit_margin: parseFloat(p.margin_percent) || parseFloat(p.profit_margin) || 0,
      total_cost: parseFloat(p.total_cost) || 0,
      revenue: parseFloat(p.revenue) || 0,
      profit: parseFloat(p.profit) || 0,
      material_cost: parseFloat(p.material_cost) || 0,
      labor_cost: parseFloat(p.labor_cost) || 0,
      expense_cost: parseFloat(p.expense_cost) || 0,
    }))
    
    // Sort projects
    const sorted = [...normalizedData].sort((a, b) => {
      if (sortBy.value === 'margin') return (b.profit_margin || 0) - (a.profit_margin || 0)
      if (sortBy.value === 'revenue') return (b.revenue || 0) - (a.revenue || 0)
      return (b.profit || 0) - (a.profit || 0)
    })
    
    topProjects.value = sorted.slice(0, 10)
    
    renderCharts(normalizedData)
  } catch (error) {
    console.error('加载项目分析数据失败', error)
    // 使用空数据
    summary.total_projects = 0
    summary.total_revenue = 0
    summary.total_profit = 0
    topProjects.value = []
    renderCharts([])
  }
}

const renderCharts = (projects) => {
  renderStatusChart(projects)
  renderProfitChart(projects)
  renderCostChart(projects)
}

const renderStatusChart = (projects) => {
  if (!statusChart.value) return
  
  const chart = echarts.init(statusChart.value)
  
  // Count by status
  const statusCount = {}
  projects.forEach(p => {
    statusCount[p.status] = (statusCount[p.status] || 0) + 1
  })
  
  const data = Object.entries(statusCount).map(([status, count]) => ({
    name: getStatusLabel(status),
    value: count
  }))
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [
      {
        name: '项目状态',
        type: 'pie',
        radius: '60%',
        data: data,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }
  
  chart.setOption(option)
}

const renderProfitChart = (projects) => {
  if (!profitChart.value) return
  
  const chart = echarts.init(profitChart.value)
  
  // Group by profit margin ranges
  const ranges = {
    '负利润': 0,
    '0-10%': 0,
    '10-20%': 0,
    '20-30%': 0,
    '30%以上': 0
  }
  
  projects.forEach(p => {
    const margin = p.profit_margin
    if (margin < 0) ranges['负利润']++
    else if (margin < 10) ranges['0-10%']++
    else if (margin < 20) ranges['10-20%']++
    else if (margin < 30) ranges['20-30%']++
    else ranges['30%以上']++
  })
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    xAxis: {
      type: 'category',
      data: Object.keys(ranges)
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '项目数量',
        type: 'bar',
        data: Object.values(ranges),
        itemStyle: {
          color: '#5470c6'
        }
      }
    ]
  }
  
  chart.setOption(option)
}

const renderCostChart = (projects) => {
  if (!costChart.value) return
  
  const chart = echarts.init(costChart.value)
  
  // Calculate average cost structure
  const avgCosts = {
    material_cost: 0,
    labor_cost: 0,
    expense_cost: 0
  }
  
  projects.forEach(p => {
    avgCosts.material_cost += p.material_cost || 0
    avgCosts.labor_cost += p.labor_cost || 0
    avgCosts.expense_cost += p.expense_cost || 0
  })
  
  const total = Object.values(avgCosts).reduce((sum, v) => sum + v, 0)
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)'
    },
    legend: {
      top: 'bottom'
    },
    series: [
      {
        name: '成本结构',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          formatter: (params) => `${params.name}\n¥${params.value.toFixed(2)}`
        },
        data: [
          { value: avgCosts.material_cost, name: '材料成本' },
          { value: avgCosts.labor_cost, name: '人工成本' },
          { value: avgCosts.expense_cost, name: '费用成本' }
        ]
      }
    ]
  }
  
  chart.setOption(option)
}

onMounted(() => {
  loadProjectPerformance()
})
</script>

<style scoped>
.project-analytics {
  padding: 20px;
}

.summary-card .card-content {
  display: flex;
  align-items: center;
}

.summary-card .icon {
  width: 60px;
  height: 60px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
  color: white;
  margin-right: 20px;
}

.summary-card .icon.projects {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.summary-card .icon.revenue {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.summary-card .icon.profit {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.summary-card .info .value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.summary-card .info .label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>

