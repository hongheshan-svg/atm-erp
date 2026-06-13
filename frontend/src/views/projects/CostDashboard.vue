<template>
  <div class="cost-dashboard">
    <!-- 项目选择器 -->
    <el-card class="filter-card">
      <el-row :gutter="20" align="middle">
        <el-col :span="8">
          <el-select v-model="selectedProject" filterable placeholder="选择项目" style="width: 100%" @change="loadProjectCost">
            <el-option v-for="p in projects" :key="p.id" :label="`${p.code} - ${p.name}`" :value="p.id" />
          </el-select>
        </el-col>
        <el-col :span="16" class="project-info" v-if="projectData">
          <span class="info-item"><strong>客户：</strong>{{ projectData.project?.customer_name }}</span>
          <span class="info-item"><strong>订单：</strong>{{ projectData.project?.sales_order_no || '未关联' }}</span>
          <el-tag :type="profitWarningType" size="large" style="margin-left: 16px">
            净利率: {{ projectData.net_margin || 0 }}%
          </el-tag>
        </el-col>
      </el-row>
    </el-card>

    <div v-if="projectData" v-loading="loading">
      <!-- 收入与利润概览 -->
      <el-row :gutter="16" class="stat-row">
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card revenue">
            <div class="stat-label">合同收入</div>
            <div class="stat-value">¥{{ formatMoney(projectData.revenue) }}</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card primary">
            <div class="stat-label">总成本</div>
            <div class="stat-value">¥{{ formatMoney(projectData.actual_total) }}</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" :class="['stat-card', grossProfitClass]">
            <div class="stat-label">毛利润</div>
            <div class="stat-value">¥{{ formatMoney(projectData.gross_profit) }}</div>
            <div class="stat-sub">毛利率: {{ projectData.gross_margin || 0 }}%</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" :class="['stat-card', netProfitClass]">
            <div class="stat-label">净利润</div>
            <div class="stat-value">¥{{ formatMoney(projectData.net_profit) }}</div>
            <div class="stat-sub">净利率: {{ projectData.net_margin || 0 }}%</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" :class="['stat-card', remainingClass]">
            <div class="stat-label">剩余预算</div>
            <div class="stat-value">¥{{ formatMoney(projectData.budget_total - projectData.actual_total) }}</div>
            <div class="stat-sub">使用率: {{ projectData.budget_used_rate || 0 }}%</div>
          </el-card>
        </el-col>
        <el-col :span="4">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">待处理预警</div>
            <div class="stat-value warning-text">{{ projectData.pending_alerts || 0 }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 成本构成分析 -->
      <el-row :gutter="16">
        <el-col :span="8">
          <el-card>
            <template #header>
              <span>成本构成明细</span>
            </template>
            <div class="cost-breakdown">
              <div class="cost-section">
                <div class="section-title">
                  <span>直接成本</span>
                  <span class="section-amount">¥{{ formatMoney(projectData.direct_cost) }}</span>
                </div>
                <div class="cost-item" v-for="(item, key) in directCosts" :key="key">
                  <div class="item-info">
                    <span class="item-name">{{ item.name }}</span>
                    <span class="item-amount">¥{{ formatMoney(item.amount) }}</span>
                  </div>
                  <el-progress 
                    :percentage="item.percentage" 
                    :stroke-width="8"
                    :color="getProgressColor(item.usage_rate)"
                  />
                  <div class="item-detail">
                    <span>预算: ¥{{ formatMoney(item.budget) }}</span>
                    <span :class="item.variance >= 0 ? 'text-success' : 'text-danger'">
                      {{ item.variance >= 0 ? '节余' : '超支' }}: ¥{{ formatMoney(Math.abs(item.variance)) }}
                    </span>
                  </div>
                </div>
              </div>
              <el-divider />
              <div class="cost-section">
                <div class="section-title">
                  <span>间接成本</span>
                  <span class="section-amount">¥{{ formatMoney(projectData.indirect_cost) }}</span>
                </div>
                <div class="cost-item" v-for="(item, key) in indirectCosts" :key="key">
                  <div class="item-info">
                    <span class="item-name">{{ item.name }}</span>
                    <span class="item-amount">¥{{ formatMoney(item.amount) }}</span>
                  </div>
                  <el-progress 
                    :percentage="item.percentage" 
                    :stroke-width="8"
                    :color="getProgressColor(item.usage_rate)"
                  />
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card>
            <template #header>
              <span>成本构成饼图</span>
            </template>
            <div ref="pieChartRef" style="height: 350px"></div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card>
            <template #header>
              <span>利润瀑布图</span>
            </template>
            <div ref="waterfallChartRef" style="height: 350px"></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 预算vs实际 + 成本趋势 -->
      <el-row :gutter="16" style="margin-top: 16px">
        <el-col :span="14">
          <el-card>
            <template #header>
              <span>预算 vs 实际成本对比</span>
            </template>
            <div ref="comparisonChartRef" style="height: 300px"></div>
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card>
            <template #header>
              <span>成本趋势</span>
            </template>
            <div ref="trendChartRef" style="height: 300px"></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 各阶段成本 + 最近记录 -->
      <el-row :gutter="16" style="margin-top: 16px">
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
                  {{ projectData.actual_total ? ((row.total / projectData.actual_total) * 100).toFixed(1) : '0.0' }}%
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="14">
          <el-card>
            <template #header>
              <div class="card-header">
                <span>最近成本记录</span>
                <el-button type="primary" link @click="viewAllRecords">查看全部</el-button>
              </div>
            </template>
            <el-table :data="recentCosts" size="small" max-height="280">
              <el-table-column prop="cost_date" label="日期" width="100" />
              <el-table-column prop="cost_type_display" label="类型" width="80" />
              <el-table-column prop="description" label="说明" min-width="150" show-overflow-tooltip />
              <el-table-column prop="source_doc_no" label="单据号" width="120" show-overflow-tooltip />
              <el-table-column label="金额" width="100" align="right">
                <template #default="{ row }">¥{{ formatMoney(row.amount) }}</template>
              </el-table-column>
              <el-table-column prop="is_verified" label="核实" width="60" align="center">
                <template #default="{ row }">
                  <el-icon :color="row.is_verified ? '#67c23a' : '#909399'">
                    <Check v-if="row.is_verified" /><Close v-else />
                  </el-icon>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 未选择项目提示 -->
    <el-empty v-else description="请选择项目查看成本看板" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Check, Close } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getProjectList, getProjectCostDashboard } from '@/api/projects/project'

const router = useRouter()

const loading = ref(false)
const projects = ref<any[]>([])
const selectedProject = ref(null)
const projectData = ref(null)

const comparisonChartRef = ref(null)
const pieChartRef = ref(null)
const trendChartRef = ref(null)
const waterfallChartRef = ref(null)
let comparisonChart = null
let pieChart = null
let trendChart = null
let waterfallChart = null

const phaseCosts = computed(() => projectData.value?.phase_costs || [])
const recentCosts = computed(() => projectData.value?.recent_costs || [])

// 直接成本
const directCosts = computed(() => {
  if (!projectData.value?.cost_breakdown) return []
  const breakdown = projectData.value.cost_breakdown
  return ['material', 'labor', 'outsource']
    .map(key => breakdown[key])
    .filter(item => item)
})

// 间接成本
const indirectCosts = computed(() => {
  if (!projectData.value?.cost_breakdown) return []
  const breakdown = projectData.value.cost_breakdown
  return ['equipment', 'travel', 'management', 'other']
    .map(key => breakdown[key])
    .filter(item => item)
})

// 利润预警类型
const profitWarningType = computed(() => {
  if (!projectData.value) return 'info'
  if (projectData.value.profit_warning === 'critical') return 'danger'
  if (projectData.value.profit_warning === 'warning') return 'warning'
  return 'success'
})

// 毛利润样式
const grossProfitClass = computed(() => {
  if (!projectData.value) return ''
  if (projectData.value.gross_profit < 0) return 'danger'
  if (projectData.value.gross_margin < 20) return 'warning'
  return 'success'
})

// 净利润样式
const netProfitClass = computed(() => {
  if (!projectData.value) return ''
  if (projectData.value.net_profit < 0) return 'danger'
  if (projectData.value.net_margin < 10) return 'warning'
  return 'success'
})

const remainingClass = computed(() => {
  const remaining = (projectData.value?.budget_total || 0) - (projectData.value?.actual_total || 0)
  if (remaining < 0) return 'danger'
  if (projectData.value?.budget_used_rate > 80) return 'warning'
  return 'success'
})

// 预算使用率进度条颜色
const getProgressColor = (usageRate) => {
  if (usageRate > 100) return '#f56c6c'
  if (usageRate > 80) return '#e6a23c'
  return '#409eff'
}

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
  // 列出项目供成本看板选择。后端 filterset 仅支持精确 status=，不支持 status__in，
  // 且模型并无 DEBUGGING/INSTALLATION 状态（旧值会被静默忽略），故不再传无效过滤值。
  const res = await getProjectList({ page_size: 500 })
  projects.value = res.results || res || []
}

const loadProjectCost = async () => {
  if (!selectedProject.value) {
    projectData.value = null
    return
  }
  
  loading.value = true
  try {
    const res = await getProjectCostDashboard(selectedProject.value)
    projectData.value = res
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

  // 利润瀑布图
  if (waterfallChartRef.value) {
    if (!waterfallChart) {
      waterfallChart = echarts.init(waterfallChartRef.value)
    }
    const data = projectData.value
    const revenue = data.revenue || 0
    const directCost = data.direct_cost || 0
    const indirectCost = data.indirect_cost || 0
    const grossProfit = data.gross_profit || 0
    const netProfit = data.net_profit || 0

    waterfallChart.setOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params) => {
          const item = params[0]
          return `${item.name}<br/>¥${parseFloat(item.value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`
        }
      },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: ['合同收入', '直接成本', '毛利润', '间接成本', '净利润']
      },
      yAxis: { type: 'value' },
      series: [
        {
          name: '辅助',
          type: 'bar',
          stack: 'Total',
          itemStyle: { borderColor: 'transparent', color: 'transparent' },
          emphasis: { itemStyle: { borderColor: 'transparent', color: 'transparent' } },
          data: [0, grossProfit, 0, netProfit, 0]
        },
        {
          name: '金额',
          type: 'bar',
          stack: 'Total',
          label: {
            show: true,
            position: 'top',
            formatter: (params) => `¥${(params.value / 10000).toFixed(1)}万`
          },
          data: [
            { value: revenue, itemStyle: { color: '#409eff' } },
            { value: -directCost, itemStyle: { color: '#f56c6c' } },
            { value: grossProfit, itemStyle: { color: grossProfit >= 0 ? '#67c23a' : '#f56c6c' } },
            { value: -indirectCost, itemStyle: { color: '#e6a23c' } },
            { value: netProfit, itemStyle: { color: netProfit >= 0 ? '#67c23a' : '#f56c6c' } }
          ]
        }
      ]
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
  if (waterfallChart) { waterfallChart.dispose(); waterfallChart = null }
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
  font-size: 22px;
  font-weight: bold;
  margin-top: 6px;
  color: #303133;
}
.stat-card .stat-sub {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.stat-card.primary .stat-value { color: #409eff; }
.stat-card.revenue .stat-value { color: #409eff; }
.stat-card.success .stat-value { color: #67c23a; }
.stat-card.warning .stat-value { color: #e6a23c; }
.stat-card.danger .stat-value { color: #f56c6c; }
.warning-text { color: #f56c6c; }
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 成本构成明细样式 */
.cost-breakdown {
  max-height: 350px;
  overflow-y: auto;
}
.cost-section {
  margin-bottom: 12px;
}
.section-title {
  display: flex;
  justify-content: space-between;
  font-weight: bold;
  font-size: 14px;
  color: #303133;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
}
.section-amount {
  color: #409eff;
}
.cost-item {
  margin-bottom: 12px;
  padding: 8px;
  background: #fafafa;
  border-radius: 4px;
}
.item-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}
.item-name {
  font-size: 13px;
  color: #606266;
}
.item-amount {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}
.item-detail {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
}
.text-success {
  color: #67c23a;
}
.text-danger {
  color: #f56c6c;
}
</style>
