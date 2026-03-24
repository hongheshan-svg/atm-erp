<template>
  <div class="tech-document-list">
    <!-- 搜索和筛选 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="文档编号">
          <el-input v-model="filters.keyword" placeholder="编号/标题" clearable style="width: 200px" 
                    @keyup.enter="loadDocuments" />
        </el-form-item>
        <el-form-item label="分类">
          <el-cascader v-model="filters.category" :options="categoryTree" 
                       :props="{ value: 'id', label: 'name', checkStrictly: true }"
                       clearable placeholder="选择分类" style="width: 200px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="状态" style="width: 120px">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="评审中" value="REVIEWING" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已发布" value="RELEASED" />
            <el-option label="已作废" value="OBSOLETE" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目">
          <el-select v-model="filters.project" clearable filterable placeholder="选择项目" style="width: 180px">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadDocuments">
            <el-icon><Search /></el-icon>搜索
          </el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 文档列表 -->
    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <span>技术文档列表</span>
          <el-button type="primary" @click="showUploadDialog = true">
            <el-icon><Upload /></el-icon>上传文档
          </el-button>
        </div>
      </template>

      <el-table :data="documents" v-loading="loading" stripe @row-click="viewDocument">
        <el-table-column prop="doc_no" label="文档编号" width="140" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="category_name" label="分类" width="120" />
        <el-table-column label="版本" width="80" align="center">
          <template #default="{ row }">
            {{ row.version }}.{{ row.revision }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="受控级别" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getControlType(row.control_level)" size="small">
              {{ row.control_level_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="所属项目" width="150" show-overflow-tooltip />
        <el-table-column prop="author_name" label="作者" width="100" />
        <el-table-column prop="file_type" label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-icon :size="20" :color="getFileColor(row.file_type)">
              <Document />
            </el-icon>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click.stop="viewDocument(row)">查看</el-button>
            <el-button size="small" link type="primary" @click.stop="downloadDocument(row)">下载</el-button>
            <el-dropdown @command="(cmd) => handleCommand(cmd, row)" @click.stop>
              <el-button size="small" link>更多</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="review" v-if="row.status === 'DRAFT'">提交评审</el-dropdown-item>
                  <el-dropdown-item command="approve" v-if="row.status === 'REVIEWING'">批准</el-dropdown-item>
                  <el-dropdown-item command="release" v-if="row.status === 'APPROVED'">发布</el-dropdown-item>
                  <el-dropdown-item command="revision">创建修订版</el-dropdown-item>
                  <el-dropdown-item command="distribute" v-if="row.status === 'RELEASED'">发放</el-dropdown-item>
                  <el-dropdown-item command="log">访问日志</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadDocuments"
        @current-change="loadDocuments"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>

    <!-- 上传文档对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传技术文档" width="600px">
      <el-form :model="uploadForm" :rules="uploadRules" ref="uploadFormRef" label-width="100px">
        <el-form-item label="文档标题" prop="title">
          <el-input v-model="uploadForm.title" placeholder="输入文档标题" />
        </el-form-item>
        <el-form-item label="文档分类" prop="category">
          <el-cascader v-model="uploadForm.category" :options="categoryTree"
                       :props="{ value: 'id', label: 'name', checkStrictly: true, emitPath: false }"
                       placeholder="选择分类" style="width: 100%" />
        </el-form-item>
        <el-form-item label="所属项目">
          <el-select v-model="uploadForm.project" clearable filterable placeholder="选择项目" style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="受控级别" prop="control_level">
          <el-radio-group v-model="uploadForm.control_level">
            <el-radio label="UNCONTROLLED">非受控</el-radio>
            <el-radio label="CONTROLLED">受控</el-radio>
            <el-radio label="CONFIDENTIAL">机密</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="文档描述">
          <el-input v-model="uploadForm.description" type="textarea" :rows="3" placeholder="输入文档描述" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-select v-model="uploadForm.keywords" multiple filterable allow-create default-first-option
                     placeholder="输入关键词后回车" style="width: 100%" />
        </el-form-item>
        <el-form-item label="上传文件" prop="file">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            drag
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文件到此处，或<em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">支持 PDF、Word、Excel、图片等格式</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" @click="submitUpload" :loading="uploading">上传</el-button>
      </template>
    </el-dialog>

    <!-- 文档详情抽屉 -->
    <el-drawer v-model="showDetailDrawer" title="文档详情" size="60%">
      <template v-if="currentDocument">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="文档编号">{{ currentDocument.doc_no }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ currentDocument.version }}.{{ currentDocument.revision }}</el-descriptions-item>
          <el-descriptions-item label="标题" :span="2">{{ currentDocument.title }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ currentDocument.category_name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentDocument.status)">{{ currentDocument.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="作者">{{ currentDocument.author_name }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(currentDocument.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ currentDocument.description || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider>批注</el-divider>
        <div class="annotations-section">
          <el-button type="primary" size="small" @click="showAnnotationDialog = true">添加批注</el-button>
          <div v-for="ann in currentDocument.annotations" :key="ann.id" class="annotation-item">
            <div class="annotation-header">
              <span class="annotator">{{ ann.annotated_by_name }}</span>
              <el-tag size="small">{{ ann.annotation_type }}</el-tag>
              <span class="time">{{ formatDate(ann.created_at) }}</span>
              <el-tag v-if="ann.resolved" type="success" size="small">已解决</el-tag>
            </div>
            <div class="annotation-content">{{ ann.content }}</div>
            <div v-if="ann.replies?.length" class="replies">
              <div v-for="reply in ann.replies" :key="reply.id" class="reply-item">
                <span class="annotator">{{ reply.annotated_by_name }}:</span>
                {{ reply.content }}
              </div>
            </div>
          </div>
        </div>

        <el-divider>版本历史</el-divider>
        <el-timeline>
          <el-timeline-item v-for="ver in currentDocument.versions" :key="ver.id" :timestamp="formatDate(ver.created_at)">
            <strong>版本 {{ ver.version }}.{{ ver.revision }}</strong>
            <p>{{ ver.change_description }}</p>
            <p class="text-muted">创建人: {{ ver.created_by_name }}</p>
          </el-timeline-item>
        </el-timeline>
      </template>
    </el-drawer>

    <!-- 发放 -->
    <el-dialog v-model="distributeDialogVisible" title="文档发放" width="500px">
      <el-form label-width="100px">
        <el-form-item label="文档">{{ distributeRow?.title || distributeRow?.document_no }}</el-form-item>
        <el-form-item label="备注">
          <el-input v-model="distributeForm.remarks" type="textarea" :rows="2" placeholder="发放说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="distributeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="distributeSaving" @click="handleDistributeSave">确认发放</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Upload, Document, UploadFilled } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const uploading = ref(false)
const showUploadDialog = ref(false)
const showDetailDrawer = ref(false)
const distributeDialogVisible = ref(false)
const distributeRow = ref(null)
const distributeForm = reactive({ recipients: [], remarks: '' })
const distributeSaving = ref(false)
const showAnnotationDialog = ref(false)

const documents = ref([])
const categoryTree = ref([])
const projects = ref([])
const currentDocument = ref(null)

const filters = reactive({
  keyword: '',
  category: null,
  status: '',
  project: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const uploadForm = reactive({
  title: '',
  category: null,
  project: null,
  control_level: 'CONTROLLED',
  description: '',
  keywords: [],
  file: null
})

const uploadRules = {
  title: [{ required: true, message: '请输入文档标题', trigger: 'blur' }],
  control_level: [{ required: true, message: '请选择受控级别', trigger: 'change' }]
}

const uploadFormRef = ref(null)

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

const getStatusType = (status) => {
  const map = { DRAFT: 'info', REVIEWING: 'warning', APPROVED: 'success', RELEASED: 'primary', OBSOLETE: 'danger' }
  return map[status] || 'info'
}

const getControlType = (level) => {
  const map = { UNCONTROLLED: 'info', CONTROLLED: 'warning', CONFIDENTIAL: 'danger' }
  return map[level] || 'info'
}

const getFileColor = (type) => {
  if (type?.includes('pdf')) return '#F56C6C'
  if (type?.includes('word') || type?.includes('doc')) return '#409EFF'
  if (type?.includes('excel') || type?.includes('xls')) return '#67C23A'
  return '#909399'
}

const loadDocuments = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.category) params.category = Array.isArray(filters.category) ? filters.category[filters.category.length - 1] : filters.category
    if (filters.status) params.status = filters.status
    if (filters.project) params.project = filters.project

    const res = await request.get('/projects/tech-documents/', { params })
    documents.value = res.results || res
    pagination.total = res.count || documents.value.length
  } catch (e) {
    ElMessage.error('加载文档列表失败')
  } finally {
    loading.value = false
  }
}

const loadCategories = async () => {
  try {
    const res = await request.get('/projects/tech-doc-categories/tree/')
    categoryTree.value = res
  } catch (e) {
    console.error('加载分类失败')
  }
}

const loadProjects = async () => {
  try {
    const res = await request.get('/projects/projects/', { params: { page_size: 1000 } })
    projects.value = res.results || res
  } catch (e) {
    console.error('加载项目列表失败')
  }
}

const resetFilters = () => {
  filters.keyword = ''
  filters.category = null
  filters.status = ''
  filters.project = null
  loadDocuments()
}

const viewDocument = async (row) => {
  try {
    const res = await request.get(`/projects/tech-documents/${row.id}/`)
    currentDocument.value = res
    showDetailDrawer.value = true
    // 记录访问
    request.post(`/projects/tech-documents/${row.id}/log_access/`, { access_type: 'VIEW' })
  } catch (e) {
    ElMessage.error('加载文档详情失败')
  }
}

const downloadDocument = async (row) => {
  try {
    await request.post(`/projects/tech-documents/${row.id}/log_access/`, { access_type: 'DOWNLOAD' })
    ElMessage.success('开始下载')
    // 实际下载逻辑
  } catch (e) {
    ElMessage.error('下载失败')
  }
}

const handleFileChange = (file) => {
  uploadForm.file = file.raw
}

const submitUpload = async () => {
  try {
    await uploadFormRef.value.validate()
    uploading.value = true
    
    const formData = new FormData()
    formData.append('title', uploadForm.title)
    if (uploadForm.category) formData.append('category', uploadForm.category)
    if (uploadForm.project) formData.append('project', uploadForm.project)
    formData.append('control_level', uploadForm.control_level)
    formData.append('description', uploadForm.description)
    formData.append('keywords', JSON.stringify(uploadForm.keywords))
    if (uploadForm.file) formData.append('file', uploadForm.file)

    await request.post('/projects/tech-documents/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success('文档上传成功')
    showUploadDialog.value = false
    loadDocuments()
  } catch (e) {
    if (e !== false) ElMessage.error('上传失败')
  } finally {
    uploading.value = false
  }
}

const handleCommand = async (cmd, row) => {
  switch (cmd) {
    case 'review':
      ElMessageBox.prompt('请输入评审人ID（逗号分隔）', '提交评审').then(async ({ value }) => {
        const reviewers = value.split(',').map(v => parseInt(v.trim())).filter(v => !isNaN(v))
        await request.post(`/projects/tech-documents/${row.id}/submit_review/`, { reviewers })
        ElMessage.success('已提交评审')
        loadDocuments()
      })
      break
    case 'approve':
      await request.post(`/projects/tech-documents/${row.id}/approve/`)
      ElMessage.success('文档已批准')
      loadDocuments()
      break
    case 'release':
      await request.post(`/projects/tech-documents/${row.id}/release/`)
      ElMessage.success('文档已发布')
      loadDocuments()
      break
    case 'revision':
      ElMessageBox.prompt('请输入变更说明', '创建修订版').then(async ({ value }) => {
        await request.post(`/projects/tech-documents/${row.id}/new_revision/`, { change_description: value })
        ElMessage.success('修订版已创建')
        loadDocuments()
      })
      break
    case 'distribute':
      distributeRow.value = row
      Object.assign(distributeForm, { recipients: [], remarks: '' })
      distributeDialogVisible.value = true
      break
    case 'log':
      const logs = await request.get(`/projects/tech-documents/${row.id}/access_log/`)
      ElMessage.info(`共 ${logs.length} 条访问记录`)
      break
  }
}


const handleDistributeSave = async () => {
  distributeSaving.value = true
  try {
    await request.post(`/projects/tech-documents/${distributeRow.value.id}/distribute/`, distributeForm)
    ElMessage.success('发放成功')
    distributeDialogVisible.value = false
    loadDocuments()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
    else ElMessage.error('发放失败')
  } finally {
    distributeSaving.value = false
  }
}
onMounted(() => {
  loadDocuments()
  loadCategories()
  loadProjects()
})
</script>

<style scoped>
.tech-document-list {
  padding: 20px;
}
.filter-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.annotations-section {
  margin-top: 16px;
}
.annotation-item {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  margin-top: 12px;
}
.annotation-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.annotator {
  font-weight: bold;
}
.time {
  color: #909399;
  font-size: 12px;
}
.annotation-content {
  color: #606266;
}
.replies {
  margin-top: 8px;
  padding-left: 16px;
  border-left: 2px solid #dcdfe6;
}
.reply-item {
  margin-top: 4px;
  font-size: 13px;
}
.text-muted {
  color: #909399;
  font-size: 12px;
}
</style>
