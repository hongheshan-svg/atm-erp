<template>
  <div class="cost-dashboard">
    <!-- 项目选择器 -->
    <el-card class="filter-card">
      <el-row :gutter="20" align="middle">
        <el-col :span="8">
          <el-select v-model="selectedProject" filterable placeholder="选择项目" style="width: 100%" @change="loadProjectCost">
            <el-option v-for="p in projects" :key="p.id" :label="`${p.project_no} - ${p.name}`" :value="p.id" />
          </el-select>
        </el-col>
        <el-col :span="16" class="project-info" v-if="projectData">
          <span class="info-item"><strong>客户：</strong>{{ projectData.project?.customer_name }}</span>
          <span class="info-item"><strong>状态：</strong>{{ projectData.project?.status }}</span>
          <el-tag :type="warningType" size="large" style="margin-left: 16px">
            预算使用率: {{ projectData.budget_used_rate || 0 }}%
          </el-tag>
        </el-col>
      </el-row>
    </el-card>

    <div v-if="projectData" v-loading="loading">
      <!-- 成本概览 -->
      <el-row :gutter="16" class="stat-row">
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">预算总额</div>
            <div class="stat-value">¥{{ formatMoney(projectData.budget_total) }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card primary">
            <div class="stat-label">实际成本</div>
            <div class="stat-value">¥{{ formatMoney(projectData.actual_total) }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" :class="['stat-card', remainingClass]">
            <div class="stat-label">剩余预算</div>
            <div class="stat-value">¥{{ formatMoney(projectData.budget_total - projectData.actual_total) }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">待处理预警</div>
            <div class="stat-value warning-text">{{ projectData.pending_alerts || 0 }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 预算vs实际对比 -->
      <el-row :gutter="16">
        <el-col :span="14">
          <el-card>
            <template #header>
              <span>预算 vs 实际成本对比</span>
            </template>
            <div ref="comparisonChartRef" style="height: 350px"></div>
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card>
            <template #header>
              <span>成本构成分布</span>
            </template>
            <div ref="pieChartRef" style="height: 350px"></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 成本趋势和阶段分布 -->
      <el-row :gutter="16" style="margin-top: 16px">
        <el-col :span="14">
          <el-card>
            <template #header>
              <span>成本趋势</span>
            </template>
            <div ref="trendChartRef" style="height: 300px"></div>
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card>
            <template #header>
              <span>各阶段成本</span>
            </template>
            <el-table :data="phaseCosts" size="small" max-height="280">
              <el-table-column prop="project_phase" label="阶段" width="120">
                <template #default="{ row }">{{ getPhaseLabel(row.project_phase) }}</template>
              </el-table-column>
              <el-table-column label="金额" align="right">
                <template #default="{ row }">¥{{ formatMoney(row.total) }}</template>
              </el-table-column>
              <el-table-column label="占比" width="80" align="center">
                <template #default="{ row }">
                  {{ ((row.total / projectData.actual_total) * 100).toFixed(1) }}%
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>

      <!-- 最近成本记录 -->
      <el-card style="margin-top: 16px">
        <template #header>
          <div class="card-header">
            <span>最近成本记录</span>
            <el-button type="primary" link @click="viewAllRecords">查看全部</el-button>
          </div>
        </template>
        <el-table :data="recentCosts" size="small">
          <el-table-column prop="cost_date" label="日期" width="110" />
          <el-table-column prop="cost_type_display" label="类型" width="90" />
          <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip />
          <el-table-column prop="source_doc_no" label="单据号" width="130" />
          <el-table-column label="金额" width="120" align="right">
            <template #default="{ row }">¥{{ formatMoney(row.amount) }}</template>
          </el-table-column>
          <el-table-column prop="is_verified" label="核实" width="70" align="center">
            <template #default="{ row }">
              <el-icon :color="row.is_verified ? '#67c23a' : '#909399'">
                <Check v-if="row.is_verified" /><Close v-else />
              </el-icon>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 未选择项目提示 -->
    <el-empty v-else description="请选择项目查看成本看板" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Check, Close } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import request from '@/utils/request'

const router = useRouter()

const loading = ref(false)
const projects = ref([])
const selectedProject = ref(null)
const projectData = ref(null)

const comparisonChartRef = ref(null)
const pieChartRef = ref(null)
const trendChartRef = ref(null)
let comparisonChart = null
let pieChart = null
let trendChart = null

const phaseCosts = computed(() => projectData.value?.phase_costs || [])
const recentCosts = computed(() => projectData.value?.recent_costs || [])

const warningType = computed(() => {
  if (!projectData.value) return 'info'
  if (projectData.value.warning_status === 'critical') return 'danger'
  if (projectData.value.warning_status === 'warning') return 'warning'
  return 'success'
})

const remainingClass = computed(() => {
  const remaining = (projectData.value?.budget_total || 0) - (projectData.value?.actual_total || 0)
  if (remaining < 0) return 'danger'
  if (projectData.value?.budget_used_rate > 80) return 'warning'
  return 'success'
})

const formatMoney = (val) => {
  if (!val) return '0.00'
  return parseFloat(val).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

const getPhaseLabel = (phase) => {
  const map = {
    DESIGN: '设计阶段',
    PROCUREMENT: '采购阶段',
    PRODUCTION: '生产阶段',
    ASSEMBLY: '装配阶段',
    TESTING: '测试阶段',
    INSTALLATION: '安装调试',
    ACCEPTANCE: '验收阶段',
    WARRANTY: '质保期'
  }
  return map[phase] || phase
}

const loadProjects = async () => {
  const res = await request.get('/api/projects/projects/', { 
    params: { page_size: 500, status__in: 'IN_PROGRESS,DEBUGGING,INSTALLATION' } 
  })
  projects.value = res.data.results || res.data
}

const loadProjectCost = async () => {
  if (!selectedProject.value) {
    projectData.value = null
    return
  }
  
  loading.value = true
  try {
    const res = await request.get(`/api/projects/cost/dashboard/${selectedProject.value}/`)
    projectData.value = res.data
    await nextTick()
    renderCharts()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const renderCharts = () => {
  if (!projectData.value) return
  
  // 预算vs实际对比图
  if (comparisonChartRef.value) {
    if (!comparisonChart) {
      comparisonChart = echarts.init(comparisonChartRef.value)
    }
    const comparison = projectData.value.budget_comparison || []
    comparisonChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['预算', '实际', '差异'] },
      xAxis: {
        type: 'category',
        data: comparison.map(c => c.cost_type_display)
      },
      yAxis: { type: 'value' },
      series: [
        { name: '预算', type: 'bar', data: comparison.map(c => c.budget) },
        { name: '实际', type: 'bar', data: comparison.map(c => c.actual) },
        { name: '差异', type: 'bar', data: comparison.map(c => c.variance) }
      ]
    })
  }

  // 成本构成饼图
  if (pieChartRef.value) {
    if (!pieChart) {
      pieChart = echarts.init(pieChartRef.value)
    }
    const comparison = projectData.value.budget_comparison || []
    pieChart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: comparison.filter(c => c.actual > 0).map(c => ({
          name: c.cost_type_display,
          value: c.actual
        })),
        label: { formatter: '{b}\n{d}%' }
      }]
    })
  }

  // 成本趋势图
  if (trendChartRef.value) {
    if (!trendChart) {
      trendChart = echarts.init(trendChartRef.value)
    }
    const trend = projectData.value.cost_trend || []
    trendChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: trend.map(t => t.month ? t.month.substring(0, 7) : '')
      },
      yAxis: { type: 'value' },
      series: [{
        name: '月度成本',
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.3 },
        data: trend.map(t => t.total)
      }]
    })
  }
}

const viewAllRecords = () => {
  router.push(`/projects/cost-records?project=${selectedProject.value}`)
}

watch(() => selectedProject.value, () => {
  if (comparisonChart) { comparisonChart.dispose(); comparisonChart = null }
  if (pieChart) { pieChart.dispose(); pieChart = null }
  if (trendChart) { trendChart.dispose(); trendChart = null }
})

onMounted(() => {
  loadProjects()
  
  // 从URL参数获取项目ID
  const urlParams = new URLSearchParams(window.location.search)
  const projectId = urlParams.get('project')
  if (projectId) {
    selectedProject.value = parseInt(projectId)
    loadProjectCost()
  }
})
</script>

<style scoped>
.filter-card {
  margin-bottom: 16px;
}
.project-info {
  display: flex;
  align-items: center;
}
.info-item {
  margin-right: 24px;
  color: #606266;
}
.stat-row {
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
  padding: 10px 0;
}
.stat-card .stat-label {
  font-size: 14px;
  color: #909399;
}
.stat-card .stat-value {
  font-size: 24px;
  font-weight: bold;
  margin-top: 8px;
  color: #303133;
}
.stat-card.primary .stat-value { color: #409eff; }
.stat-card.success .stat-value { color: #67c23a; }
.stat-card.warning .stat-value { color: #e6a23c; }
.stat-card.danger .stat-value { color: #f56c6c; }
.warning-text { color: #f56c6c; }
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
