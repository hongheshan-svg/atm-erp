<template>
  <div class="notification-center">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">通知中心</span>
          <div>
            <el-button type="primary" @click="markAllRead" :disabled="unreadCount === 0">
              全部标记已读
            </el-button>
            <el-button @click="refreshData">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <!-- Filters -->
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="全部" name="all">
          <el-badge :value="unreadCount" :hidden="unreadCount === 0" class="badge">
          </el-badge>
        </el-tab-pane>
        <el-tab-pane label="未读" name="unread">
          <el-badge :value="unreadCount" :hidden="unreadCount === 0">
          </el-badge>
        </el-tab-pane>
        <el-tab-pane label="已读" name="read" />
      </el-tabs>

      <!-- Notification List -->
      <div v-loading="loading" class="notification-list">
        <el-empty v-if="notifications.length === 0" description="暂无通知" />
        
        <div
          v-for="notification in notifications"
          :key="notification.id"
          :class="['notification-item', { 'is-read': notification.is_read }]"
          @click="handleNotificationClick(notification)"
        >
          <div class="notification-icon">
            <el-icon :color="getNotificationColor(notification.type)" :size="32">
              <component :is="getNotificationIcon(notification.type)" />
            </el-icon>
          </div>
          
          <div class="notification-content">
            <div class="notification-header">
              <span class="notification-title">{{ notification.title }}</span>
              <el-tag :type="getNotificationType(notification.type)" size="small">
                {{ notification.type }}
              </el-tag>
            </div>
            <div class="notification-message">{{ notification.message }}</div>
            <div class="notification-time">
              {{ formatDateTime(notification.created_at) }}
            </div>
          </div>

          <div class="notification-actions">
            <el-button
              v-if="!notification.is_read"
              type="primary"
              size="small"
              @click.stop="markAsRead(notification.id)"
            >
              标记已读
            </el-button>
            <el-icon v-else class="read-icon" color="#67C23A">
              <Check />
            </el-icon>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div class="pagination" v-if="pagination.total > pagination.pageSize">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { 
  Refresh, Check, InfoFilled, WarningFilled, 
  CircleCheckFilled, CircleCloseFilled 
} from '@element-plus/icons-vue'
import { getNotifications, getUnreadCount, markNotificationRead, markAllNotificationsRead } from '@/api/core'
import { ElMessage, ElNotification } from 'element-plus'

const loading = ref(false)
const notifications = ref([])
const activeTab = ref('all')
const unreadCount = ref(0)
const wsConnection = ref(null)
const wsConnected = ref(false)

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const getNotificationType = (type) => {
  const types = {
    'INFO': 'info',
    'WARNING': 'warning',
    'ERROR': 'danger',
    'SUCCESS': 'success'
  }
  return types[type] || 'info'
}

const getNotificationColor = (type) => {
  const colors = {
    'INFO': '#409EFF',
    'WARNING': '#E6A23C',
    'ERROR': '#F56C6C',
    'SUCCESS': '#67C23A'
  }
  return colors[type] || '#909399'
}

const getNotificationIcon = (type) => {
  const icons = {
    'INFO': InfoFilled,
    'WARNING': WarningFilled,
    'ERROR': CircleCloseFilled,
    'SUCCESS': CircleCheckFilled
  }
  return icons[type] || InfoFilled
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  
  // Less than 1 minute
  if (diff < 60000) {
    return '刚刚'
  }
  // Less than 1 hour
  if (diff < 3600000) {
    return `${Math.floor(diff / 60000)}分钟前`
  }
  // Less than 1 day
  if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)}小时前`
  }
  // Less than 7 days
  if (diff < 604800000) {
    return `${Math.floor(diff / 86400000)}天前`
  }
  
  return date.toLocaleString('zh-CN')
}

const loadNotifications = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }

    // Filter by read status
    if (activeTab.value === 'unread') {
      params.is_read = false
    } else if (activeTab.value === 'read') {
      params.is_read = true
    }

    const response = await getNotifications(params)
    notifications.value = response.results || response || []
    pagination.total = response.count || notifications.value.length
    
    // Get unread count
    await loadUnreadCount()
  } catch (error) {
    ElMessage.error('加载通知失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const loadUnreadCount = async () => {
  try {
    const response = await getUnreadCount()
    unreadCount.value = response.count
  } catch (error) {
    console.error('获取未读数量失败', error)
  }
}

const markAsRead = async (id) => {
  try {
    await markNotificationRead(id)
    ElMessage.success('已标记为已读')
    loadNotifications()
  } catch (error) {
    ElMessage.error('操作失败')
    console.error(error)
  }
}

const markAllRead = async () => {
  try {
    await markAllNotificationsRead()
    ElMessage.success('已全部标记为已读')
    loadNotifications()
  } catch (error) {
    ElMessage.error('操作失败')
    console.error(error)
  }
}

const handleNotificationClick = (notification) => {
  if (!notification.is_read) {
    markAsRead(notification.id)
  }
}

const handleTabChange = () => {
  pagination.page = 1
  loadNotifications()
}

const refreshData = () => {
  loadNotifications()
}

const handleSizeChange = (size) => {
  pagination.pageSize = size
  loadNotifications()
}

const handleCurrentChange = (page) => {
  pagination.page = page
  loadNotifications()
}

// WebSocket connection for real-time notifications
const connectWebSocket = () => {
  const token = localStorage.getItem('access_token')
  if (!token) return
  
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${wsProtocol}//${window.location.host}/ws/notifications/?token=${token}`
  
  try {
    wsConnection.value = new WebSocket(wsUrl)
    
    wsConnection.value.onopen = () => {
      wsConnected.value = true
    }
    
    wsConnection.value.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'notification') {
        // Show desktop notification
        ElNotification({
          title: data.data.title,
          message: data.data.message,
          type: getNotificationType(data.data.type),
          duration: 5000
        })
        // Refresh list
        loadNotifications()
      }
    }
    
    wsConnection.value.onclose = () => {
      wsConnected.value = false
      // Reconnect after 5 seconds
      setTimeout(connectWebSocket, 5000)
    }
    
    wsConnection.value.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  } catch (error) {
    console.error('WebSocket connection failed:', error)
  }
}

const disconnectWebSocket = () => {
  if (wsConnection.value) {
    wsConnection.value.close()
    wsConnection.value = null
  }
}

onMounted(() => {
  loadNotifications()
  connectWebSocket()
})

onUnmounted(() => {
  disconnectWebSocket()
})
</script>

<style scoped>
.notification-center {
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

.notification-list {
  min-height: 400px;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  padding: 20px;
  border-bottom: 1px solid #EBEEF5;
  cursor: pointer;
  transition: background-color 0.3s;
}

.notification-item:hover {
  background-color: #F5F7FA;
}

.notification-item.is-read {
  opacity: 0.6;
}

.notification-icon {
  margin-right: 15px;
  flex-shrink: 0;
}

.notification-content {
  flex: 1;
  min-width: 0;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.notification-title {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.notification-message {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
  line-height: 1.5;
}

.notification-time {
  font-size: 12px;
  color: #909399;
}

.notification-actions {
  margin-left: 15px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.read-icon {
  font-size: 24px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.badge {
  position: relative;
}
</style>

