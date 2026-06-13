<template>
  <div class="announcement-container">
    <div class="page-header">
      <h2>系统公告</h2>
      <el-button type="primary" v-permission="'system:config'" @click="handleAdd">发布公告</el-button>
    </div>
    
    <el-card shadow="never">
      <template #header>
        <el-form :inline="true">
          <el-form-item>
            <el-input v-model="queryParams.search" placeholder="搜索标题" clearable @clear="fetchList" />
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.announcement_type" placeholder="类型" clearable @change="fetchList">
              <el-option label="通知公告" value="NOTICE" />
              <el-option label="系统公告" value="SYSTEM" />
              <el-option label="更新公告" value="UPDATE" />
              <el-option label="维护通知" value="MAINTENANCE" />
              <el-option label="重要通知" value="IMPORTANT" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchList">
              <el-option label="草稿" value="DRAFT" />
              <el-option label="已发布" value="PUBLISHED" />
              <el-option label="已过期" value="EXPIRED" />
              <el-option label="已撤回" value="WITHDRAWN" />
            </el-select>
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
      
      <el-table :data="announcements" v-loading="loading" border stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column width="50" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.is_top" color="#e6a23c"><Top /></el-icon>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="250">
          <template #default="{ row }">
            <el-tag v-if="row.priority === 'URGENT'" type="danger" size="small" style="margin-right: 5px">紧急</el-tag>
            <el-tag v-else-if="row.priority === 'HIGH'" type="warning" size="small" style="margin-right: 5px">重要</el-tag>
            <span>{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="announcement_type_display" label="类型" width="100" />
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="view_count" label="浏览" width="80" align="center" />
        <el-table-column prop="publisher_name" label="发布人" width="100" />
        <el-table-column prop="publish_time" label="发布时间" width="160">
          <template #default="{ row }">
            {{ row.publish_time ? formatDateTime(row.publish_time) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" v-permission="'system:config'" @click="handleEdit(row)">编辑</el-button>
            <el-button type="success" link size="small" v-permission="'system:config'" @click="handlePublish(row)" v-if="row.status === 'DRAFT'">发布</el-button>
            <el-button type="warning" link size="small" v-permission="'system:config'" @click="handleWithdraw(row)" v-if="row.status === 'PUBLISHED'">撤回</el-button>
            <el-button type="danger" link size="small" v-permission="'system:config'" @click="handleDelete(row)">删除</el-button>
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
    
    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑公告' : '发布公告'" width="700px">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="formData.title" placeholder="请输入公告标题" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="formData.summary" type="textarea" :rows="2" placeholder="简短描述" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="公告类型">
              <el-select v-model="formData.announcement_type" style="width: 100%">
                <el-option label="通知公告" value="NOTICE" />
                <el-option label="新闻动态" value="NEWS" />
                <el-option label="系统公告" value="SYSTEM" />
                <el-option label="更新公告" value="UPDATE" />
                <el-option label="维护通知" value="MAINTENANCE" />
                <el-option label="重要通知" value="IMPORTANT" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级">
              <el-select v-model="formData.priority" style="width: 100%">
                <el-option label="低" value="LOW" />
                <el-option label="普通" value="NORMAL" />
                <el-option label="高" value="HIGH" />
                <el-option label="紧急" value="URGENT" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="公告内容" prop="content">
          <el-input v-model="formData.content" type="textarea" :rows="8" placeholder="请输入公告内容" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="过期时间">
              <el-date-picker v-model="formData.expire_time" type="datetime" style="width: 100%"
                placeholder="留空表示不过期" value-format="YYYY-MM-DD HH:mm:ss" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="显示设置">
              <el-checkbox v-model="formData.is_top">置顶</el-checkbox>
              <el-checkbox v-model="formData.is_popup">弹窗显示</el-checkbox>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="目标受众">
          <el-checkbox v-model="formData.target_all">全员可见</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="info" @click="submitForm('DRAFT')" :loading="submitLoading">保存草稿</el-button>
        <el-button type="primary" @click="submitForm('PUBLISH')" :loading="submitLoading">立即发布</el-button>
      </template>
    </el-dialog>
    
    <!-- 查看对话框 -->
    <el-dialog v-model="viewDialogVisible" :title="viewAnnouncement?.title" width="600px">
      <div class="announcement-view">
        <div class="meta">
          <el-tag>{{ viewAnnouncement?.announcement_type_display }}</el-tag>
          <span class="publisher">{{ viewAnnouncement?.publisher_name }}</span>
          <span class="time">{{ formatDateTime(viewAnnouncement?.publish_time) }}</span>
        </div>
        <div class="content" v-html="viewAnnouncement?.content?.replace(/\n/g, '<br/>')"></div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Top } from '@element-plus/icons-vue'
import { getAnnouncementList, createAnnouncement, updateAnnouncement, deleteAnnouncement, publishAnnouncement, withdrawAnnouncement } from '@/api/system'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/core/announcements/', { onSuccess: () => fetchList() })


const loading = ref(false)
const submitLoading = ref(false)
const announcements = ref<any[]>([])

const queryParams = reactive({
  search: '',
  announcement_type: null,
  status: null
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const viewAnnouncement = ref(null)

const formData = reactive({
  id: null,
  title: '',
  summary: '',
  content: '',
  announcement_type: 'NOTICE',
  priority: 'NORMAL',
  expire_time: null,
  is_top: false,
  is_popup: false,
  target_all: true
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }]
}

const fetchList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.size,
      ...queryParams
    }
    const data = await getAnnouncementList(params)
    announcements.value = data.results || data
    pagination.total = data.count || (data.results || data)?.length || 0
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  isEdit.value = false
  Object.assign(formData, {
    id: null,
    title: '',
    summary: '',
    content: '',
    announcement_type: 'NOTICE',
    priority: 'NORMAL',
    expire_time: null,
    is_top: false,
    is_popup: false,
    target_all: true
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(formData, row)
  dialogVisible.value = true
}

const handlePublish = async (row) => {
  try {
    await publishAnnouncement(row.id)
    ElMessage.success('发布成功')
    fetchList()
  } catch (e) {
    ElMessage.error('发布失败')
  }
}

const handleWithdraw = async (row) => {
  try {
    await ElMessageBox.confirm('确定要撤回此公告吗？', '提示', { type: 'warning' })
    await withdrawAnnouncement(row.id)
    ElMessage.success('撤回成功')
    fetchList()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('撤回失败')
    }
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除此公告吗？', '提示', { type: 'warning' })
    await deleteAnnouncement(row.id)
    ElMessage.success('删除成功')
    fetchList()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const submitForm = async (action) => {
  const valid = await formRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    let result
    if (isEdit.value) {
      result = await updateAnnouncement(formData.id, formData)
    } else {
      result = await createAnnouncement(formData)
    }
    
    if (action === 'PUBLISH' && result.status === 'DRAFT') {
      await publishAnnouncement(result.id)
    }
    
    ElMessage.success(action === 'PUBLISH' ? '发布成功' : '保存成功')
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error('操作失败')
  } finally {
    submitLoading.value = false
  }
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

const getStatusType = (status) => {
  const types = {
    DRAFT: 'info',
    PUBLISHED: 'success',
    EXPIRED: 'warning',
    WITHDRAWN: ''
  }
  return types[status] || ''
}

onMounted(() => {
  fetchList()
})
</script>

<style scoped>
.announcement-container {
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

.announcement-view {
  padding: 16px 0;
}

.announcement-view .meta {
  margin-bottom: 16px;
  color: #909399;
  font-size: 13px;
}

.announcement-view .meta .publisher {
  margin-left: 12px;
}

.announcement-view .meta .time {
  margin-left: 12px;
}

.announcement-view .content {
  line-height: 1.8;
  color: #303133;
}
</style>
