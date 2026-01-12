<template>
  <div class="spc-container">
    <div class="page-header">
      <h2>SPC统计过程控制</h2>
      <div class="header-actions">
        <el-button type="primary" @click="handleAddChart">
          <el-icon><Plus /></el-icon>新建控制图
        </el-button>
      </div>
    </div>
    
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.total_charts || 0 }}</div>
          <div class="stat-label">控制图总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card warning">
          <div class="stat-value">{{ stats.unhandled_alarms || 0 }}</div>
          <div class="stat-label">未处理报警</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card success">
          <div class="stat-value">{{ stats.avg_cpk ? stats.avg_cpk.toFixed(2) : '-' }}</div>
          <div class="stat-label">平均Cpk</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card info">
          <div class="stat-value">{{ stats.data_points_today || 0 }}</div>
          <div class="stat-label">今日采集点数</div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="16">
      <!-- 控制图列表 -->
      <el-col :span="16">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>控制图列表</span>
              <el-input v-model="searchQuery" placeholder="搜索控制图..." style="width: 250px" 
                @input="handleSearch" clearable>
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
            </div>
          </template>
          
          <el-table :data="chartList" v-loading="loading" border stripe @row-click="handleSelectChart">
            <el-table-column prop="name" label="控制图名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="chart_type_display" label="类型" width="120" />
            <el-table-column prop="measurement_name" label="测量项目" width="120" />
            <el-table-column prop="process_name" label="工序" width="120" show-overflow-tooltip />
            <el-table-column label="规格限" width="150">
              <template #default="{ row }">
                <span v-if="row.lsl && row.usl">
                  {{ row.lsl }} ~ {{ row.usl }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click.stop="handleViewChart(row)">
                  查看图表
                </el-button>
                <el-button type="success" link size="small" @click.stop="handleAddData(row)">
                  采集数据
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.size"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next"
            @change="fetchChartList"
            style="margin-top: 16px; justify-content: flex-end"
          />
        </el-card>
      </el-col>
      
      <!-- 未处理报警 -->
      <el-col :span="8">
        <el-card shadow="never" header="未处理报警">
          <div v-if="unhandledAlarms.length === 0" class="empty-tip">
            <el-icon><CircleCheck /></el-icon>
            <span>暂无未处理报警</span>
          </div>
          <div v-else class="alarm-list">
            <div v-for="alarm in unhandledAlarms" :key="alarm.id" class="alarm-item" 
              :class="alarm.alarm_type">
              <div class="alarm-header">
                <el-tag type="danger" size="small">{{ alarm.alarm_type_display }}</el-tag>
                <span class="alarm-time">{{ formatTime(alarm.alarm_time) }}</span>
              </div>
              <div class="alarm-info">
                <div class="alarm-chart">{{ alarm.chart_name }}</div>
                <div class="alarm-value">子组 #{{ alarm.subgroup_no }}: {{ alarm.value }}</div>
              </div>
              <el-button type="primary" size="small" @click="handleAlarm(alarm)">处理</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 控制图详情对话框 -->
    <el-dialog v-model="chartDialogVisible" :title="currentChart?.name" width="1200px" top="5vh">
      <div v-if="currentChart" class="chart-detail">
        <!-- 控制图图表 -->
        <el-row :gutter="16">
          <el-col :span="18">
            <div class="control-chart-container">
              <div class="chart-title">X̄-R 控制图</div>
              <div ref="xbarChartRef" class="chart-area" style="height: 280px"></div>
              <div ref="rChartRef" class="chart-area" style="height: 200px"></div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="chart-info-panel">
              <h4>控制限</h4>
              <div class="info-item">
                <span class="label">UCL (X̄):</span>
                <span class="value">{{ chartData.control_limits?.xbar?.ucl?.toFixed(4) || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="label">CL (X̄):</span>
                <span class="value">{{ chartData.control_limits?.xbar?.cl?.toFixed(4) || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="label">LCL (X̄):</span>
                <span class="value">{{ chartData.control_limits?.xbar?.lcl?.toFixed(4) || '-' }}</span>
              </div>
              <el-divider />
              <div class="info-item">
                <span class="label">UCL (R):</span>
                <span class="value">{{ chartData.control_limits?.r?.ucl?.toFixed(4) || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="label">CL (R):</span>
                <span class="value">{{ chartData.control_limits?.r?.cl?.toFixed(4) || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="label">LCL (R):</span>
                <span class="value">{{ chartData.control_limits?.r?.lcl?.toFixed(4) || '-' }}</span>
              </div>
              <el-divider />
              <h4>规格限</h4>
              <div class="info-item">
                <span class="label">USL:</span>
                <span class="value">{{ currentChart.usl || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="label">Target:</span>
                <span class="value">{{ currentChart.target || '-' }}</span>
              </div>
              <div class="info-item">
                <span class="label">LSL:</span>
                <span class="value">{{ currentChart.lsl || '-' }}</span>
              </div>
              
              <el-button type="primary" style="margin-top: 16px; width: 100%" 
                @click="handleCalculateCapability">计算过程能力</el-button>
            </div>
          </el-col>
        </el-row>
        
        <!-- 数据表格 -->
        <el-table :data="chartData.subgroups" size="small" border stripe style="margin-top: 16px" max-height="300">
          <el-table-column prop="subgroup_no" label="子组号" width="80" align="center" />
          <el-table-column prop="sample_time" label="采样时间" width="160">
            <template #default="{ row }">
              {{ formatDateTime(row.sample_time) }}
            </template>
          </el-table-column>
          <el-table-column prop="x_bar" label="X̄" width="100" align="right">
            <template #default="{ row }">
              {{ Number(row.x_bar).toFixed(4) }}
            </template>
          </el-table-column>
          <el-table-column prop="r_value" label="R" width="100" align="right">
            <template #default="{ row }">
              {{ row.r_value ? Number(row.r_value).toFixed(4) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="sample_size" label="样本量" width="80" align="center" />
          <el-table-column prop="is_out_of_control" label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_out_of_control ? 'danger' : 'success'" size="small">
                {{ row.is_out_of_control ? '失控' : '受控' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
    
    <!-- 数据采集对话框 -->
    <el-dialog v-model="dataDialogVisible" title="数据采集" width="600px">
      <el-form :model="dataForm" label-width="100px" ref="dataFormRef">
        <el-form-item label="控制图">
          <el-input :value="dataForm.chartName" disabled />
        </el-form-item>
        <el-form-item label="子组编号" prop="subgroup_no" :rules="[{required: true, message: '请输入子组编号'}]">
          <el-input-number v-model="dataForm.subgroup_no" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="测量值" prop="values" :rules="[{required: true, message: '请输入测量值'}]">
          <div class="measurement-inputs">
            <el-input-number v-for="i in 5" :key="i" v-model="dataForm.values[i-1]" 
              :precision="4" placeholder="样本" style="width: 100px" />
          </div>
        </el-form-item>
        <el-form-item label="批次号">
          <el-input v-model="dataForm.batch_no" placeholder="可选" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="dataForm.remarks" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dataDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitData" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 新建控制图对话框 -->
    <el-dialog v-model="addDialogVisible" title="新建控制图" width="700px">
      <el-form :model="chartForm" :rules="chartRules" ref="chartFormRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="控制图名称" prop="name">
              <el-input v-model="chartForm.name" placeholder="请输入名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="控制图类型" prop="chart_type">
              <el-select v-model="chartForm.chart_type" style="width: 100%">
                <el-option label="X̄-R控制图" value="XBAR_R" />
                <el-option label="X̄-S控制图" value="XBAR_S" />
                <el-option label="P控制图" value="P" />
                <el-option label="NP控制图" value="NP" />
                <el-option label="C控制图" value="C" />
                <el-option label="U控制图" value="U" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="测量项目" prop="measurement_name">
              <el-input v-model="chartForm.measurement_name" placeholder="如:直径、长度等" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位">
              <el-input v-model="chartForm.unit" placeholder="mm, kg等" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="规格下限(LSL)">
              <el-input-number v-model="chartForm.lsl" :precision="4" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="目标值">
              <el-input-number v-model="chartForm.target" :precision="4" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="规格上限(USL)">
              <el-input-number v-model="chartForm.usl" :precision="4" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="子组大小">
          <el-input-number v-model="chartForm.subgroup_size" :min="2" :max="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitChart" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 报警处理对话框 -->
    <el-dialog v-model="alarmDialogVisible" title="处理报警" width="500px">
      <el-form :model="alarmForm" label-width="100px">
        <el-form-item label="报警类型">
          <el-tag type="danger">{{ currentAlarm?.alarm_type_display }}</el-tag>
        </el-form-item>
        <el-form-item label="异常值">
          {{ currentAlarm?.value }}
        </el-form-item>
        <el-form-item label="处理措施" prop="action_taken">
          <el-input v-model="alarmForm.action_taken" type="textarea" :rows="4" 
            placeholder="请描述采取的处理措施..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="alarmDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAlarmHandle" :loading="submitLoading">确认处理</el-button>
      </template>
    </el-dialog>
    
    <!-- 过程能力对话框 -->
    <el-dialog v-model="capabilityDialogVisible" title="过程能力分析" width="600px">
      <div v-if="capabilityData" class="capability-result">
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="capability-item">
              <div class="capability-label">样本数</div>
              <div class="capability-value">{{ capabilityData.sample_count }}</div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="capability-item">
              <div class="capability-label">均值 (μ)</div>
              <div class="capability-value">{{ Number(capabilityData.mean).toFixed(4) }}</div>
            </div>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="capability-item">
              <div class="capability-label">标准差 (σ)</div>
              <div class="capability-value">{{ Number(capabilityData.std_dev).toFixed(4) }}</div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="capability-item highlight">
              <div class="capability-label">Cp</div>
              <div class="capability-value" :class="getCpkClass(capabilityData.cp)">
                {{ capabilityData.cp ? Number(capabilityData.cp).toFixed(2) : '-' }}
              </div>
            </div>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="capability-item highlight">
              <div class="capability-label">Cpk</div>
              <div class="capability-value" :class="getCpkClass(capabilityData.cpk)">
                {{ capabilityData.cpk ? Number(capabilityData.cpk).toFixed(2) : '-' }}
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="capability-item">
              <div class="capability-label">分析期间</div>
              <div class="capability-value small">
                {{ capabilityData.start_date }} ~ {{ capabilityData.end_date }}
              </div>
            </div>
          </el-col>
        </el-row>
        
        <div class="capability-interpretation">
          <h4>能力评价</h4>
          <div v-if="capabilityData.cpk >= 1.33" class="interpretation good">
            <el-icon><CircleCheck /></el-icon>
            过程能力充足 (Cpk ≥ 1.33)，过程稳定且满足规格要求
          </div>
          <div v-else-if="capabilityData.cpk >= 1.0" class="interpretation warning">
            <el-icon><Warning /></el-icon>
            过程能力勉强 (1.0 ≤ Cpk < 1.33)，需要加强过程控制
          </div>
          <div v-else class="interpretation danger">
            <el-icon><CircleClose /></el-icon>
            过程能力不足 (Cpk < 1.0)，需要改进工艺或设备
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, CircleCheck, Warning, CircleClose } from '@element-plus/icons-vue'
import request from '@/utils/request'
import * as echarts from 'echarts'

const loading = ref(false)
const submitLoading = ref(false)
const searchQuery = ref('')

const chartList = ref([])
const unhandledAlarms = ref([])
const stats = ref({})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

// 控制图详情
const chartDialogVisible = ref(false)
const currentChart = ref(null)
const chartData = ref({ subgroups: [], control_limits: {} })
const xbarChartRef = ref(null)
const rChartRef = ref(null)
let xbarChart = null
let rChart = null

// 数据采集
const dataDialogVisible = ref(false)
const dataFormRef = ref(null)
const dataForm = reactive({
  chartId: null,
  chartName: '',
  subgroup_no: 1,
  values: [null, null, null, null, null],
  batch_no: '',
  remarks: ''
})

// 新建控制图
const addDialogVisible = ref(false)
const chartFormRef = ref(null)
const chartForm = reactive({
  name: '',
  chart_type: 'XBAR_R',
  measurement_name: '',
  unit: '',
  usl: null,
  lsl: null,
  target: null,
  subgroup_size: 5
})
const chartRules = {
  name: [{ required: true, message: '请输入控制图名称', trigger: 'blur' }],
  measurement_name: [{ required: true, message: '请输入测量项目', trigger: 'blur' }]
}

// 报警处理
const alarmDialogVisible = ref(false)
const currentAlarm = ref(null)
const alarmForm = reactive({
  action_taken: ''
})

// 过程能力
const capabilityDialogVisible = ref(false)
const capabilityData = ref(null)

const fetchChartList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.size,
      search: searchQuery.value
    }
    const data = await request.get('/production/control-charts/', { params })
    chartList.value = data.results || data
    pagination.total = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    // 获取报警统计
    const [alarmsRes] = await Promise.all([
      request.get('/production/spc-alarms/unhandled/')
    ])
    unhandledAlarms.value = alarmsRes.data.slice(0, 10)
    
    stats.value = {
      total_charts: chartList.value.length || 0,
      unhandled_alarms: alarmsRes.data.length,
      avg_cpk: null,
      data_points_today: 0
    }
  } catch (e) {
    console.error(e)
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchChartList()
}

const handleAddChart = () => {
  Object.assign(chartForm, {
    name: '',
    chart_type: 'XBAR_R',
    measurement_name: '',
    unit: '',
    usl: null,
    lsl: null,
    target: null,
    subgroup_size: 5
  })
  addDialogVisible.value = true
}

const submitChart = async () => {
  const valid = await chartFormRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    await request.post('/production/control-charts/', chartForm)
    ElMessage.success('控制图创建成功')
    addDialogVisible.value = false
    fetchChartList()
  } catch (e) {
    ElMessage.error('创建失败')
  } finally {
    submitLoading.value = false
  }
}

const handleSelectChart = (row) => {
  handleViewChart(row)
}

const handleViewChart = async (row) => {
  currentChart.value = row
  chartDialogVisible.value = true
  
  try {
    const data = await request.get(`/production/control-charts/${row.id}/chart_data/`)
    chartData.value = data
    
    await nextTick()
    renderCharts()
  } catch (e) {
    ElMessage.error('加载图表数据失败')
  }
}

const renderCharts = () => {
  if (!xbarChartRef.value || !rChartRef.value) return
  
  // X̄ 控制图
  if (xbarChart) xbarChart.dispose()
  xbarChart = echarts.init(xbarChartRef.value)
  
  const subgroups = chartData.value.subgroups || []
  const limits = chartData.value.control_limits || {}
  
  const xData = subgroups.map(s => s.subgroup_no)
  const xBarData = subgroups.map(s => Number(s.x_bar))
  const rData = subgroups.map(s => Number(s.r_value || 0))
  
  xbarChart.setOption({
    title: { text: 'X̄ 均值控制图', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 30, top: 50, bottom: 30 },
    xAxis: { type: 'category', data: xData, name: '子组' },
    yAxis: { type: 'value', name: 'X̄' },
    series: [
      { name: 'X̄', type: 'line', data: xBarData, symbol: 'circle', symbolSize: 6, 
        lineStyle: { color: '#409eff' }, itemStyle: { color: '#409eff' } },
      { name: 'UCL', type: 'line', data: Array(xData.length).fill(limits.xbar?.ucl),
        lineStyle: { color: '#f56c6c', type: 'dashed' }, symbol: 'none' },
      { name: 'CL', type: 'line', data: Array(xData.length).fill(limits.xbar?.cl),
        lineStyle: { color: '#67c23a', type: 'dashed' }, symbol: 'none' },
      { name: 'LCL', type: 'line', data: Array(xData.length).fill(limits.xbar?.lcl),
        lineStyle: { color: '#f56c6c', type: 'dashed' }, symbol: 'none' }
    ]
  })
  
  // R 控制图
  if (rChart) rChart.dispose()
  rChart = echarts.init(rChartRef.value)
  
  rChart.setOption({
    title: { text: 'R 极差控制图', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 30, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: xData, name: '子组' },
    yAxis: { type: 'value', name: 'R' },
    series: [
      { name: 'R', type: 'line', data: rData, symbol: 'circle', symbolSize: 6,
        lineStyle: { color: '#e6a23c' }, itemStyle: { color: '#e6a23c' } },
      { name: 'UCL', type: 'line', data: Array(xData.length).fill(limits.r?.ucl),
        lineStyle: { color: '#f56c6c', type: 'dashed' }, symbol: 'none' },
      { name: 'CL', type: 'line', data: Array(xData.length).fill(limits.r?.cl),
        lineStyle: { color: '#67c23a', type: 'dashed' }, symbol: 'none' },
      { name: 'LCL', type: 'line', data: Array(xData.length).fill(limits.r?.lcl),
        lineStyle: { color: '#f56c6c', type: 'dashed' }, symbol: 'none' }
    ]
  })
}

const handleAddData = (row) => {
  dataForm.chartId = row.id
  dataForm.chartName = row.name
  dataForm.subgroup_no = 1
  dataForm.values = [null, null, null, null, null]
  dataForm.batch_no = ''
  dataForm.remarks = ''
  dataDialogVisible.value = true
}

const submitData = async () => {
  submitLoading.value = true
  try {
    const validValues = dataForm.values.filter(v => v !== null && v !== undefined)
    if (validValues.length === 0) {
      ElMessage.warning('请至少输入一个测量值')
      return
    }
    
    for (let i = 0; i < validValues.length; i++) {
      await request.post('/production/spc-data-points/', {
        control_chart: dataForm.chartId,
        subgroup_no: dataForm.subgroup_no,
        value: validValues[i],
        sample_no: i + 1,
        batch_no: dataForm.batch_no,
        remarks: dataForm.remarks
      })
    }
    
    ElMessage.success('数据采集成功')
    dataDialogVisible.value = false
    
    if (currentChart.value?.id === dataForm.chartId) {
      handleViewChart(currentChart.value)
    }
  } catch (e) {
    ElMessage.error('数据保存失败')
  } finally {
    submitLoading.value = false
  }
}

const handleAlarm = (alarm) => {
  currentAlarm.value = alarm
  alarmForm.action_taken = ''
  alarmDialogVisible.value = true
}

const submitAlarmHandle = async () => {
  if (!alarmForm.action_taken) {
    ElMessage.warning('请填写处理措施')
    return
  }
  
  submitLoading.value = true
  try {
    await request.post(`/production/spc-alarms/${currentAlarm.value.id}/handle/`, {
      action_taken: alarmForm.action_taken
    })
    ElMessage.success('报警已处理')
    alarmDialogVisible.value = false
    fetchStats()
  } catch (e) {
    ElMessage.error('处理失败')
  } finally {
    submitLoading.value = false
  }
}

const handleCalculateCapability = async () => {
  try {
    const data = await request.post(`/production/control-charts/${currentChart.value.id}/calculate_capability/`, {
      days: 30
    })
    capabilityData.value = data
    capabilityDialogVisible.value = true
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '计算失败')
  }
}

const getCpkClass = (cpk) => {
  if (!cpk) return ''
  if (cpk >= 1.33) return 'good'
  if (cpk >= 1.0) return 'warning'
  return 'danger'
}

const formatTime = (datetime) => {
  if (!datetime) return ''
  return new Date(datetime).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatDateTime = (datetime) => {
  if (!datetime) return ''
  return new Date(datetime).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchChartList().then(() => {
    fetchStats()
  })
})

onUnmounted(() => {
  if (xbarChart) xbarChart.dispose()
  if (rChart) rChart.dispose()
})
</script>

<style scoped>
.spc-container {
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

.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 20px 0;
}

.stat-card .stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}

.stat-card .stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.stat-card.warning .stat-value { color: #f56c6c; }
.stat-card.success .stat-value { color: #67c23a; }
.stat-card.info .stat-value { color: #909399; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-tip {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  color: #67c23a;
}

.empty-tip .el-icon {
  font-size: 48px;
  margin-bottom: 8px;
}

.alarm-list {
  max-height: 400px;
  overflow-y: auto;
}

.alarm-item {
  padding: 12px;
  border-radius: 6px;
  background: #fef0f0;
  margin-bottom: 12px;
}

.alarm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.alarm-time {
  font-size: 12px;
  color: #909399;
}

.alarm-chart {
  font-weight: 500;
  margin-bottom: 4px;
}

.alarm-value {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}

.control-chart-container {
  background: #fafafa;
  border-radius: 8px;
  padding: 16px;
}

.chart-title {
  text-align: center;
  font-weight: 500;
  margin-bottom: 8px;
}

.chart-area {
  width: 100%;
}

.chart-info-panel {
  background: #fafafa;
  border-radius: 8px;
  padding: 16px;
  height: 100%;
}

.chart-info-panel h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #303133;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
}

.info-item .label {
  color: #909399;
}

.info-item .value {
  font-weight: 500;
}

.measurement-inputs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.capability-result {
  padding: 16px 0;
}

.capability-item {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  text-align: center;
}

.capability-item.highlight {
  background: #ecf5ff;
}

.capability-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.capability-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.capability-value.small {
  font-size: 14px;
}

.capability-value.good {
  color: #67c23a;
}

.capability-value.warning {
  color: #e6a23c;
}

.capability-value.danger {
  color: #f56c6c;
}

.capability-interpretation {
  margin-top: 24px;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
}

.capability-interpretation h4 {
  margin: 0 0 12px 0;
}

.interpretation {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border-radius: 6px;
}

.interpretation.good {
  background: #f0f9eb;
  color: #67c23a;
}

.interpretation.warning {
  background: #fdf6ec;
  color: #e6a23c;
}

.interpretation.danger {
  background: #fef0f0;
  color: #f56c6c;
}
</style>
