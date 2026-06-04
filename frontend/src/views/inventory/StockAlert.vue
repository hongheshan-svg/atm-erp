<template>
  <div class="alert-container">
    <div class="page-header">
      <h2>库存预警</h2>
      <div class="header-actions">
        <el-button @click="handleInitRules">初始化规则</el-button>
        <el-button type="primary" @click="handleCheckAll">检查预警</el-button>
      </div>
    </div>
    
    <!-- 预警统计 -->
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
    
    <el-tabs v-model="activeTab">
      <el-tab-pane label="预警列表" name="alerts">
        <el-card shadow="never">
          <template #header>
            <el-form :inline="true">
              <el-form-item>
                <el-input v-model="queryParams.search" placeholder="搜索物料" clearable @clear="fetchAlerts" />
              </el-form-item>
              <el-form-item>
                <el-select v-model="queryParams.alert_type" placeholder="预警类型" clearable @change="fetchAlerts">
                  <el-option label="低库存" value="LOW_STOCK" />
                  <el-option label="积压" value="OVERSTOCK" />
                  <el-option label="补货" value="REORDER" />
                  <el-option label="呆滞" value="SLOW_MOVING" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchAlerts">
                  <el-option label="活跃" value="ACTIVE" />
                  <el-option label="已确认" value="ACKNOWLEDGED" />
                  <el-option label="已解决" value="RESOLVED" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="fetchAlerts">查询</el-button>
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
                <el-icon :size="18" :color="getSeverityColor(row.severity)">
                  <WarningFilled v-if="row.severity === 'CRITICAL'" />
                  <Warning v-else-if="row.severity === 'WARNING'" />
                  <InfoFilled v-else />
                </el-icon>
              </template>
            </el-table-column>
            <el-table-column prop="item_code" label="物料编码" width="120" />
            <el-table-column prop="item_name" label="物料名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="alert_type" label="预警类型" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ getTypeLabel(row.alert_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="当前/阈值" width="140" align="right">
              <template #default="{ row }">
                <span :class="row.current_qty < row.threshold_value ? 'text-danger' : ''">
                  {{ row.current_qty }}
                </span>
                <span> / {{ row.threshold_value }}</span>
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
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
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
            @size-change="fetchAlerts"
            @current-change="fetchAlerts"
            style="margin-top: 16px; justify-content: flex-end"
          />
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="预警规则" name="rules">
        <el-card shadow="never">
          <el-table :data="rules" border stripe>
            <el-table-column prop="name" label="规则名称" min-width="150" />
            <el-table-column prop="alert_type_display" label="预警类型" width="120" />
            <el-table-column prop="scope_display" label="适用范围" width="100" />
            <el-table-column label="阈值" width="150">
              <template #default="{ row }">
                <span v-if="row.threshold_qty">数量: {{ row.threshold_qty }}</span>
                <span v-if="row.threshold_days">天数: {{ row.threshold_days }}</span>
                <span v-if="row.threshold_percentage">比例: {{ row.threshold_percentage }}%</span>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { WarningFilled, Warning, InfoFilled } from '@element-plus/icons-vue'
import { getStockAlerts, getStockAlertRules, getStockAlertsSummary, initStockAlertRules, checkAllStockAlerts, acknowledgeStockAlert, resolveStockAlert, ignoreStockAlert } from '@/api/inventory'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/inventory/stock-alerts/')


const loading = ref(false)
const activeTab = ref('alerts')
const alertList = ref<any[]>([])
const rules = ref<any[]>([])
const summaryData = ref<Record<string, any>>({})

const queryParams = reactive({
  search: '',
  alert_type: null,
  status: 'ACTIVE'
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

const summary = computed(() => {
  const byS = summaryData.value.by_severity || []
  return {
    total: summaryData.value.total_active || 0,
    critical: byS.find(s => s.severity === 'CRITICAL')?.count || 0,
    warning: byS.find(s => s.severity === 'WARNING')?.count || 0,
    info: byS.find(s => s.severity === 'INFO')?.count || 0
  }
})

const fetchAlerts = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.size,
      ...queryParams
    }
    const data = await getStockAlerts(params)
    alertList.value = data.results || data
    pagination.total = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchRules = async () => {
  try {
    const data = await getStockAlertRules()
    rules.value = data.results || data
  } catch (e) {
    console.error(e)
  }
}

const fetchSummary = async () => {
  try {
    const data = await getStockAlertsSummary()
    summaryData.value = data
  } catch (e) {
    console.error(e)
  }
}

const handleInitRules = async () => {
  try {
    const data = await initStockAlertRules()
    ElMessage.success(`初始化完成，新增 ${data.created} 条规则`)
    fetchRules()
  } catch (e) {
    ElMessage.error('初始化失败')
  }
}

const handleCheckAll = async () => {
  try {
    ElMessage.info('正在检查预警...')
    const data = await checkAllStockAlerts()
    ElMessage.success(`检查完成，新增 ${data.alerts_created} 条预警`)
    fetchAlerts()
    fetchSummary()
  } catch (e) {
    ElMessage.error('检查失败')
  }
}

const handleAcknowledge = async (row) => {
  try {
    await acknowledgeStockAlert(row.id)
    ElMessage.success('已确认')
    fetchAlerts()
    fetchSummary()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleResolve = async (row) => {
  try {
    await ElMessageBox.prompt('请输入解决方案', '解决预警', {
      inputPlaceholder: '解决方案'
    }).then(async ({ value }) => {
      await resolveStockAlert(row.id, { resolution: value })
      ElMessage.success('已解决')
      fetchAlerts()
      fetchSummary()
    })
  } catch (e) {
    console.error('StockAlert fetchSummary error:', e)
  }
}

const handleIgnore = async (row) => {
  try {
    await ignoreStockAlert(row.id)
    ElMessage.success('已忽略')
    fetchAlerts()
    fetchSummary()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getTypeLabel = (type) => {
  const labels = {
    LOW_STOCK: '低库存',
    OVERSTOCK: '积压',
    REORDER: '补货',
    SLOW_MOVING: '呆滞',
    EXPIRY: '效期'
  }
  return labels[type] || type
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
  fetchAlerts()
  fetchRules()
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

.text-danger { color: #f56c6c; }
</style>
