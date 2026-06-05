<template>
  <div class="alert-container">
    <div class="page-header">
      <h2>项目预警</h2>
      <el-button type="primary" @click="handleCheckAll">检查预警</el-button>
    </div>
    
    <!-- 预警统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card critical">
          <div class="stat-value">{{ summary.critical || 0 }}</div>
          <div class="stat-label">严重预警</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card warning">
          <div class="stat-value">{{ summary.warning || 0 }}</div>
          <div class="stat-label">警告预警</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card info">
          <div class="stat-value">{{ summary.info || 0 }}</div>
          <div class="stat-label">提示预警</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card total">
          <div class="stat-value">{{ summary.total || 0 }}</div>
          <div class="stat-label">活跃预警总数</div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-card shadow="never">
      <template #header>
        <el-form :inline="true">
          <el-form-item>
            <el-input v-model="queryParams.search" placeholder="搜索项目/标题" clearable @clear="fetchList" />
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.alert_type" placeholder="预警类型" clearable @change="fetchList">
              <el-option label="进度预警" value="PROGRESS" />
              <el-option label="预算预警" value="BUDGET" />
              <el-option label="时间预警" value="TIMELINE" />
              <el-option label="任务预警" value="TASK" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.severity" placeholder="严重程度" clearable @change="fetchList">
              <el-option label="提示" value="INFO" />
              <el-option label="警告" value="WARNING" />
              <el-option label="严重" value="CRITICAL" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchList">
              <el-option label="活跃" value="ACTIVE" />
              <el-option label="已确认" value="ACKNOWLEDGED" />
              <el-option label="已解决" value="RESOLVED" />
              <el-option label="已忽略" value="IGNORED" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="fetchList">查询</el-button>
          </el-form-item>
        </el-form>
      </template>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="alertList" v-loading="loading" border stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column width="60" align="center">
          <template #default="{ row }">
            <el-icon :size="20" :color="getSeverityColor(row.severity)">
              <WarningFilled v-if="row.severity === 'CRITICAL'" />
              <Warning v-else-if="row.severity === 'WARNING'" />
              <InfoFilled v-else />
            </el-icon>
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="项目" width="200" show-overflow-tooltip />
        <el-table-column prop="title" label="预警标题" min-width="250" show-overflow-tooltip />
        <el-table-column prop="alert_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ getTypeLabel(row.alert_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="严重程度" width="100">
          <template #default="{ row }">
            <el-tag :type="getSeverityType(row.severity)" size="small">{{ getSeverityLabel(row.severity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">详情</el-button>
            <el-button type="success" link size="small" @click="handleAcknowledge(row)" 
              v-if="row.status === 'ACTIVE'">确认</el-button>
            <el-button type="warning" link size="small" @click="handleResolve(row)" 
              v-if="row.status === 'ACTIVE' || row.status === 'ACKNOWLEDGED'">解决</el-button>
            <el-button type="info" link size="small" @click="handleIgnore(row)" 
              v-if="row.status === 'ACTIVE'">忽略</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchList"
        @current-change="fetchList"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>
    
    <!-- 预警详情对话框 -->
    <el-dialog v-model="detailDialogVisible" :title="currentAlert?.title" width="600px">
      <el-descriptions v-if="currentAlert" :column="2" border>
        <el-descriptions-item label="项目">{{ currentAlert.project_name }}</el-descriptions-item>
        <el-descriptions-item label="项目编号">{{ currentAlert.project_code }}</el-descriptions-item>
        <el-descriptions-item label="预警类型">{{ getTypeLabel(currentAlert.alert_type) }}</el-descriptions-item>
        <el-descriptions-item label="严重程度">
          <el-tag :type="getSeverityType(currentAlert.severity)">{{ getSeverityLabel(currentAlert.severity) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentAlert.status)">{{ currentAlert.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(currentAlert.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ currentAlert.description }}</el-descriptions-item>
        <el-descriptions-item label="预警数据" :span="2" v-if="currentAlert.alert_data">
          <pre style="margin: 0; font-size: 12px;">{{ JSON.stringify(currentAlert.alert_data, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="确认人" v-if="currentAlert.acknowledged_by_name">
          {{ currentAlert.acknowledged_by_name }}
        </el-descriptions-item>
        <el-descriptions-item label="确认时间" v-if="currentAlert.acknowledged_at">
          {{ formatDateTime(currentAlert.acknowledged_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="解决方案" :span="2" v-if="currentAlert.resolution">
          {{ currentAlert.resolution }}
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
    
    <!-- 解决预警对话框 -->
    <el-dialog v-model="resolveDialogVisible" title="解决预警" width="500px">
      <el-form label-width="80px">
        <el-form-item label="解决方案">
          <el-input v-model="resolution" type="textarea" :rows="4" placeholder="请输入解决方案" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resolveDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitResolve" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { WarningFilled, Warning, InfoFilled } from '@element-plus/icons-vue'
import { getAlertList, getAlert, getAlertSummary, checkAllAlerts, acknowledgeAlert, resolveAlert, ignoreAlert } from '@/api/projects/alert'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects/alerts/', { onSuccess: () => fetchList() })


const loading = ref(false)
const submitLoading = ref(false)
const alertList = ref<any[]>([])
const summaryData = ref<Record<string, any>>({})

const queryParams = reactive({
  search: '',
  alert_type: null,
  severity: null,
  status: 'ACTIVE'
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

const detailDialogVisible = ref(false)
const resolveDialogVisible = ref(false)
const currentAlert = ref(null)
const resolution = ref('')

const summary = computed(() => {
  const byS = summaryData.value.by_severity || []
  return {
    total: summaryData.value.total_active || 0,
    critical: byS.find(s => s.severity === 'CRITICAL')?.count || 0,
    warning: byS.find(s => s.severity === 'WARNING')?.count || 0,
    info: byS.find(s => s.severity === 'INFO')?.count || 0
  }
})

const fetchList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.size,
      ...queryParams
    }
    const data = await getAlertList(params)
    alertList.value = data.results || data
    pagination.total = data.count || (data.results || data)?.length || 0
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchSummary = async () => {
  try {
    const data = await getAlertSummary()
    summaryData.value = data
  } catch (e) {
    console.error(e)
  }
}

const handleCheckAll = async () => {
  try {
    ElMessage.info('正在检查项目预警...')
    const data = await checkAllAlerts()
    ElMessage.success(`检查完成，新增 ${data.alerts_created} 条预警`)
    fetchList()
    fetchSummary()
  } catch (e) {
    ElMessage.error('检查失败')
  }
}

const handleView = async (row) => {
  try {
    const data = await getAlert(row.id)
    currentAlert.value = data
    detailDialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

const handleAcknowledge = async (row) => {
  try {
    await acknowledgeAlert(row.id)
    ElMessage.success('已确认')
    fetchList()
    fetchSummary()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleResolve = (row) => {
  currentAlert.value = row
  resolution.value = ''
  resolveDialogVisible.value = true
}

const submitResolve = async () => {
  submitLoading.value = true
  try {
    await resolveAlert(currentAlert.value.id, {
      resolution: resolution.value
    })
    ElMessage.success('已解决')
    resolveDialogVisible.value = false
    fetchList()
    fetchSummary()
  } catch (e) {
    ElMessage.error('操作失败')
  } finally {
    submitLoading.value = false
  }
}

const handleIgnore = async (row) => {
  try {
    await ElMessageBox.prompt('请输入忽略原因', '忽略预警', {
      inputPlaceholder: '忽略原因'
    }).then(async ({ value }) => {
      await ignoreAlert(row.id, { reason: value })
      ElMessage.success('已忽略')
      fetchList()
      fetchSummary()
    })
  } catch (e) {
    console.error('AlertList fetchSummary error:', e)
  }
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getTypeLabel = (type) => {
  const labels = {
    PROGRESS: '进度',
    BUDGET: '预算',
    TIMELINE: '时间',
    TASK: '任务',
    RESOURCE: '资源'
  }
  return labels[type] || type
}

const getSeverityLabel = (severity) => {
  const labels = { INFO: '提示', WARNING: '警告', CRITICAL: '严重' }
  return labels[severity] || severity
}

const getSeverityType = (severity) => {
  const types = { INFO: 'info', WARNING: 'warning', CRITICAL: 'danger' }
  return types[severity] || ''
}

const getSeverityColor = (severity) => {
  const colors = { INFO: '#909399', WARNING: '#e6a23c', CRITICAL: '#f56c6c' }
  return colors[severity] || '#909399'
}

const getStatusType = (status) => {
  const types = { ACTIVE: 'danger', ACKNOWLEDGED: 'warning', RESOLVED: 'success', IGNORED: 'info' }
  return types[status] || ''
}

onMounted(() => {
  fetchList()
  fetchSummary()
})
</script>

<style scoped>
.alert-container {
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
  padding: 16px 0;
}

.stat-card .stat-value {
  font-size: 32px;
  font-weight: bold;
}

.stat-card .stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.stat-card.critical .stat-value { color: #f56c6c; }
.stat-card.warning .stat-value { color: #e6a23c; }
.stat-card.info .stat-value { color: #909399; }
.stat-card.total .stat-value { color: #409eff; }
</style>
