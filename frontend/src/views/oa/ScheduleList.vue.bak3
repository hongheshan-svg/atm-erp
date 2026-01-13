<template>
  <div class="schedule-list">
    <el-card class="header-card">
      <div class="header-content">
        <h2>日程管理</h2>
        <div class="header-actions">
          <el-button type="primary" @click="showAddDialog">
            <el-icon><Plus /></el-icon> 新建日程
          </el-button>
        </div>
      </div>
    </el-card>

    <el-row :gutter="16">
      <!-- 日历视图 -->
      <el-col :span="18">
        <el-card>
          <div class="calendar-header">
            <el-button-group>
              <el-button @click="prevMonth"><el-icon><ArrowLeft /></el-icon></el-button>
              <el-button>{{ currentMonthLabel }}</el-button>
              <el-button @click="nextMonth"><el-icon><ArrowRight /></el-icon></el-button>
            </el-button-group>
            <el-button @click="goToday">今天</el-button>
          </div>
          
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
                  <div class="day-events">
                    <div 
                      v-for="event in day.events.slice(0, 2)" 
                      :key="event.id" 
                      class="event-item"
                      :style="{ backgroundColor: event.color }"
                      @click.stop="showDetail(event)"
                    >
                      {{ event.title }}
                    </div>
                    <div v-if="day.events.length > 2" class="more-events">
                      +{{ day.events.length - 2 }} 更多
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧日程列表 -->
      <el-col :span="6">
        <el-card>
          <template #header>
            <span>{{ selectedDate ? formatDate(selectedDate) : '今日' }}日程</span>
          </template>
          <div class="schedule-sidebar">
            <div v-if="selectedDayEvents.length === 0" class="no-events">
              暂无日程安排
            </div>
            <div v-else>
              <div 
                v-for="event in selectedDayEvents" 
                :key="event.id" 
                class="sidebar-event"
                @click="showDetail(event)"
              >
                <div class="event-time">
                  {{ event.all_day ? '全天' : formatTime(event.start_time) }}
                </div>
                <div class="event-info">
                  <div class="event-title">{{ event.title }}</div>
                  <div class="event-location" v-if="event.location">
                    <el-icon><Location /></el-icon> {{ event.location }}
                  </div>
                </div>
                <el-tag :type="getTypeColor(event.schedule_type)" size="small">
                  {{ event.type_display }}
                </el-tag>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 新建对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入日程标题" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="类型" prop="schedule_type">
              <el-select v-model="form.schedule_type" style="width: 100%">
                <el-option label="任务" value="TASK" />
                <el-option label="会议" value="MEETING" />
                <el-option label="提醒" value="REMINDER" />
                <el-option label="事件" value="EVENT" />
                <el-option label="个人" value="PERSONAL" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级">
              <el-select v-model="form.priority" style="width: 100%">
                <el-option label="紧急" value="URGENT" />
                <el-option label="高" value="HIGH" />
                <el-option label="普通" value="NORMAL" />
                <el-option label="低" value="LOW" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="全天">
          <el-switch v-model="form.all_day" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始时间" prop="start_time">
              <el-date-picker
                v-model="form.start_time"
                :type="form.all_day ? 'date' : 'datetime'"
                placeholder="开始时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束时间" prop="end_time">
              <el-date-picker
                v-model="form.end_time"
                :type="form.all_day ? 'date' : 'datetime'"
                placeholder="结束时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="地点">
          <el-input v-model="form.location" placeholder="地点（可选）" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="日程描述" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="form.color" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, ArrowLeft, ArrowRight, Location } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const schedules = ref([])
const currentDate = ref(new Date())
const selectedDate = ref(null)
const formRef = ref(null)

const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const form = reactive({
  id: null,
  title: '',
  schedule_type: 'TASK',
  priority: 'NORMAL',
  all_day: false,
  start_time: null,
  end_time: null,
  location: '',
  description: '',
  color: '#409EFF'
})

const rules = {
  title: [{ required: true, message: '请输入日程标题', trigger: 'blur' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  end_time: [{ required: true, message: '请选择结束时间', trigger: 'change' }]
}

const dialogTitle = computed(() => form.id ? '编辑日程' : '新建日程')

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
  
  // 上月日期
  const prevMonthLast = new Date(year, month, 0).getDate()
  for (let i = startOffset - 1; i >= 0; i--) {
    const day = prevMonthLast - i
    const date = new Date(year, month - 1, day).toISOString().split('T')[0]
    currentWeek.push({
      day,
      date,
      isCurrentMonth: false,
      isToday: false,
      events: getEventsForDate(date)
    })
  }
  
  // 当月日期
  const today = new Date().toISOString().split('T')[0]
  for (let i = 1; i <= totalDays; i++) {
    const date = new Date(year, month, i).toISOString().split('T')[0]
    currentWeek.push({
      day: i,
      date,
      isCurrentMonth: true,
      isToday: date === today,
      events: getEventsForDate(date)
    })
    
    if (currentWeek.length === 7) {
      weeks.push(currentWeek)
      currentWeek = []
    }
  }
  
  // 下月日期
  let nextDay = 1
  while (currentWeek.length < 7 && currentWeek.length > 0) {
    const date = new Date(year, month + 1, nextDay).toISOString().split('T')[0]
    currentWeek.push({
      day: nextDay++,
      date,
      isCurrentMonth: false,
      isToday: false,
      events: getEventsForDate(date)
    })
  }
  if (currentWeek.length > 0) {
    weeks.push(currentWeek)
  }
  
  return weeks
})

const selectedDayEvents = computed(() => {
  const date = selectedDate.value || new Date().toISOString().split('T')[0]
  return getEventsForDate(date)
})

const getEventsForDate = (date) => {
  return schedules.value.filter(s => {
    const start = s.start_time?.split('T')[0]
    const end = s.end_time?.split('T')[0]
    return start <= date && date <= end
  })
}

const loadData = async () => {
  loading.value = true
  try {
    const year = currentDate.value.getFullYear()
    const month = currentDate.value.getMonth()
    const start = new Date(year, month - 1, 1).toISOString()
    const end = new Date(year, month + 2, 0).toISOString()
    
    const res = await request.get('/core/schedules/calendar/', {
      params: { start, end }
    })
    schedules.value = res.data
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
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

const showAddDialog = () => {
  Object.assign(form, {
    id: null, title: '', schedule_type: 'TASK', priority: 'NORMAL',
    all_day: false, start_time: null, end_time: null,
    location: '', description: '', color: '#409EFF'
  })
  dialogVisible.value = true
}

const showDetail = (event) => {
  Object.assign(form, { ...event })
  dialogVisible.value = true
}

const handleSave = async () => {
  await formRef.value.validate()
  saving.value = true
  try {
    if (form.id) {
      await request.put(`/core/schedules/${form.id}/`, form)
      ElMessage.success('更新成功')
    } else {
      await request.post('/core/schedules/', form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    console.error(error)
  } finally {
    saving.value = false
  }
}

const getTypeColor = (type) => {
  const map = { TASK: '', MEETING: 'warning', REMINDER: 'info', EVENT: 'success', PERSONAL: 'danger' }
  return map[type] || ''
}

const formatDate = (dateStr) => {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const formatTime = (dateStr) => {
  return new Date(dateStr).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  selectedDate.value = new Date().toISOString().split('T')[0]
  loadData()
})
</script>

<style scoped>
.schedule-list {
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

.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
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
  transition: background-color 0.2s;
}

.day-cell:last-child {
  border-right: none;
}

.day-cell:hover {
  background: #f5f7fa;
}

.day-cell.other-month {
  background: #fafafa;
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

.event-item {
  font-size: 11px;
  padding: 2px 4px;
  margin-bottom: 2px;
  border-radius: 2px;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
}

.more-events {
  font-size: 11px;
  color: #909399;
}

.schedule-sidebar {
  max-height: 500px;
  overflow-y: auto;
}

.no-events {
  text-align: center;
  color: #909399;
  padding: 40px 0;
}

.sidebar-event {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid #ebeef5;
  cursor: pointer;
}

.sidebar-event:hover {
  background: #f5f7fa;
}

.event-time {
  font-size: 12px;
  color: #909399;
  width: 50px;
  flex-shrink: 0;
}

.event-info {
  flex: 1;
  min-width: 0;
}

.event-title {
  font-weight: 500;
  margin-bottom: 4px;
}

.event-location {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
