<template>
  <div class="attendance-container">
    <div class="page-header">
      <h2>考勤管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="handleCheckIn" :disabled="todayStatus.check_in_time">
          <el-icon><Location /></el-icon> 签到
        </el-button>
        <el-button type="warning" @click="handleCheckOut" :disabled="!todayStatus.check_in_time || todayStatus.check_out_time">
          <el-icon><CircleCheck /></el-icon> 签退
        </el-button>
      </div>
    </div>
    
    <!-- 今日打卡状态 -->
    <el-card shadow="never" class="status-card">
      <el-row :gutter="20">
        <el-col :span="8">
          <div class="status-item">
            <div class="status-label">签到时间</div>
            <div class="status-value">
              {{ todayStatus.check_in_time ? formatTime(todayStatus.check_in_time) : '--:--' }}
            </div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="status-item">
            <div class="status-label">签退时间</div>
            <div class="status-value">
              {{ todayStatus.check_out_time ? formatTime(todayStatus.check_out_time) : '--:--' }}
            </div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="status-item">
            <div class="status-label">状态</div>
            <div class="status-value">
              <el-tag :type="getStatusType(todayStatus.status)" size="large">
                {{ getStatusLabel(todayStatus.status) }}
              </el-tag>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>
    
    <el-tabs v-model="activeTab">
      <el-tab-pane label="考勤记录" name="records">
        <el-card shadow="never">
          <template #header>
            <el-form :inline="true">
              <el-form-item label="月份">
                <el-date-picker v-model="queryMonth" type="month" placeholder="选择月份" 
                  value-format="YYYY-MM" @change="fetchRecords" style="width: 150px" />
              </el-form-item>
            </el-form>
          </template>
          
          <!-- 批量操作 -->
          
          <div v-if="selectedRows.length > 0" class="batch-toolbar">
          
            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
          
            <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
          
            <el-button size="small" @click="batchExport">导出选中</el-button>
          
          </div>
          
          <el-table :data="records" v-loading="loading" border stripe @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="attendance_date" label="日期" width="110" />
            <el-table-column label="签到" width="140">
              <template #default="{ row }">
                <span v-if="row.check_in_time">{{ formatTime(row.check_in_time) }}</span>
                <span v-else class="text-muted">--</span>
              </template>
            </el-table-column>
            <el-table-column label="签退" width="140">
              <template #default="{ row }">
                <span v-if="row.check_out_time">{{ formatTime(row.check_out_time) }}</span>
                <span v-else class="text-muted">--</span>
              </template>
            </el-table-column>
            <el-table-column label="工作时长" width="100" align="right">
              <template #default="{ row }">
                {{ row.work_hours ? row.work_hours + 'h' : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="迟到/早退" width="120">
              <template #default="{ row }">
                <span v-if="row.late_minutes > 0" class="text-warning">迟到{{ row.late_minutes }}分</span>
                <span v-if="row.early_minutes > 0" class="text-warning">早退{{ row.early_minutes }}分</span>
                <span v-if="!row.late_minutes && !row.early_minutes">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="remarks" label="备注" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="请假申请" name="leaves">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>我的请假</span>
              <el-button type="primary" size="small" @click="handleAddLeave">申请请假</el-button>
            </div>
          </template>
          
          <el-table :data="leaveRequests" border stripe>
            <el-table-column prop="leave_type_display" label="类型" width="90" />
            <el-table-column label="时间" min-width="200">
              <template #default="{ row }">
                {{ row.start_date }} ~ {{ row.end_date }} ({{ row.days }}天)
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="原因" show-overflow-tooltip />
            <el-table-column prop="status_display" label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="getLeaveStatusType(row.status)">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="approver_name" label="审批人" width="100" />
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleSubmitLeave(row)" 
                  v-if="row.status === 'DRAFT'">提交</el-button>
                <el-button type="info" link size="small" @click="handleCancelLeave(row)" 
                  v-if="row.status === 'PENDING'">撤回</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="加班申请" name="overtime">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>我的加班</span>
              <el-button type="primary" size="small" @click="handleAddOvertime">申请加班</el-button>
            </div>
          </template>
          
          <el-table :data="overtimeRequests" border stripe>
            <el-table-column prop="overtime_date" label="日期" width="110" />
            <el-table-column label="时间" width="150">
              <template #default="{ row }">
                {{ row.start_time }} - {{ row.end_time }}
              </template>
            </el-table-column>
            <el-table-column label="时长" width="80" align="right">
              <template #default="{ row }">
                {{ row.hours }}h
              </template>
            </el-table-column>
            <el-table-column prop="project_name" label="项目" show-overflow-tooltip />
            <el-table-column prop="reason" label="原因" show-overflow-tooltip />
            <el-table-column prop="status_display" label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="getLeaveStatusType(row.status)">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleSubmitOvertime(row)" 
                  v-if="row.status === 'DRAFT'">提交</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="月度汇总" name="summary">
        <el-card shadow="never">
          <template #header>
            <el-form :inline="true">
              <el-form-item label="月份">
                <el-date-picker v-model="summaryMonth" type="month" placeholder="选择月份" 
                  value-format="YYYY-MM" @change="fetchSummary" style="width: 150px" />
              </el-form-item>
            </el-form>
          </template>
          
          <el-row :gutter="16">
            <el-col :span="4" v-for="(item, key) in summaryData" :key="key">
              <el-card shadow="never" class="summary-card">
                <div class="summary-value">{{ item.value }}</div>
                <div class="summary-label">{{ item.label }}</div>
              </el-card>
            </el-col>
          </el-row>
        </el-card>
      </el-tab-pane>
    </el-tabs>
    
    <!-- 请假申请对话框 -->
    <el-dialog v-model="leaveDialogVisible" title="申请请假" width="500px">
      <el-form :model="leaveForm" :rules="leaveRules" ref="leaveFormRef" label-width="80px">
        <el-form-item label="请假类型" prop="leave_type">
          <el-select v-model="leaveForm.leave_type" placeholder="选择类型" style="width: 100%">
            <el-option v-for="t in leaveTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期" prop="start_date">
          <el-date-picker v-model="leaveForm.start_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="结束日期" prop="end_date">
          <el-date-picker v-model="leaveForm.end_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="请假天数" prop="days">
          <el-input-number v-model="leaveForm.days" :min="0.5" :step="0.5" style="width: 100%" />
        </el-form-item>
        <el-form-item label="原因" prop="reason">
          <el-input v-model="leaveForm.reason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="leaveDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitLeaveForm" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 加班申请对话框 -->
    <el-dialog v-model="overtimeDialogVisible" title="申请加班" width="500px">
      <el-form :model="overtimeForm" :rules="overtimeRules" ref="overtimeFormRef" label-width="80px">
        <el-form-item label="加班日期" prop="overtime_date">
          <el-date-picker v-model="overtimeForm.overtime_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="开始时间" prop="start_time">
          <el-time-picker v-model="overtimeForm.start_time" style="width: 100%" value-format="HH:mm:ss" />
        </el-form-item>
        <el-form-item label="结束时间" prop="end_time">
          <el-time-picker v-model="overtimeForm.end_time" style="width: 100%" value-format="HH:mm:ss" />
        </el-form-item>
        <el-form-item label="原因" prop="reason">
          <el-input v-model="overtimeForm.reason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="overtimeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitOvertimeForm" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Location, CircleCheck } from '@element-plus/icons-vue'
import {
getAttendanceToday,
  getMyAttendanceRecords,
  getAttendanceMonthlySummary,
  attendanceCheckIn,
  attendanceCheckOut,
  getMyLeaveRequests,
  getLeaveTypes,
  createLeaveRequest,
  submitLeaveRequest,
  cancelLeaveRequest,
  getMyOvertimeRequests,
  createOvertimeRequest,
  submitOvertimeRequest
} from '@/api/accounts'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/auth/attendance-records/', { onSuccess: () => fetchRecords() })


const activeTab = ref('records')
const loading = ref(false)
const submitLoading = ref(false)

const currentDate = new Date()
const queryMonth = ref(`${currentDate.getFullYear()}-${String(currentDate.getMonth() + 1).padStart(2, '0')}`)
const summaryMonth = ref(queryMonth.value)

const todayStatus = ref({ check_in_time: null, check_out_time: null, status: 'NOT_CHECKED' })
const records = ref<any[]>([])
const leaveRequests = ref<any[]>([])
const overtimeRequests = ref<any[]>([])
const monthlySummary = ref<any[]>([])
const leaveTypes = ref<any[]>([])

const leaveDialogVisible = ref(false)
const overtimeDialogVisible = ref(false)
const leaveFormRef = ref(null)
const overtimeFormRef = ref(null)

const leaveForm = reactive({
  leave_type: 'PERSONAL',
  start_date: '',
  end_date: '',
  days: 1,
  reason: ''
})

const overtimeForm = reactive({
  overtime_date: '',
  start_time: '18:00:00',
  end_time: '21:00:00',
  reason: ''
})

const leaveRules = {
  leave_type: [{ required: true, message: '请选择请假类型', trigger: 'change' }],
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }],
  reason: [{ required: true, message: '请填写请假原因', trigger: 'blur' }]
}

const overtimeRules = {
  overtime_date: [{ required: true, message: '请选择加班日期', trigger: 'change' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  end_time: [{ required: true, message: '请选择结束时间', trigger: 'change' }],
  reason: [{ required: true, message: '请填写加班原因', trigger: 'blur' }]
}

const summaryData = computed(() => {
  if (!monthlySummary.value.length) return {}
  const s = monthlySummary.value[0]
  return {
    total: { label: '出勤天数', value: s.total_days || 0 },
    normal: { label: '正常', value: s.normal_days || 0 },
    late: { label: '迟到', value: s.late_days || 0 },
    early: { label: '早退', value: s.early_days || 0 },
    leave: { label: '请假', value: s.leave_days || 0 },
    overtime: { label: '加班(h)', value: s.total_overtime_hours || 0 }
  }
})

const fetchTodayStatus = async () => {
  try {
    const data = await getAttendanceToday()
    todayStatus.value = data
  } catch (e) {
    console.error(e)
  }
}

const fetchRecords = async () => {
  loading.value = true
  try {
    const data = await getMyAttendanceRecords({ month: queryMonth.value })
    records.value = data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchLeaveRequests = async () => {
  try {
    const data = await getMyLeaveRequests()
    leaveRequests.value = data
  } catch (e) {
    console.error(e)
  }
}

const fetchOvertimeRequests = async () => {
  try {
    const data = await getMyOvertimeRequests()
    overtimeRequests.value = data
  } catch (e) {
    console.error(e)
  }
}

const fetchSummary = async () => {
  try {
    const data = await getAttendanceMonthlySummary({ month: summaryMonth.value })
    monthlySummary.value = data
  } catch (e) {
    console.error(e)
  }
}

const fetchLeaveTypes = async () => {
  try {
    const data = await getLeaveTypes()
    leaveTypes.value = data
  } catch (e) {
    leaveTypes.value = [
      { value: 'ANNUAL', label: '年假' },
      { value: 'SICK', label: '病假' },
      { value: 'PERSONAL', label: '事假' },
      { value: 'OTHER', label: '其他' }
    ]
  }
}

const handleCheckIn = async () => {
  try {
    const data = await attendanceCheckIn({ location: '办公室' })
    todayStatus.value = data
    ElMessage.success('签到成功')
    fetchRecords()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '签到失败')
  }
}

const handleCheckOut = async () => {
  try {
    const data = await attendanceCheckOut({ location: '办公室' })
    todayStatus.value = data
    ElMessage.success('签退成功')
    fetchRecords()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '签退失败')
  }
}

const handleAddLeave = () => {
  Object.assign(leaveForm, {
    leave_type: 'PERSONAL',
    start_date: '',
    end_date: '',
    days: 1,
    reason: ''
  })
  leaveDialogVisible.value = true
}

const handleAddOvertime = () => {
  Object.assign(overtimeForm, {
    overtime_date: '',
    start_time: '18:00:00',
    end_time: '21:00:00',
    reason: ''
  })
  overtimeDialogVisible.value = true
}

const submitLeaveForm = async () => {
  const valid = await leaveFormRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    await createLeaveRequest(leaveForm)
    ElMessage.success('申请已保存')
    leaveDialogVisible.value = false
    fetchLeaveRequests()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    submitLoading.value = false
  }
}

const submitOvertimeForm = async () => {
  const valid = await overtimeFormRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    await createOvertimeRequest(overtimeForm)
    ElMessage.success('申请已保存')
    overtimeDialogVisible.value = false
    fetchOvertimeRequests()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    submitLoading.value = false
  }
}

const handleSubmitLeave = async (row) => {
  try {
    await submitLeaveRequest(row.id)
    ElMessage.success('已提交审批')
    fetchLeaveRequests()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '提交失败')
  }
}

const handleSubmitOvertime = async (row) => {
  try {
    await submitOvertimeRequest(row.id)
    ElMessage.success('已提交审批')
    fetchOvertimeRequests()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '提交失败')
  }
}

const handleCancelLeave = async (row) => {
  try {
    await ElMessageBox.confirm('确定要撤回该请假申请吗？', '提示', { type: 'warning' })
    await cancelLeaveRequest(row.id)
    ElMessage.success('撤回成功')
    fetchLeaveRequests()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error.response?.data?.error || '撤回失败')
  }
}

const formatTime = (dateTimeStr) => {
  if (!dateTimeStr) return '--:--'
  const date = new Date(dateTimeStr)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const getStatusType = (status) => {
  const types = {
    NORMAL: 'success',
    LATE: 'warning',
    EARLY: 'warning',
    ABSENT: 'danger',
    LEAVE: 'info',
    OVERTIME: 'primary',
    NOT_CHECKED: 'info'
  }
  return types[status] || ''
}

const getStatusLabel = (status) => {
  const labels = {
    NORMAL: '正常',
    LATE: '迟到',
    EARLY: '早退',
    ABSENT: '缺勤',
    LEAVE: '请假',
    OVERTIME: '加班',
    NOT_CHECKED: '未打卡'
  }
  return labels[status] || status
}

const getLeaveStatusType = (status) => {
  const types = {
    DRAFT: 'info',
    PENDING: 'warning',
    APPROVED: 'success',
    REJECTED: 'danger',
    CANCELLED: ''
  }
  return types[status] || ''
}

onMounted(() => {
  fetchTodayStatus()
  fetchRecords()
  fetchLeaveRequests()
  fetchOvertimeRequests()
  fetchSummary()
  fetchLeaveTypes()
})
</script>

<style scoped>
.attendance-container {
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

.header-actions {
  display: flex;
  gap: 10px;
}

.status-card {
  margin-bottom: 16px;
}

.status-item {
  text-align: center;
  padding: 10px 0;
}

.status-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.status-value {
  font-size: 22px;
  font-weight: 500;
  color: #303133;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.summary-card {
  text-align: center;
  padding: 12px 0;
}

.summary-value {
  font-size: 28px;
  font-weight: bold;
  color: #409eff;
}

.summary-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.text-muted { color: #c0c4cc; }
.text-warning { color: #e6a23c; }
</style>
