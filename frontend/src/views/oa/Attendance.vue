<template>
  <div class="attendance-page">
    <!-- 打卡卡片 -->
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card class="clock-card">
          <div class="current-time">
            <div class="time">{{ currentTime }}</div>
            <div class="date">{{ currentDate }}</div>
          </div>
          <div class="clock-status">
            <div class="status-item">
              <span class="label">签到时间:</span>
              <span class="value" :class="{ late: todayRecord?.late_minutes > 0 }">
                {{ todayRecord?.check_in_time ? formatTime(todayRecord.check_in_time) : '--:--' }}
                <el-tag v-if="todayRecord?.late_minutes > 0" type="danger" size="small">迟到{{ todayRecord.late_minutes }}分钟</el-tag>
              </span>
            </div>
            <div class="status-item">
              <span class="label">签退时间:</span>
              <span class="value" :class="{ early: todayRecord?.early_minutes > 0 }">
                {{ todayRecord?.check_out_time ? formatTime(todayRecord.check_out_time) : '--:--' }}
                <el-tag v-if="todayRecord?.early_minutes > 0" type="warning" size="small">早退{{ todayRecord.early_minutes }}分钟</el-tag>
              </span>
            </div>
          </div>
          <div class="clock-actions">
            <el-button 
              type="primary" 
              size="large" 
              :disabled="!!todayRecord?.check_in_time"
              @click="handleCheckIn"
              :loading="checking"
            >
              <el-icon><Clock /></el-icon>
              签到打卡
            </el-button>
            <el-button 
              type="success" 
              size="large"
              :disabled="!todayRecord?.check_in_time || !!todayRecord?.check_out_time"
              @click="handleCheckOut"
              :loading="checking"
            >
              <el-icon><CircleCheck /></el-icon>
              签退打卡
            </el-button>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card class="stats-card">
          <template #header>
            <span>本月考勤统计</span>
          </template>
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-value">{{ monthSummary.total_days || 0 }}</div>
              <div class="stat-label">出勤天数</div>
            </div>
            <div class="stat-item">
              <div class="stat-value text-danger">{{ monthSummary.late_days || 0 }}</div>
              <div class="stat-label">迟到</div>
            </div>
            <div class="stat-item">
              <div class="stat-value text-warning">{{ monthSummary.early_days || 0 }}</div>
              <div class="stat-label">早退</div>
            </div>
            <div class="stat-item">
              <div class="stat-value text-info">{{ monthSummary.leave_days || 0 }}</div>
              <div class="stat-label">请假</div>
            </div>
          </div>
          <el-divider />
          <div class="work-hours">
            <span>本月工时: <strong>{{ monthSummary.total_work_hours || 0 }}</strong> 小时</span>
            <span>加班: <strong>{{ monthSummary.total_overtime_hours || 0 }}</strong> 小时</span>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card class="quick-card">
          <template #header>
            <span>快捷申请</span>
          </template>
          <div class="quick-actions">
            <el-button type="primary" plain @click="$router.push('/oa/leave')">
              <el-icon><Document /></el-icon>
              请假申请
            </el-button>
            <el-button type="success" plain @click="$router.push('/oa/overtime')">
              <el-icon><Timer /></el-icon>
              加班申请
            </el-button>
            <el-button type="warning" plain @click="$router.push('/oa/vehicle-request')">
              <el-icon><Van /></el-icon>
              用车申请
            </el-button>
            <el-button type="info" plain @click="$router.push('/oa/asset-borrow')">
              <el-icon><Box /></el-icon>
              资产借用
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 考勤记录 -->
    <el-card style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>考勤记录</span>
          <el-date-picker
            v-model="selectedMonth"
            type="month"
            placeholder="选择月份"
            format="YYYY年MM月"
            value-format="YYYY-MM"
            @change="loadRecords"
          />
        </div>
      </template>
      
      <el-empty v-if="!loading && records.length === 0" description="本月暂无考勤记录，点击上方按钮开始打卡" />
      
      <el-table v-else :data="records" v-loading="loading" stripe border>
        <el-table-column prop="attendance_date" label="日期" width="120" />
        <el-table-column label="签到时间" width="100">
          <template #default="{ row }">
            {{ row.check_in_time ? formatTime(row.check_in_time) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="签退时间" width="100">
          <template #default="{ row }">
            {{ row.check_out_time ? formatTime(row.check_out_time) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="work_hours" label="工时" width="80" align="right">
          <template #default="{ row }">
            {{ row.work_hours }}h
          </template>
        </el-table-column>
        <el-table-column prop="late_minutes" label="迟到" width="80" align="center">
          <template #default="{ row }">
            <span v-if="row.late_minutes > 0" class="text-danger">{{ row.late_minutes }}分</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="early_minutes" label="早退" width="80" align="center">
          <template #default="{ row }">
            <span v-if="row.early_minutes > 0" class="text-warning">{{ row.early_minutes }}分</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="remarks" label="备注" min-width="150" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Clock, CircleCheck, Document, Timer, Van, Box } from '@element-plus/icons-vue'
import { getAttendanceToday, getAttendanceRecords, getAttendanceMonthlySummary, checkIn, checkOut } from '@/api/oa'

const loading = ref(false)
const checking = ref(false)
const records = ref([])
const todayRecord = ref(null)
const monthSummary = ref({})
const selectedMonth = ref(new Date().toISOString().slice(0, 7))
const currentTime = ref('')
const currentDate = ref('')

let timer = null

const updateTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  currentDate.value = now.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
}

const formatTime = (datetime) => {
  if (!datetime) return ''
  return new Date(datetime).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const getStatusType = (status) => {
  const types = {
    'NORMAL': 'success',
    'LATE': 'danger',
    'EARLY': 'warning',
    'ABSENT': 'danger',
    'LEAVE': 'info',
    'OVERTIME': 'primary',
    'TRAVEL': 'primary',
    'REMOTE': 'primary'
  }
  return types[status] || 'info'
}

const loadTodayStatus = async () => {
  try {
    const res = await getAttendanceToday()
    // res 已经是 response.data
    todayRecord.value = res
  } catch (error) {
    console.error('加载今日状态失败', error)
    // 设置默认值
    todayRecord.value = { check_in_time: null, check_out_time: null, status: 'NOT_CHECKED' }
  }
}

const loadRecords = async () => {
  loading.value = true
  try {
    const res = await getAttendanceRecords({
      params: { month: selectedMonth.value }
    })
    // res 已经是 response.data
    if (Array.isArray(res)) {
      records.value = res
    } else if (res && res.results) {
      records.value = res.results
    } else {
      records.value = []
    }
  } catch (error) {
    console.error('加载考勤记录失败', error)
    records.value = []
  } finally {
    loading.value = false
  }
}

const loadMonthlySummary = async () => {
  try {
    const res = await getAttendanceMonthlySummary({
      params: { month: selectedMonth.value }
    })
    // res 已经是 response.data
    if (Array.isArray(res) && res.length > 0) {
      monthSummary.value = res[0]
    } else if (res && typeof res === 'object' && !Array.isArray(res)) {
      monthSummary.value = res
    } else {
      monthSummary.value = {}
    }
  } catch (error) {
    console.error('加载月度统计失败', error)
    monthSummary.value = {}
  }
}

const handleCheckIn = async () => {
  checking.value = true
  try {
    const res = await checkIn({
      location: '办公室'
    })
    // res 已经是 response.data
    todayRecord.value = res
    ElMessage.success('签到成功')
    loadRecords()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '签到失败')
  } finally {
    checking.value = false
  }
}

const handleCheckOut = async () => {
  checking.value = true
  try {
    const res = await checkOut({
      location: '办公室'
    })
    // res 已经是 response.data
    todayRecord.value = res
    ElMessage.success('签退成功')
    loadRecords()
    loadMonthlySummary()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '签退失败')
  } finally {
    checking.value = false
  }
}

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  loadTodayStatus()
  loadRecords()
  loadMonthlySummary()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.attendance-page {
  padding: 20px;
}

.clock-card {
  text-align: center;
}

.current-time {
  margin-bottom: 20px;
}

.current-time .time {
  font-size: 48px;
  font-weight: bold;
  color: #409EFF;
  font-family: 'Courier New', monospace;
}

.current-time .date {
  font-size: 16px;
  color: #666;
  margin-top: 8px;
}

.clock-status {
  margin: 20px 0;
  text-align: left;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
}

.status-item .label {
  color: #666;
}

.status-item .value {
  font-weight: bold;
}

.status-item .value.late {
  color: #f56c6c;
}

.status-item .value.early {
  color: #e6a23c;
}

.clock-actions {
  display: flex;
  gap: 15px;
  justify-content: center;
}

.clock-actions .el-button {
  flex: 1;
}

.stats-card .stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 15px;
  text-align: center;
}

.stat-item .stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #409EFF;
}

.stat-item .stat-label {
  font-size: 12px;
  color: #999;
  margin-top: 5px;
}

.text-danger {
  color: #f56c6c !important;
}

.text-warning {
  color: #e6a23c !important;
}

.text-info {
  color: #909399 !important;
}

.work-hours {
  display: flex;
  justify-content: space-around;
  color: #666;
}

.quick-card .quick-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
}

.quick-card .el-button {
  height: 60px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
