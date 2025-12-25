<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <!-- Financial KPIs - Responsive -->
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card">
          <div class="kpi-icon revenue">
            <el-icon><Money /></el-icon>
          </div>
          <div class="kpi-content">
            <div class="kpi-value">{{ formatCurrency(kpis.financial.revenue.total) }}</div>
            <div class="kpi-label">总收入</div>
            <div class="kpi-detail">{{ kpis.financial.revenue.orders }} 订单</div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card">
          <div class="kpi-icon projects">
            <el-icon><Document /></el-icon>
          </div>
          <div class="kpi-content">
            <div class="kpi-value">{{ kpis.projects.active_projects }}</div>
            <div class="kpi-label">活跃项目</div>
            <div class="kpi-detail">{{ formatCurrency(kpis.projects.total_budget) }} 预算</div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card">
          <div class="kpi-icon inventory">
            <el-icon><Box /></el-icon>
          </div>
          <div class="kpi-content">
            <div class="kpi-value">{{ formatCurrency(kpis.inventory.inventory_value) }}</div>
            <div class="kpi-label">库存价值</div>
            <div class="kpi-detail">{{ kpis.inventory.total_items }} 物料</div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card">
          <div class="kpi-icon cash">
            <el-icon><Wallet /></el-icon>
          </div>
          <div class="kpi-content">
            <div class="kpi-value">{{ formatCurrency(kpis.financial.net_cash_position) }}</div>
            <div class="kpi-label">资金净额</div>
            <div class="kpi-detail">应收 - 应付</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts Row - Responsive -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <span>现金流预测（30天）</span>
          </template>
          <div ref="cashFlowChart" style="height: 300px;"></div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card shadow="hover">
          <template #header>
            <span>项目完成状态</span>
          </template>
          <div ref="projectChart" style="height: 300px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Alerts and Notifications -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <span>最近提醒</span>
          </template>
          <el-table :data="notifications" style="width: 100%">
            <el-table-column prop="type" label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="getNotificationType(row.type)">{{ row.type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" />
            <el-table-column prop="message" label="消息" />
            <el-table-column prop="created_at" label="时间" width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button 
                  v-if="!row.is_read" 
                  size="small" 
                  @click="markAsRead(row.id)"
                >
                  标为已读
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Money, Document, Box, Wallet } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import request from '@/utils/request'

const kpis = ref({
  financial: {
    revenue: { total: 0, orders: 0 },
    purchases: { total: 0, orders: 0 },
    receivables: 0,
    payables: 0,
    net_cash_position: 0
  },
  projects: {
    active_projects: 0,
    total_budget: 0,
    task_completion_rate: 0,
    total_tasks: 0,
    completed_tasks: 0
  },
  inventory: {
    inventory_value: 0,
    total_items: 0,
    low_stock_items: 0,
    recent_movements: 0
  }
})

const cashFlowForecast = ref({})
const notifications = ref([])
const cashFlowChart = ref(null)
const projectChart = ref(null)

const formatCurrency = (value) => {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY'
  }).format(value || 0)
}

const formatDateTime = (dateStr) => {
  return new Date(dateStr).toLocaleString()
}

const getNotificationType = (type) => {
  const types = {
    'INFO': 'info',
    'WARNING': 'warning',
    'ERROR': 'danger',
    'SUCCESS': 'success'
  }
  return types[type] || 'info'
}

const loadKPIs = async () => {
  try {
    const res = await request.get('/analytics/dashboard/')
    const data = res.data || res
    // 后端返回格式: { financial: {...}, projects: {...}, inventory: {...} }
    kpis.value = {
      financial: {
        revenue: { 
          total: data.financial?.revenue?.total || 0, 
          orders: data.financial?.revenue?.orders || 0 
        },
        purchases: {
          total: data.financial?.purchases?.total || 0,
          orders: data.financial?.purchases?.orders || 0
        },
        receivables: data.financial?.receivables || 0,
        payables: data.financial?.payables || 0,
        net_cash_position: data.financial?.net_cash_position || 0
      },
      projects: {
        active_projects: data.projects?.active_projects || 0,
        total_budget: data.projects?.total_budget || 0,
        task_completion_rate: data.projects?.task_completion_rate || 0,
        total_tasks: data.projects?.total_tasks || 0,
        completed_tasks: data.projects?.completed_tasks || 0
      },
      inventory: {
        inventory_value: data.inventory?.inventory_value || 0,
        total_items: data.inventory?.total_items || 0,
        low_stock_items: data.inventory?.low_stock_items || 0,
        recent_movements: data.inventory?.recent_movements || 0
      }
    }
  } catch (error) {
    console.error('Failed to load KPIs', error)
    // 设置默认空数据
    kpis.value = {
      financial: {
        revenue: { total: 0, orders: 0 },
        purchases: { total: 0, orders: 0 },
        receivables: 0,
        payables: 0,
        net_cash_position: 0
      },
      projects: {
        active_projects: 0,
        total_budget: 0,
        task_completion_rate: 0,
        total_tasks: 0,
        completed_tasks: 0
      },
      inventory: {
        inventory_value: 0,
        total_items: 0,
        low_stock_items: 0,
        recent_movements: 0
      }
    }
  }
}

const loadCashFlowForecast = async () => {
  try {
    const res = await request.get('/analytics/cash_flow_forecast/')
    const data = res.data || res
    cashFlowForecast.value = data
    renderCashFlowChart()
  } catch (error) {
    console.error('Failed to load cash flow forecast', error)
    // 设置默认空数据
    cashFlowForecast.value = {
      expected_inflows: 0,
      expected_outflows: 0,
      net_cash_flow: 0
    }
    renderCashFlowChart()
  }
}

const loadNotifications = async () => {
  try {
    const response = await request.get('/core/notifications/')
    notifications.value = (response.results || response || []).slice(0, 5)
  } catch (error) {
    console.error('Failed to load notifications', error)
    notifications.value = []
  }
}

const markAsRead = async (id) => {
  try {
    await request.post(`/core/notifications/${id}/mark_read/`)
    loadNotifications()
  } catch (error) {
    console.error('Failed to mark notification as read', error)
  }
}

const renderCashFlowChart = () => {
  if (!cashFlowChart.value) return
  
  const chart = echarts.init(cashFlowChart.value)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    legend: {
      data: ['预期流出', '净现金流'],
      top: 10
    },
    xAxis: {
      type: 'category',
      data: ['未来30天']
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '预期流入',
        type: 'bar',
        data: [cashFlowForecast.value.expected_inflows || 0],
        itemStyle: { color: '#67C23A' }
      },
      {
        name: '预期流出',
        type: 'bar',
        data: [cashFlowForecast.value.expected_outflows || 0],
        itemStyle: { color: '#F56C6C' }
      },
      {
        name: '净现金流',
        type: 'bar',
        data: [cashFlowForecast.value.net_cash_flow || 0],
        itemStyle: { color: '#409EFF' }
      }
    ]
  }
  
  chart.setOption(option)
}

const renderProjectChart = () => {
  if (!projectChart.value) return
  
  const chart = echarts.init(projectChart.value)
  
  const completionRate = kpis.value.projects.task_completion_rate || 0
  
  const option = {
    tooltip: {
      trigger: 'item'
    },
    series: [
      {
        name: '任务',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false,
          position: 'center'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: '20',
            fontWeight: 'bold'
          }
        },
        labelLine: {
          show: false
        },
        data: [
          { 
            value: kpis.value.projects.completed_tasks, 
            name: '已完成',
            itemStyle: { color: '#67C23A' }
          },
          { 
            value: kpis.value.projects.total_tasks - kpis.value.projects.completed_tasks, 
            name: '进行中',
            itemStyle: { color: '#E6A23C' }
          }
        ]
      }
    ]
  }
  
  chart.setOption(option)
}

onMounted(async () => {
  await loadKPIs()
  await loadCashFlowForecast()
  await loadNotifications()
  
  // Render charts after data is loaded
  setTimeout(() => {
    renderProjectChart()
  }, 300)
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.kpi-card {
  padding: 20px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
}

.kpi-icon {
  width: 60px;
  height: 60px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
  color: white;
  margin-right: 20px;
  flex-shrink: 0;
}

.kpi-icon.revenue {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.kpi-icon.projects {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.kpi-icon.inventory {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}

.kpi-icon.cash {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
}

.kpi-content {
  flex: 1;
  min-width: 0;
}

.kpi-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kpi-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.kpi-detail {
  font-size: 12px;
  color: #C0C4CC;
  margin-top: 5px;
}

/* Responsive styles */
@media (max-width: 768px) {
  .dashboard {
    padding: 10px;
  }
  
  .kpi-card {
    padding: 15px;
  }
  
  .kpi-icon {
    width: 50px;
    height: 50px;
    font-size: 24px;
    margin-right: 15px;
  }
  
  .kpi-value {
    font-size: 20px;
  }
}

@media (max-width: 480px) {
  .kpi-icon {
    width: 40px;
    height: 40px;
    font-size: 20px;
    margin-right: 10px;
  }
  
  .kpi-value {
    font-size: 18px;
  }
  
  .kpi-label {
    font-size: 12px;
  }
}
</style>
