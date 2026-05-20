<template>
  <div class="announcement-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>公告通知</span>
          <div class="header-actions">
            <el-button @click="markAllRead" :loading="markingRead">
              <el-icon><Check /></el-icon>
              全部已读
            </el-button>
            <el-button v-if="isAdmin" type="primary" v-permission="'oa:archive:create'" @click="handleCreate">
              <el-icon><Plus /></el-icon>
              发布公告
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="类型">
          <el-select v-model="searchForm.announcement_type" placeholder="选择类型" clearable style="width: 120px;">
            <el-option label="通知公告" value="NOTICE" />
            <el-option label="新闻动态" value="NEWS" />
            <el-option label="系统公告" value="SYSTEM" />
            <el-option label="更新公告" value="UPDATE" />
            <el-option label="维护通知" value="MAINTENANCE" />
            <el-option label="重要通知" value="IMPORTANT" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
        </el-form-item>
      </el-form>
      
      <!-- 公告列表 -->
      <div class="announcement-items">
        <div 
          v-for="item in list" 
          :key="item.id" 
          class="announcement-item"
          :class="{ unread: !item.is_read, top: item.is_top }"
          @click="handleView(item)"
        >
          <div class="item-header">
            <div class="item-tags">
              <el-tag v-if="item.is_top" type="danger" size="small">置顶</el-tag>
              <el-tag :type="getTypeColor(item.announcement_type)" size="small">{{ item.announcement_type_display }}</el-tag>
              <el-tag v-if="item.priority === 'URGENT'" type="danger" size="small">紧急</el-tag>
              <el-tag v-else-if="item.priority === 'HIGH'" type="warning" size="small">重要</el-tag>
            </div>
            <span class="item-time">{{ formatTime(item.publish_time || item.created_at) }}</span>
          </div>
          <div class="item-title">
            <span v-if="!item.is_read" class="unread-dot"></span>
            {{ item.title }}
          </div>
          <div class="item-summary" v-if="item.summary">{{ item.summary }}</div>
          <div class="item-footer">
            <span class="publisher">{{ item.publisher_name }}</span>
            <span class="views"><el-icon><View /></el-icon> {{ item.view_count }}</span>
          </div>
        </div>
        
        <el-empty v-if="list.length === 0 && !loading" description="暂无公告" />
      </div>
      
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>
    
    <!-- 查看公告详情 -->
    <el-dialog v-model="viewDialogVisible" :title="currentItem?.title" width="700px" destroy-on-close>
      <div class="announcement-detail">
        <div class="detail-meta">
          <el-tag :type="getTypeColor(currentItem?.announcement_type)" size="small">{{ currentItem?.announcement_type_display }}</el-tag>
          <span class="meta-item">发布人: {{ currentItem?.publisher_name }}</span>
          <span class="meta-item">发布时间: {{ formatTime(currentItem?.publish_time) }}</span>
          <span class="meta-item">浏览: {{ currentItem?.view_count }}</span>
        </div>
        <el-divider />
        <div class="detail-content" v-html="currentItem?.content"></div>
      </div>
    </el-dialog>
    
    <!-- 发布公告 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑公告' : '发布公告'" width="700px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="公告类型" prop="announcement_type">
          <el-select v-model="form.announcement_type" style="width: 100%;">
            <el-option label="通知公告" value="NOTICE" />
            <el-option label="新闻动态" value="NEWS" />
            <el-option label="系统公告" value="SYSTEM" />
            <el-option label="更新公告" value="UPDATE" />
            <el-option label="维护通知" value="MAINTENANCE" />
            <el-option label="重要通知" value="IMPORTANT" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-radio-group v-model="form.priority">
            <el-radio value="LOW">低</el-radio>
            <el-radio value="NORMAL">普通</el-radio>
            <el-radio value="HIGH">高</el-radio>
            <el-radio value="URGENT">紧急</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入公告标题" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" type="textarea" :rows="2" placeholder="可选，简短描述" />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="8" placeholder="请输入公告内容" />
        </el-form-item>
        <el-form-item label="显示设置">
          <el-checkbox v-model="form.is_top">置顶</el-checkbox>
          <el-checkbox v-model="form.is_popup">弹窗显示</el-checkbox>
          <el-checkbox v-model="form.target_all">全员可见</el-checkbox>
        </el-form-item>
        <el-form-item label="过期时间">
          <el-date-picker v-model="form.expire_time" type="datetime" placeholder="可选" value-format="YYYY-MM-DD HH:mm:ss" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="info" @click="handleSave('DRAFT')" :loading="saving">保存草稿</el-button>
        <el-button type="primary" @click="handleSaveAndPublish" :loading="saving">保存并发布</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Check, View } from '@element-plus/icons-vue'
import { getPublishedAnnouncements, createAnnouncement, updateAnnouncement, publishAnnouncement, readAnnouncement, markAllAnnouncementsRead } from '@/api/oa'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.userInfo?.is_superuser || userStore.userInfo?.is_staff)

const loading = ref(false)
const saving = ref(false)
const markingRead = ref(false)
const list = ref([])
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const isEdit = ref(false)
const currentItem = ref(null)
const formRef = ref(null)

const searchForm = reactive({
  announcement_type: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = reactive({
  announcement_type: 'NOTICE',
  priority: 'NORMAL',
  title: '',
  summary: '',
  content: '',
  is_top: false,
  is_popup: false,
  target_all: true,
  expire_time: null
})

const rules = {
  announcement_type: [{ required: true, message: '请选择公告类型', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }]
}

const getTypeColor = (type) => {
  const colors = {
    'NOTICE': '',
    'NEWS': 'success',
    'SYSTEM': 'warning',
    'UPDATE': 'primary',
    'MAINTENANCE': 'danger',
    'IMPORTANT': 'danger'
  }
  return colors[type] || ''
}

const formatTime = (time) => {
  if (!time) return ''
  const date = new Date(time)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  
  return date.toLocaleDateString('zh-CN')
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const res = await getPublishedAnnouncements(params)
    // res 已经是 response.data
    if (Array.isArray(res)) {
      list.value = res
      pagination.total = res.length
    } else if (res && res.results) {
      list.value = res.results
      pagination.total = res.count || 0
    } else {
      list.value = []
      pagination.total = 0
    }
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleView = async (item) => {
  currentItem.value = item
  viewDialogVisible.value = true
  
  // 标记为已读
  if (!item.is_read) {
    try {
      await readAnnouncement(item.id)
      item.is_read = true
      item.view_count++
    } catch (error) {
      console.error('标记已读失败', error)
    }
  }
}

const markAllRead = async () => {
  markingRead.value = true
  try {
    await markAllAnnouncementsRead()
    ElMessage.success('已全部标记为已读')
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    markingRead.value = false
  }
}

const handleCreate = () => {
  isEdit.value = false
  Object.assign(form, {
    announcement_type: 'NOTICE',
    priority: 'NORMAL',
    title: '',
    summary: '',
    content: '',
    is_top: false,
    is_popup: false,
    target_all: true,
    expire_time: null
  })
  dialogVisible.value = true
}

const handleSave = async (status = 'DRAFT') => {
  try {
    await formRef.value?.validate()
    saving.value = true
    
    const data = { ...form, status }
    
    if (isEdit.value) {
      await updateAnnouncement(form.id, data)
    } else {
      await createAnnouncement(data)
    }
    
    ElMessage.success(status === 'DRAFT' ? '保存成功' : '发布成功')
    dialogVisible.value = false
    loadData()
  } catch (error) {
    if (error.response?.data) {
      ElMessage.error(JSON.stringify(error.response.data))
    }
  } finally {
    saving.value = false
  }
}

const handleSaveAndPublish = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    
    // 先保存
    const data = { ...form, status: 'DRAFT' }
    let announcement
    
    if (isEdit.value) {
      const res = await updateAnnouncement(form.id, data)
      // res 已经是 response.data
      announcement = res
    } else {
      const res = await createAnnouncement(data)
      // res 已经是 response.data
      announcement = res
    }
    
    // 再发布
    await publishAnnouncement(announcement.id)
    
    ElMessage.success('发布成功')
    dialogVisible.value = false
    loadData()
  } catch (error) {
    if (error.response?.data) {
      ElMessage.error(JSON.stringify(error.response.data))
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.announcement-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.search-form {
  margin-bottom: 20px;
}

.announcement-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.announcement-item {
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.announcement-item:hover {
  border-color: #409EFF;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.1);
}

.announcement-item.unread {
  background: #f0f9ff;
  border-color: #b3d8ff;
}

.announcement-item.top {
  border-left: 4px solid #f56c6c;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.item-tags {
  display: flex;
  gap: 8px;
}

.item-time {
  font-size: 12px;
  color: #999;
}

.item-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.unread-dot {
  width: 8px;
  height: 8px;
  background: #f56c6c;
  border-radius: 50%;
}

.item-summary {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-footer {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #999;
}

.views {
  display: flex;
  align-items: center;
  gap: 4px;
}

.announcement-detail .detail-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.detail-meta .meta-item {
  font-size: 14px;
  color: #666;
}

.detail-content {
  line-height: 1.8;
  white-space: pre-wrap;
}
</style>
