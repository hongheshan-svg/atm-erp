<template>
  <div class="attachment-upload">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>{{ title }}</span>
          <el-button type="primary" size="small" @click="triggerUpload" :disabled="disabled">
            <el-icon><Upload /></el-icon>
            上传附件
          </el-button>
        </div>
      </template>
      
      <!-- 隐藏的文件输入 -->
      <input
        ref="fileInput"
        type="file"
        :multiple="multiple"
        :accept="accept"
        style="display: none;"
        @change="handleFileChange"
      />
      
      <!-- 上传提示 -->
      <div v-if="!attachments.length && !uploading" class="empty-tip">
        <el-icon size="48" color="#c0c4cc"><Folder /></el-icon>
        <p>暂无附件，点击上方按钮上传</p>
        <p class="tip-text">支持格式：{{ acceptText }}</p>
        <p class="tip-text">单个文件最大：{{ maxSizeText }}</p>
      </div>
      
      <!-- 上传中状态 -->
      <div v-if="uploading" class="uploading-status">
        <el-progress :percentage="uploadProgress" :stroke-width="10" />
        <p>正在上传...</p>
      </div>
      
      <!-- 附件列表 -->
      <el-table v-if="attachments.length" :data="attachments" size="small" border stripe>
        <el-table-column label="文件名" min-width="200">
          <template #default="{ row }">
            <div class="file-info">
              <el-icon :size="20" :color="getFileIconColor(row.file_type)">
                <component :is="getFileIcon(row.file_type)" />
              </el-icon>
              <span class="file-name" :title="row.original_name">{{ row.original_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="category_display" label="分类" width="100" />
        <el-table-column prop="file_size_display" label="大小" width="100" />
        <el-table-column prop="uploaded_by_name" label="上传人" width="100" />
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.uploaded_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handlePreview(row)">
              <el-icon><View /></el-icon>
            </el-button>
            <el-button type="success" link size="small" @click="handleDownload(row)">
              <el-icon><Download /></el-icon>
            </el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)" :disabled="disabled">
              <el-icon><Delete /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 图片预览对话框 -->
    <el-dialog v-model="previewVisible" title="文件预览" width="800px" destroy-on-close>
      <div class="preview-content">
        <img v-if="isImage(previewFile?.file_type)" :src="previewFile?.file_url" style="max-width: 100%;" />
        <iframe v-else-if="isPdf(previewFile?.file_type)" :src="previewFile?.file_url" style="width: 100%; height: 500px; border: none;" />
        <div v-else class="no-preview">
          <el-icon size="64" color="#c0c4cc"><Document /></el-icon>
          <p>该文件类型不支持预览，请下载后查看</p>
          <el-button type="primary" @click="handleDownload(previewFile)">下载文件</el-button>
        </div>
      </div>
    </el-dialog>
    
    <!-- 上传分类选择对话框 -->
    <el-dialog v-model="categoryDialogVisible" title="选择文件分类" width="400px">
      <el-form label-width="80px">
        <el-form-item label="文件分类">
          <el-select v-model="uploadCategory" placeholder="选择分类" style="width: 100%;">
            <el-option
              v-for="cat in categoryOptions"
              :key="cat.value"
              :label="cat.label"
              :value="cat.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="文件描述">
          <el-input v-model="uploadDescription" type="textarea" :rows="2" placeholder="可选，添加文件描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="categoryDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmUpload" :loading="uploading">确定上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Folder, View, Download, Delete, Document, Picture, VideoPlay, Headset, FolderOpened } from '@element-plus/icons-vue'
import request from '@/utils/request'

const props = defineProps({
  // 关联的模型名称，如 'Customer', 'Supplier', 'Contract'
  relatedModel: {
    type: String,
    required: true
  },
  // 关联的对象ID
  relatedId: {
    type: [Number, String],
    required: true
  },
  // 标题
  title: {
    type: String,
    default: '相关附件'
  },
  // 是否禁用
  disabled: {
    type: Boolean,
    default: false
  },
  // 是否支持多文件上传
  multiple: {
    type: Boolean,
    default: true
  },
  // 接受的文件类型
  accept: {
    type: String,
    default: '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.zip,.rar'
  },
  // 最大文件大小（MB）
  maxSize: {
    type: Number,
    default: 50
  }
})

const emit = defineEmits(['uploaded', 'deleted'])

const fileInput = ref(null)
const attachments = ref([])
const uploading = ref(false)
const uploadProgress = ref(0)
const previewVisible = ref(false)
const previewFile = ref(null)
const categoryDialogVisible = ref(false)
const uploadCategory = ref('OTHER')
const uploadDescription = ref('')
const pendingFiles = ref([])

const categoryOptions = [
  { value: 'CONTRACT', label: '合同文件' },
  { value: 'INVOICE', label: '发票' },
  { value: 'RECEIPT', label: '收据' },
  { value: 'CERTIFICATE', label: '证书/资质' },
  { value: 'REPORT', label: '报告' },
  { value: 'IMAGE', label: '图片' },
  { value: 'OTHER', label: '其他' }
]

const acceptText = computed(() => {
  return props.accept.replace(/\./g, '').toUpperCase().replace(/,/g, ', ')
})

const maxSizeText = computed(() => {
  return `${props.maxSize}MB`
})

// 获取文件图标
const getFileIcon = (fileType) => {
  if (!fileType) return Document
  if (fileType.startsWith('image/')) return Picture
  if (fileType.startsWith('video/')) return VideoPlay
  if (fileType.startsWith('audio/')) return Headset
  if (fileType.includes('pdf')) return Document
  if (fileType.includes('word') || fileType.includes('document')) return Document
  if (fileType.includes('excel') || fileType.includes('spreadsheet')) return Document
  if (fileType.includes('zip') || fileType.includes('rar') || fileType.includes('compressed')) return FolderOpened
  return Document
}

// 获取文件图标颜色
const getFileIconColor = (fileType) => {
  if (!fileType) return '#909399'
  if (fileType.startsWith('image/')) return '#67c23a'
  if (fileType.includes('pdf')) return '#f56c6c'
  if (fileType.includes('word') || fileType.includes('document')) return '#409eff'
  if (fileType.includes('excel') || fileType.includes('spreadsheet')) return '#67c23a'
  return '#909399'
}

// 判断是否为图片
const isImage = (fileType) => {
  return fileType && fileType.startsWith('image/')
}

// 判断是否为PDF
const isPdf = (fileType) => {
  return fileType && fileType.includes('pdf')
}

// 格式化日期时间
const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 加载附件列表
const loadAttachments = async () => {
  if (!props.relatedId) return
  
  try {
    const res = await request.get('/core/attachments/', {
      params: {
        related_model: props.relatedModel,
        related_id: props.relatedId
      }
    })
    attachments.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载附件失败:', error)
  }
}

// 触发文件选择
const triggerUpload = () => {
  fileInput.value?.click()
}

// 处理文件选择
const handleFileChange = (event) => {
  const files = Array.from(event.target.files)
  if (!files.length) return
  
  // 验证文件
  const validFiles = []
  for (const file of files) {
    // 检查文件大小
    if (file.size > props.maxSize * 1024 * 1024) {
      ElMessage.warning(`文件 "${file.name}" 超过最大限制 ${props.maxSize}MB`)
      continue
    }
    validFiles.push(file)
  }
  
  if (!validFiles.length) {
    event.target.value = ''
    return
  }
  
  pendingFiles.value = validFiles
  uploadCategory.value = 'OTHER'
  uploadDescription.value = ''
  categoryDialogVisible.value = true
  
  // 清空input
  event.target.value = ''
}

// 确认上传
const confirmUpload = async () => {
  if (!pendingFiles.value.length) return
  
  uploading.value = true
  uploadProgress.value = 0
  categoryDialogVisible.value = false
  
  try {
    const formData = new FormData()
    formData.append('related_model', props.relatedModel)
    formData.append('related_id', props.relatedId)
    formData.append('category', uploadCategory.value)
    formData.append('description', uploadDescription.value)
    
    // 批量上传
    for (const file of pendingFiles.value) {
      formData.append('files', file)
    }
    
    const res = await request.post('/core/attachments/batch_upload/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        uploadProgress.value = Math.round((progressEvent.loaded * 100) / progressEvent.total)
      }
    })
    
    ElMessage.success('上传成功')
    loadAttachments()
    emit('uploaded', res.data || res)
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error('上传失败，请重试')
  } finally {
    uploading.value = false
    uploadProgress.value = 0
    pendingFiles.value = []
  }
}

// 预览文件
const handlePreview = (attachment) => {
  previewFile.value = attachment
  previewVisible.value = true
}

// 下载文件
const handleDownload = (attachment) => {
  const link = document.createElement('a')
  link.href = attachment.file_url
  link.download = attachment.original_name
  link.target = '_blank'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// 删除文件
const handleDelete = async (attachment) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除附件 "${attachment.original_name}" 吗？`,
      '删除确认',
      { type: 'warning' }
    )
    
    await request.delete(`/core/attachments/${attachment.id}/`)
    ElMessage.success('删除成功')
    loadAttachments()
    emit('deleted', attachment)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 监听relatedId变化
watch(() => props.relatedId, (newVal) => {
  if (newVal) {
    loadAttachments()
  }
}, { immediate: true })

// 暴露方法给父组件
defineExpose({
  loadAttachments
})
</script>

<style scoped>
.attachment-upload {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-tip {
  text-align: center;
  padding: 40px 20px;
  color: #909399;
}

.empty-tip p {
  margin: 10px 0 5px;
}

.tip-text {
  font-size: 12px;
  color: #c0c4cc;
}

.uploading-status {
  text-align: center;
  padding: 40px 20px;
}

.uploading-status p {
  margin-top: 15px;
  color: #909399;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-content {
  text-align: center;
  min-height: 200px;
}

.no-preview {
  padding: 60px 20px;
  color: #909399;
}

.no-preview p {
  margin: 20px 0;
}
</style>

