<template>
  <div class="capacity-planning">
    <!-- 产能概览 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="总资源数" :value="dashboard.totalResources" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="平均利用率" :value="dashboard.avgUtilization" suffix="%" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card warning">
          <el-statistic title="超负荷资源" :value="dashboard.overloadedResources" value-style="color: #E6A23C" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card danger">
          <el-statistic title="资源冲突" :value="dashboard.conflictsCount" value-style="color: #F56C6C" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 资源负荷图表 -->
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>资源负荷分析</span>
              <el-date-picker v-model="dateRange" type="daterange" range-separator="至"
                              start-placeholder="开始日期" end-placeholder="结束日期"
                              value-format="YYYY-MM-DD" @change="loadDashboard" />
            </div>
          </template>
          <div ref="loadChartRef" style="height: 350px"></div>
        </el-card>
      </el-col>

      <!-- 资源类型分布 -->
      <el-col :span="8">
        <el-card>
          <template #header>资源类型分布</template>
          <div ref="typeChartRef" style="height: 350px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 资源列表 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>资源管理</span>
          <div>
            <el-select v-model="resourceFilter.type" placeholder="资源类型" clearable style="width: 150px; margin-right: 12px"
                       @change="loadResources">
              <el-option v-for="t in resourceTypes" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
            <el-button type="primary" @click="showResourceDialog = true">
              <el-icon><Plus /></el-icon>添加资源
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="resources" v-loading="loading" stripe>
        <el-table-column prop="code" label="资源编码" width="120" />
        <el-table-column prop="name" label="资源名称" min-width="150" />
        <el-table-column prop="resource_type_name" label="类型" width="100" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_available ? 'success' : 'danger'">
              {{ row.is_available ? '可用' : '不可用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="效率" width="100" align="center">
          <template #default="{ row }">
            {{ (row.efficiency * 100).toFixed(0) }}%
          </template>
        </el-table-column>
        <el-table-column label="当前负荷" width="180">
          <template #default="{ row }">
            <el-progress :percentage="row.currentLoad || 0" 
                         :status="row.currentLoad > 100 ? 'exception' : (row.currentLoad > 80 ? 'warning' : '')" />
          </template>
        </el-table-column>
        <el-table-column prop="daily_capacity" label="日产能(小时)" width="120" align="center" />
        <el-table-column prop="hourly_cost" label="时费率(¥)" width="100" align="right">
          <template #default="{ row }">
            {{ formatMoney(row.hourly_cost) }}
          </template>
        </el-table-column>
        <el-table-column label="冲突" width="80" align="center">
          <template #default="{ row }">
            <el-badge :value="row.conflictCount || 0" :hidden="!row.conflictCount" type="danger">
              <el-icon v-if="row.conflictCount"><WarningFilled /></el-icon>
              <el-icon v-else><CircleCheck /></el-icon>
            </el-badge>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="viewResourceLoad(row)">负荷详情</el-button>
            <el-button size="small" link @click="viewConflicts(row)">冲突</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 资源分配列表 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>资源分配</span>
          <el-button type="primary" @click="showAllocationDialog = true">
            <el-icon><Plus /></el-icon>新建分配
          </el-button>
        </div>
      </template>

      <el-table :data="allocations" v-loading="allocationLoading" stripe>
        <el-table-column prop="resource_name" label="资源" width="150" />
        <el-table-column prop="project_name" label="项目" min-width="180" show-overflow-tooltip />
        <el-table-column prop="task_name" label="任务" width="150" show-overflow-tooltip />
        <el-table-column prop="start_date" label="开始日期" width="110" />
        <el-table-column prop="end_date" label="结束日期" width="110" />
        <el-table-column prop="allocated_hours" label="分配工时" width="100" align="center" />
        <el-table-column label="优先级" width="80" align="center">
          <template #default="{ row }">
            <el-rate v-model="row.priority" disabled :max="10" :low-threshold="3" :high-threshold="7" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getAllocationStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加资源对话框 -->
    <el-dialog v-model="showResourceDialog" title="添加资源" width="500px">
      <el-form :model="resourceForm" :rules="resourceRules" ref="resourceFormRef" label-width="100px">
        <el-form-item label="资源编码" prop="code">
          <el-input v-model="resourceForm.code" />
        </el-form-item>
        <el-form-item label="资源名称" prop="name">
          <el-input v-model="resourceForm.name" />
        </el-form-item>
        <el-form-item label="资源类型" prop="resource_type">
          <el-select v-model="resourceForm.resource_type" style="width: 100%">
            <el-option v-for="t in resourceTypes" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="日产能">
          <el-input-number v-model="resourceForm.daily_capacity" :min="1" :max="24" style="width: 100%" />
        </el-form-item>
        <el-form-item label="效率系数">
          <el-slider v-model="resourceForm.efficiency" :min="0.5" :max="1.5" :step="0.05" show-input />
        </el-form-item>
        <el-form-item label="时费率">
          <el-input-number v-model="resourceForm.hourly_cost" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showResourceDialog = false">取消</el-button>
        <el-button type="primary" @click="createResource" :loading="submitting">创建</el-button>
      </template>
    </el-dialog>

    <!-- 新建分配对话框 -->
    <el-dialog v-model="showAllocationDialog" title="新建资源分配" width="500px">
      <el-form :model="allocationForm" :rules="allocationRules" ref="allocationFormRef" label-width="100px">
        <el-form-item label="资源" prop="resource">
          <el-select v-model="allocationForm.resource" filterable style="width: 100%">
            <el-option v-for="r in resources" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目" prop="project">
          <el-select v-model="allocationForm.project" filterable style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="allocationForm.task_name" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="开始日期" prop="start_date">
              <el-date-picker v-model="allocationForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="end_date">
              <el-date-picker v-model="allocationForm.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="分配工时" prop="allocated_hours">
          <el-input-number v-model="allocationForm.allocated_hours" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-slider v-model="allocationForm.priority" :min="1" :max="10" :marks="{ 1: '低', 5: '中', 10: '高' }" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAllocationDialog = false">取消</el-button>
        <el-button @click="checkAvailability" :loading="checking">检查可用性</el-button>
        <el-button type="primary" @click="createAllocation" :loading="submitting">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, WarningFilled, CircleCheck } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import request from '@/utils/request'

const loading = ref(false)
const allocationLoading = ref(false)
const submitting = ref(false)
const checking = ref(false)
const showResourceDialog = ref(false)
const showAllocationDialog = ref(false)

const loadChartRef = ref(null)
const typeChartRef = ref(null)
let loadChart = null
let typeChart = null

const dashboard = ref({
  totalResources: 0,
  avgUtilization: 0,
  overloadedResources: 0,
  conflictsCount: 0
})

const resources = ref([])
const allocations = ref([])
const resourceTypes = ref([])
const projects = ref([])

const dateRange = ref([])

const resourceFilter = reactive({
  type: null
})

const resourceForm = reactive({
  code: '',
  name: '',
  resource_type: null,
  daily_capacity: 8,
  efficiency: 1.0,
  hourly_cost: 100
})

const resourceRules = {
  code: [{ required: true, message: '请输入资源编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入资源名称', trigger: 'blur' }],
  resource_type: [{ required: true, message: '请选择资源类型', trigger: 'change' }]
}

const allocationForm = reactive({
  resource: null,
  project: null,
  task_name: '',
  start_date: '',
  end_date: '',
  allocated_hours: 8,
  priority: 5
})

const allocationRules = {
  resource: [{ required: true, message: '请选择资源', trigger: 'change' }],
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }],
  allocated_hours: [{ required: true, message: '请输入分配工时', trigger: 'blur' }]
}

const resourceFormRef = ref(null)
const allocationFormRef = ref(null)

const formatMoney = (val) => Number(val || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })

const getAllocationStatusType = (status) => {
  const map = { PLANNED: 'info', CONFIRMED: 'warning', IN_PROGRESS: 'primary', COMPLETED: 'success', CANCELLED: 'danger' }
  return map[status] || 'info'
}

const loadDashboard = async () => {
  try {
    const params = {}
    if (dateRange.value?.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await request.get('/production/capacity/dashboard/', { params })
    dashboard.value = res.summary || {}
    
    // 渲染图表
    renderLoadChart(res.resource_loads || [])
    renderTypeChart(res.type_distribution || [])
  } catch (e) {
    console.error('加载产能看板失败', e)
  }
}

const renderLoadChart = (data) => {
  if (!loadChart) {
    loadChart = echarts.init(loadChartRef.value)
  }
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['负荷率', '产能'] },
    xAxis: { type: 'category', data: data.map(d => d.resource_name) },
    yAxis: [
      { type: 'value', name: '负荷率(%)', max: 150 },
      { type: 'value', name: '产能(小时)' }
    ],
    series: [
      {
        name: '负荷率',
        type: 'bar',
        data: data.map(d => d.utilization || 0),
        itemStyle: {
          color: (params) => params.value > 100 ? '#F56C6C' : (params.value > 80 ? '#E6A23C' : '#67C23A')
        }
      },
      {
        name: '产能',
        type: 'line',
        yAxisIndex: 1,
        data: data.map(d => d.capacity || 0)
      }
    ]
  }
  loadChart.setOption(option)
}

const renderTypeChart = (data) => {
  if (!typeChart) {
    typeChart = echarts.init(typeChartRef.value)
  }
  const option = {
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: data.map(d => ({ name: d.type_name, value: d.count })),
      label: { formatter: '{b}: {c}' }
    }]
  }
  typeChart.setOption(option)
}

const loadResources = async () => {
  loading.value = true
  try {
    const params = {}
    if (resourceFilter.type) params.resource_type = resourceFilter.type
    const res = await request.get('/production/resources/', { params })
    resources.value = res.results || res
  } catch (e) {
    ElMessage.error('加载资源列表失败')
  } finally {
    loading.value = false
  }
}

const loadAllocations = async () => {
  allocationLoading.value = true
  try {
    const res = await request.get('/production/resource-allocations/')
    allocations.value = res.results || res
  } catch (e) {
    ElMessage.error('加载分配列表失败')
  } finally {
    allocationLoading.value = false
  }
}

const loadResourceTypes = async () => {
  try {
    const res = await request.get('/production/resource-types/')
    resourceTypes.value = res.results || res
  } catch (e) {
    console.error('加载资源类型失败')
  }
}

const loadProjects = async () => {
  try {
    const res = await request.get('/projects/projects/', { params: { page_size: 1000 } })
    projects.value = res.results || res
  } catch (e) {
    console.error('加载项目列表失败')
  }
}

const createResource = async () => {
  try {
    await resourceFormRef.value.validate()
    submitting.value = true
    await request.post('/production/resources/', resourceForm)
    ElMessage.success('资源创建成功')
    showResourceDialog.value = false
    loadResources()
    loadDashboard()
  } catch (e) {
    if (e !== false) ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

const checkAvailability = async () => {
  try {
    await allocationFormRef.value.validate()
    checking.value = true
    const res = await request.post('/production/resource-allocations/check_availability/', {
      resource: allocationForm.resource,
      start_date: allocationForm.start_date,
      end_date: allocationForm.end_date,
      hours: allocationForm.allocated_hours
    })
    if (res.available) {
      ElMessage.success('资源可用')
    } else {
      ElMessage.warning(`资源不可用: ${res.reason}`)
    }
  } catch (e) {
    if (e !== false) ElMessage.error('检查失败')
  } finally {
    checking.value = false
  }
}

const createAllocation = async () => {
  try {
    await allocationFormRef.value.validate()
    submitting.value = true
    await request.post('/production/resource-allocations/', allocationForm)
    ElMessage.success('分配创建成功')
    showAllocationDialog.value = false
    loadAllocations()
    loadDashboard()
  } catch (e) {
    if (e !== false) ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

const viewResourceLoad = async (row) => {
  try {
    const res = await request.get(`/production/resources/${row.id}/load/`)
    ElMessage.info(`负荷率: ${res.utilization_rate}%, 已分配: ${res.allocated_hours}小时`)
  } catch (e) {
    ElMessage.error('获取负荷详情失败')
  }
}

const viewConflicts = async (row) => {
  try {
    const res = await request.get(`/production/resources/${row.id}/conflicts/`)
    ElMessage.info(`共 ${res.length} 个冲突`)
  } catch (e) {
    ElMessage.error('获取冲突信息失败')
  }
}

onMounted(() => {
  // 设置默认日期范围
  const today = new Date()
  const nextMonth = new Date(today)
  nextMonth.setMonth(nextMonth.getMonth() + 1)
  dateRange.value = [
    today.toISOString().split('T')[0],
    nextMonth.toISOString().split('T')[0]
  ]

  loadDashboard()
  loadResources()
  loadAllocations()
  loadResourceTypes()
  loadProjects()
})
</script>

<style scoped>
.capacity-planning {
  padding: 20px;
}
.stat-row {
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
}
.stat-card.warning {
  border-left: 3px solid #E6A23C;
}
.stat-card.danger {
  border-left: 3px solid #F56C6C;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
