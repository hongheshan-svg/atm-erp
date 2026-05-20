<template>
  <div class="equipment-monitoring">
    <!-- 统计概览 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon">
            <el-icon size="40" color="#409eff"><Monitor /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.total || 0 }}</div>
            <div class="stat-label">设备总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card success">
          <div class="stat-icon">
            <el-icon size="40" color="#67c23a"><CircleCheck /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.online || 0 }}</div>
            <div class="stat-label">在线设备</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card warning">
          <div class="stat-icon">
            <el-icon size="40" color="#e6a23c"><Warning /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ activeAlarms.length }}</div>
            <div class="stat-label">活动报警</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card danger">
          <div class="stat-icon">
            <el-icon size="40" color="#f56c6c"><Bell /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ pendingPM.length }}</div>
            <div class="stat-label">待处理维护</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 活动报警列表 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>活动报警</span>
              <el-badge :value="activeAlarms.length" :hidden="activeAlarms.length === 0">
                <el-button type="primary" link @click="viewAllAlarms">查看全部</el-button>
              </el-badge>
            </div>
          </template>
          <!-- 批量操作 -->
          <div v-if="selectedRows.length > 0" class="batch-toolbar">
            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
            <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
            <el-button size="small" @click="batchExport">导出选中</el-button>
          </div>
          <el-table :data="activeAlarms" size="small" max-height="350" v-loading="loading" @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column label="严重程度" width="80">
              <template #default="{ row }">
                <el-tag :type="getSeverityType(row.severity)" size="small">{{ row.severity_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="equipment_no" label="设备" width="100" />
            <el-table-column prop="alarm_message" label="报警消息" show-overflow-tooltip />
            <el-table-column label="触发时间" width="100">
              <template #default="{ row }">{{ formatTime(row.triggered_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleAckAlarm(row)">确认</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="activeAlarms.length === 0" description="暂无活动报警" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 预测性维护提醒 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>预测性维护提醒</span>
              <el-button type="primary" link @click="viewAllPM">查看全部</el-button>
            </div>
          </template>
          <el-table :data="pendingPM" size="small" max-height="350" v-loading="loading">
            <el-table-column label="紧急程度" width="80">
              <template #default="{ row }">
                <el-tag :type="getUrgencyType(row.urgency)" size="small">{{ row.urgency_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="equipment_name" label="设备" width="120" show-overflow-tooltip />
            <el-table-column prop="model_name" label="预测模型" width="100" show-overflow-tooltip />
            <el-table-column prop="recommendation" label="建议" show-overflow-tooltip />
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleActionPM(row)">处理</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="pendingPM.length === 0" description="暂无待处理维护" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 设备状态列表 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>设备连接状态</span>
          <el-button type="primary" @click="refreshData" :loading="loading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>
      <el-table :data="connections" v-loading="loading" stripe>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_online ? 'success' : 'danger'" effect="dark" round size="small">
              {{ row.is_online ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="equipment_no" label="设备编号" width="120" />
        <el-table-column prop="equipment_name" label="设备名称" min-width="180" />
        <el-table-column prop="protocol_display" label="通信协议" width="110" />
        <el-table-column label="最后心跳" width="160">
          <template #default="{ row }">
            <span :class="{ 'text-danger': isHeartbeatOld(row.last_heartbeat) }">
              {{ row.last_heartbeat ? formatDateTime(row.last_heartbeat) : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最后数据" width="160">
          <template #default="{ row }">
            {{ row.last_data_time ? formatDateTime(row.last_data_time) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="采集状态" width="90" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.is_enabled" @change="toggleCollection(row)" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewEquipmentData(row)">数据</el-button>
            <el-button type="primary" link @click="testConnection(row)">测试</el-button>
            <el-button type="primary" link @click="startDiagnosis(row)">诊断</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 诊断对话框 -->
    <el-dialog v-model="diagnosisDialogVisible" title="远程诊断" width="700px" destroy-on-close>
      <el-form :model="diagnosisForm" label-width="100px">
        <el-form-item label="诊断原因">
          <el-select v-model="diagnosisForm.reason" style="width: 100%">
            <el-option label="报警触发" value="ALARM" />
            <el-option label="计划诊断" value="SCHEDULED" />
            <el-option label="客户请求" value="REQUEST" />
            <el-option label="主动巡检" value="PROACTIVE" />
          </el-select>
        </el-form-item>
        <el-form-item label="诊断说明">
          <el-input v-model="diagnosisForm.description" type="textarea" :rows="3" placeholder="请输入诊断说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="diagnosisDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleStartDiagnosis" :loading="submitting">开始诊断</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Monitor, CircleCheck, Warning, Bell, Refresh } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { getMonitoringDashboard, getEquipmentConnectionList, patchEquipmentConnection, testEquipmentConnection, acknowledgeEquipmentAlarm, takePMAction } from '@/api/projects/equipment-monitoring'
import { createDiagnosticSession } from '@/api/projects/diagnostic'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects_equipment-monitoring/')


const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const stats = ref({})
const activeAlarms = ref([])
const pendingPM = ref([])
const connections = ref([])
const diagnosisDialogVisible = ref(false)
const currentEquipment = ref(null)
let refreshInterval = null

const diagnosisForm = reactive({
  reason: 'PROACTIVE',
  description: ''
})

const getSeverityType = (severity) => {
  const map = { INFO: 'info', WARNING: 'warning', ALARM: 'danger', CRITICAL: 'danger' }
  return map[severity] || 'info'
}

const getUrgencyType = (urgency) => {
  const map = { LOW: 'info', MEDIUM: 'warning', HIGH: 'danger', IMMEDIATE: 'danger' }
  return map[urgency] || 'info'
}

const formatTime = (datetime) => {
  if (!datetime) return '-'
  const d = new Date(datetime)
  return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`
}

const formatDateTime = (datetime) => {
  if (!datetime) return '-'
  const d = new Date(datetime)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

const isHeartbeatOld = (datetime) => {
  if (!datetime) return true
  const diff = Date.now() - new Date(datetime).getTime()
  return diff > 5 * 60 * 1000 // 5分钟
}

const loadDashboard = async () => {
  loading.value = true
  try {
    const res = await getMonitoringDashboard()
    stats.value = res.data.equipment_stats || {}
    activeAlarms.value = res.data.active_alarms || []
    pendingPM.value = res.data.pending_pm || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const loadConnections = async () => {
  try {
    const res = await getEquipmentConnectionList({ page_size: 100 })
    connections.value = res.data.results || res.data
  } catch (e) {
    console.error(e)
  }
}

const refreshData = () => {
  loadDashboard()
  loadConnections()
}

const handleAckAlarm = async (alarm) => {
  try {
    await acknowledgeEquipmentAlarm(alarm.id)
    ElMessage.success('报警已确认')
    loadDashboard()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleActionPM = async (pm) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入处理措施', '处理维护提醒', {
      confirmButtonText: '确认',
      cancelButtonText: '取消'
    })
    await takePMAction(pm.id, { action_taken: value })
    ElMessage.success('已标记处理')
    loadDashboard()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('操作失败')
  }
}

const toggleCollection = async (conn) => {
  try {
    await patchEquipmentConnection(conn.id, {
      is_enabled: conn.is_enabled
    })
    ElMessage.success(conn.is_enabled ? '采集已启用' : '采集已停止')
  } catch (e) {
    conn.is_enabled = !conn.is_enabled
    ElMessage.error('操作失败')
  }
}

const testConnection = async (conn) => {
  try {
    const res = await testEquipmentConnection(conn.id)
    if (res.data.success) {
      ElMessage.success(`连接正常，延迟: ${res.data.latency_ms}ms`)
    } else {
      ElMessage.error('连接失败')
    }
  } catch (e) {
    ElMessage.error('测试失败')
  }
}

const viewEquipmentData = (conn) => {
  router.push(`/projects/equipment-data?equipment=${conn.equipment}`)
}

const startDiagnosis = (conn) => {
  currentEquipment.value = conn
  diagnosisForm.reason = 'PROACTIVE'
  diagnosisForm.description = ''
  diagnosisDialogVisible.value = true
}

const handleStartDiagnosis = async () => {
  submitting.value = true
  try {
    const res = await createDiagnosticSession({
      equipment: currentEquipment.value.equipment,
      reason: diagnosisForm.reason,
      started_at: new Date().toISOString()
    })
    ElMessage.success('诊断会话已创建')
    diagnosisDialogVisible.value = false
    router.push(`/projects/diagnostic-session/${res.data.id}`)
  } catch (e) {
    ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

const viewAllAlarms = () => {
  router.push('/projects/equipment-alarms')
}

const viewAllPM = () => {
  router.push('/projects/pm-results')
}

onMounted(() => {
  refreshData()
  // 自动刷新
  refreshInterval = setInterval(refreshData, 60000) // 每分钟刷新
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.stat-row {
  margin-bottom: 16px;
}
.stat-card {
  display: flex;
  align-items: center;
  padding: 10px;
}
.stat-icon {
  margin-right: 16px;
}
.stat-content {
  flex: 1;
}
.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}
.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.text-danger {
  color: #f56c6c;
}
</style>
