<template>
  <div class="meeting-container">
    <div class="page-header">
      <h2>会议管理</h2>
      <el-button type="primary" v-permission="'oa:archive:create'" @click="handleAdd">预约会议</el-button>
    </div>
    
    <el-row :gutter="16">
      <el-col :span="18">
        <el-card shadow="never">
          <template #header>
            <el-form :inline="true">
              <el-form-item>
                <el-input v-model="queryParams.search" placeholder="搜索会议" clearable />
              </el-form-item>
              <el-form-item>
                <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchList">
                  <el-option label="已安排" value="SCHEDULED" />
                  <el-option label="进行中" value="IN_PROGRESS" />
                  <el-option label="已完成" value="COMPLETED" />
                  <el-option label="已取消" value="CANCELLED" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-date-picker 
                  v-model="queryParams.date_range" 
                  type="daterange" 
                  value-format="YYYY-MM-DD"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  @change="fetchList"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="fetchList">查询</el-button>
              </el-form-item>
            </el-form>
          </template>
          
          <!-- 批量操作 -->
          
          <div v-if="selectedRows.length > 0" class="batch-toolbar">
          
            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
          
            <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
          
            <el-button size="small" @click="batchExport">导出选中</el-button>
          
          </div>
          
          <el-table :data="meetingList" v-loading="loading" border stripe @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="meeting_no" label="会议编号" width="120" />
            <el-table-column prop="title" label="会议主题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="start_time" label="开始时间" width="160">
              <template #default="{ row }">
                {{ formatDateTime(row.start_time) }}
              </template>
            </el-table-column>
            <el-table-column prop="end_time" label="结束时间" width="160">
              <template #default="{ row }">
                {{ formatDateTime(row.end_time) }}
              </template>
            </el-table-column>
            <el-table-column label="方式" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_online ? 'success' : ''" size="small">
                  {{ row.is_online ? '线上' : '线下' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="room_name" label="会议室" width="120" />
            <el-table-column prop="organizer_name" label="组织者" width="100" />
            <el-table-column prop="participant_count" label="参会人" width="80" align="center" />
            <el-table-column prop="status_display" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleView(row)">详情</el-button>
                <el-button type="success" link size="small" @click="handleStart(row)" 
                  v-if="row.status === 'SCHEDULED'">开始</el-button>
                <el-button type="warning" link size="small" @click="handleComplete(row)" 
                  v-if="row.status === 'IN_PROGRESS'">结束</el-button>
                <el-button type="danger" link size="small" @click="handleCancel(row)" 
                  v-if="row.status === 'SCHEDULED'">取消</el-button>
              </template>
            </el-table-column>
          </el-table>
          
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.size"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next"
            @size-change="fetchList"
            @current-change="fetchList"
            style="margin-top: 16px; justify-content: flex-end"
          />
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="never" header="今日会议">
          <div v-if="todayMeetings.length === 0" class="empty-tip">今日暂无会议</div>
          <div v-else class="today-list">
            <div 
              v-for="item in todayMeetings" 
              :key="item.id" 
              class="meeting-item"
              :class="item.status.toLowerCase()"
            >
              <div class="meeting-time">
                {{ formatTime(item.start_time) }} - {{ formatTime(item.end_time) }}
              </div>
              <div class="meeting-title">{{ item.title }}</div>
              <div class="meeting-location">
                <el-icon v-if="item.is_online"><VideoCameraFilled /></el-icon>
                <el-icon v-else><Location /></el-icon>
                {{ item.is_online ? '线上会议' : item.room_name }}
              </div>
            </div>
          </div>
        </el-card>
        
        <el-card shadow="never" header="会议室" style="margin-top: 16px">
          <div v-for="room in meetingRooms" :key="room.id" class="room-item">
            <div class="room-name">{{ room.name }}</div>
            <div class="room-info">
              <span>容纳 {{ room.capacity }} 人</span>
              <el-tag :type="room.is_available ? 'success' : 'danger'" size="small">
                {{ room.is_available ? '可用' : '占用' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 新建会议对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑会议' : '预约会议'" width="700px">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="会议主题" prop="title">
          <el-input v-model="formData.title" placeholder="请输入会议主题" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始时间" prop="start_time">
              <el-date-picker 
                v-model="formData.start_time" 
                type="datetime"
                style="width: 100%" 
                value-format="YYYY-MM-DDTHH:mm:ss"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束时间" prop="end_time">
              <el-date-picker 
                v-model="formData.end_time" 
                type="datetime"
                style="width: 100%" 
                value-format="YYYY-MM-DDTHH:mm:ss"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="会议方式">
          <el-radio-group v-model="formData.is_online">
            <el-radio :label="false">线下</el-radio>
            <el-radio :label="true">线上</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="会议室" v-if="!formData.is_online">
          <el-select v-model="formData.meeting_room" style="width: 100%" placeholder="选择会议室">
            <el-option 
              v-for="room in meetingRooms" 
              :key="room.id" 
              :label="`${room.name} (${room.capacity}人)`" 
              :value="room.id"
              :disabled="!room.is_available"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="会议链接" v-if="formData.is_online">
          <el-input v-model="formData.meeting_link" placeholder="线上会议链接" />
        </el-form-item>
        <el-form-item label="会议议程">
          <el-input v-model="formData.agenda" type="textarea" :rows="3" placeholder="会议议程" />
        </el-form-item>
        <el-form-item label="参会人员">
          <el-select v-model="formData.participant_ids" multiple style="width: 100%" placeholder="选择参会人员">
            <el-option v-for="user in userList" :key="user.id" :label="user.name" :value="user.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 会议详情对话框 -->
    <el-dialog v-model="detailDialogVisible" :title="currentMeeting?.title" width="800px">
      <el-descriptions v-if="currentMeeting" :column="2" border>
        <el-descriptions-item label="会议编号">{{ currentMeeting.meeting_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentMeeting.status)">{{ currentMeeting.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ formatDateTime(currentMeeting.start_time) }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ formatDateTime(currentMeeting.end_time) }}</el-descriptions-item>
        <el-descriptions-item label="会议方式">{{ currentMeeting.is_online ? '线上' : '线下' }}</el-descriptions-item>
        <el-descriptions-item label="会议室/链接">
          {{ currentMeeting.is_online ? currentMeeting.meeting_link : currentMeeting.room_name }}
        </el-descriptions-item>
        <el-descriptions-item label="组织者">{{ currentMeeting.organizer_name }}</el-descriptions-item>
        <el-descriptions-item label="关联项目">{{ currentMeeting.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="会议议程" :span="2">{{ currentMeeting.agenda || '-' }}</el-descriptions-item>
      </el-descriptions>
      
      <el-divider content-position="left">参会人员</el-divider>
      <el-table :data="currentMeeting?.meeting_participants" size="small" border>
        <el-table-column prop="user_name" label="姓名" />
        <el-table-column prop="response_display" label="回复状态">
          <template #default="{ row }">
            <el-tag :type="getResponseType(row.response)" size="small">{{ row.response_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_required" label="必须参加" width="100">
          <template #default="{ row }">
            {{ row.is_required ? '是' : '否' }}
          </template>
        </el-table-column>
        <el-table-column prop="attended" label="实际出席" width="100">
          <template #default="{ row }">
            <el-tag :type="row.attended ? 'success' : 'info'" size="small">
              {{ row.attended ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      
      <template v-if="currentMeeting?.minutes">
        <el-divider content-position="left">会议纪要</el-divider>
        <div class="minutes-content">{{ currentMeeting.minutes }}</div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoCameraFilled, Location } from '@element-plus/icons-vue'
import { getCoreMeetings, getCoreMeeting, getTodayMeetings, getMeetingRooms, startMeeting, completeMeeting, cancelMeeting, updateCoreMeeting, createCoreMeeting } from '@/api/oa'
import { usePermissionStore } from '@/stores/permission'
import { getUsers } from '@/api/auth'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/oa/')


const loading = ref(false)
const submitLoading = ref(false)
const meetingList = ref([])
const todayMeetings = ref([])
const meetingRooms = ref([])
const userList = ref([])
const userListLoaded = ref(false)
const permissionStore = usePermissionStore()

const queryParams = reactive({
  search: '',
  status: null,
  date_range: []
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

const dialogVisible = ref(false)
const detailDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const currentMeeting = ref(null)

const formData = reactive({
  title: '',
  start_time: '',
  end_time: '',
  is_online: false,
  meeting_room: null,
  meeting_link: '',
  agenda: '',
  participant_ids: []
})

const rules = {
  title: [{ required: true, message: '请输入会议主题', trigger: 'blur' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  end_time: [{ required: true, message: '请选择结束时间', trigger: 'change' }]
}

const fetchList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.size,
      search: queryParams.search,
      status: queryParams.status
    }
    const data = await getCoreMeetings(params)
    meetingList.value = data.results || data
    pagination.total = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchToday = async () => {
  try {
    const data = await getTodayMeetings()
    todayMeetings.value = data || []
  } catch (e) {
    console.error(e)
  }
}

const fetchRooms = async () => {
  try {
    const data = await getMeetingRooms()
    meetingRooms.value = data.results || data
  } catch (e) {
    console.error(e)
  }
}

const fetchUsers = async () => {
  if (userListLoaded.value) {
    return true
  }

  try {
    const data = await getUsers()
    userList.value = (data.results || data).map(u => ({
      id: u.id,
      name: u.full_name || u.username
    }))
    userListLoaded.value = true
    return true
  } catch (e) {
    if (e?.response?.status !== 403) {
      console.error(e)
    }
    return false
  }
}

const ensureUsersLoaded = async () => {
  if (!permissionStore.hasPermission('system:users')) {
    userList.value = []
    userListLoaded.value = false
    return false
  }

  return fetchUsers()
}

const handleAdd = async () => {
  await ensureUsersLoaded()
  isEdit.value = false
  const now = new Date()
  const later = new Date(now.getTime() + 3600000)
  Object.assign(formData, {
    title: '',
    start_time: now.toISOString().slice(0, 16),
    end_time: later.toISOString().slice(0, 16),
    is_online: false,
    meeting_room: null,
    meeting_link: '',
    agenda: '',
    participant_ids: []
  })
  dialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const data = await getCoreMeeting(row.id)
    currentMeeting.value = data
    detailDialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

const handleStart = async (row) => {
  try {
    await startMeeting(row.id)
    ElMessage.success('会议已开始')
    fetchList()
    fetchToday()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleComplete = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入会议纪要', '结束会议', {
      inputType: 'textarea'
    })
    
    await completeMeeting(row.id, { minutes: value })
    ElMessage.success('会议已结束')
    fetchList()
    fetchToday()
  } catch (e) {
    console.error('Meeting fetchToday error:', e)
  }
}

const handleCancel = async (row) => {
  try {
    await ElMessageBox.confirm('确定取消此会议吗?', '提示')
    await cancelMeeting(row.id)
    ElMessage.success('已取消')
    fetchList()
    fetchToday()
  } catch (e) {
    console.error('Meeting fetchToday error:', e)
  }
}

const submitForm = async () => {
  const valid = await formRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateCoreMeeting(currentMeeting.value.id, formData)
    } else {
      await createCoreMeeting(formData)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    fetchList()
    fetchToday()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    submitLoading.value = false
  }
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  return dateStr.replace('T', ' ').slice(0, 16)
}

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  return dateStr.slice(11, 16)
}

const getStatusType = (status) => {
  const types = {
    SCHEDULED: '',
    IN_PROGRESS: 'success',
    COMPLETED: 'info',
    CANCELLED: 'danger'
  }
  return types[status] || ''
}

const getResponseType = (response) => {
  const types = {
    PENDING: 'info',
    ACCEPTED: 'success',
    DECLINED: 'danger',
    TENTATIVE: 'warning'
  }
  return types[response] || ''
}

onMounted(() => {
  fetchList()
  fetchToday()
  fetchRooms()
})
</script>

<style scoped>
.meeting-container {
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

.empty-tip {
  text-align: center;
  color: #909399;
  padding: 20px 0;
}

.today-list {
  max-height: 300px;
  overflow-y: auto;
}

.meeting-item {
  padding: 12px;
  border-left: 3px solid #409eff;
  background: #f5f7fa;
  margin-bottom: 10px;
  border-radius: 0 4px 4px 0;
}

.meeting-item.in_progress {
  border-left-color: #67c23a;
  background: #f0f9eb;
}

.meeting-item.completed {
  border-left-color: #909399;
  background: #f4f4f5;
}

.meeting-time {
  font-size: 12px;
  color: #909399;
}

.meeting-title {
  font-size: 14px;
  font-weight: 500;
  margin: 4px 0;
}

.meeting-location {
  font-size: 12px;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 4px;
}

.room-item {
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
}

.room-name {
  font-weight: 500;
}

.room-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.minutes-content {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
  white-space: pre-wrap;
}
</style>
