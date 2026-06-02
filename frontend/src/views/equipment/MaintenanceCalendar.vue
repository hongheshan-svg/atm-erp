<template>
  <div class="maintenance-calendar">
    <el-card class="header-card">
      <div class="header-content">
        <h2>设备维护日历</h2>
        <div class="header-actions">
          <el-button-group>
            <el-button @click="prevMonth"><el-icon><ArrowLeft /></el-icon></el-button>
            <el-button>{{ currentMonthLabel }}</el-button>
            <el-button @click="nextMonth"><el-icon><ArrowRight /></el-icon></el-button>
          </el-button-group>
          <el-button @click="goToday">今天</el-button>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col :span="18">
        <el-card>
          <div class="calendar-grid">
            <div class="weekday-header">
              <div v-for="day in weekDays" :key="day" class="weekday-cell">{{ day }}</div>
            </div>
            <div class="calendar-body">
              <div v-for="(week, wIndex) in calendarDays" :key="wIndex" class="week-row">
                <div 
                  v-for="(day, dIndex) in week" 
                  :key="dIndex" 
                  class="day-cell"
                  :class="{ 
                    'other-month': !day.isCurrentMonth,
                    'today': day.isToday,
                    'selected': day.date === selectedDate
                  }"
                  @click="selectDate(day)"
                >
                  <div class="day-number">{{ day.day }}</div>
                  <div class="maintenance-items">
                    <div 
                      v-for="item in day.maintenances.slice(0, 2)" 
                      :key="item.id" 
                      class="maintenance-item"
                      :class="item.type"
                    >
                      {{ item.equipment_name }}
                    </div>
                    <div v-if="day.maintenances.length > 2" class="more-items">
                      +{{ day.maintenances.length - 2 }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card>
          <template #header>
            <span>{{ selectedDate ? formatDate(selectedDate) : '今日' }}维护计划</span>
          </template>
          <div class="day-details">
            <div v-if="selectedDayMaintenances.length === 0" class="no-items">
              暂无维护安排
            </div>
            <div v-else>
              <div v-for="item in selectedDayMaintenances" :key="item.id" class="detail-item">
                <div class="detail-header">
                  <el-tag :type="getTypeColor(item.maintenance_type)" size="small">
                    {{ getTypeName(item.maintenance_type) }}
                  </el-tag>
                  <el-tag :type="getStatusColor(item.status)" size="small">
                    {{ getStatusName(item.status) }}
                  </el-tag>
                </div>
                <div class="detail-equipment">{{ item.equipment_name }}</div>
                <div class="detail-info">{{ item.description }}</div>
              </div>
            </div>
          </div>
        </el-card>

        <el-card style="margin-top: 16px;">
          <template #header>统计</template>
          <div class="statistics">
            <div class="stat-item">
              <span>本月计划</span>
              <strong>{{ statistics.total || 0 }}</strong>
            </div>
            <div class="stat-item">
              <span>已完成</span>
              <strong class="success">{{ statistics.completed || 0 }}</strong>
            </div>
            <div class="stat-item">
              <span>待执行</span>
              <strong class="warning">{{ statistics.pending || 0 }}</strong>
            </div>
            <div class="stat-item">
              <span>已逾期</span>
              <strong class="danger">{{ statistics.overdue || 0 }}</strong>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { getMaintenanceCalendar } from '@/api/equipment'

const maintenances = ref<any[]>([])
const statistics = ref<Record<string, any>>({})
const currentDate = ref(new Date())
const selectedDate = ref(null)
const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const currentMonthLabel = computed(() => {
  const d = currentDate.value
  return `${d.getFullYear()}年${d.getMonth() + 1}月`
})

const calendarDays = computed(() => {
  const year = currentDate.value.getFullYear()
  const month = currentDate.value.getMonth()
  
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  
  const startOffset = firstDay.getDay()
  const totalDays = lastDay.getDate()
  
  const weeks = []
  let currentWeek = []
  
  const prevMonthLast = new Date(year, month, 0).getDate()
  for (let i = startOffset - 1; i >= 0; i--) {
    const day = prevMonthLast - i
    const date = new Date(year, month - 1, day).toISOString().split('T')[0]
    currentWeek.push({
      day,
      date,
      isCurrentMonth: false,
      isToday: false,
      maintenances: getMaintenancesForDate(date)
    })
  }
  
  const today = new Date().toISOString().split('T')[0]
  for (let i = 1; i <= totalDays; i++) {
    const date = new Date(year, month, i).toISOString().split('T')[0]
    currentWeek.push({
      day: i,
      date,
      isCurrentMonth: true,
      isToday: date === today,
      maintenances: getMaintenancesForDate(date)
    })
    
    if (currentWeek.length === 7) {
      weeks.push(currentWeek)
      currentWeek = []
    }
  }
  
  let nextDay = 1
  while (currentWeek.length < 7 && currentWeek.length > 0) {
    const date = new Date(year, month + 1, nextDay).toISOString().split('T')[0]
    currentWeek.push({
      day: nextDay++,
      date,
      isCurrentMonth: false,
      isToday: false,
      maintenances: getMaintenancesForDate(date)
    })
  }
  if (currentWeek.length > 0) {
    weeks.push(currentWeek)
  }
  
  return weeks
})

const selectedDayMaintenances = computed(() => {
  const date = selectedDate.value || new Date().toISOString().split('T')[0]
  return getMaintenancesForDate(date)
})

const getMaintenancesForDate = (dateStr) => {
  return maintenances.value.filter(m => m.date === dateStr)
}

const loadData = async () => {
  try {
    const year = currentDate.value.getFullYear()
    const month = currentDate.value.getMonth() + 1
    
    const res = await getMaintenanceCalendar({ year, month })
    maintenances.value = res.events || []
    statistics.value = res.summary || {}
  } catch (error) {
    console.error(error)
  }
}

const prevMonth = () => {
  currentDate.value = new Date(currentDate.value.getFullYear(), currentDate.value.getMonth() - 1, 1)
  loadData()
}

const nextMonth = () => {
  currentDate.value = new Date(currentDate.value.getFullYear(), currentDate.value.getMonth() + 1, 1)
  loadData()
}

const goToday = () => {
  currentDate.value = new Date()
  selectedDate.value = new Date().toISOString().split('T')[0]
  loadData()
}

const selectDate = (day) => {
  selectedDate.value = day.date
}

const formatDate = (dateStr) => {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const getTypeColor = (type) => {
  const map = { ROUTINE: 'info', REPAIR: 'warning', CALIBRATION: 'primary', OVERHAUL: 'danger' }
  return map[type] || 'info'
}

const getTypeName = (type) => {
  const map = { ROUTINE: '日常保养', REPAIR: '维修', CALIBRATION: '校准', OVERHAUL: '大修' }
  return map[type] || type
}

const getStatusColor = (status) => {
  const map = { PENDING: 'info', IN_PROGRESS: 'warning', COMPLETED: 'success', OVERDUE: 'danger' }
  return map[status] || 'info'
}

const getStatusName = (status) => {
  const map = { PENDING: '待执行', IN_PROGRESS: '进行中', COMPLETED: '已完成', OVERDUE: '已逾期' }
  return map[status] || status
}

onMounted(() => {
  selectedDate.value = new Date().toISOString().split('T')[0]
  loadData()
})
</script>

<style scoped>
.maintenance-calendar {
  padding: 0;
}

.header-card {
  margin-bottom: 16px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content h2 {
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 16px;
}

.weekday-header {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  background: #f5f7fa;
  border-radius: 4px;
}

.weekday-cell {
  padding: 12px;
  text-align: center;
  font-weight: bold;
  color: #606266;
}

.calendar-body {
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.week-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  border-bottom: 1px solid #ebeef5;
}

.week-row:last-child {
  border-bottom: none;
}

.day-cell {
  min-height: 100px;
  padding: 8px;
  border-right: 1px solid #ebeef5;
  cursor: pointer;
}

.day-cell:last-child {
  border-right: none;
}

.day-cell:hover {
  background: #f5f7fa;
}

.day-cell.other-month .day-number {
  color: #c0c4cc;
}

.day-cell.today {
  background: #ecf5ff;
}

.day-cell.today .day-number {
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.day-cell.selected {
  background: #e6f7ff;
}

.day-number {
  font-size: 14px;
  margin-bottom: 4px;
}

.maintenance-item {
  font-size: 11px;
  padding: 2px 4px;
  margin-bottom: 2px;
  border-radius: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.maintenance-item.ROUTINE {
  background: #f4f4f5;
  color: #909399;
}

.maintenance-item.REPAIR {
  background: #fdf6ec;
  color: #e6a23c;
}

.maintenance-item.CALIBRATION {
  background: #ecf5ff;
  color: #409eff;
}

.more-items {
  font-size: 11px;
  color: #909399;
}

.day-details {
  max-height: 300px;
  overflow-y: auto;
}

.no-items {
  text-align: center;
  color: #909399;
  padding: 40px 0;
}

.detail-item {
  padding: 12px;
  border-bottom: 1px solid #ebeef5;
}

.detail-header {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.detail-equipment {
  font-weight: 500;
  margin-bottom: 4px;
}

.detail-info {
  font-size: 12px;
  color: #909399;
}

.statistics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.stat-item strong {
  color: #303133;
}

.stat-item .success {
  color: #67c23a;
}

.stat-item .warning {
  color: #e6a23c;
}

.stat-item .danger {
  color: #f56c6c;
}
</style>
