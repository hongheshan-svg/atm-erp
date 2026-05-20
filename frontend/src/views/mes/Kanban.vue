<template>
  <div class="kanban-container">
    <div class="page-header">
      <h2>生产看板</h2>
      <div class="header-actions">
        <span class="update-time">更新时间: {{ updateTime }}</span>
        <el-button type="primary" @click="refreshData" :loading="loading">刷新</el-button>
        <el-switch v-model="autoRefresh" active-text="自动刷新" @change="toggleAutoRefresh" />
      </div>
    </div>
    
    <!-- 生产概况 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card total">
          <div class="stat-icon">
            <el-icon :size="32"><Calendar /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ production.total_schedules || 0 }}</div>
            <div class="stat-label">今日排程</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card progress">
          <div class="stat-icon">
            <el-icon :size="32"><VideoPlay /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ production.in_progress || 0 }}</div>
            <div class="stat-label">进行中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card completed">
          <div class="stat-icon">
            <el-icon :size="32"><CircleCheck /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ production.completed_today || 0 }}</div>
            <div class="stat-label">今日完成</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card delayed">
          <div class="stat-icon">
            <el-icon :size="32"><WarningFilled /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ production.delayed || 0 }}</div>
            <div class="stat-label">延期任务</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="16">
      <!-- 项目进度 -->
      <el-col :span="12">
        <el-card shadow="never" header="项目进度" class="chart-card">
          <div v-if="projects.length === 0" class="empty-tip">暂无进行中的项目</div>
          <div v-else class="project-list">
            <div v-for="project in projects" :key="project.id" class="project-item">
              <div class="project-info">
                <div class="project-name">{{ project.name }}</div>
                <div class="project-code">{{ project.code }}</div>
              </div>
              <div class="project-progress">
                <el-progress 
                  :percentage="project.progress" 
                  :stroke-width="10"
                  :color="getProgressColor(project.progress)"
                />
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <!-- 工作中心负载 -->
      <el-col :span="12">
        <el-card shadow="never" header="工作中心负载" class="chart-card">
          <div v-if="workCenters.length === 0" class="empty-tip">暂无工作中心数据</div>
          <div v-else class="workcenter-list">
            <div v-for="wc in workCenters" :key="wc.id" class="workcenter-item">
              <div class="wc-info">
                <span class="wc-name">{{ wc.name }}</span>
                <span class="wc-code">{{ wc.code }}</span>
              </div>
              <div class="wc-load">
                <el-progress 
                  :percentage="Math.min(100, wc.load_rate)" 
                  :stroke-width="12"
                  :color="getLoadColor(wc.load_rate)"
                  :format="() => `${wc.load_rate}%`"
                />
              </div>
              <div class="wc-hours">
                {{ toFixedSafe(wc.scheduled_hours, 1, '0.0') }}h / {{ toFixedSafe(wc.capacity, 1, '0.0') }}h
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="16" style="margin-top: 16px">
      <!-- 今日排程列表 -->
      <el-col :span="16">
        <el-card shadow="never" header="今日排程" class="schedule-card">
          <el-table :data="todaySchedules" size="small" stripe border>
            <el-table-column prop="schedule_no" label="排程编号" width="120" />
            <el-table-column prop="project_name" label="项目" min-width="150" show-overflow-tooltip />
            <el-table-column prop="work_center" label="工作中心" width="120" />
            <el-table-column label="计划时间" width="130">
              <template #default="{ row }">
                {{ row.planned_start }} - {{ row.planned_end }}
              </template>
            </el-table-column>
            <el-table-column prop="assignee" label="负责人" width="100" />
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      
      <!-- 质量概况 -->
      <el-col :span="8">
        <el-card shadow="never" header="质量概况" class="quality-card">
          <div class="quality-item">
            <div class="quality-label">今日检验数</div>
            <div class="quality-value">{{ quality.inspections_today || 0 }}</div>
          </div>
          <div class="quality-item success">
            <div class="quality-label">合格率</div>
            <div class="quality-value">{{ quality.pass_rate || 0 }}%</div>
          </div>
          <div class="quality-item warning">
            <div class="quality-label">今日缺陷</div>
            <div class="quality-value">{{ quality.defects_today || 0 }}</div>
          </div>
        </el-card>
        
        <el-card shadow="never" header="系统时间" style="margin-top: 16px" class="time-card">
          <div class="current-time">{{ currentTime }}</div>
          <div class="current-date">{{ currentDate }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Calendar, VideoPlay, CircleCheck, WarningFilled } from '@element-plus/icons-vue'
import { getKanbanData } from '@/api/mes'
import { toFixedSafe } from '@/utils/number'

const loading = ref(false)
const autoRefresh = ref(true)
const updateTime = ref('')
const currentTime = ref('')
const currentDate = ref('')

let refreshTimer = null
let clockTimer = null

const production = ref({})
const projects = ref([])
const workCenters = ref([])
const quality = ref({})
const todaySchedules = ref([])

const refreshData = async () => {
  loading.value = true
  try {
    const data = await getKanbanData()
    production.value = data.production || {}
    projects.value = data.projects || []
    workCenters.value = data.work_centers || []
    quality.value = data.quality || {}
    todaySchedules.value = data.today_schedules || []
    updateTime.value = new Date().toLocaleTimeString()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const toggleAutoRefresh = (val) => {
  if (val) {
    refreshTimer = setInterval(refreshData, 30000)
  } else {
    clearInterval(refreshTimer)
  }
}

const updateClock = () => {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false })
  currentDate.value = now.toLocaleDateString('zh-CN', { 
    year: 'numeric', 
    month: 'long', 
    day: 'numeric',
    weekday: 'long'
  })
}

const getProgressColor = (progress) => {
  if (progress >= 80) return '#67c23a'
  if (progress >= 50) return '#409eff'
  if (progress >= 30) return '#e6a23c'
  return '#f56c6c'
}

const getLoadColor = (load) => {
  if (load >= 90) return '#f56c6c'
  if (load >= 70) return '#e6a23c'
  return '#67c23a'
}

const getStatusType = (status) => {
  const types = {
    DRAFT: 'info',
    CONFIRMED: '',
    RELEASED: 'warning',
    IN_PROGRESS: 'success',
    COMPLETED: 'success',
    CANCELLED: 'info'
  }
  return types[status] || ''
}

const getStatusText = (status) => {
  const texts = {
    DRAFT: '草稿',
    CONFIRMED: '已确认',
    RELEASED: '已下达',
    IN_PROGRESS: '进行中',
    COMPLETED: '已完成',
    CANCELLED: '已取消'
  }
  return texts[status] || status
}

onMounted(() => {
  refreshData()
  updateClock()
  
  if (autoRefresh.value) {
    refreshTimer = setInterval(refreshData, 30000)
  }
  clockTimer = setInterval(updateClock, 1000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
  clearInterval(clockTimer)
})
</script>

<style scoped>
.kanban-container {
  padding: 0;
  background: linear-gradient(135deg, #1a1f36 0%, #0d1117 100%);
  min-height: calc(100vh - 140px);
  color: #fff;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  color: #fff;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.update-time {
  font-size: 12px;
  color: rgba(255,255,255,0.6);
}

.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  display: flex;
  align-items: center;
  padding: 20px;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  width: 100%;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
  background: rgba(64, 158, 255, 0.2);
  color: #409eff;
}

.stat-card.progress .stat-icon {
  background: rgba(103, 194, 58, 0.2);
  color: #67c23a;
}

.stat-card.completed .stat-icon {
  background: rgba(64, 158, 255, 0.2);
  color: #409eff;
}

.stat-card.delayed .stat-icon {
  background: rgba(245, 108, 108, 0.2);
  color: #f56c6c;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #fff;
}

.stat-label {
  font-size: 14px;
  color: rgba(255,255,255,0.6);
}

.chart-card, .schedule-card, .quality-card, .time-card {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
}

.chart-card :deep(.el-card__header),
.schedule-card :deep(.el-card__header),
.quality-card :deep(.el-card__header),
.time-card :deep(.el-card__header) {
  color: #fff;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.empty-tip {
  text-align: center;
  color: rgba(255,255,255,0.4);
  padding: 40px 0;
}

.project-list {
  max-height: 300px;
  overflow-y: auto;
}

.project-item {
  display: flex;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.project-info {
  width: 40%;
}

.project-name {
  font-size: 14px;
  color: #fff;
}

.project-code {
  font-size: 12px;
  color: rgba(255,255,255,0.5);
}

.project-progress {
  flex: 1;
}

.workcenter-list {
  max-height: 300px;
  overflow-y: auto;
}

.workcenter-item {
  display: flex;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.wc-info {
  width: 30%;
}

.wc-name {
  display: block;
  color: #fff;
  font-size: 14px;
}

.wc-code {
  font-size: 12px;
  color: rgba(255,255,255,0.5);
}

.wc-load {
  flex: 1;
  padding: 0 16px;
}

.wc-hours {
  font-size: 12px;
  color: rgba(255,255,255,0.6);
  width: 100px;
  text-align: right;
}

.quality-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.quality-label {
  color: rgba(255,255,255,0.7);
}

.quality-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.quality-item.success .quality-value {
  color: #67c23a;
}

.quality-item.warning .quality-value {
  color: #e6a23c;
}

.time-card {
  text-align: center;
}

.current-time {
  font-size: 48px;
  font-weight: bold;
  color: #409eff;
  font-family: 'Courier New', monospace;
}

.current-date {
  font-size: 14px;
  color: rgba(255,255,255,0.6);
  margin-top: 8px;
}

/* 表格深色主题 */
.schedule-card :deep(.el-table) {
  background: transparent;
  color: #fff;
}

.schedule-card :deep(.el-table tr) {
  background: transparent;
}

.schedule-card :deep(.el-table--striped .el-table__body tr.el-table__row--striped td) {
  background: rgba(255,255,255,0.03);
}

.schedule-card :deep(.el-table td, .el-table th) {
  border-color: rgba(255,255,255,0.1);
}

.schedule-card :deep(.el-table th) {
  background: rgba(255,255,255,0.05);
  color: rgba(255,255,255,0.8);
}

.schedule-card :deep(.el-table--border) {
  border-color: rgba(255,255,255,0.1);
}
</style>
