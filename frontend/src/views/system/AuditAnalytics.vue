<template>
  <div class="audit-analytics">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value primary">{{ stats.summary?.total || 0 }}</div>
          <div class="stat-label">总操作数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value success">{{ stats.summary?.today || 0 }}</div>
          <div class="stat-label">今日操作</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value warning">{{ stats.summary?.this_week || 0 }}</div>
          <div class="stat-label">本周操作</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value info">{{ stats.summary?.this_month || 0 }}</div>
          <div class="stat-label">本月操作</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="16" style="margin-top: 20px">
      <el-col :span="16">
        <el-card>
          <template #header>近30天操作趋势</template>
          <div ref="trendChart" style="height: 300px"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>操作类型分布</template>
          <div ref="actionPieChart" style="height: 300px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>活跃用户TOP10</template>
          <el-table :data="stats.by_user" size="small" stripe>
            <el-table-column prop="user__username" label="用户" />
            <el-table-column prop="count" label="操作次数" width="100" align="right">
              <template #default="{ row }">
                <el-tag type="primary">{{ row.count }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="占比" width="150">
              <template #default="{ row }">
                <el-progress 
                  :percentage="getPercentage(row.count)" 
                  :stroke-width="10" 
                  :show-text="false"
                />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>今日操作时段分布</template>
          <div ref="hourlyChart" style="height: 280px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 安全分析 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>安全分析</span>
          <el-button type="primary" size="small" @click="fetchSecurityData">刷新</el-button>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic title="敏感操作(本周)" :value="security.sensitive_operations?.count || 0" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="登录成功" :value="security.login_stats?.success || 0" value-style="color: #67c23a" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="登录失败" :value="security.login_stats?.failed || 0" value-style="color: #f56c6c" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="账户锁定" :value="security.login_stats?.locked || 0" value-style="color: #e6a23c" />
        </el-col>
      </el-row>

      <el-divider />

      <h4>最近敏感操作</h4>
      <el-table :data="security.recent_sensitive" size="small" stripe max-height="300">
        <el-table-column prop="user" label="用户" width="100" />
        <el-table-column prop="action" label="操作" width="100">
          <template #default="{ row }">
            <el-tag :type="getActionType(row.action)" size="small">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content_type" label="模块" width="150" />
        <el-table-column prop="object_id" label="对象ID" width="100" />
        <el-table-column prop="ip_address" label="IP地址" width="130" />
        <el-table-column prop="created_at" label="时间" min-width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'


const stats = ref({})
const security = ref({})

const trendChart = ref(null)
const actionPieChart = ref(null)
const hourlyChart = ref(null)
let trendChartInstance = null
let pieChartInstance = null
let hourlyChartInstance = null

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getPercentage = (count) => {
  const maxCount = Math.max(...(stats.value.by_user || []).map(u => u.count), 1)
  return Math.round((count / maxCount) * 100)
}

const getActionType = (action) => {
  const types = {
    'delete': 'danger',
    'bulk_delete': 'danger',
    'export': 'warning',
    'approve': 'success',
    'reject': 'warning'
  }
  return types[action] || 'info'
}

const fetchStats = async () => {
  try {
    const res = await request({ url: '/core/audit-analytics/', method: 'get' })
    stats.value = res || {}
    nextTick(() => {
      renderTrendChart()
      renderPieChart()
      renderHourlyChart()
    })
  } catch (error) {
    console.error('获取统计失败', error)
  }
}

const fetchSecurityData = async () => {
  try {
    const res = await request({ url: '/core/audit-analytics/security/', method: 'get' })
    security.value = res || {}
  } catch (error) {
    console.error('获取安全数据失败', error)
  }
}

const renderTrendChart = () => {
  if (!trendChart.value) return
  
  if (!trendChartInstance) {
    trendChartInstance = echarts.init(trendChart.value)
  }
  
  const data = stats.value.daily_trend || []
  
  trendChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: data.map(d => d.date?.substring(5) || ''),
      axisLabel: { rotate: 45 }
    },
    yAxis: { type: 'value', name: '操作数' },
    series: [{
      type: 'line',
      data: data.map(d => d.count),
      smooth: true,
      areaStyle: { opacity: 0.3 },
      itemStyle: { color: '#409eff' }
    }]
  })
}

const renderPieChart = () => {
  if (!actionPieChart.value) return
  
  if (!pieChartInstance) {
    pieChartInstance = echarts.init(actionPieChart.value)
  }
  
  const data = (stats.value.by_action || []).slice(0, 8)
  
  pieChartInstance.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: data.map(d => ({
        name: d.action,
        value: d.count
      })),
      label: { show: true, formatter: '{b}' }
    }]
  })
}

const renderHourlyChart = () => {
  if (!hourlyChart.value) return
  
  if (!hourlyChartInstance) {
    hourlyChartInstance = echarts.init(hourlyChart.value)
  }
  
  const data = stats.value.hourly_distribution || []
  
  // 填充24小时数据
  const hourlyData = Array(24).fill(0)
  data.forEach(d => {
    const hour = new Date(d.hour).getHours()
    hourlyData[hour] = d.count
  })
  
  hourlyChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: Array.from({length: 24}, (_, i) => `${i}:00`),
      axisLabel: { rotate: 45 }
    },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: hourlyData,
      itemStyle: { color: '#67c23a' }
    }]
  })
}

onMounted(() => {
  fetchStats()
  fetchSecurityData()
})
</script>

<style scoped>
.audit-analytics {
  padding: 20px;
}
.stat-cards {
  margin-bottom: 10px;
}
.stat-card {
  text-align: center;
  padding: 15px;
}
.stat-value {
  font-size: 32px;
  font-weight: bold;
}
.stat-value.primary { color: #409eff; }
.stat-value.success { color: #67c23a; }
.stat-value.warning { color: #e6a23c; }
.stat-value.info { color: #909399; }
.stat-label {
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
