<template>
  <div class="andon-container">
    <div class="page-header">
      <h2>安灯系统</h2>
      <div class="header-actions">
        <el-button type="danger" @click="handleNewCall">
          <el-icon><Bell /></el-icon>发起呼叫
        </el-button>
        <el-button @click="handleViewBoard">工位看板</el-button>
      </div>
    </div>
    
    <!-- 状态概览 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="4">
        <el-card shadow="never" class="stat-card green">
          <div class="stat-value">{{ stationSummary.GREEN || 0 }}</div>
          <div class="stat-label">正常工位</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card yellow">
          <div class="stat-value">{{ stationSummary.YELLOW || 0 }}</div>
          <div class="stat-label">警告工位</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card red">
          <div class="stat-value">{{ stationSummary.RED || 0 }}</div>
          <div class="stat-label">异常工位</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card pending">
          <div class="stat-value">{{ callStats.pending || 0 }}</div>
          <div class="stat-label">待响应</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card processing">
          <div class="stat-value">{{ callStats.processing || 0 }}</div>
          <div class="stat-label">处理中</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card avg-time">
          <div class="stat-value">{{ avgResponseTime }}min</div>
          <div class="stat-label">平均响应</div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="16">
      <!-- 待处理呼叫 -->
      <el-col :span="16">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>安灯呼叫</span>
              <el-radio-group v-model="callFilter" size="small" @change="fetchCalls">
                <el-radio-button label="pending">待处理</el-radio-button>
                <el-radio-button label="all">全部</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          
          <el-table :data="callList" v-loading="loading" border stripe>
            <el-table-column prop="call_no" label="呼叫编号" width="120" fixed />
            <el-table-column prop="title" label="异常标题" min-width="180" show-overflow-tooltip />
            <el-table-column prop="station_name" label="工位" width="110" />
            <el-table-column prop="type_name" label="类型" width="100" />
            <el-table-column prop="priority_display" label="优先级" width="80">
              <template #default="{ row }">
                <el-tag :type="getPriorityType(row.priority)" size="small">
                  {{ row.priority_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status_display" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ row.status_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="caller_name" label="呼叫人" width="90" />
            <el-table-column prop="call_time" label="呼叫时间" width="150">
              <template #default="{ row }">
                {{ formatDateTime(row.call_time) }}
              </template>
            </el-table-column>
            <el-table-column prop="response_duration" label="响应时长" width="90" align="center">
              <template #default="{ row }">
                <span v-if="row.response_duration" :class="getTimeClass(row.response_duration, 15)">
                  {{ row.response_duration }}分钟
                </span>
                <span v-else-if="row.status === 'PENDING'" class="waiting">
                  {{ getWaitingTime(row.call_time) }}分钟
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleViewCall(row)">详情</el-button>
                <template v-if="row.status === 'PENDING'">
                  <el-button type="success" link size="small" @click="handleRespond(row)">响应</el-button>
                </template>
                <template v-else-if="row.status === 'RESPONDING' || row.status === 'PROCESSING'">
                  <el-button type="success" link size="small" @click="handleResolve(row)">解决</el-button>
                  <el-button type="warning" link size="small" @click="handleEscalate(row)">升级</el-button>
                </template>
              </template>
            </el-table-column>
          </el-table>
          
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.size"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next"
            @change="fetchCalls"
            style="margin-top: 16px; justify-content: flex-end"
          />
        </el-card>
      </el-col>
      
      <!-- 工位状态 -->
      <el-col :span="8">
        <el-card shadow="never" header="工位状态" class="station-card">
          <div class="station-grid">
            <div v-for="station in stationList" :key="station.id" 
              class="station-item" :class="station.status.toLowerCase()"
              @click="handleStationClick(station)">
              <div class="station-code">{{ station.code }}</div>
              <div class="station-name">{{ station.name }}</div>
              <div v-if="station.active_call" class="station-call">
                {{ station.active_call.title }}
              </div>
            </div>
          </div>
        </el-card>
        
        <!-- 今日统计 -->
        <el-card shadow="never" header="今日统计" style="margin-top: 16px">
          <div ref="statsChartRef" style="height: 200px"></div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 发起呼叫对话框 -->
    <el-dialog v-model="callDialogVisible" title="发起安灯呼叫" width="600px">
      <el-form :model="callForm" :rules="callRules" ref="callFormRef" label-width="100px">
        <el-form-item label="工位" prop="station">
          <el-select v-model="callForm.station" placeholder="选择工位" style="width: 100%">
            <el-option v-for="s in stations" :key="s.id" :label="`${s.code} - ${s.name}`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="异常类型" prop="andon_type">
          <el-select v-model="callForm.andon_type" placeholder="选择类型" style="width: 100%">
            <el-option v-for="t in andonTypes" :key="t.id" 
              :label="t.name" :value="t.id">
              <span :style="{ color: t.color }">●</span> {{ t.name }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="异常标题" prop="title">
          <el-input v-model="callForm.title" placeholder="简述异常情况" />
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-radio-group v-model="callForm.priority">
            <el-radio-button label="LOW">低</el-radio-button>
            <el-radio-button label="MEDIUM">中</el-radio-button>
            <el-radio-button label="HIGH">高</el-radio-button>
            <el-radio-button label="CRITICAL">紧急</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="详细描述">
          <el-input v-model="callForm.description" type="textarea" :rows="4" 
            placeholder="详细描述异常情况..." />
        </el-form-item>
        <el-form-item label="批次号">
          <el-input v-model="callForm.batch_no" placeholder="相关批次号(可选)" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="callDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="submitCall" :loading="submitLoading">发起呼叫</el-button>
      </template>
    </el-dialog>
    
    <!-- 呼叫详情对话框 -->
    <el-dialog v-model="detailDialogVisible" :title="currentCall?.call_no" width="800px">
      <div v-if="currentCall" class="call-detail">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="异常标题" :span="3">{{ currentCall.title }}</el-descriptions-item>
          <el-descriptions-item label="工位">{{ currentCall.station_name }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ currentCall.type_name }}</el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="getPriorityType(currentCall.priority)">{{ currentCall.priority_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentCall.status)">{{ currentCall.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="呼叫人">{{ currentCall.caller_name }}</el-descriptions-item>
          <el-descriptions-item label="呼叫时间">{{ formatDateTime(currentCall.call_time) }}</el-descriptions-item>
          <el-descriptions-item label="响应人">{{ currentCall.responder_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="响应时间">{{ currentCall.response_time ? formatDateTime(currentCall.response_time) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="响应时长">{{ currentCall.response_duration ? `${currentCall.response_duration}分钟` : '-' }}</el-descriptions-item>
          <el-descriptions-item label="解决人">{{ currentCall.resolver_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="解决时间">{{ currentCall.resolve_time ? formatDateTime(currentCall.resolve_time) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="总时长">{{ currentCall.total_duration ? `${currentCall.total_duration}分钟` : '-' }}</el-descriptions-item>
          <el-descriptions-item label="异常描述" :span="3">{{ currentCall.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="解决方案" :span="3" v-if="currentCall.resolution">
            {{ currentCall.resolution }}
          </el-descriptions-item>
        </el-descriptions>
        
        <!-- 处理记录 -->
        <h4 style="margin: 16px 0 12px">处理记录</h4>
        <el-timeline>
          <el-timeline-item 
            v-for="action in currentCall.actions" 
            :key="action.id"
            :timestamp="formatDateTime(action.action_time)"
            :type="getActionType(action.action_type)">
            <div class="action-content">
              <span class="action-type">{{ action.action_type_display }}</span>
              <span class="action-actor">{{ action.actor_name }}</span>
              <p v-if="action.content">{{ action.content }}</p>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </el-dialog>
    
    <!-- 解决问题对话框 -->
    <el-dialog v-model="resolveDialogVisible" title="解决问题" width="500px">
      <el-form :model="resolveForm" label-width="80px">
        <el-form-item label="解决方案">
          <el-input v-model="resolveForm.resolution" type="textarea" :rows="4" 
            placeholder="请描述解决方案..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resolveDialogVisible = false">取消</el-button>
        <el-button type="success" @click="submitResolve" :loading="submitLoading">确认解决</el-button>
      </template>
    </el-dialog>
    
    <!-- 升级对话框 -->
    <el-dialog v-model="escalateDialogVisible" title="升级呼叫" width="500px">
      <el-form :model="escalateForm" label-width="80px">
        <el-form-item label="升级原因">
          <el-input v-model="escalateForm.reason" type="textarea" :rows="3" 
            placeholder="请说明升级原因..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="escalateDialogVisible = false">取消</el-button>
        <el-button type="warning" @click="submitEscalate" :loading="submitLoading">确认升级</el-button>
      </template>
    </el-dialog>
    
    <!-- 工位看板对话框 -->
    <el-dialog v-model="boardDialogVisible" title="工位状态看板" width="90%" top="5vh" fullscreen>
      <div class="board-container">
        <div class="board-grid">
          <div v-for="station in stationList" :key="station.id" 
            class="board-item" :class="station.status.toLowerCase()">
            <div class="board-status-indicator"></div>
            <div class="board-code">{{ station.code }}</div>
            <div class="board-name">{{ station.name }}</div>
            <div class="board-location">{{ station.location }}</div>
            <div v-if="station.active_call" class="board-call">
              <div class="call-title">{{ station.active_call.title }}</div>
              <div class="call-time">{{ getWaitingTime(station.active_call.call_time) }}分钟</div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Bell } from '@element-plus/icons-vue'
import request from '@/utils/request'
import * as echarts from 'echarts'

const loading = ref(false)
const submitLoading = ref(false)
const callFilter = ref('pending')

const callList = ref([])
const stationList = ref([])
const stations = ref([])
const andonTypes = ref([])
const callStats = ref({})
const stationSummary = ref({})
const avgResponseTime = ref(0)

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

// 发起呼叫
const callDialogVisible = ref(false)
const callFormRef = ref(null)
const callForm = reactive({
  station: null,
  andon_type: null,
  title: '',
  priority: 'MEDIUM',
  description: '',
  batch_no: ''
})
const callRules = {
  station: [{ required: true, message: '请选择工位', trigger: 'change' }],
  andon_type: [{ required: true, message: '请选择异常类型', trigger: 'change' }],
  title: [{ required: true, message: '请输入异常标题', trigger: 'blur' }]
}

// 呼叫详情
const detailDialogVisible = ref(false)
const currentCall = ref(null)

// 解决问题
const resolveDialogVisible = ref(false)
const resolveForm = reactive({
  resolution: ''
})
const resolveCallId = ref(null)

// 升级
const escalateDialogVisible = ref(false)
const escalateForm = reactive({
  reason: ''
})
const escalateCallId = ref(null)

// 看板
const boardDialogVisible = ref(false)

// 统计图表
const statsChartRef = ref(null)
let statsChart = null

let refreshTimer = null

const fetchCalls = async () => {
  loading.value = true
  try {
    let url = '/production/andon-calls/'
    if (callFilter.value === 'pending') {
      url = '/production/andon-calls/pending/'
    }
    
    const params = callFilter.value === 'all' ? {
      page: pagination.page,
      page_size: pagination.size
    } : {}
    
    const data = await request.get(url, { params })
    callList.value = data.results || data
    pagination.total = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchStations = async () => {
  try {
    const data = await request.get('/production/andon-stations/status_board/')
    stationList.value = data.stations || []
    
    // 计算状态统计
    const summary = {}
    data.summary?.forEach(s => {
      summary[s.current_status] = s.count
    })
    stationSummary.value = summary
  } catch (e) {
    console.error(e)
  }
}

const fetchOptions = async () => {
  try {
    const [stationsRes, typesRes] = await Promise.all([
      request.get('/production/andon-stations/', { params: { is_active: true } }),
      request.get('/production/andon-types/', { params: { is_active: true } })
    ])
    stations.value = stationsRes.results || stationsRes || []
    andonTypes.value = typesRes.results || typesRes || []
  } catch (e) {
    console.error(e)
  }
}

const fetchStats = async () => {
  try {
    const data = await request.get('/production/andon-calls/statistics/', { params: { days: 1 } })
    
    const byStatus = {}
    data.by_status?.forEach(s => {
      byStatus[s.status.toLowerCase()] = s.count
    })
    callStats.value = byStatus
    
    avgResponseTime.value = Math.round(data.avg_times?.avg_response || 0)
    
    // 渲染图表
    await nextTick()
    renderStatsChart(data)
  } catch (e) {
    console.error(e)
  }
}

const renderStatsChart = (data) => {
  if (!statsChartRef.value) return
  
  if (statsChart) statsChart.dispose()
  statsChart = echarts.init(statsChartRef.value)
  
  const byType = data.by_type || []
  
  statsChart.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: byType.map(t => ({
        name: t.andon_type__name || '未分类',
        value: t.count
      })),
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      },
      label: { show: false },
      labelLine: { show: false }
    }]
  })
}

const handleNewCall = () => {
  Object.assign(callForm, {
    station: null,
    andon_type: null,
    title: '',
    priority: 'MEDIUM',
    description: '',
    batch_no: ''
  })
  callDialogVisible.value = true
}

const submitCall = async () => {
  const valid = await callFormRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    await request.post('/production/andon-calls/', callForm)
    ElMessage.success('呼叫已发起')
    callDialogVisible.value = false
    fetchCalls()
    fetchStations()
    fetchStats()
  } catch (e) {
    ElMessage.error('发起呼叫失败')
  } finally {
    submitLoading.value = false
  }
}

const handleViewCall = async (row) => {
  try {
    const data = await request.get(`/production/andon-calls/${row.id}/`)
    currentCall.value = data
    detailDialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载详情失败')
  }
}

const handleRespond = async (row) => {
  try {
    await request.post(`/production/andon-calls/${row.id}/respond/`)
    ElMessage.success('已响应')
    fetchCalls()
    fetchStations()
    fetchStats()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  }
}

const handleResolve = (row) => {
  resolveCallId.value = row.id
  resolveForm.resolution = ''
  resolveDialogVisible.value = true
}

const submitResolve = async () => {
  submitLoading.value = true
  try {
    await request.post(`/production/andon-calls/${resolveCallId.value}/resolve/`, {
      resolution: resolveForm.resolution
    })
    ElMessage.success('问题已解决')
    resolveDialogVisible.value = false
    fetchCalls()
    fetchStations()
    fetchStats()
  } catch (e) {
    ElMessage.error('操作失败')
  } finally {
    submitLoading.value = false
  }
}

const handleEscalate = (row) => {
  escalateCallId.value = row.id
  escalateForm.reason = ''
  escalateDialogVisible.value = true
}

const submitEscalate = async () => {
  submitLoading.value = true
  try {
    await request.post(`/production/andon-calls/${escalateCallId.value}/escalate/`, {
      reason: escalateForm.reason
    })
    ElMessage.success('已升级')
    escalateDialogVisible.value = false
    fetchCalls()
    fetchStats()
  } catch (e) {
    ElMessage.error('操作失败')
  } finally {
    submitLoading.value = false
  }
}

const handleStationClick = (station) => {
  if (station.active_call) {
    handleViewCall(station.active_call)
  }
}

const handleViewBoard = () => {
  boardDialogVisible.value = true
}

const getPriorityType = (priority) => {
  const types = {
    LOW: 'info',
    MEDIUM: '',
    HIGH: 'warning',
    CRITICAL: 'danger'
  }
  return types[priority] || ''
}

const getStatusType = (status) => {
  const types = {
    PENDING: 'danger',
    RESPONDING: 'warning',
    PROCESSING: 'warning',
    RESOLVED: 'success',
    ESCALATED: 'danger',
    CANCELLED: 'info'
  }
  return types[status] || ''
}

const getActionType = (actionType) => {
  const types = {
    RESPONSE: 'success',
    UPDATE: 'primary',
    TRANSFER: 'warning',
    ESCALATE: 'danger',
    RESOLVE: 'success',
    CLOSE: 'info'
  }
  return types[actionType] || ''
}

const getTimeClass = (minutes, limit) => {
  if (minutes > limit) return 'time-over'
  if (minutes > limit * 0.8) return 'time-warning'
  return 'time-ok'
}

const getWaitingTime = (callTime) => {
  if (!callTime) return 0
  const diff = Date.now() - new Date(callTime).getTime()
  return Math.round(diff / 60000)
}

const formatDateTime = (datetime) => {
  if (!datetime) return ''
  return new Date(datetime).toLocaleString('zh-CN')
}

const refreshData = () => {
  fetchCalls()
  fetchStations()
  fetchStats()
}

onMounted(() => {
  fetchOptions()
  refreshData()
  
  // 自动刷新
  refreshTimer = setInterval(refreshData, 30000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
  if (statsChart) statsChart.dispose()
})
</script>

<style scoped>
.andon-container {
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

.header-actions {
  display: flex;
  gap: 8px;
}

.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 16px 0;
  border-left: 4px solid #dcdfe6;
}

.stat-card .stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-card .stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.stat-card.green { border-left-color: #67c23a; }
.stat-card.green .stat-value { color: #67c23a; }

.stat-card.yellow { border-left-color: #e6a23c; }
.stat-card.yellow .stat-value { color: #e6a23c; }

.stat-card.red { border-left-color: #f56c6c; }
.stat-card.red .stat-value { color: #f56c6c; }

.stat-card.pending { border-left-color: #f56c6c; }
.stat-card.pending .stat-value { color: #f56c6c; }

.stat-card.processing { border-left-color: #e6a23c; }
.stat-card.processing .stat-value { color: #e6a23c; }

.stat-card.avg-time { border-left-color: #409eff; }
.stat-card.avg-time .stat-value { color: #409eff; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.station-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.station-item {
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  text-align: center;
}

.station-item.green {
  background: linear-gradient(135deg, #f0f9eb 0%, #e1f3d8 100%);
  border: 1px solid #c2e7b0;
}

.station-item.yellow {
  background: linear-gradient(135deg, #fdf6ec 0%, #faecd8 100%);
  border: 1px solid #f5dab1;
}

.station-item.red {
  background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
  border: 1px solid #fab6b6;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.station-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.station-code {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.station-name {
  font-size: 12px;
  color: #606266;
  margin-top: 4px;
}

.station-call {
  font-size: 11px;
  color: #f56c6c;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.time-over { color: #f56c6c; font-weight: bold; }
.time-warning { color: #e6a23c; }
.time-ok { color: #67c23a; }
.waiting { color: #f56c6c; animation: blink 1s infinite; }

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.call-detail {
  padding: 0;
}

.action-content {
  font-size: 14px;
}

.action-type {
  font-weight: 500;
  margin-right: 8px;
}

.action-actor {
  color: #909399;
}

.action-content p {
  margin: 4px 0 0 0;
  color: #606266;
}

/* 看板样式 */
.board-container {
  background: linear-gradient(135deg, #1a1f36 0%, #0d1117 100%);
  min-height: calc(100vh - 200px);
  padding: 20px;
}

.board-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
}

.board-item {
  background: rgba(255,255,255,0.05);
  border-radius: 12px;
  padding: 20px;
  position: relative;
  overflow: hidden;
}

.board-status-indicator {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
}

.board-item.green .board-status-indicator { background: #67c23a; }
.board-item.yellow .board-status-indicator { background: #e6a23c; }
.board-item.red .board-status-indicator { 
  background: #f56c6c; 
  animation: flash 0.5s infinite;
}

@keyframes flash {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.board-code {
  font-size: 24px;
  font-weight: bold;
  color: #fff;
}

.board-name {
  font-size: 14px;
  color: rgba(255,255,255,0.7);
  margin-top: 4px;
}

.board-location {
  font-size: 12px;
  color: rgba(255,255,255,0.5);
  margin-top: 4px;
}

.board-call {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,0.1);
}

.board-call .call-title {
  color: #f56c6c;
  font-size: 13px;
}

.board-call .call-time {
  color: #f56c6c;
  font-size: 20px;
  font-weight: bold;
  margin-top: 4px;
}
</style>
