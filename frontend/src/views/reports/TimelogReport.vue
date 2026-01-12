<template>
  <div class="timelog-report">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ statistics.today_hours?.toFixed(1) || 0 }}</div>
          <div class="stat-label">今日工时</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ statistics.week_hours?.toFixed(1) || 0 }}</div>
          <div class="stat-label">本周工时</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ statistics.month_hours?.toFixed(1) || 0 }}</div>
          <div class="stat-label">本月工时</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ avgDailyHours }}</div>
          <div class="stat-label">日均工时</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选和图表 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>工时统计报表</span>
          <div class="filter-area">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="-"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              @change="fetchData"
            />
            <el-select v-model="groupBy" placeholder="分组方式" @change="handleGroupChange">
              <el-option label="按用户" value="user" />
              <el-option label="按项目" value="project" />
            </el-select>
            <el-button type="primary" @click="exportReport">
              <el-icon><Download /></el-icon> 导出
            </el-button>
          </div>
        </div>
      </template>

      <!-- 趋势图 -->
      <div class="chart-container">
        <h4>本月工时趋势</h4>
        <div ref="trendChart" style="height: 300px"></div>
      </div>

      <el-divider />

      <!-- 分组统计表格 -->
      <el-table :data="groupedData" stripe v-loading="loading" style="width: 100%">
        <el-table-column :prop="groupBy === 'user' ? 'user__username' : 'project__name'" 
                         :label="groupBy === 'user' ? '用户' : '项目'" 
                         min-width="150" />
        <el-table-column prop="total_hours" label="总工时" width="120" align="right">
          <template #default="{ row }">
            {{ row.total_hours?.toFixed(1) }} h
          </template>
        </el-table-column>
        <el-table-column prop="work_days" label="工作天数" width="100" v-if="groupBy === 'user'" />
        <el-table-column prop="unique_users" label="参与人数" width="100" v-if="groupBy === 'project'" />
        <el-table-column prop="log_count" label="填报次数" width="100" />
        <el-table-column label="日均工时" width="120" align="right" v-if="groupBy === 'user'">
          <template #default="{ row }">
            {{ row.work_days ? (row.total_hours / row.work_days).toFixed(1) : 0 }} h
          </template>
        </el-table-column>
        <el-table-column label="工时占比" width="150">
          <template #default="{ row }">
            <el-progress :percentage="getPercentage(row.total_hours)" :stroke-width="10" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 项目工时分布 -->
    <el-row :gutter="16" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>项目工时分布</template>
          <div ref="projectPieChart" style="height: 300px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>加班统计</template>
          <el-table :data="overtimeData" stripe size="small">
            <el-table-column prop="username" label="用户" />
            <el-table-column prop="total_hours" label="总工时" width="100">
              <template #default="{ row }">{{ row.total_hours?.toFixed(1) }} h</template>
            </el-table-column>
            <el-table-column prop="overtime_hours" label="加班工时" width="100">
              <template #default="{ row }">
                <span :class="{ 'overtime-highlight': row.overtime_hours > 20 }">
                  {{ row.overtime_hours?.toFixed(1) }} h
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="overtime_days" label="加班天数" width="100" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import request from '@/utils/request'

const loading = ref(false)
const statistics = ref({})
const groupedData = ref([])
const overtimeData = ref([])
const dateRange = ref([])
const groupBy = ref('user')

let trendChartInstance = null
let pieChartInstance = null
const trendChart = ref(null)
const projectPieChart = ref(null)

const avgDailyHours = computed(() => {
  if (!statistics.value.daily_trend?.length) return 0
  const workDays = statistics.value.daily_trend.length
  return workDays ? (statistics.value.month_hours / workDays).toFixed(1) : 0
})

const getPercentage = (hours) => {
  const maxHours = Math.max(...groupedData.value.map(d => d.total_hours || 0), 1)
  return Math.round((hours / maxHours) * 100)
}

const fetchStatistics = async () => {
  try {
    const res = await request({ url: '/reports/timelog/statistics/', method: 'get' })
    statistics.value = res || {}
    renderTrendChart()
    renderPieChart()
  } catch (error) {
    console.error('获取统计失败', error)
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {}
    if (dateRange.value?.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    
    const endpoint = groupBy.value === 'user' 
      ? '/reports/timelog/by-user/' 
      : '/reports/timelog/by-project/'
    
    const res = await request({ url: endpoint, method: 'get', params })
    groupedData.value = groupBy.value === 'user' ? res?.by_user || [] : res?.by_project || []
  } catch (error) {
    console.error('获取数据失败', error)
  } finally {
    loading.value = false
  }
}

const fetchOvertime = async () => {
  try {
    const params = {}
    if (dateRange.value?.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await request({ url: '/reports/timelog/overtime/', method: 'get', params })
    overtimeData.value = res?.overtime_by_user || []
  } catch (error) {
    console.error('获取加班数据失败', error)
  }
}

const handleGroupChange = () => {
  fetchData()
}

const renderTrendChart = () => {
  if (!trendChart.value) return
  
  if (!trendChartInstance) {
    trendChartInstance = echarts.init(trendChart.value)
  }
  
  const data = statistics.value.daily_trend || []
  
  trendChartInstance.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: data.map(d => d.date?.substring(5) || ''),
      axisLabel: { rotate: 45 }
    },
    yAxis: { type: 'value', name: '工时 (h)' },
    series: [{
      type: 'bar',
      data: data.map(d => d.hours),
      itemStyle: { color: '#409eff' }
    }]
  })
}

const renderPieChart = () => {
  if (!projectPieChart.value) return
  
  if (!pieChartInstance) {
    pieChartInstance = echarts.init(projectPieChart.value)
  }
  
  const data = (statistics.value.by_project || []).slice(0, 8)
  
  pieChartInstance.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}h ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: data.map(d => ({
        name: d.project__name || '未知项目',
        value: d.hours
      })),
      label: { show: true, formatter: '{b}' }
    }]
  })
}

const exportReport = () => {
  ElMessage.info('导出功能开发中')
}

onMounted(async () => {
  await fetchStatistics()
  await fetchData()
  await fetchOvertime()
  
  nextTick(() => {
    renderTrendChart()
    renderPieChart()
  })
})
</script>

<style scoped>
.timelog-report {
  padding: 20px;
}
.stat-cards {
  margin-bottom: 20px;
}
.stat-card {
  text-align: center;
  padding: 15px;
}
.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}
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
.filter-area {
  display: flex;
  gap: 12px;
  align-items: center;
}
.chart-container {
  padding: 10px 0;
}
.chart-container h4 {
  margin: 0 0 10px 0;
  color: #303133;
}
.overtime-highlight {
  color: #f56c6c;
  font-weight: bold;
}
</style>
