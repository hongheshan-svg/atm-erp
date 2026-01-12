<template>
  <div class="schedule-container">
    <div class="page-header">
      <h2>日程管理</h2>
      <el-button type="primary" @click="handleAdd">新建日程</el-button>
    </div>
    
    <el-row :gutter="16">
      <!-- 日历视图 -->
      <el-col :span="18">
        <el-card shadow="never">
          <template #header>
            <div class="calendar-header">
              <el-button-group>
                <el-button @click="changeMonth(-1)">上月</el-button>
                <el-button @click="goToday">今天</el-button>
                <el-button @click="changeMonth(1)">下月</el-button>
              </el-button-group>
              <span class="current-month">{{ currentMonthText }}</span>
            </div>
          </template>
          
          <div class="calendar">
            <div class="calendar-week">
              <div class="calendar-day-name" v-for="name in weekDays" :key="name">{{ name }}</div>
            </div>
            <div class="calendar-days">
              <div 
                v-for="day in calendarDays" 
                :key="day.date" 
                class="calendar-day"
                :class="{ 
                  'other-month': !day.currentMonth, 
                  'today': day.isToday,
                  'has-events': day.events.length > 0
                }"
                @click="handleDayClick(day)"
              >
                <div class="day-number">{{ day.day }}</div>
                <div class="day-events">
                  <div 
                    v-for="event in day.events.slice(0, 3)" 
                    :key="event.id"
                    class="event-dot"
                    :style="{ backgroundColor: event.color }"
                    :title="event.title"
                  ></div>
                  <div v-if="day.events.length > 3" class="event-more">+{{ day.events.length - 3 }}</div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <!-- 侧边栏 -->
      <el-col :span="6">
        <el-card shadow="never" header="今日日程">
          <div v-if="todaySchedules.length === 0" class="empty-tip">今日暂无日程</div>
          <div v-else class="today-list">
            <div 
              v-for="item in todaySchedules" 
              :key="item.id" 
              class="today-item"
              @click="handleView(item)"
            >
              <div class="item-time">
                {{ item.all_day ? '全天' : formatTime(item.start_time) }}
              </div>
              <div class="item-content">
                <div class="item-title">{{ item.title }}</div>
                <div class="item-location" v-if="item.location">{{ item.location }}</div>
              </div>
              <div class="item-color" :style="{ backgroundColor: item.color }"></div>
            </div>
          </div>
        </el-card>
        
        <el-card shadow="never" header="即将到来" style="margin-top: 16px">
          <div v-if="upcomingSchedules.length === 0" class="empty-tip">暂无即将到来的日程</div>
          <div v-else class="upcoming-list">
            <div 
              v-for="item in upcomingSchedules" 
              :key="item.id" 
              class="upcoming-item"
              @click="handleView(item)"
            >
              <div class="item-date">{{ formatDate(item.start_time) }}</div>
              <div class="item-title">{{ item.title }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 新建日程对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑日程' : '新建日程'" width="600px">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="formData.title" placeholder="日程标题" />
        </el-form-item>
        <el-form-item label="类型" prop="schedule_type">
          <el-select v-model="formData.schedule_type" style="width: 100%">
            <el-option label="会议" value="MEETING" />
            <el-option label="任务" value="TASK" />
            <el-option label="提醒" value="REMINDER" />
            <el-option label="拜访" value="VISIT" />
            <el-option label="电话" value="CALL" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="全天">
          <el-switch v-model="formData.all_day" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始时间" prop="start_time">
              <el-date-picker 
                v-model="formData.start_time" 
                :type="formData.all_day ? 'date' : 'datetime'"
                style="width: 100%" 
                value-format="YYYY-MM-DDTHH:mm:ss"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束时间" prop="end_time">
              <el-date-picker 
                v-model="formData.end_time" 
                :type="formData.all_day ? 'date' : 'datetime'"
                style="width: 100%" 
                value-format="YYYY-MM-DDTHH:mm:ss"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="地点">
          <el-input v-model="formData.location" placeholder="地点" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="formData.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="formData.color" />
        </el-form-item>
        <el-form-item label="公开">
          <el-switch v-model="formData.is_public" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 日期详情对话框 -->
    <el-dialog v-model="dayDialogVisible" :title="selectedDay?.date" width="500px">
      <div v-if="selectedDay?.events.length === 0" class="empty-tip">当日无日程</div>
      <div v-else>
        <div 
          v-for="event in selectedDay?.events" 
          :key="event.id" 
          class="day-event-item"
          @click="handleView(event)"
        >
          <div class="event-color" :style="{ backgroundColor: event.color }"></div>
          <div class="event-info">
            <div class="event-title">{{ event.title }}</div>
            <div class="event-time">
              {{ event.allDay ? '全天' : `${formatTime(event.start)} - ${formatTime(event.end)}` }}
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const weekDays = ['日', '一', '二', '三', '四', '五', '六']
const currentDate = ref(new Date())
const events = ref([])
const todaySchedules = ref([])
const upcomingSchedules = ref([])

const dialogVisible = ref(false)
const dayDialogVisible = ref(false)
const isEdit = ref(false)
const submitLoading = ref(false)
const formRef = ref(null)
const selectedDay = ref(null)

const formData = reactive({
  title: '',
  schedule_type: 'TASK',
  all_day: false,
  start_time: '',
  end_time: '',
  location: '',
  description: '',
  color: '#409EFF',
  is_public: false
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  end_time: [{ required: true, message: '请选择结束时间', trigger: 'change' }]
}

const currentMonthText = computed(() => {
  const year = currentDate.value.getFullYear()
  const month = currentDate.value.getMonth() + 1
  return `${year}年${month}月`
})

const calendarDays = computed(() => {
  const year = currentDate.value.getFullYear()
  const month = currentDate.value.getMonth()
  
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  
  const days = []
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  
  // 上月补齐
  const startDayOfWeek = firstDay.getDay()
  for (let i = startDayOfWeek - 1; i >= 0; i--) {
    const d = new Date(year, month, -i)
    days.push({
      date: d.toISOString().slice(0, 10),
      day: d.getDate(),
      currentMonth: false,
      isToday: d.getTime() === today.getTime(),
      events: getEventsForDate(d)
    })
  }
  
  // 本月
  for (let i = 1; i <= lastDay.getDate(); i++) {
    const d = new Date(year, month, i)
    days.push({
      date: d.toISOString().slice(0, 10),
      day: i,
      currentMonth: true,
      isToday: d.getTime() === today.getTime(),
      events: getEventsForDate(d)
    })
  }
  
  // 下月补齐
  const remaining = 42 - days.length
  for (let i = 1; i <= remaining; i++) {
    const d = new Date(year, month + 1, i)
    days.push({
      date: d.toISOString().slice(0, 10),
      day: i,
      currentMonth: false,
      isToday: d.getTime() === today.getTime(),
      events: getEventsForDate(d)
    })
  }
  
  return days
})

const getEventsForDate = (date) => {
  const dateStr = date.toISOString().slice(0, 10)
  return events.value.filter(e => {
    const start = e.start.slice(0, 10)
    const end = e.end.slice(0, 10)
    return dateStr >= start && dateStr <= end
  })
}

const fetchCalendar = async () => {
  const year = currentDate.value.getFullYear()
  const month = currentDate.value.getMonth()
  
  const start = new Date(year, month, 1).toISOString().slice(0, 10)
  const end = new Date(year, month + 2, 0).toISOString().slice(0, 10)
  
  try {
    const data = await request.get('/core/schedules/calendar/', {
      params: { start, end }
    })
    events.value = data || []
  } catch (e) {
    console.error(e)
  }
}

const fetchToday = async () => {
  try {
    const data = await request.get('/core/schedules/today/')
    todaySchedules.value = data || []
  } catch (e) {
    console.error(e)
  }
}

const fetchUpcoming = async () => {
  try {
    const data = await request.get('/core/schedules/upcoming/')
    upcomingSchedules.value = data || []
  } catch (e) {
    console.error(e)
  }
}

const changeMonth = (delta) => {
  const d = new Date(currentDate.value)
  d.setMonth(d.getMonth() + delta)
  currentDate.value = d
  fetchCalendar()
}

const goToday = () => {
  currentDate.value = new Date()
  fetchCalendar()
}

const handleDayClick = (day) => {
  selectedDay.value = day
  dayDialogVisible.value = true
}

const handleAdd = () => {
  isEdit.value = false
  const now = new Date()
  Object.assign(formData, {
    title: '',
    schedule_type: 'TASK',
    all_day: false,
    start_time: now.toISOString().slice(0, 16),
    end_time: new Date(now.getTime() + 3600000).toISOString().slice(0, 16),
    location: '',
    description: '',
    color: '#409EFF',
    is_public: false
  })
  dialogVisible.value = true
}

const handleView = async (item) => {
  try {
    const data = await request.get(`/core/schedules/${item.id}/`)
    Object.assign(formData, data)
    isEdit.value = true
    dialogVisible.value = true
    dayDialogVisible.value = false
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

const submitForm = async () => {
  const valid = await formRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await request.patch(`/core/schedules/${formData.id}/`, formData)
    } else {
      await request.post('/core/schedules/', formData)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    fetchCalendar()
    fetchToday()
    fetchUpcoming()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    submitLoading.value = false
  }
}

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  return dateStr.slice(11, 16)
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return dateStr.slice(5, 10).replace('-', '/')
}

onMounted(() => {
  fetchCalendar()
  fetchToday()
  fetchUpcoming()
})
</script>

<style scoped>
.schedule-container {
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

.calendar-header {
  display: flex;
  align-items: center;
  gap: 20px;
}

.current-month {
  font-size: 18px;
  font-weight: bold;
}

.calendar-week {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  border-bottom: 1px solid #ebeef5;
}

.calendar-day-name {
  padding: 10px;
  text-align: center;
  font-weight: bold;
  color: #606266;
}

.calendar-days {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
}

.calendar-day {
  min-height: 80px;
  padding: 8px;
  border: 1px solid #ebeef5;
  cursor: pointer;
  transition: background-color 0.2s;
}

.calendar-day:hover {
  background-color: #f5f7fa;
}

.calendar-day.other-month {
  background-color: #fafafa;
}

.calendar-day.other-month .day-number {
  color: #c0c4cc;
}

.calendar-day.today {
  background-color: #ecf5ff;
}

.calendar-day.today .day-number {
  color: #409eff;
  font-weight: bold;
}

.day-number {
  font-size: 14px;
  margin-bottom: 4px;
}

.day-events {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}

.event-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.event-more {
  font-size: 10px;
  color: #909399;
}

.empty-tip {
  text-align: center;
  color: #909399;
  padding: 20px 0;
}

.today-list, .upcoming-list {
  max-height: 300px;
  overflow-y: auto;
}

.today-item, .upcoming-item {
  display: flex;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
  cursor: pointer;
}

.today-item:hover, .upcoming-item:hover {
  background-color: #f5f7fa;
}

.item-time {
  width: 50px;
  font-size: 12px;
  color: #909399;
}

.item-content {
  flex: 1;
}

.item-title {
  font-size: 14px;
}

.item-location, .item-date {
  font-size: 12px;
  color: #909399;
}

.item-color {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.day-event-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-bottom: 1px solid #ebeef5;
  cursor: pointer;
}

.day-event-item:hover {
  background-color: #f5f7fa;
}

.event-color {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 12px;
}

.event-info {
  flex: 1;
}

.event-title {
  font-size: 14px;
  font-weight: 500;
}

.event-time {
  font-size: 12px;
  color: #909399;
}
</style>
