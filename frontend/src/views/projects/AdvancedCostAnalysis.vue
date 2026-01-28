<template>
  <div class="advanced-cost-analysis">
    <!-- 项目选择 -->
    <el-card class="filter-card">
      <el-row :gutter="20" align="middle">
        <el-col :span="8">
          <el-select v-model="selectedProject" filterable placeholder="选择项目" style="width: 100%" @change="loadProjectCost">
            <el-option v-for="p in projects" :key="p.id" :label="`${p.project_no} - ${p.name}`" :value="p.id" />
          </el-select>
        </el-col>
        <el-col :span="16" class="project-info" v-if="summary">
          <el-tag size="large" :type="marginType" effect="plain" style="margin-right: 16px">
            毛利率: {{ (summary.actual_margin * 100).toFixed(1) }}%
          </el-tag>
          <el-tag size="large" :type="cpiType" effect="plain" style="margin-right: 16px">
            CPI: {{ summary.cpi }}
          </el-tag>
          <el-tag size="large" effect="plain">
            完工度: {{ summary.completion_percentage }}%
          </el-tag>
        </el-col>
      </el-row>
    </el-card>

    <div v-if="summary" v-loading="loading">
      <!-- 成本汇总卡片 -->
      <el-row :gutter="16" class="stat-row">
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">合同金额</div>
            <div class="stat-value">¥{{ formatMoney(summary.contract_amount) }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card warning">
            <div class="stat-label">实际成本</div>
            <div class="stat-value">¥{{ formatMoney(summary.total_cost) }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" :class="['stat-card', summary.actual_profit >= 0 ? 'success' : 'danger']">
            <div class="stat-label">实际毛利</div>
            <div class="stat-value">¥{{ formatMoney(summary.actual_profit) }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-label">完工估算(EAC)</div>
            <div class="stat-value">¥{{ formatMoney(summary.eac) }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <!-- 成本要素构成 -->
        <el-col :span="12">
          <el-card>
            <template #header>
              <span>成本要素构成</span>
            </template>
            <div ref="elementChartRef" style="height: 350px"></div>
          </el-card>
        </el-col>

        <!-- 成本趋势 -->
        <el-col :span="12">
          <el-card>
            <template #header>
              <span>成本趋势</span>
            </template>
            <div ref="trendChartRef" style="height: 350px"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" style="margin-top: 16px">
        <!-- 按阶段分析 -->
        <el-col :span="12">
          <el-card>
            <template #header>
              <span>各阶段成本</span>
            </template>
            <el-table :data="phaseData" size="small" max-height="300">
              <el-table-column prop="project_phase" label="阶段" width="120">
                <template #default="{ row }">{{ getPhaseLabel(row.project_phase) }}</template>
              </el-table-column>
              <el-table-column label="实际金额" align="right">
                <template #default="{ row }">¥{{ formatMoney(row.total) }}</template>
              </el-table-column>
              <el-table-column label="占比" width="100" align="center">
                <template #default="{ row }">
                  <el-progress :percentage="getPercentage(row.total)" :stroke-width="10" :show-text="false" />
                  <span>{{ getPercentage(row.total) }}%</span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>

        <!-- 成本差异TOP10 -->
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header">
                <span>成本差异TOP10</span>
                <el-button type="primary" link @click="viewAllVariances">查看全部</el-button>
              </div>
            </template>
            <el-table :data="topVariances" size="small" max-height="300">
              <el-table-column prop="description" label="说明" min-width="150" show-overflow-tooltip />
              <el-table-column label="差异" width="100" align="right">
                <template #default="{ row }">
                  <span :class="{ 'text-danger': row.variance_amount > 0 }">
                    {{ row.variance_amount > 0 ? '+' : '' }}¥{{ formatMoney(row.variance_amount) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="类型" width="80">
                <template #default="{ row }">{{ row.variance_type || '-' }}</template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>

      <!-- 详细成本明细 -->
      <el-card style="margin-top: 16px">
        <template #header>
          <div class="card-header">
            <span>成本明细</span>
            <div>
              <el-select v-model="elementFilter" placeholder="成本要素" clearable style="width: 120px; margin-right: 10px" @change="loadDetails">
                <el-option label="直接材料" value="DIRECT_MATERIAL" />
                <el-option label="直接人工" value="DIRECT_LABOR" />
                <el-option label="制造费用" value="MANUFACTURING_OH" />
                <el-option label="外协费用" value="OUTSOURCE" />
                <el-option label="差旅费用" value="TRAVEL" />
              </el-select>
              <el-button type="primary" @click="showAddDialog">添加成本</el-button>
            </div>
          </div>
        </template>
        <el-table :data="costDetails" v-loading="detailLoading" stripe size="small">
          <el-table-column prop="cost_date" label="日期" width="100" />
          <el-table-column prop="cost_element_display" label="成本要素" width="90" />
          <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
          <el-table-column prop="source_type_display" label="来源" width="90" />
          <el-table-column prop="source_doc_no" label="单据号" width="120" />
          <el-table-column label="数量" width="80" align="right">
            <template #default="{ row }">{{ row.quantity }}{{ row.unit }}</template>
          </el-table-column>
          <el-table-column label="实际金额" width="110" align="right">
            <template #default="{ row }">¥{{ formatMoney(row.actual_amount) }}</template>
          </el-table-column>
          <el-table-column label="差异" width="100" align="right">
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.variance_amount > 0, 'text-success': row.variance_amount < 0 }">
                {{ row.variance_amount != 0 ? (row.variance_amount > 0 ? '+' : '') + '¥' + formatMoney(row.variance_amount) : '-' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="is_verified" label="审核" width="70" align="center">
            <template #default="{ row }">
              <el-icon :color="row.is_verified ? '#67c23a' : '#909399'">
                <Check v-if="row.is_verified" /><Close v-else />
              </el-icon>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="detailPage"
          v-model:page-size="detailPageSize"
          :total="detailTotal"
          layout="total, prev, pager, next"
          @current-change="loadDetails"
          style="margin-top: 16px; justify-content: flex-end"
        />
      </el-card>
    </div>

    <el-empty v-else description="请选择项目查看成本分析" />
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
const detailLoading = ref(false)
const projects = ref([])
const selectedProject = ref(null)
const summary = ref(null)
const analysisData = ref(null)
const trendData = ref([])
const topVariances = ref([])
const costDetails = ref([])
const detailPage = ref(1)
const detailPageSize = ref(10)
const detailTotal = ref(0)
const elementFilter = ref('')

const elementChartRef = ref(null)
const trendChartRef = ref(null)
let elementChart = null
let trendChart = null

const phaseData = computed(() => analysisData.value?.by_phase || [])

const marginType = computed(() => {
  if (!summary.value) return 'info'
  const margin = summary.value.actual_margin * 100
  if (margin >= 20) return 'success'
  if (margin >= 10) return 'warning'
  return 'danger'
})

const cpiType = computed(() => {
  if (!summary.value) return 'info'
  if (summary.value.cpi >= 1) return 'success'
  if (summary.value.cpi >= 0.9) return 'warning'
  return 'danger'
})

const formatMoney = (val) => {
  if (!val) return '0.00'
  return parseFloat(val).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

const getPhaseLabel = (phase) => {
  const map = {
    REQUIREMENT: '需求分析',
    DESIGN: '设计阶段',
    PROCUREMENT: '采购阶段',
    PRODUCTION: '生产制造',
    ASSEMBLY: '装配阶段',
    TESTING: '测试调试',
    SHIPPING: '发货运输',
    INSTALLATION: '现场安装',
    COMMISSIONING: '现场调试',
    ACCEPTANCE: '验收阶段',
    WARRANTY: '质保期',
    AFTER_SALE: '售后服务'
  }
  return map[phase] || phase
}

const getPercentage = (value) => {
  if (!summary.value || !summary.value.total_cost) return 0
  return Math.round(parseFloat(value) / parseFloat(summary.value.total_cost) * 100)
}

const loadProjects = async () => {
  const res = await request.get('/projects/projects/', {
    params: { page_size: 500 }
  })
  projects.value = res.data.results || res.data
}

const loadProjectCost = async () => {
  if (!selectedProject.value) {
    summary.value = null
    return
  }
  
  loading.value = true
  try {
    const res = await request.get(`/api/projects/cost/analysis/${selectedProject.value}/`)
    summary.value = res.data.summary
    analysisData.value = res.data.analysis
    trendData.value = res.data.trend || []
    topVariances.value = res.data.top_variances || []
    
    await nextTick()
    renderCharts()
    loadDetails()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const loadDetails = async () => {
  if (!selectedProject.value) return
  
  detailLoading.value = true
  try {
    const params = {
      project: selectedProject.value,
      page: detailPage.value,
      page_size: detailPageSize.value,
      cost_element: elementFilter.value || undefined
    }
    const res = await request.get('/projects/cost-details/', { params })
    costDetails.value = res.data.results || res.data
    detailTotal.value = res.data.count || costDetails.value.length
  } catch (e) {
    console.error(e)
  } finally {
    detailLoading.value = false
  }
}

const renderCharts = () => {
  if (!summary.value) return
  
  // 成本要素饼图
  if (elementChartRef.value) {
    if (!elementChart) {
      elementChart = echarts.init(elementChartRef.value)
    }
    const elementData = [
      { name: '直接材料', value: parseFloat(summary.value.direct_material_cost) },
      { name: '直接人工', value: parseFloat(summary.value.direct_labor_cost) },
      { name: '制造费用', value: parseFloat(summary.value.manufacturing_overhead) },
      { name: '外协成本', value: parseFloat(summary.value.outsource_cost) },
      { name: '差旅费用', value: parseFloat(summary.value.travel_cost) },
      { name: '设备费用', value: parseFloat(summary.value.equipment_cost) },
      { name: '其他', value: parseFloat(summary.value.other_direct_cost) + parseFloat(summary.value.indirect_cost) },
    ].filter(d => d.value > 0)
    
    elementChart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
      legend: { orient: 'vertical', right: 10, top: 'center' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['40%', '50%'],
        data: elementData,
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14 } }
      }]
    })
  }
  
  // 成本趋势图
  if (trendChartRef.value) {
    if (!trendChart) {
      trendChart = echarts.init(trendChartRef.value)
    }
    trendChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['总成本', '材料', '人工'] },
      xAxis: {
        type: 'category',
        data: trendData.value.map(t => t.month ? t.month.substring(0, 7) : '')
      },
      yAxis: { type: 'value' },
      series: [
        {
          name: '总成本',
          type: 'line',
          smooth: true,
          areaStyle: { opacity: 0.2 },
          data: trendData.value.map(t => t.total)
        },
        {
          name: '材料',
          type: 'line',
          smooth: true,
          data: trendData.value.map(t => t.material || 0)
        },
        {
          name: '人工',
          type: 'line',
          smooth: true,
          data: trendData.value.map(t => t.labor || 0)
        }
      ]
    })
  }
}

const viewAllVariances = () => {
  router.push(`/projects/cost-details?project=${selectedProject.value}&variance=true`)
}

const showAddDialog = () => {
  // TODO: 打开添加成本对话框
}

watch(() => selectedProject.value, () => {
  if (elementChart) { elementChart.dispose(); elementChart = null }
  if (trendChart) { trendChart.dispose(); trendChart = null }
})

onMounted(() => {
  loadProjects()
  
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
  margin-top: 8px;
  color: #303133;
}
.stat-card.warning .stat-value { color: #e6a23c; }
.stat-card.success .stat-value { color: #67c23a; }
.stat-card.danger .stat-value { color: #f56c6c; }
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.text-danger { color: #f56c6c; }
.text-success { color: #67c23a; }
</style>
