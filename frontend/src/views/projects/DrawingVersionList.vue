<template>
  <div class="drawing-version-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>图纸版本管理</span>
          <div>
            <el-input v-model="queryParams.search" placeholder="搜索图纸编号/名称" clearable style="width: 220px; margin-right: 12px"
              @keyup.enter="loadList" />
            <el-select v-model="queryParams.status" placeholder="状态" clearable style="width: 120px; margin-right: 12px" @change="loadList">
              <el-option label="草稿" value="draft" />
              <el-option label="审核中" value="reviewing" />
              <el-option label="已批准" value="approved" />
              <el-option label="已发布" value="released" />
              <el-option label="已废弃" value="obsolete" />
            </el-select>
            <el-button type="primary" @click="showUploadDialog = true">
              <el-icon><Upload /></el-icon>上传新版本
            </el-button>
          </div>
        </div>
      </template>

      <!-- 批量操作 -->

      <div v-if="selectedRows.length > 0" class="batch-toolbar">

        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>

        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>

        <el-button size="small" @click="batchExport">导出选中</el-button>

      </div>

      <el-table :data="drawingList" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="drawing_number" label="图纸编号" width="150" />
        <el-table-column prop="drawing_name" label="图纸名称" min-width="200" />
        <el-table-column prop="version" label="版本" width="80" align="center">
          <template #default="{ row }">
            <el-tag>V{{ row.version }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="revision" label="修订号" width="80" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="change_description" label="变更说明" min-width="200" show-overflow-tooltip />
        <el-table-column prop="affected_parts_count" label="影响零件" width="100" align="center">
          <template #default="{ row }">
            <el-badge :value="row.affected_parts_count || 0" :type="row.affected_parts_count > 0 ? 'warning' : 'info'" />
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="创建人" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="viewTimeline(row)">版本线</el-button>
            <el-button size="small" link type="warning" @click="submitReview(row)" v-if="row.status === 'draft'">提交审核</el-button>
            <el-button size="small" link type="success" @click="approveDrawing(row)" v-if="row.status === 'reviewing'">批准</el-button>
            <el-button size="small" link type="danger" @click="rejectDrawing(row)" v-if="row.status === 'reviewing'">驳回</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size"
          :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @change="loadList" />
      </div>
    </el-card>

    <!-- 版本时间线 -->
    <el-drawer v-model="timelineVisible" title="版本时间线" size="500px">
      <el-timeline>
        <el-timeline-item v-for="item in timeline" :key="item.id" :timestamp="item.created_at" :type="statusType(item.status)" placement="top">
          <el-card shadow="hover">
            <h4>V{{ item.version }}.{{ item.revision }} — {{ statusLabel(item.status) }}</h4>
            <p>{{ item.change_description }}</p>
            <p style="color:#909399; font-size: 12px">创建人: {{ item.created_by_name }}</p>
          </el-card>
        </el-timeline-item>
      </el-timeline>
    </el-drawer>

    <!-- 上传新版本对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传新图纸版本" width="600px">
      <el-form :model="uploadForm" ref="uploadFormRef" label-width="100px">
        <el-form-item label="图纸编号" prop="drawing_number" :rules="[{required:true, message:'必填'}]">
          <el-input v-model="uploadForm.drawing_number" />
        </el-form-item>
        <el-form-item label="图纸名称" prop="drawing_name" :rules="[{required:true, message:'必填'}]">
          <el-input v-model="uploadForm.drawing_name" />
        </el-form-item>
        <el-form-item label="变更说明" prop="change_description">
          <el-input type="textarea" v-model="uploadForm.change_description" :rows="3" />
        </el-form-item>
        <el-form-item label="图纸文件">
          <el-upload action="#" :auto-upload="false" :limit="1" :on-change="handleFileChange">
            <el-button type="primary"><el-icon><Upload /></el-icon>选择文件</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" @click="handleUpload" :loading="submitLoading">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import {
getDrawingVersions, createDrawingVersion, getDrawingTimeline,
  approveDrawingVersion, rejectDrawingVersion, submitDrawingReview
} from '@/api/projects/enhancement'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects_enhancement/')


const loading = ref(false)
const submitLoading = ref(false)
const drawingList = ref([])
const total = ref(0)
const timelineVisible = ref(false)
const timeline = ref([])
const showUploadDialog = ref(false)
const uploadFormRef = ref(null)

const queryParams = reactive({ page: 1, page_size: 20, search: '', status: '' })
const uploadForm = reactive({ drawing_number: '', drawing_name: '', change_description: '', file: null })

const statusType = (s) => ({ draft: 'info', reviewing: 'warning', approved: 'success', released: '', obsolete: 'danger' }[s] || 'info')
const statusLabel = (s) => ({ draft: '草稿', reviewing: '审核中', approved: '已批准', released: '已发布', obsolete: '已废弃' }[s] || s)

const loadList = async () => {
  loading.value = true
  try {
    const params = { ...queryParams }
    if (!params.search) delete params.search
    if (!params.status) delete params.status
    const res = await getDrawingVersions(params)
    drawingList.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
  } finally { loading.value = false }
}

const viewTimeline = async (row) => {
  const res = await getDrawingTimeline(row.drawing_number)
  timeline.value = res.data || res || []
  timelineVisible.value = true
}

const submitReview = async (row) => {
  await ElMessageBox.confirm('确认提交审核？', '提示')
  try {
    await submitDrawingReview(row.id)
    ElMessage.success('已提交审核')
    loadList()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '提交审核失败')
  }
}

const approveDrawing = async (row) => {
  await ElMessageBox.confirm('确认批准该图纸版本？', '批准')
  await approveDrawingVersion(row.id)
  ElMessage.success('批准成功')
  loadList()
}

const rejectDrawing = async (row) => {
  const { value } = await ElMessageBox.prompt('请输入驳回原因', '驳回', { inputType: 'textarea' })
  await rejectDrawingVersion(row.id, { reason: value })
  ElMessage.success('已驳回')
  loadList()
}

const handleFileChange = (file) => { uploadForm.file = file.raw }

const handleUpload = async () => {
  await uploadFormRef.value.validate()
  submitLoading.value = true
  try {
    await createDrawingVersion(uploadForm)
    ElMessage.success('上传成功')
    showUploadDialog.value = false
    loadList()
  } finally { submitLoading.value = false }
}

onMounted(() => { loadList() })
</script>

<style scoped>
.drawing-version-list { padding: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
