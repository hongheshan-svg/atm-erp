<template>
  <div class="audit-log-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">审计日志</span>
          <el-button type="primary" @click="refreshData">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <!-- Filters -->
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="操作类型">
          <el-select v-model="filters.action" placeholder="全部" clearable>
            <el-option label="创建" value="CREATE" />
            <el-option label="更新" value="UPDATE" />
            <el-option label="删除" value="DELETE" />
            <el-option label="登录" value="LOGIN" />
            <el-option label="登出" value="LOGOUT" />
            <el-option label="审批" value="APPROVE" />
            <el-option label="拒绝" value="REJECT" />
          </el-select>
        </el-form-item>

        <el-form-item label="模块">
          <el-input v-model="filters.model_name" placeholder="模块名称" clearable />
        </el-form-item>

        <el-form-item label="开始日期">
          <el-date-picker
            v-model="filters.start_date"
            type="date"
            placeholder="开始日期"
          />
        </el-form-item>

        <el-form-item label="结束日期">
          <el-date-picker
            v-model="filters.end_date"
            type="date"
            placeholder="结束日期"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="searchLogs">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- Data Table -->
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table
        :data="auditLogs"
        v-loading="loading"
        border
        stripe
        style="width: 100%"
        max-height="600"
       @selection-change="handleSelectionChange">

        <el-table-column type="selection" width="45" />
        <el-table-column prop="timestamp" label="时间" width="180" sortable>
          <template #default="{ row }">
            {{ formatDateTime(row.timestamp) }}
          </template>
        </el-table-column>

        <el-table-column prop="username" label="用户" width="120" />

        <el-table-column prop="action" label="操作" width="100">
          <template #default="{ row }">
            <el-tag :type="getActionType(row.action)">
              {{ getActionLabel(row.action) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="model_name" label="模块" width="120" />

        <el-table-column prop="object_repr" label="对象描述" />

        <el-table-column prop="ip_address" label="IP地址" width="140" />

        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              link
              @click="viewDetails(row)"
            >
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- Details Dialog -->
    <el-dialog
      v-model="detailsVisible"
      title="审计日志详情"
      width="60%"
    >
      <el-descriptions :column="2" border v-if="currentLog">
        <el-descriptions-item label="时间">
          {{ formatDateTime(currentLog.timestamp) }}
        </el-descriptions-item>
        <el-descriptions-item label="用户">
          {{ currentLog.username }}
        </el-descriptions-item>
        <el-descriptions-item label="操作">
          {{ getActionLabel(currentLog.action) }}
        </el-descriptions-item>
        <el-descriptions-item label="模块">
          {{ currentLog.model_name }}
        </el-descriptions-item>
        <el-descriptions-item label="对象ID">
          {{ currentLog.object_id || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="IP地址">
          {{ currentLog.ip_address || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="用户代理" :span="2">
          {{ currentLog.user_agent || '-' }}
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="currentLog.changes" style="margin-top: 20px;">
        <h4>变更内容</h4>
        <pre class="changes-content">{{ JSON.stringify(currentLog.changes, null, 2) }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { getAuditLogs } from '@/api/core'
import { ElMessage } from 'element-plus'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/core/audit-logs/')


const loading = ref(false)
const auditLogs = ref<any[]>([])
const detailsVisible = ref(false)
const currentLog = ref(null)

const filters = reactive({
  action: '',
  model_name: '',
  start_date: '',
  end_date: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const actionLabels = {
  'CREATE': '创建',
  'UPDATE': '更新',
  'DELETE': '删除',
  'LOGIN': '登录',
  'LOGOUT': '登出',
  'APPROVE': '审批',
  'REJECT': '拒绝'
}

const getActionLabel = (action) => {
  return actionLabels[action] || action
}

const getActionType = (action) => {
  const types = {
    'CREATE': 'success',
    'UPDATE': 'info',
    'DELETE': 'danger',
    'LOGIN': 'success',
    'LOGOUT': 'info',
    'APPROVE': 'success',
    'REJECT': 'warning'
  }
  return types[action] || 'info'
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const loadAuditLogs = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters
    }

    // Convert dates to ISO format
    if (filters.start_date) {
      params.start_date = new Date(filters.start_date).toISOString()
    }
    if (filters.end_date) {
      params.end_date = new Date(filters.end_date).toISOString()
    }

    const response = await getAuditLogs(params)
    auditLogs.value = response.results || response || []
    pagination.total = response.count || auditLogs.value.length
  } catch (error) {
    ElMessage.error('加载审计日志失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const searchLogs = () => {
  pagination.page = 1
  loadAuditLogs()
}

const resetFilters = () => {
  filters.action = ''
  filters.model_name = ''
  filters.start_date = ''
  filters.end_date = ''
  searchLogs()
}

const refreshData = () => {
  loadAuditLogs()
}

const viewDetails = (log) => {
  currentLog.value = log
  detailsVisible.value = true
}

const handleSizeChange = (size) => {
  pagination.pageSize = size
  loadAuditLogs()
}

const handleCurrentChange = (page) => {
  pagination.page = page
  loadAuditLogs()
}

onMounted(() => {
  loadAuditLogs()
})
</script>

<style scoped>
.audit-log-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 18px;
  font-weight: bold;
}

.filter-form {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.changes-content {
  background: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 15px;
  max-height: 300px;
  overflow: auto;
  font-size: 12px;
}
</style>

