<template>
  <div class="monitor-container">
    <el-row :gutter="16">
      <!-- 系统状态卡片 -->
      <el-col :span="6">
        <el-card shadow="hover" class="status-card" :class="systemHealth.status === 'healthy' ? 'healthy' : 'warning'">
          <div class="status-icon">
            <el-icon :size="48"><Monitor /></el-icon>
          </div>
          <div class="status-info">
            <div class="status-value">{{ systemHealth.status === 'healthy' ? '正常' : '异常' }}</div>
            <div class="status-label">系统状态</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="status-card">
          <div class="status-icon">
            <el-icon :size="48" color="#67c23a"><CircleCheck /></el-icon>
          </div>
          <div class="status-info">
            <div class="status-value">{{ systemHealth.uptime || '-' }}</div>
            <div class="status-label">运行时间</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="status-card">
          <div class="status-icon">
            <el-icon :size="48" color="#409eff"><User /></el-icon>
          </div>
          <div class="status-info">
            <div class="status-value">{{ systemStatus.active_users || 0 }}</div>
            <div class="status-label">活跃用户</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="status-card">
          <div class="status-icon">
            <el-icon :size="48" color="#e6a23c"><Tickets /></el-icon>
          </div>
          <div class="status-info">
            <div class="status-value">{{ systemStatus.pending_tasks || 0 }}</div>
            <div class="status-label">待处理任务</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 服务状态 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>服务状态</span>
          <el-button type="primary" size="small" @click="refreshStatus" :loading="loading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>
      
      <el-table :data="services" stripe>
        <el-table-column prop="name" label="服务名称" width="200" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'running' ? 'success' : 'danger'">
              {{ row.status === 'running' ? '运行中' : '已停止' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="port" label="端口" width="100" />
        <el-table-column prop="memory" label="内存使用" width="120" />
        <el-table-column prop="cpu" label="CPU使用" width="100" />
        <el-table-column prop="last_check" label="最后检查" />
      </el-table>
    </el-card>

    <!-- 数据库统计 -->
    <el-row :gutter="16" style="margin-top: 20px">
      <el-col :span="12">
        <el-card>
          <template #header>数据统计</template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="项目数量">{{ dataStats.projects || 0 }}</el-descriptions-item>
            <el-descriptions-item label="客户数量">{{ dataStats.customers || 0 }}</el-descriptions-item>
            <el-descriptions-item label="供应商数量">{{ dataStats.suppliers || 0 }}</el-descriptions-item>
            <el-descriptions-item label="物料数量">{{ dataStats.items || 0 }}</el-descriptions-item>
            <el-descriptions-item label="采购订单">{{ dataStats.purchase_orders || 0 }}</el-descriptions-item>
            <el-descriptions-item label="销售订单">{{ dataStats.sales_orders || 0 }}</el-descriptions-item>
            <el-descriptions-item label="库存记录">{{ dataStats.stock_records || 0 }}</el-descriptions-item>
            <el-descriptions-item label="用户数量">{{ dataStats.users || 0 }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>安全状态</template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="今日登录次数">{{ securityStatus.login_count_today || 0 }}</el-descriptions-item>
            <el-descriptions-item label="登录失败次数">{{ securityStatus.failed_logins_today || 0 }}</el-descriptions-item>
            <el-descriptions-item label="活跃会话数">{{ securityStatus.active_sessions || 0 }}</el-descriptions-item>
            <el-descriptions-item label="最近敏感操作">{{ securityStatus.last_sensitive_operation || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近审计日志 -->
    <el-card style="margin-top: 20px">
      <template #header>最近操作日志</template>
      <el-table :data="recentLogs" stripe size="small">
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="user_detail.username" label="用户" width="120" />
        <el-table-column prop="action" label="操作" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="getActionType(row.action)">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="model_name" label="模块" width="120" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column prop="ip_address" label="IP地址" width="130" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { Monitor, CircleCheck, User, Tickets, Refresh } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const systemHealth = ref({})
const systemStatus = ref({})
const securityStatus = ref({})
const dataStats = ref({})
const recentLogs = ref([])

const services = ref([
  { name: 'Web服务 (Django)', status: 'running', port: '8000', memory: '-', cpu: '-', last_check: '-' },
  { name: '数据库 (PostgreSQL)', status: 'running', port: '5432', memory: '-', cpu: '-', last_check: '-' },
  { name: '缓存 (Redis)', status: 'running', port: '6379', memory: '-', cpu: '-', last_check: '-' },
  { name: '任务队列 (Celery)', status: 'running', port: '-', memory: '-', cpu: '-', last_check: '-' },
  { name: '搜索引擎 (Elasticsearch)', status: 'running', port: '9200', memory: '-', cpu: '-', last_check: '-' },
])

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getActionType = (action) => {
  const map = { CREATE: 'success', UPDATE: 'warning', DELETE: 'danger', LOGIN: 'primary' }
  return map[action] || 'info'
}

const fetchHealthStatus = async () => {
  try {
    const res = await request({ url: '/api/core/health/', method: 'get' })
    systemHealth.value = res.data
  } catch (error) {
    systemHealth.value = { status: 'error' }
  }
}

const fetchSystemStatus = async () => {
  try {
    const res = await request({ url: '/api/core/health/status/', method: 'get' })
    systemStatus.value = res.data
    dataStats.value = res.data.data_stats || {}
    
    // 更新服务状态
    if (res.data.services) {
      services.value = services.value.map(s => {
        const svcData = res.data.services[s.name.toLowerCase()] || {}
        return { ...s, ...svcData, last_check: new Date().toLocaleTimeString('zh-CN') }
      })
    }
  } catch (error) {
    console.error('获取系统状态失败', error)
  }
}

const fetchSecurityStatus = async () => {
  try {
    const res = await request({ url: '/api/core/health/security/', method: 'get' })
    securityStatus.value = res.data
  } catch (error) {
    console.error('获取安全状态失败', error)
  }
}

const fetchRecentLogs = async () => {
  try {
    const res = await request({ url: '/api/core/audit-logs/', method: 'get', params: { page_size: 10 } })
    recentLogs.value = res.results || res || []
  } catch (error) {
    console.error('获取日志失败', error)
  }
}

const refreshStatus = async () => {
  loading.value = true
  await Promise.all([
    fetchHealthStatus(),
    fetchSystemStatus(),
    fetchSecurityStatus(),
    fetchRecentLogs()
  ])
  loading.value = false
}

let refreshInterval

onMounted(() => {
  refreshStatus()
  // 每30秒自动刷新
  refreshInterval = setInterval(refreshStatus, 30000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<style scoped>
.monitor-container {
  padding: 20px;
}
.status-card {
  display: flex;
  align-items: center;
  padding: 20px;
}
.status-card.healthy {
  border-left: 4px solid #67c23a;
}
.status-card.warning {
  border-left: 4px solid #e6a23c;
}
.status-icon {
  margin-right: 20px;
}
.status-info {
  flex: 1;
}
.status-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}
.status-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
