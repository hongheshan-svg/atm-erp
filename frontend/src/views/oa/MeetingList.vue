<template>
  <div class="meeting-list">
    <el-card class="header-card">
      <div class="header-content">
        <h2>会议管理</h2>
        <el-button type="primary" @click="showAddDialog">
          <el-icon><Plus /></el-icon> 预约会议
        </el-button>
      </div>
    </el-card>

    <el-row :gutter="16">
      <el-col :span="6">
        <el-card>
          <template #header>即将进行</template>
          <div class="upcoming-meetings">
            <div v-for="m in upcomingMeetings" :key="m.id" class="meeting-item" @click="showDetail(m)">
              <div class="meeting-time">{{ formatTime(m.start_time) }}</div>
              <div class="meeting-info">
                <div class="meeting-title">{{ m.title }}</div>
                <div class="meeting-meta">
                  <el-icon><Location /></el-icon>
                  {{ m.location || m.room || '线上' }}
                </div>
              </div>
            </div>
            <el-empty v-if="upcomingMeetings.length === 0" description="暂无会议" :image-size="60" />
          </div>
        </el-card>
      </el-col>

      <el-col :span="18">
        <el-card>
          <template #header>
            <div class="table-header">
              <span>会议列表</span>
              <el-radio-group v-model="statusFilter" size="small" @change="loadMeetings">
                <el-radio-button value="">全部</el-radio-button>
                <el-radio-button value="SCHEDULED">已安排</el-radio-button>
                <el-radio-button value="COMPLETED">已完成</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <el-table :data="meetings" v-loading="loading" stripe>
            <el-table-column prop="meeting_no" label="会议编号" width="130" />
            <el-table-column prop="title" label="会议主题" min-width="200" />
            <el-table-column prop="type_display" label="类型" width="90" />
            <el-table-column prop="start_time" label="开始时间" width="160">
              <template #default="{ row }">
                {{ formatDateTime(row.start_time) }}
              </template>
            </el-table-column>
            <el-table-column prop="location" label="地点" width="120" />
            <el-table-column prop="organizer_name" label="组织者" width="100" />
            <el-table-column prop="attendee_count" label="参会人" width="80" align="center" />
            <el-table-column prop="status_display" label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="showDetail(row)">详情</el-button>
                <el-button link type="success" size="small" @click="startMeeting(row)" v-if="row.status === 'SCHEDULED'">开始</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next"
            @change="loadMeetings"
            class="pagination"
          />
        </el-card>
      </el-col>
    </el-row>

    <!-- 新建会议对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="会议主题" prop="title">
          <el-input v-model="form.title" placeholder="请输入会议主题" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="会议类型" prop="meeting_type">
              <el-select v-model="form.meeting_type" style="width: 100%">
                <el-option label="例会" value="REGULAR" />
                <el-option label="项目会" value="PROJECT" />
                <el-option label="评审会" value="REVIEW" />
                <el-option label="培训" value="TRAINING" />
                <el-option label="客户会议" value="CUSTOMER" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="线上会议">
              <el-switch v-model="form.is_online" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始时间" prop="start_time">
              <el-date-picker v-model="form.start_time" type="datetime" style="width: 100%" placeholder="开始时间" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束时间" prop="end_time">
              <el-date-picker v-model="form.end_time" type="datetime" style="width: 100%" placeholder="结束时间" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="会议地点">
              <el-input v-model="form.location" placeholder="会议地点" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="会议室">
              <el-input v-model="form.room" placeholder="会议室" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="会议链接" v-if="form.is_online">
          <el-input v-model="form.online_link" placeholder="线上会议链接" />
        </el-form-item>
        <el-form-item label="会议议程">
          <el-input v-model="form.agenda" type="textarea" :rows="4" placeholder="会议议程" />
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Location } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const meetings = ref([])
const upcomingMeetings = ref([])
const statusFilter = ref('')
const formRef = ref(null)

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  title: '',
  meeting_type: 'REGULAR',
  is_online: false,
  start_time: null,
  end_time: null,
  location: '',
  room: '',
  online_link: '',
  agenda: ''
})

const rules = {
  title: [{ required: true, message: '请输入会议主题', trigger: 'blur' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  end_time: [{ required: true, message: '请选择结束时间', trigger: 'change' }]
}

const dialogTitle = computed(() => form.id ? '编辑会议' : '预约会议')

const loadMeetings = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    if (statusFilter.value) params.status = statusFilter.value
    const res = await request.get('/core/meetings/', { params })
    meetings.value = res.results || res || []
    pagination.total = res.count || (Array.isArray(meetings.value) ? meetings.value.length : 0)
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const loadUpcoming = async () => {
  try {
    const res = await request.get('/core/meetings/upcoming/')
    upcomingMeetings.value = res || []
  } catch (error) {
    console.error(error)
  }
}

const showAddDialog = () => {
  Object.assign(form, {
    id: null, title: '', meeting_type: 'REGULAR', is_online: false,
    start_time: null, end_time: null, location: '', room: '',
    online_link: '', agenda: ''
  })
  dialogVisible.value = true
}

const showDetail = (row) => {
  Object.assign(form, { ...row })
  dialogVisible.value = true
}

const handleSave = async () => {
  await formRef.value.validate()
  saving.value = true
  try {
    if (form.id) {
      await request.put(`/core/meetings/${form.id}/`, form)
      ElMessage.success('更新成功')
    } else {
      await request.post('/core/meetings/', form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadMeetings()
    loadUpcoming()
  } catch (error) {
    console.error(error)
  } finally {
    saving.value = false
  }
}

const startMeeting = async (row) => {
  await ElMessageBox.confirm('确定开始会议？', '确认')
  try {
    await request.post(`/core/meetings/${row.id}/start/`)
    ElMessage.success('会议已开始')
    loadMeetings()
  } catch (error) {
    console.error(error)
  }
}

const getStatusType = (status) => {
  const map = { DRAFT: 'info', SCHEDULED: 'warning', IN_PROGRESS: 'primary', COMPLETED: 'success', CANCELLED: 'info' }
  return map[status] || 'info'
}

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadMeetings()
  loadUpcoming()
})
</script>

<style scoped>
.meeting-list {
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

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upcoming-meetings {
  max-height: 400px;
  overflow-y: auto;
}

.meeting-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid #ebeef5;
  cursor: pointer;
}

.meeting-item:hover {
  background: #f5f7fa;
}

.meeting-time {
  font-size: 14px;
  font-weight: 500;
  color: #409eff;
  width: 50px;
}

.meeting-info {
  flex: 1;
}

.meeting-title {
  font-weight: 500;
  margin-bottom: 4px;
}

.meeting-meta {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
