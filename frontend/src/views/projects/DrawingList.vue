<template>
  <div class="drawing-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>图纸管理</span>
          <div class="header-actions">
            <el-select v-model="selectedProject" placeholder="选择项目" clearable filterable style="width: 250px; margin-right: 10px;" @change="loadDrawings">
              <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
            </el-select>
            <el-button type="primary" @click="handleAdd" :disabled="!selectedProject">
              <el-icon><Plus /></el-icon>
              新增图纸
            </el-button>
          </div>
        </div>
      </template>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="图纸号">
          <el-input v-model="searchForm.drawing_no" placeholder="请输入图纸号" clearable style="width: 150px;" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 120px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="审核中" value="REVIEWING" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已发布" value="RELEASED" />
            <el-option label="已废弃" value="OBSOLETE" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件类型">
          <el-select v-model="searchForm.file_type" placeholder="选择类型" clearable style="width: 120px;">
            <el-option label="PDF" value="PDF" />
            <el-option label="STEP" value="STEP" />
            <el-option label="STP" value="STP" />
            <el-option label="DWG" value="DWG" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadDrawings">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 提示信息 -->
      <el-alert type="info" :closable="false" style="margin-bottom: 15px;">
        <template #title>
          <span>图纸放公共盘，图纸号必须一致（如：PDF、3D、STEP）。图纸新增或变更必须发邮件提醒。</span>
        </template>
      </el-alert>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <!-- 数据表格 -->
      <el-table :data="drawings" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="drawing_no" label="图纸号" width="120" />
        <el-table-column prop="name" label="图纸名称" min-width="150" show-overflow-tooltip />
        <el-table-column label="版本" width="80" align="center">
          <template #default="{ row }">
            {{ row.version }}.{{ row.revision }}
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="项目" width="150" show-overflow-tooltip />
        <el-table-column prop="item_sku" label="关联物料" width="100" />
        <el-table-column prop="file_type_display" label="文件类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getFileTypeTag(row.file_type)" size="small">{{ row.file_type_display || row.file_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="public_share_path" label="公共盘路径" min-width="180" show-overflow-tooltip />
        <el-table-column prop="status_display" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="designer_name" label="设计者" width="90" />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link @click="handleView(row)">查看</el-button>
            <el-button size="small" link @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" link type="warning" @click="handleSubmitReview(row)" v-if="row.status === 'DRAFT'">提审</el-button>
            <el-button size="small" link type="success" @click="handleApprove(row)" v-if="row.status === 'REVIEWING'">批准</el-button>
            <el-button size="small" link type="primary" @click="handleRelease(row)" v-if="row.status === 'APPROVED'">发布</el-button>
            <el-button size="small" link type="info" @click="handleNewRevision(row)" v-if="row.status === 'RELEASED'">新版本</el-button>
            <el-button v-if="canDelete && row.status === 'DRAFT'" size="small" link type="danger" @click="deleteRow(row)" :loading="deleteLoading">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadDrawings"
        @current-change="loadDrawings"
        style="margin-top: 16px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="图纸号" prop="drawing_no">
              <el-input v-model="form.drawing_no" placeholder="请输入图纸号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="图纸名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入图纸名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="版本" prop="version">
              <el-input v-model="form.version" placeholder="A0" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="文件类型" prop="file_type">
              <el-select v-model="form.file_type" placeholder="选择类型" style="width: 100%;">
                <el-option label="PDF" value="PDF" />
                <el-option label="STEP 3D" value="STEP" />
                <el-option label="STP 3D" value="STP" />
                <el-option label="AutoCAD DWG" value="DWG" />
                <el-option label="DXF" value="DXF" />
                <el-option label="SolidWorks" value="SOLIDWORKS" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="关联物料">
              <el-select v-model="form.item" placeholder="选择物料" clearable filterable style="width: 100%;">
                <el-option v-for="item in items" :key="item.id" :label="`${item.sku} - ${item.name}`" :value="item.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="公共盘路径" prop="public_share_path">
          <el-input v-model="form.public_share_path" placeholder="\\192.168.x.x\shared\drawings\项目名\图纸号.pdf">
            <template #prepend>路径</template>
          </el-input>
        </el-form-item>
        <el-form-item label="文件路径">
          <el-input v-model="form.file_path" placeholder="本地或服务器文件路径" />
        </el-form-item>
        <el-form-item label="变更说明">
          <el-input v-model="form.change_description" type="textarea" :rows="2" placeholder="版本变更说明" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新版本对话框 -->
    <el-dialog v-model="revisionDialogVisible" title="创建新版本" width="500px">
      <el-form label-width="100px">
        <el-form-item label="原版本">
          <el-input :value="`${currentDrawing?.version}.${currentDrawing?.revision}`" disabled />
        </el-form-item>
        <el-form-item label="变更说明" required>
          <el-input v-model="revisionForm.change_description" type="textarea" :rows="3" placeholder="请输入变更说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="revisionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitNewRevision" :loading="saving">创建新版本</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/projects/drawings/',
  { onSuccess: () => loadDrawings(), confirmTitle: '删除图纸', confirmMessage: '确定要删除该图纸吗？' }
)

const loading = ref(false)
const saving = ref(false)
const drawings = ref([])
const projects = ref([])
const items = ref([])
const selectedProject = ref(null)
const dialogVisible = ref(false)
const dialogTitle = ref('新增图纸')
const revisionDialogVisible = ref(false)
const currentDrawing = ref(null)
const formRef = ref(null)

const searchForm = reactive({
  drawing_no: '',
  status: '',
  file_type: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  drawing_no: '',
  name: '',
  version: 'A0',
  file_type: 'PDF',
  item: null,
  file_path: '',
  public_share_path: '',
  change_description: '',
  notes: ''
})

const revisionForm = reactive({
  change_description: ''
})

const rules = {
  drawing_no: [{ required: true, message: '请输入图纸号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入图纸名称', trigger: 'blur' }],
  file_type: [{ required: true, message: '请选择文件类型', trigger: 'change' }]
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'REVIEWING': 'warning',
    'APPROVED': 'success',
    'RELEASED': 'primary',
    'OBSOLETE': 'danger'
  }
  return types[status] || 'info'
}

const getFileTypeTag = (type) => {
  const types = {
    'PDF': '',
    'STEP': 'success',
    'STP': 'success',
    'DWG': 'warning',
    'SOLIDWORKS': 'primary'
  }
  return types[type] || 'info'
}

const loadProjects = async () => {
  try {
    const res = await request.get('/projects/projects/', { params: { page_size: 200 } })
    projects.value = res.results || res || []
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const loadItems = async () => {
  try {
    const res = await request.get('/masterdata/items/', { params: { page_size: 500 } })
    items.value = res.results || res || []
  } catch (error) {
    console.error('加载物料失败:', error)
  }
}

const loadDrawings = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    if (selectedProject.value) {
      params.project = selectedProject.value
    }
    Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
    
    const res = await request.get('/projects/drawings/', { params })
    drawings.value = res.results || res || []
    pagination.total = res.count || 0
  } catch (error) {
    ElMessage.error('加载图纸列表失败')
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.drawing_no = ''
  searchForm.status = ''
  searchForm.file_type = ''
  pagination.page = 1
  loadDrawings()
}

const handleAdd = () => {
  dialogTitle.value = '新增图纸'
  Object.assign(form, {
    id: null,
    drawing_no: '',
    name: '',
    version: 'A0',
    file_type: 'PDF',
    item: null,
    file_path: '',
    public_share_path: '',
    change_description: '',
    notes: ''
  })
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑图纸'
  Object.assign(form, {
    id: row.id,
    drawing_no: row.drawing_no,
    name: row.name,
    version: row.version,
    file_type: row.file_type,
    item: row.item,
    file_path: row.file_path,
    public_share_path: row.public_share_path,
    change_description: row.change_description,
    notes: row.notes
  })
  dialogVisible.value = true
}

const handleView = (row) => {
  ElMessage.info(`查看图纸: ${row.drawing_no} - ${row.name}`)
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    
    const payload = {
      ...form,
      project: selectedProject.value
    }
    
    if (form.id) {
      await request.put(`/projects/drawings/${form.id}/`, payload)
      ElMessage.success('图纸更新成功')
    } else {
      await request.post('/projects/drawings/', payload)
      ElMessage.success('图纸创建成功')
    }
    
    dialogVisible.value = false
    loadDrawings()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '保存失败')
    }
  } finally {
    saving.value = false
  }
}

const handleSubmitReview = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交该图纸进行审核吗？', '提交审核', { type: 'warning' })
    await request.post(`/projects/drawings/${row.id}/submit_review/`)
    ElMessage.success('已提交审核')
    loadDrawings()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '提交失败')
    }
  }
}

const handleApprove = async (row) => {
  try {
    await ElMessageBox.confirm('确定要批准该图纸吗？', '批准确认', { type: 'warning' })
    await request.post(`/projects/drawings/${row.id}/approve/`)
    ElMessage.success('图纸已批准')
    loadDrawings()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '批准失败')
    }
  }
}

const handleRelease = async (row) => {
  try {
    await ElMessageBox.confirm('确定要发布该图纸吗？发布后将发送变更通知邮件。', '发布确认', { type: 'warning' })
    await request.post(`/projects/drawings/${row.id}/release/`)
    ElMessage.success('图纸已发布，变更通知已发送')
    loadDrawings()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '发布失败')
    }
  }
}

const handleNewRevision = (row) => {
  currentDrawing.value = row
  revisionForm.change_description = ''
  revisionDialogVisible.value = true
}

const submitNewRevision = async () => {
  if (!revisionForm.change_description) {
    ElMessage.warning('请输入变更说明')
    return
  }
  
  saving.value = true
  try {
    await request.post(`/projects/drawings/${currentDrawing.value.id}/new_revision/`, {
      change_description: revisionForm.change_description
    })
    ElMessage.success('新版本创建成功')
    revisionDialogVisible.value = false
    loadDrawings()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '创建失败')
  } finally {
    saving.value = false
  }
}

// handleDelete 已被 useBatchDelete 的 deleteRow 替代

onMounted(() => {
  loadProjects()
  loadItems()
  loadDrawings()
})
</script>

<style scoped>
.drawing-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
}

.search-form {
  margin-bottom: 16px;
}
</style>

