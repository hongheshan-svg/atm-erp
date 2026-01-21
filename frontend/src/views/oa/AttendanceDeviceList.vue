<template>
  <div class="attendance-device-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h2>考勤设备管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="handleAdd">
          <el-icon><Plus /></el-icon> 添加设备
        </el-button>
        <el-button @click="loadDevices">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <!-- 设备概览 -->
    <el-row :gutter="20" class="overview-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="overview-card">
          <el-statistic title="设备总数" :value="stats.total_devices">
            <template #prefix>
              <el-icon><Monitor /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="overview-card online">
          <el-statistic title="在线设备" :value="stats.online_devices">
            <template #prefix>
              <el-icon color="#67c23a"><CircleCheck /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="overview-card offline">
          <el-statistic title="离线设备" :value="stats.offline_devices">
            <template #prefix>
              <el-icon color="#909399"><Remove /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="overview-card">
          <el-statistic title="今日打卡" :value="stats.today_records">
            <template #prefix>
              <el-icon color="#409eff"><Clock /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <!-- 设备列表 -->
    <el-card class="device-list-card">
      <el-table :data="devices" v-loading="loading" stripe>
        <el-table-column prop="name" label="设备名称" min-width="150">
          <template #default="{ row }">
            <div class="device-name">
              <el-icon :class="getStatusClass(row.status)"><Monitor /></el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="device_sn" label="序列号" width="150" />
        <el-table-column prop="model" label="型号" width="120" />
        <el-table-column prop="connection_type_display" label="连接方式" width="120" />
        <el-table-column prop="location" label="安装位置" width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="user_count" label="用户数" width="80" align="center" />
        <el-table-column prop="today_records" label="今日打卡" width="90" align="center" />
        <el-table-column prop="last_sync_time" label="最后同步" width="160">
          <template #default="{ row }">
            <span v-if="row.last_sync_time">{{ formatDateTime(row.last_sync_time) }}</span>
            <span v-else class="text-muted">从未同步</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleTestConnection(row)" :loading="row.testing">
              测试连接
            </el-button>
            <el-button size="small" type="primary" @click="handleSyncNow(row)" :loading="row.syncing">
              立即同步
            </el-button>
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑设备对话框 -->
    <el-dialog 
      v-model="dialogVisible" 
      :title="editingDevice ? '编辑设备' : '添加设备'" 
      width="600px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="设备名称" prop="name">
          <el-input v-model="form.name" placeholder="如：前台考勤机" />
        </el-form-item>
        <el-form-item label="设备序列号" prop="device_sn">
          <el-input v-model="form.device_sn" placeholder="设备背面的序列号" :disabled="!!editingDevice" />
        </el-form-item>
        <el-form-item label="设备型号" prop="model">
          <el-select v-model="form.model" placeholder="选择型号" allow-create filterable>
            <el-option label="WX3960WIFI" value="WX3960WIFI" />
            <el-option label="K40" value="K40" />
            <el-option label="F18" value="F18" />
            <el-option label="iClock880" value="iClock880" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备类型" prop="device_type">
          <el-select v-model="form.device_type">
            <el-option label="ZKTECO智能云考勤机" value="ZKTECO_CLOUD" />
            <el-option label="ZKTECO本地考勤机" value="ZKTECO_LOCAL" />
            <el-option label="人脸识别考勤机" value="FACE_RECOGNITION" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="连接方式" prop="connection_type">
          <el-radio-group v-model="form.connection_type">
            <el-radio label="CLOUD_PUSH">云端推送</el-radio>
            <el-radio label="CLOUD_PULL">云端拉取</el-radio>
            <el-radio label="TCP_IP">TCP/IP直连</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <!-- TCP/IP 连接配置 -->
        <template v-if="form.connection_type === 'TCP_IP'">
          <el-form-item label="IP地址" prop="ip_address">
            <el-input v-model="form.ip_address" placeholder="192.168.1.100" />
          </el-form-item>
          <el-form-item label="端口号" prop="port">
            <el-input-number v-model="form.port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="通讯密码">
            <el-input v-model="form.device_password" placeholder="设备通讯密码(可选)" show-password />
          </el-form-item>
        </template>
        
        <!-- 云服务配置 -->
        <template v-if="form.connection_type.startsWith('CLOUD')">
          <el-form-item label="云服务地址">
            <el-input v-model="form.cloud_server" placeholder="https://cloud.zkteco.com" />
          </el-form-item>
          <el-form-item label="API Token">
            <el-input v-model="form.api_token" placeholder="云服务API Token" show-password />
          </el-form-item>
        </template>
        
        <el-form-item label="安装位置">
          <el-input v-model="form.location" placeholder="如：一楼大厅" />
        </el-form-item>
        <el-form-item label="所属部门">
          <el-select v-model="form.department" placeholder="选择部门" clearable>
            <el-option 
              v-for="dept in departments" 
              :key="dept.id" 
              :label="dept.name" 
              :value="dept.id" 
            />
          </el-select>
        </el-form-item>
        <el-form-item label="自动同步">
          <el-switch v-model="form.sync_enabled" />
          <span class="form-tip">启用后将自动同步考勤数据</span>
        </el-form-item>
        <el-form-item label="同步间隔" v-if="form.sync_enabled">
          <el-select v-model="form.sync_interval">
            <el-option label="每5分钟" :value="300" />
            <el-option label="每10分钟" :value="600" />
            <el-option label="每30分钟" :value="1800" />
            <el-option label="每小时" :value="3600" />
          </el-select>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- 用户映射对话框 -->
    <el-dialog v-model="mappingDialogVisible" title="用户映射管理" width="800px">
      <div class="mapping-content">
        <el-alert type="info" :closable="false" class="mb-4">
          将考勤机中的用户ID与系统员工进行绑定，绑定后打卡数据将自动关联到对应员工
        </el-alert>
        
        <el-table :data="mappings" v-loading="mappingLoading" max-height="400">
          <el-table-column prop="device_user_id" label="设备用户ID" width="120" />
          <el-table-column prop="device_user_name" label="设备用户名" width="150" />
          <el-table-column prop="employee_name" label="关联员工" width="150" />
          <el-table-column prop="fingerprint_count" label="指纹数" width="80" align="center" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_synced ? 'success' : 'info'" size="small">
                {{ row.is_synced ? '已同步' : '未同步' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button size="small" @click="handleEditMapping(row)">修改</el-button>
              <el-button size="small" type="danger" @click="handleDeleteMapping(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        
        <div class="mapping-actions">
          <el-button type="primary" @click="handleAddMapping">添加映射</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Monitor, CircleCheck, Remove, Clock } from '@element-plus/icons-vue'
import request from '@/utils/request'

// 数据
const loading = ref(false)
const devices = ref([])
const stats = ref({
  total_devices: 0,
  online_devices: 0,
  offline_devices: 0,
  today_records: 0
})

const dialogVisible = ref(false)
const editingDevice = ref(null)
const submitting = ref(false)
const formRef = ref(null)

const form = reactive({
  name: '',
  device_sn: '',
  model: 'WX3960WIFI',
  device_type: 'ZKTECO_CLOUD',
  connection_type: 'CLOUD_PUSH',
  ip_address: '',
  port: 4370,
  cloud_server: '',
  api_token: '',
  device_password: '',
  location: '',
  department: null,
  sync_enabled: true,
  sync_interval: 300
})

const rules = {
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  device_sn: [{ required: true, message: '请输入设备序列号', trigger: 'blur' }],
  device_type: [{ required: true, message: '请选择设备类型', trigger: 'change' }],
  connection_type: [{ required: true, message: '请选择连接方式', trigger: 'change' }]
}

const departments = ref([])
const mappingDialogVisible = ref(false)
const mappingLoading = ref(false)
const mappings = ref([])
const currentDevice = ref(null)

// 方法
const loadDevices = async () => {
  loading.value = true
  try {
    const res = await request.get('/oa/attendance-devices/')
    devices.value = (res.results || res || []).map(d => ({
      ...d,
      testing: false,
      syncing: false
    }))
  } catch (error) {
    console.error('加载设备列表失败:', error)
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const res = await request.get('/oa/attendance-devices/overview/')
    stats.value = res
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

const loadDepartments = async () => {
  try {
    const res = await request.get('/accounts/departments/')
    departments.value = res.results || res || []
  } catch (error) {
    console.error('加载部门失败:', error)
  }
}

const handleAdd = () => {
  editingDevice.value = null
  Object.assign(form, {
    name: '',
    device_sn: '',
    model: 'WX3960WIFI',
    device_type: 'ZKTECO_CLOUD',
    connection_type: 'CLOUD_PUSH',
    ip_address: '',
    port: 4370,
    cloud_server: '',
    api_token: '',
    device_password: '',
    location: '',
    department: null,
    sync_enabled: true,
    sync_interval: 300
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  editingDevice.value = row
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    
    submitting.value = true
    try {
      if (editingDevice.value) {
        await request.put(`/oa/attendance-devices/${editingDevice.value.id}/`, form)
        ElMessage.success('设备更新成功')
      } else {
        await request.post('/oa/attendance-devices/', form)
        ElMessage.success('设备添加成功')
      }
      dialogVisible.value = false
      loadDevices()
      loadStats()
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '操作失败')
    } finally {
      submitting.value = false
    }
  })
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该设备吗？', '提示', {
      type: 'warning'
    })
    await request.delete(`/oa/attendance-devices/${row.id}/`)
    ElMessage.success('删除成功')
    loadDevices()
    loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleTestConnection = async (row) => {
  row.testing = true
  try {
    const res = await request.post(`/oa/attendance-devices/${row.id}/test_connection/`)
    if (res.success) {
      ElMessage.success(res.message || '连接成功')
      row.status = 'ONLINE'
      row.status_display = '在线'
    } else {
      ElMessage.warning(res.message || '连接失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '连接测试失败')
  } finally {
    row.testing = false
  }
}

const handleSyncNow = async (row) => {
  row.syncing = true
  try {
    const res = await request.post(`/oa/attendance-devices/${row.id}/sync_now/`)
    if (res.success) {
      ElMessage.success(res.message || '同步成功')
      loadDevices()
      loadStats()
    } else {
      ElMessage.warning(res.message || '同步失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '同步失败')
  } finally {
    row.syncing = false
  }
}

const getStatusType = (status) => {
  const types = {
    'ONLINE': 'success',
    'OFFLINE': 'info',
    'ERROR': 'danger',
    'UNKNOWN': 'warning'
  }
  return types[status] || 'info'
}

const getStatusClass = (status) => {
  return {
    'status-online': status === 'ONLINE',
    'status-offline': status === 'OFFLINE',
    'status-error': status === 'ERROR'
  }
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 用户映射相关方法
const handleManageMappings = async (row) => {
  currentDevice.value = row
  mappingDialogVisible.value = true
  await loadMappings(row.id)
}

const loadMappings = async (deviceId) => {
  mappingLoading.value = true
  try {
    const res = await request.get('/oa/device-user-mappings/', {
      params: { device: deviceId }
    })
    mappings.value = res.results || res || []
  } catch (error) {
    console.error('加载映射失败:', error)
  } finally {
    mappingLoading.value = false
  }
}

const handleAddMapping = () => {
  // TODO: 打开添加映射对话框
  ElMessage.info('添加映射功能开发中')
}

const handleEditMapping = (row) => {
  // TODO: 打开编辑映射对话框
  ElMessage.info('编辑映射功能开发中')
}

const handleDeleteMapping = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该映射吗？', '提示', { type: 'warning' })
    await request.delete(`/oa/device-user-mappings/${row.id}/`)
    ElMessage.success('删除成功')
    loadMappings(currentDevice.value.id)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 初始化
onMounted(() => {
  loadDevices()
  loadStats()
  loadDepartments()
})
</script>

<style scoped>
.attendance-device-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.overview-cards {
  margin-bottom: 20px;
}

.overview-card {
  text-align: center;
}

.overview-card :deep(.el-statistic__head) {
  font-size: 14px;
  color: #909399;
}

.overview-card :deep(.el-statistic__content) {
  font-size: 28px;
  font-weight: bold;
}

.device-list-card {
  margin-bottom: 20px;
}

.device-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-online {
  color: #67c23a;
}

.status-offline {
  color: #909399;
}

.status-error {
  color: #f56c6c;
}

.text-muted {
  color: #909399;
  font-size: 12px;
}

.form-tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}

.mapping-content {
  padding: 10px 0;
}

.mapping-actions {
  margin-top: 20px;
  text-align: right;
}

.mb-4 {
  margin-bottom: 16px;
}
</style>
