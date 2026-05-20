<template>
  <div class="data-acquisition-container">
    <div class="page-header">
      <h2>数据采集与监控</h2>
      <div class="header-actions">
        <el-button type="primary" :icon="Plus" @click="showDataSourceDialog = true">新增数据源</el-button>
        <el-button :icon="Refresh" @click="fetchAll">刷新</el-button>
      </div>
    </div>
    
    <el-row :gutter="16">
      <!-- 数据源列表 -->
      <el-col :span="6">
        <el-card shadow="never" class="source-card">
          <template #header>
            <span>数据源 ({{ dataSources.length }})</span>
          </template>
          
          <div class="source-list" v-loading="loadingSource">
            <div 
              v-for="source in dataSources" 
              :key="source.id"
              class="source-item"
              :class="{ active: currentSource?.id === source.id, [source.status.toLowerCase()]: true }"
              @click="selectSource(source)"
            >
              <div class="source-icon">
                <el-icon v-if="source.source_type === 'MQTT'"><Connection /></el-icon>
                <el-icon v-else-if="source.source_type === 'OPC_UA'"><Monitor /></el-icon>
                <el-icon v-else><DataLine /></el-icon>
              </div>
              <div class="source-info">
                <div class="source-name">{{ source.name }}</div>
                <div class="source-meta">
                  <el-tag :type="getStatusType(source.status)" size="small">
                    {{ source.status_display }}
                  </el-tag>
                  <span class="source-points">{{ source.data_points_count }} 点</span>
                </div>
              </div>
            </div>
            
            <el-empty v-if="!dataSources.length" description="暂无数据源" :image-size="60" />
          </div>
        </el-card>
      </el-col>
      
      <!-- 数据点与实时数据 -->
      <el-col :span="18">
        <el-tabs v-model="activeTab" type="border-card">
          <!-- 实时监控 -->
          <el-tab-pane label="实时监控" name="realtime">
            <div class="realtime-grid" v-if="dataPoints.length">
              <div 
                v-for="point in dataPoints" 
                :key="point.id"
                class="data-card"
                :class="{ alarm: point.alarm_status }"
              >
                <div class="data-header">
                  <span class="data-name">{{ point.name }}</span>
                  <el-tag :type="getCategoryType(point.category)" size="small">
                    {{ point.category_display }}
                  </el-tag>
                </div>
                <div class="data-value">
                  <span class="value">{{ point.current_value || '--' }}</span>
                  <span class="unit">{{ point.unit }}</span>
                </div>
                <div class="data-footer">
                  <span class="time">{{ formatTime(point.current_value_at) }}</span>
                  <el-tag v-if="point.alarm_status" type="danger" size="small">
                    {{ point.alarm_status }}
                  </el-tag>
                </div>
              </div>
            </div>
            <el-empty v-else description="请选择数据源查看数据点" />
          </el-tab-pane>
          
          <!-- 数据点配置 -->
          <el-tab-pane label="数据点配置" name="points">
            <div class="table-toolbar">
              <el-button type="primary" size="small" :icon="Plus" @click="showPointDialog = true">
                新增数据点
              </el-button>
            </div>
            
            <!-- 批量操作 -->
            
            <div v-if="selectedRows.length > 0" class="batch-toolbar">
            
              <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
            
              <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
            
              <el-button size="small" @click="batchExport">导出选中</el-button>
            
            </div>
            
            <el-table :data="dataPoints" border stripe v-loading="loadingPoints" @selection-change="handleSelectionChange">
              <el-table-column type="selection" width="45" />
              <el-table-column prop="code" label="编码" width="120" />
              <el-table-column prop="name" label="名称" width="150" />
              <el-table-column prop="type_display" label="类型" width="80" />
              <el-table-column prop="category_display" label="分类" width="100" />
              <el-table-column prop="unit" label="单位" width="60" />
              <el-table-column prop="address" label="地址" min-width="150" show-overflow-tooltip />
              <el-table-column prop="current_value" label="当前值" width="100">
                <template #default="{ row }">
                  <span :class="{ 'alarm-value': row.alarm_status }">
                    {{ row.current_value || '--' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="is_active" label="状态" width="80">
                <template #default="{ row }">
                  <el-switch v-model="row.is_active" @change="togglePoint(row)" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="viewHistory(row)">历史</el-button>
                  <el-button link type="primary" size="small" @click="editPoint(row)">编辑</el-button>
                  <el-button link type="danger" size="small" @click="deletePoint(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          
          <!-- 告警记录 -->
          <el-tab-pane label="告警记录" name="alarms">
            <el-table :data="alarms" border stripe v-loading="loadingAlarms">
              <el-table-column prop="data_point_name" label="数据点" width="150" />
              <el-table-column prop="level" label="级别" width="80">
                <template #default="{ row }">
                  <el-tag :type="getAlarmLevelType(row.level)" size="small">
                    {{ row.level_display }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="message" label="告警信息" min-width="200" show-overflow-tooltip />
              <el-table-column prop="value" label="触发值" width="100" />
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="getAlarmStatusType(row.status)" size="small">
                    {{ row.status_display }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="triggered_at" label="触发时间" width="160">
                <template #default="{ row }">
                  {{ formatDateTime(row.triggered_at) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button 
                    v-if="row.status === 'ACTIVE'" 
                    link type="primary" size="small" 
                    @click="handleAcknowledgeAlarm(row)"
                  >确认</el-button>
                  <el-button 
                    v-if="row.status === 'ACKNOWLEDGED'" 
                    link type="success" size="small"
                    @click="handleResolveAlarm(row)"
                  >解决</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          
          <!-- 历史趋势 -->
          <el-tab-pane label="历史趋势" name="history">
            <div class="history-toolbar">
              <el-select v-model="selectedPointId" placeholder="选择数据点" style="width: 200px">
                <el-option 
                  v-for="point in dataPoints" 
                  :key="point.id" 
                  :label="point.name" 
                  :value="point.id" 
                />
              </el-select>
              <el-date-picker
                v-model="historyDateRange"
                type="datetimerange"
                range-separator="至"
                start-placeholder="开始时间"
                end-placeholder="结束时间"
                style="width: 380px"
              />
              <el-button type="primary" @click="fetchHistory">查询</el-button>
            </div>
            
            <div class="chart-container" ref="historyChart"></div>
          </el-tab-pane>
        </el-tabs>
      </el-col>
    </el-row>
    
    <!-- 数据源对话框 -->
    <el-dialog 
      v-model="showDataSourceDialog" 
      :title="editingSource ? '编辑数据源' : '新增数据源'"
      width="600px"
    >
      <el-form :model="sourceForm" :rules="sourceRules" ref="sourceFormRef" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="sourceForm.name" placeholder="请输入数据源名称" />
        </el-form-item>
        <el-form-item label="编码" prop="code">
          <el-input v-model="sourceForm.code" placeholder="请输入编码" />
        </el-form-item>
        <el-form-item label="类型" prop="source_type">
          <el-select v-model="sourceForm.source_type" style="width: 100%">
            <el-option label="MQTT协议" value="MQTT" />
            <el-option label="OPC UA协议" value="OPC_UA" />
            <el-option label="Modbus协议" value="MODBUS" />
            <el-option label="HTTP接口" value="HTTP" />
          </el-select>
        </el-form-item>
        <el-form-item label="主机地址" prop="host">
          <el-input v-model="sourceForm.host" placeholder="如: localhost 或 192.168.1.100" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="sourceForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="sourceForm.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="sourceForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="MQTT主题" v-if="sourceForm.source_type === 'MQTT'">
          <el-input 
            v-model="sourceForm.topics" 
            type="textarea" 
            :rows="3" 
            placeholder="每行一个主题，如:&#10;/device/+/data&#10;/sensor/#" 
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="sourceForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showDataSourceDialog = false">取消</el-button>
        <el-button type="primary" @click="saveDataSource">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 数据点对话框 -->
    <el-dialog 
      v-model="showPointDialog" 
      :title="editingPoint ? '编辑数据点' : '新增数据点'"
      width="650px"
    >
      <el-form :model="pointForm" :rules="pointRules" ref="pointFormRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="名称" prop="name">
              <el-input v-model="pointForm.name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="编码" prop="code">
              <el-input v-model="pointForm.code" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="数据类型" prop="data_type">
              <el-select v-model="pointForm.data_type" style="width: 100%">
                <el-option label="浮点数" value="FLOAT" />
                <el-option label="整数" value="INT" />
                <el-option label="布尔值" value="BOOL" />
                <el-option label="字符串" value="STRING" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分类" prop="category">
              <el-select v-model="pointForm.category" style="width: 100%">
                <el-option label="生产数据" value="PRODUCTION" />
                <el-option label="质量数据" value="QUALITY" />
                <el-option label="设备数据" value="EQUIPMENT" />
                <el-option label="环境数据" value="ENVIRONMENT" />
                <el-option label="能源数据" value="ENERGY" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="数据地址">
          <el-input v-model="pointForm.address" placeholder="MQTT主题或OPC UA节点地址" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="单位">
              <el-input v-model="pointForm.unit" placeholder="如: ℃, %RH" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="缩放系数">
              <el-input-number v-model="pointForm.scale_factor" :precision="4" :step="0.1" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="偏移量">
              <el-input-number v-model="pointForm.offset" :precision="2" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">告警阈值</el-divider>
        <el-row :gutter="16">
          <el-col :span="6">
            <el-form-item label="低报警">
              <el-input-number v-model="pointForm.alarm_low" :precision="2" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="低告警">
              <el-input-number v-model="pointForm.warning_low" :precision="2" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="高告警">
              <el-input-number v-model="pointForm.warning_high" :precision="2" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="高报警">
              <el-input-number v-model="pointForm.alarm_high" :precision="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      
      <template #footer>
        <el-button @click="showPointDialog = false">取消</el-button>
        <el-button type="primary" @click="saveDataPoint">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Connection, Monitor, DataLine } from '@element-plus/icons-vue'
import { getDataSourceList, getDataPointList, getDataAlarmList, updateDataSource, createDataSource, updateDataPoint, createDataPoint, deleteDataPoint, patchDataPoint, acknowledgeAlarm, resolveAlarm, getDataPointDetailHistory } from '@/api/mes'
import * as echarts from 'echarts'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/mes/')


// 数据
const loadingSource = ref(false)
const loadingPoints = ref(false)
const loadingAlarms = ref(false)
const activeTab = ref('realtime')
const dataSources = ref([])
const dataPoints = ref([])
const alarms = ref([])
const currentSource = ref(null)
const historyData = ref([])
const selectedPointId = ref(null)
const historyDateRange = ref([])

// 对话框
const showDataSourceDialog = ref(false)
const showPointDialog = ref(false)
const editingSource = ref(null)
const editingPoint = ref(null)

// 表单
const sourceFormRef = ref(null)
const pointFormRef = ref(null)
const sourceForm = ref({
  name: '',
  code: '',
  source_type: 'MQTT',
  host: '',
  port: 1883,
  username: '',
  password: '',
  topics: '',
  description: ''
})
const pointForm = ref({
  name: '',
  code: '',
  data_type: 'FLOAT',
  category: 'PRODUCTION',
  address: '',
  unit: '',
  scale_factor: 1.0,
  offset: 0,
  alarm_low: null,
  warning_low: null,
  warning_high: null,
  alarm_high: null
})

// 校验规则
const sourceRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  source_type: [{ required: true, message: '请选择类型', trigger: 'change' }]
}
const pointRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }]
}

// 图表
const historyChart = ref(null)
let chartInstance = null

// 工具方法
const getStatusType = (status) => {
  const types = { ACTIVE: 'success', INACTIVE: 'info', ERROR: 'danger', TESTING: 'warning' }
  return types[status] || 'info'
}

const getCategoryType = (category) => {
  const types = { 
    PRODUCTION: 'primary', QUALITY: 'success', EQUIPMENT: 'warning',
    ENVIRONMENT: 'info', ENERGY: 'danger'
  }
  return types[category] || 'info'
}

const getAlarmLevelType = (level) => {
  const types = { INFO: 'info', WARNING: 'warning', ALARM: 'danger', CRITICAL: 'danger' }
  return types[level] || 'info'
}

const getAlarmStatusType = (status) => {
  const types = { ACTIVE: 'danger', ACKNOWLEDGED: 'warning', RESOLVED: 'success' }
  return types[status] || 'info'
}

const formatTime = (time) => {
  if (!time) return '--'
  return new Date(time).toLocaleTimeString('zh-CN')
}

const formatDateTime = (time) => {
  if (!time) return '--'
  return new Date(time).toLocaleString('zh-CN')
}

// API调用
const fetchDataSources = async () => {
  loadingSource.value = true
  try {
    const data = await getDataSourceList()
    dataSources.value = data.results || data
  } catch (e) {
    console.error(e)
  } finally {
    loadingSource.value = false
  }
}

const fetchDataPoints = async (sourceId) => {
  loadingPoints.value = true
  try {
    const data = await getDataPointList({ data_source: sourceId })
    dataPoints.value = data.results || data
  } catch (e) {
    console.error(e)
  } finally {
    loadingPoints.value = false
  }
}

const fetchAlarms = async () => {
  loadingAlarms.value = true
  try {
    const data = await getDataAlarmList()
    alarms.value = data.results || data
  } catch (e) {
    console.error(e)
  } finally {
    loadingAlarms.value = false
  }
}

const fetchAll = () => {
  fetchDataSources()
  if (currentSource.value) {
    fetchDataPoints(currentSource.value.id)
  }
  fetchAlarms()
}

const selectSource = (source) => {
  currentSource.value = source
  fetchDataPoints(source.id)
}

const saveDataSource = async () => {
  await sourceFormRef.value.validate()
  try {
    if (editingSource.value) {
      await updateDataSource(editingSource.value.id, sourceForm.value)
      ElMessage.success('更新成功')
    } else {
      await createDataSource(sourceForm.value)
      ElMessage.success('创建成功')
    }
    showDataSourceDialog.value = false
    fetchDataSources()
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

const saveDataPoint = async () => {
  await pointFormRef.value.validate()
  try {
    const data = { ...pointForm.value, data_source: currentSource.value?.id }
    if (editingPoint.value) {
      await updateDataPoint(editingPoint.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await createDataPoint(data)
      ElMessage.success('创建成功')
    }
    showPointDialog.value = false
    fetchDataPoints(currentSource.value.id)
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

const editPoint = (row) => {
  editingPoint.value = row
  pointForm.value = { ...row }
  showPointDialog.value = true
}

const deletePoint = async (row) => {
  await ElMessageBox.confirm('确定要删除该数据点吗？', '提示', { type: 'warning' })
  try {
    await deleteDataPoint(row.id)
    ElMessage.success('删除成功')
    fetchDataPoints(currentSource.value.id)
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const togglePoint = async (row) => {
  try {
    await patchDataPoint(row.id, { is_active: row.is_active })
    ElMessage.success(row.is_active ? '已启用' : '已禁用')
  } catch (e) {
    ElMessage.error('操作失败')
    row.is_active = !row.is_active
  }
}

const handleAcknowledgeAlarm = async (row) => {
  try {
    await acknowledgeAlarm(row.id)
    ElMessage.success('已确认')
    fetchAlarms()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleResolveAlarm = async (row) => {
  try {
    await resolveAlarm(row.id)
    ElMessage.success('已解决')
    fetchAlarms()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const viewHistory = (row) => {
  selectedPointId.value = row.id
  activeTab.value = 'history'
  fetchHistory()
}

const fetchHistory = async () => {
  if (!selectedPointId.value) return
  
  try {
    const params = {}
    if (historyDateRange.value?.length) {
      params.start = historyDateRange.value[0].toISOString()
      params.end = historyDateRange.value[1].toISOString()
    }
    
    const data = await getDataPointDetailHistory(selectedPointId.value, params)
    historyData.value = data
    renderHistoryChart()
  } catch (e) {
    console.error(e)
  }
}

const renderHistoryChart = () => {
  nextTick(() => {
    if (!historyChart.value) return
    
    if (!chartInstance) {
      chartInstance = echarts.init(historyChart.value)
    }
    
    const option = {
      title: { text: '历史趋势', left: 'center' },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'time',
        axisLabel: { formatter: '{HH}:{mm}' }
      },
      yAxis: { type: 'value' },
      dataZoom: [{ type: 'inside' }, { type: 'slider' }],
      series: [{
        name: '数值',
        type: 'line',
        smooth: true,
        data: historyData.value.map(d => [d.timestamp, parseFloat(d.value)])
      }]
    }
    
    chartInstance.setOption(option)
  })
}

// 生命周期
onMounted(() => {
  fetchDataSources()
  fetchAlarms()
})

watch(showPointDialog, (val) => {
  if (!val) {
    editingPoint.value = null
    pointForm.value = {
      name: '',
      code: '',
      data_type: 'FLOAT',
      category: 'PRODUCTION',
      address: '',
      unit: '',
      scale_factor: 1.0,
      offset: 0,
      alarm_low: null,
      warning_low: null,
      warning_high: null,
      alarm_high: null
    }
  }
})
</script>

<style scoped>
.data-acquisition-container {
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
}

.header-actions {
  display: flex;
  gap: 12px;
}

.source-card {
  height: calc(100vh - 180px);
  overflow: hidden;
}

.source-list {
  max-height: calc(100vh - 280px);
  overflow-y: auto;
}

.source-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border-left: 3px solid transparent;
  margin-bottom: 8px;
}

.source-item:hover {
  background: var(--el-fill-color-light);
}

.source-item.active {
  background: var(--el-color-primary-light-9);
  border-left-color: var(--el-color-primary);
}

.source-item.active .source-icon {
  color: var(--el-color-primary);
}

.source-item.error {
  border-left-color: var(--el-color-danger);
}

.source-icon {
  font-size: 24px;
  color: #909399;
}

.source-info {
  flex: 1;
  min-width: 0;
}

.source-name {
  font-weight: 500;
  margin-bottom: 4px;
}

.source-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.source-points {
  color: #909399;
}

.realtime-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  padding: 16px;
}

.data-card {
  background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
  border-radius: 12px;
  padding: 16px;
  transition: all 0.3s;
}

.data-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.data-card.alarm {
  background: linear-gradient(135deg, #fff5f5 0%, #ffd6d6 100%);
  border: 1px solid #ffb4b4;
}

.data-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.data-name {
  font-weight: 500;
  font-size: 14px;
}

.data-value {
  text-align: center;
  margin: 16px 0;
}

.data-value .value {
  font-size: 32px;
  font-weight: 600;
  color: #303133;
}

.data-value .unit {
  font-size: 14px;
  color: #909399;
  margin-left: 4px;
}

.data-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #909399;
}

.table-toolbar {
  margin-bottom: 12px;
}

.alarm-value {
  color: var(--el-color-danger);
  font-weight: 500;
}

.history-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.chart-container {
  height: 400px;
}
</style>
