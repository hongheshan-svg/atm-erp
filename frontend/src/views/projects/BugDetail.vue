<template>
  <div class="bug-detail" v-loading="loading">
    <el-page-header @back="goBack" :title="'返回Bug列表'">
      <template #content>
        <span class="bug-title">{{ bug?.bug_number }}: {{ bug?.title }}</span>
      </template>
      <template #extra>
        <el-button @click="handleEdit">编辑</el-button>
        <el-button type="primary" @click="handleChangeStatus">变更状态</el-button>
      </template>
    </el-page-header>

    <div class="content-wrapper" v-if="bug">
      <el-row :gutter="20">
        <!-- 左侧主要内容 -->
        <el-col :span="16">
          <!-- 基本信息 -->
          <el-card class="info-card">
            <template #header>
              <div class="card-header">
                <span>Bug详情</span>
                <div class="tags">
                  <el-tag :type="getSeverityType(bug.severity)" size="large">{{ bug.severity_display }}</el-tag>
                  <el-tag :type="getPriorityType(bug.priority)" size="large" effect="dark">{{ bug.priority }}</el-tag>
                  <el-tag :type="getStatusType(bug.status)" size="large">{{ bug.status_display }}</el-tag>
                </div>
              </div>
            </template>
            
            <el-descriptions :column="2" border>
              <el-descriptions-item label="Bug编号">{{ bug.bug_number }}</el-descriptions-item>
              <el-descriptions-item label="Bug类型">{{ bug.bug_type_display }}</el-descriptions-item>
              <el-descriptions-item label="所属项目">{{ bug.project_name }}</el-descriptions-item>
              <el-descriptions-item label="模块/组件">{{ bug.module || '-' }}</el-descriptions-item>
              <el-descriptions-item label="报告人">{{ bug.reporter_name }}</el-descriptions-item>
              <el-descriptions-item label="处理人">
                <span v-if="bug.assignee_name">{{ bug.assignee_name }}</span>
                <el-tag v-else type="warning" size="small">未分配</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="环境">{{ bug.environment || '-' }}</el-descriptions-item>
              <el-descriptions-item label="版本">{{ bug.version || '-' }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatDate(bug.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ formatDate(bug.updated_at) }}</el-descriptions-item>
              <el-descriptions-item label="解决时间" v-if="bug.resolved_at">{{ formatDate(bug.resolved_at) }}</el-descriptions-item>
              <el-descriptions-item label="关闭时间" v-if="bug.closed_at">{{ formatDate(bug.closed_at) }}</el-descriptions-item>
            </el-descriptions>

            <el-divider content-position="left">问题描述</el-divider>
            <div class="description-content">
              <pre>{{ bug.description }}</pre>
            </div>

            <template v-if="bug.resolution">
              <el-divider content-position="left">解决方案</el-divider>
              <el-alert :title="bug.resolution_display" type="success" :closable="false" show-icon>
                <template #default>
                  <pre v-if="bug.solution">{{ bug.solution }}</pre>
                </template>
              </el-alert>
            </template>
          </el-card>

          <!-- 评论区 -->
          <el-card class="comment-card">
            <template #header>
              <span>评论 ({{ bug.comments?.length || 0 }})</span>
            </template>
            
            <!-- 评论列表 -->
            <div class="comment-list">
              <div v-for="comment in bug.comments" :key="comment.id" class="comment-item">
                <div class="comment-header">
                  <el-avatar :size="32">{{ comment.user_name?.charAt(0) || 'U' }}</el-avatar>
                  <span class="comment-user">{{ comment.user_name }}</span>
                  <span class="comment-time">{{ formatDate(comment.created_at) }}</span>
                </div>
                <div class="comment-content">
                  <pre>{{ comment.content }}</pre>
                </div>
              </div>
              <el-empty v-if="!bug.comments?.length" description="暂无评论" />
            </div>
            
            <!-- 添加评论 -->
            <div class="add-comment">
              <el-input
                v-model="newComment"
                type="textarea"
                :rows="3"
                placeholder="添加评论..."
              />
              <el-button type="primary" @click="handleAddComment" :loading="addingComment" style="margin-top: 10px;">
                发表评论
              </el-button>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧信息栏 -->
        <el-col :span="8">
          <!-- 附件 -->
          <el-card class="attachment-card">
            <template #header>
              <div class="card-header">
                <span>附件 ({{ bug.attachments?.length || 0 }})</span>
                <el-upload
                  :action="uploadUrl"
                  :headers="uploadHeaders"
                  :on-success="handleUploadSuccess"
                  :on-error="handleUploadError"
                  :show-file-list="false"
                >
                  <el-button size="small" type="primary">上传附件</el-button>
                </el-upload>
              </div>
            </template>
            
            <div class="attachment-list">
              <div v-for="att in bug.attachments" :key="att.id" class="attachment-item">
                <el-icon><Document /></el-icon>
                <a :href="att.file" target="_blank" class="attachment-name">{{ att.filename }}</a>
                <span class="attachment-size">{{ formatFileSize(att.file_size) }}</span>
              </div>
              <el-empty v-if="!bug.attachments?.length" description="暂无附件" :image-size="60" />
            </div>
          </el-card>

          <!-- 变更历史 -->
          <el-card class="history-card">
            <template #header>
              <span>变更历史</span>
            </template>
            
            <el-timeline>
              <el-timeline-item
                v-for="history in bug.histories"
                :key="history.id"
                :timestamp="formatDate(history.created_at)"
                placement="top"
              >
                <p>
                  <strong>{{ history.user_name }}</strong>
                  将 <em>{{ history.field_label }}</em>
                  从 "{{ history.old_value || '空' }}" 改为 "{{ history.new_value }}"
                </p>
              </el-timeline-item>
              <el-empty v-if="!bug.histories?.length" description="暂无变更记录" :image-size="60" />
            </el-timeline>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 状态变更对话框 -->
    <el-dialog v-model="statusDialogVisible" title="变更状态" width="500px">
      <el-form :model="statusForm" label-width="100px">
        <el-form-item label="新状态">
          <el-select v-model="statusForm.status" placeholder="选择状态" style="width: 100%;">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="解决方式" v-if="statusForm.status === 'RESOLVED'">
          <el-select v-model="statusForm.resolution" placeholder="选择解决方式" style="width: 100%;">
            <el-option v-for="r in resolutionOptions" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明" v-if="statusForm.status === 'RESOLVED'">
          <el-input v-model="statusForm.solution" type="textarea" :rows="3" placeholder="解决方案说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="statusDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleStatusSubmit" :loading="changingStatus">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document } from '@element-plus/icons-vue'
import { getBug, changeBugStatus, addBugComment } from '@/api/projects/bug'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const addingComment = ref(false)
const changingStatus = ref(false)
const bug = ref(null)
const newComment = ref('')
const statusDialogVisible = ref(false)

const statusForm = reactive({
  status: '',
  resolution: '',
  solution: ''
})

const bugId = computed(() => route.params.id)

const uploadUrl = computed(() => `/api/projects/bugs/${bugId.value}/attachments/`)
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${userStore.token}`
}))

const statusOptions = [
  { value: 'NEW', label: '新建' },
  { value: 'CONFIRMED', label: '已确认' },
  { value: 'IN_PROGRESS', label: '处理中' },
  { value: 'RESOLVED', label: '已解决' },
  { value: 'CLOSED', label: '已关闭' },
  { value: 'REOPENED', label: '重新打开' },
  { value: 'SUSPENDED', label: '挂起' },
  { value: 'CANNOT_REPRODUCE', label: '无法复现' },
  { value: 'BY_DESIGN', label: '设计如此' },
  { value: 'DUPLICATE', label: '重复' }
]

const resolutionOptions = [
  { value: 'FIXED', label: '已修复' },
  { value: 'WONT_FIX', label: '不予修复' },
  { value: 'DUPLICATE', label: '重复问题' },
  { value: 'INVALID', label: '无效问题' },
  { value: 'CANNOT_REPRODUCE', label: '无法复现' },
  { value: 'BY_DESIGN', label: '设计如此' }
]

const getSeverityType = (severity) => {
  const types = {
    'CRITICAL': 'danger',
    'MAJOR': 'warning',
    'NORMAL': 'info',
    'MINOR': 'success',
    'SUGGESTION': ''
  }
  return types[severity] || ''
}

const getPriorityType = (priority) => {
  const types = {
    'P0': 'danger',
    'P1': 'warning',
    'P2': 'info',
    'P3': 'success'
  }
  return types[priority] || ''
}

const getStatusType = (status) => {
  const types = {
    'NEW': '',
    'CONFIRMED': 'warning',
    'IN_PROGRESS': 'primary',
    'RESOLVED': 'success',
    'CLOSED': 'info',
    'REOPENED': 'danger',
    'SUSPENDED': 'info',
    'CANNOT_REPRODUCE': 'info',
    'BY_DESIGN': 'info',
    'DUPLICATE': 'info'
  }
  return types[status] || ''
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const goBack = () => {
  router.push('/projects/bugs')
}

const loadBug = async () => {
  loading.value = true
  try {
    bug.value = await getBug(bugId.value)
  } catch (error) {
    ElMessage.error('加载Bug详情失败')
    router.push('/projects/bugs')
  } finally {
    loading.value = false
  }
}

const handleEdit = () => {
  router.push(`/projects/bugs/${bugId.value}/edit`)
}

const handleChangeStatus = () => {
  statusForm.status = bug.value.status
  statusForm.resolution = bug.value.resolution || ''
  statusForm.solution = bug.value.solution || ''
  statusDialogVisible.value = true
}

const handleStatusSubmit = async () => {
  if (!statusForm.status) {
    ElMessage.warning('请选择状态')
    return
  }
  
  changingStatus.value = true
  try {
    await changeBugStatus(bugId.value, statusForm)
    ElMessage.success('状态变更成功')
    statusDialogVisible.value = false
    loadBug()
  } catch (error) {
    const msg = error.response?.data?.error || '状态变更失败'
    ElMessage.error(msg)
  } finally {
    changingStatus.value = false
  }
}

const handleAddComment = async () => {
  if (!newComment.value.trim()) {
    ElMessage.warning('请输入评论内容')
    return
  }
  
  addingComment.value = true
  try {
    await addBugComment(bugId.value, {
      content: newComment.value
    })
    ElMessage.success('评论发表成功')
    newComment.value = ''
    loadBug()
  } catch (error) {
    ElMessage.error('发表评论失败')
  } finally {
    addingComment.value = false
  }
}

const handleUploadSuccess = () => {
  ElMessage.success('附件上传成功')
  loadBug()
}

const handleUploadError = () => {
  ElMessage.error('附件上传失败')
}

onMounted(() => {
  loadBug()
})
</script>

<style scoped>
.bug-detail {
  padding: 20px;
}

.bug-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.content-wrapper {
  margin-top: 20px;
}

.info-card,
.comment-card,
.attachment-card,
.history-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tags {
  display: flex;
  gap: 8px;
}

.description-content {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
}

.description-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
}

.comment-list {
  max-height: 400px;
  overflow-y: auto;
  margin-bottom: 20px;
}

.comment-item {
  padding: 12px;
  border-bottom: 1px solid #ebeef5;
}

.comment-item:last-child {
  border-bottom: none;
}

.comment-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.comment-user {
  font-weight: 600;
  color: #303133;
}

.comment-time {
  font-size: 12px;
  color: #909399;
}

.comment-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  color: #606266;
}

.add-comment {
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.attachment-list {
  max-height: 200px;
  overflow-y: auto;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #ebeef5;
}

.attachment-item:last-child {
  border-bottom: none;
}

.attachment-name {
  flex: 1;
  color: #409eff;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-name:hover {
  text-decoration: underline;
}

.attachment-size {
  font-size: 12px;
  color: #909399;
}

:deep(.el-timeline-item__content) {
  font-size: 13px;
}

:deep(.el-timeline-item__content p) {
  margin: 0;
}

:deep(.el-timeline-item__content em) {
  font-style: normal;
  color: #409eff;
}
</style>

