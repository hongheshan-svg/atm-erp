<template>
  <div class="batch-drawing-import">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>批量图纸导入</span>
          <el-button text type="primary" @click="showFormats">
            <el-icon><QuestionFilled /></el-icon> 支持的格式
          </el-button>
        </div>
      </template>

      <!-- 项目选择 -->
      <el-form :inline="true" class="import-form">
        <el-form-item label="项目" required>
          <el-select v-model="importForm.project_id" placeholder="选择项目" filterable style="width: 300px;">
            <el-option v-for="p in projects" :key="p.id" :label="`${p.code} - ${p.name}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="选项">
          <el-checkbox v-model="importForm.auto_link">自动关联BOM</el-checkbox>
          <el-checkbox v-model="importForm.overwrite">覆盖已存在</el-checkbox>
        </el-form-item>
      </el-form>

      <!-- 文件上传区域 -->
      <el-upload
        ref="uploadRef"
        class="upload-zone"
        drag
        multiple
        :auto-upload="false"
        :file-list="fileList"
        :on-change="handleFileChange"
        :on-remove="handleFileRemove"
        :accept="acceptFormats"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处，或 <em>点击选择文件</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 PDF、DWG、DXF、STEP、STP、IGES、STL、SolidWorks、Creo、Inventor 等格式
          </div>
        </template>
      </el-upload>

      <!-- 或上传ZIP -->
      <el-divider>或上传压缩包</el-divider>
      <el-upload
        ref="zipUploadRef"
        class="zip-upload"
        :auto-upload="false"
        :limit="1"
        :file-list="zipFileList"
        :on-change="handleZipChange"
        :on-remove="handleZipRemove"
        accept=".zip"
      >
        <el-button type="primary" plain>
          <el-icon><FolderOpened /></el-icon> 选择ZIP压缩包
        </el-button>
        <template #tip>
          <span class="zip-tip">上传ZIP压缩包可批量导入多个图纸文件</span>
        </template>
      </el-upload>

      <!-- 待导入文件列表 -->
      <div v-if="parsedFiles.length" class="parsed-files">
        <h4>待导入文件 ({{ parsedFiles.length }}个)</h4>
        <el-table :data="parsedFiles" border stripe max-height="300">
          <el-table-column prop="original_filename" label="文件名" min-width="200" show-overflow-tooltip />
          <el-table-column prop="drawing_no" label="图号" width="150" />
          <el-table-column prop="version" label="版本" width="80" />
          <el-table-column prop="file_type" label="类型" width="120">
            <template #default="{ row }">
              <el-tag size="small">{{ row.file_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ $index }">
              <el-button type="danger" size="small" text @click="removeFile($index)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 操作按钮 -->
      <div class="import-actions">
        <el-button type="primary" size="large" @click="startImport" :loading="importing" :disabled="!canImport">
          <el-icon><Upload /></el-icon> 开始导入
        </el-button>
        <el-button size="large" @click="clearAll">
          <el-icon><RefreshLeft /></el-icon> 清空
        </el-button>
      </div>
    </el-card>

    <!-- 导入结果 -->
    <el-card v-if="importResult" class="result-card">
      <template #header>
        <div class="card-header">
          <span>导入结果</span>
          <el-tag :type="importResult.errors?.length ? 'warning' : 'success'">
            {{ importResult.errors?.length ? '部分成功' : '全部成功' }}
          </el-tag>
        </div>
      </template>

      <!-- 统计 -->
      <el-row :gutter="20" class="result-summary">
        <el-col :span="8">
          <el-statistic title="成功导入" :value="importResult.imported || 0">
            <template #suffix>
              <el-tag type="success" size="small">个</el-tag>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="8">
          <el-statistic title="跳过" :value="importResult.skipped || 0">
            <template #suffix>
              <el-tag type="info" size="small">个</el-tag>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="8">
          <el-statistic title="失败" :value="importResult.errors?.length || 0">
            <template #suffix>
              <el-tag type="danger" size="small">个</el-tag>
            </template>
          </el-statistic>
        </el-col>
      </el-row>

      <!-- 详细结果 -->
      <el-table :data="importResult.details || []" border stripe max-height="400">
        <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="drawing_no" label="图号" width="150" />
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column label="BOM关联" width="150">
          <template #default="{ row }">
            <span v-if="row.linked_item_sku" class="linked">
              <el-icon><Link /></el-icon> {{ row.linked_item_sku }}
            </span>
            <span v-else class="not-linked">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="备注" min-width="150" show-overflow-tooltip />
      </el-table>

      <!-- 错误信息 -->
      <div v-if="importResult.errors?.length" class="error-list">
        <h4>错误信息</h4>
        <el-alert 
          v-for="(err, idx) in importResult.errors" 
          :key="idx"
          type="error"
          :title="err.filename"
          :description="err.error"
          :closable="false"
          style="margin-bottom: 10px;"
        />
      </div>
    </el-card>

    <!-- 支持格式对话框 -->
    <el-dialog v-model="formatsDialogVisible" title="支持的文件格式" width="500px">
      <el-table :data="supportedFormats" border>
        <el-table-column prop="extension" label="扩展名" width="100" />
        <el-table-column prop="type" label="类型" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { 
  UploadFilled, FolderOpened, Delete, Upload, RefreshLeft, 
  QuestionFilled, Link 
} from '@element-plus/icons-vue'
import { getDrawingImportSupportedFormats, batchImportDrawings } from '@/api/projects/drawing'
import { getProjectList } from '@/api/projects/project'

const projects = ref([])
const fileList = ref([])
const zipFileList = ref([])
const parsedFiles = ref([])
const importing = ref(false)
const importResult = ref(null)
const formatsDialogVisible = ref(false)
const supportedFormats = ref([])

const uploadRef = ref(null)
const zipUploadRef = ref(null)

const importForm = reactive({
  project_id: null,
  auto_link: true,
  overwrite: false
})

const acceptFormats = '.pdf,.dwg,.dxf,.step,.stp,.iges,.igs,.stl,.sldprt,.sldasm,.slddrw,.prt,.asm,.drw,.ipt,.iam,.idw'

const canImport = computed(() => {
  return importForm.project_id && (fileList.value.length > 0 || zipFileList.value.length > 0)
})

const loadProjects = async () => {
  try {
    const res = await getProjectList( { params: { page_size: 1000 } })
    projects.value = res.results || res || []
  } catch (error) {
    console.error('Load projects failed:', error)
  }
}

const loadFormats = async () => {
  try {
    const res = await getDrawingImportSupportedFormats()
    supportedFormats.value = res.formats || []
  } catch (error) {
    console.error('Load formats failed:', error)
  }
}

const parseFilename = (filename) => {
  const ext = filename.split('.').pop().toLowerCase()
  const nameWithoutExt = filename.replace(/\.[^.]+$/, '')
  
  // 尝试解析版本号
  let version = 'A0'
  let drawingNo = nameWithoutExt
  
  const versionPatterns = [
    /^(.+)[-_]([A-Z]\d+)$/i,  // ABC-001-A1
    /^(.+)[-_]Rev(\d+)$/i,    // ABC-001-Rev01
    /^(.+)[-_]V(\d+)$/i,      // ABC-001-V2
    /^(.+)[-_]([A-Z])$/i,     // ABC-001-A
  ]
  
  for (const pattern of versionPatterns) {
    const match = nameWithoutExt.match(pattern)
    if (match) {
      drawingNo = match[1]
      const verStr = match[2]
      if (/^[A-Z]$/i.test(verStr)) {
        version = `${verStr.toUpperCase()}0`
      } else if (/^[A-Z]\d+$/i.test(verStr)) {
        version = verStr.toUpperCase()
      } else if (/^\d+$/.test(verStr)) {
        version = `A${verStr}`
      }
      break
    }
  }
  
  const typeMap = {
    'pdf': 'PDF', 'dwg': 'DWG', 'dxf': 'DXF',
    'step': 'STEP', 'stp': 'STP', 'iges': 'IGES', 'igs': 'IGES',
    'stl': 'STL', 'sldprt': 'SOLIDWORKS', 'sldasm': 'SOLIDWORKS', 'slddrw': 'SOLIDWORKS',
    'prt': 'CREO', 'asm': 'CREO', 'drw': 'CREO',
    'ipt': 'INVENTOR', 'iam': 'INVENTOR', 'idw': 'INVENTOR'
  }
  
  return {
    original_filename: filename,
    drawing_no: drawingNo.toUpperCase(),
    version: version,
    file_type: typeMap[ext] || 'OTHER'
  }
}

const handleFileChange = (file, newFileList) => {
  fileList.value = newFileList
  updateParsedFiles()
}

const handleFileRemove = (file, newFileList) => {
  fileList.value = newFileList
  updateParsedFiles()
}

const handleZipChange = (file, newFileList) => {
  zipFileList.value = newFileList
}

const handleZipRemove = () => {
  zipFileList.value = []
}

const updateParsedFiles = () => {
  parsedFiles.value = fileList.value.map(f => parseFilename(f.name))
}

const removeFile = (index) => {
  fileList.value.splice(index, 1)
  parsedFiles.value.splice(index, 1)
}

const clearAll = () => {
  fileList.value = []
  zipFileList.value = []
  parsedFiles.value = []
  importResult.value = null
  if (uploadRef.value) uploadRef.value.clearFiles()
  if (zipUploadRef.value) zipUploadRef.value.clearFiles()
}

const startImport = async () => {
  if (!canImport.value) {
    ElMessage.warning('请选择项目并上传文件')
    return
  }
  
  importing.value = true
  importResult.value = null
  
  try {
    const formData = new FormData()
    formData.append('project_id', importForm.project_id)
    formData.append('auto_link', importForm.auto_link)
    formData.append('overwrite', importForm.overwrite)
    
    if (zipFileList.value.length > 0) {
      formData.append('zip_file', zipFileList.value[0].raw)
    } else {
      fileList.value.forEach(file => {
        formData.append('files', file.raw)
      })
    }
    
    const res = await batchImportDrawings( formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    importResult.value = res
    
    if (res.error) {
      ElMessage.error(res.error)
    } else if (res.errors?.length) {
      ElMessage.warning(`导入完成，${res.imported}个成功，${res.errors.length}个失败`)
    } else {
      ElMessage.success(`成功导入${res.imported}个图纸`)
    }
    
    // 清空文件列表
    clearAll()
    
  } catch (error) {
    ElMessage.error('导入失败')
    console.error(error)
  } finally {
    importing.value = false
  }
}

const showFormats = () => {
  formatsDialogVisible.value = true
}

const getStatusType = (status) => {
  const types = {
    'IMPORTED': 'success',
    'SKIPPED': 'info',
    'ERROR': 'danger'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    'IMPORTED': '已导入',
    'SKIPPED': '已跳过',
    'ERROR': '失败'
  }
  return labels[status] || status
}

onMounted(() => {
  loadProjects()
  loadFormats()
})
</script>

<style scoped>
.batch-drawing-import {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.import-form {
  margin-bottom: 20px;
}

.upload-zone {
  margin: 20px 0;
}

.upload-zone :deep(.el-upload-dragger) {
  width: 100%;
}

.zip-upload {
  margin: 20px 0;
}

.zip-tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}

.parsed-files {
  margin: 20px 0;
}

.parsed-files h4 {
  margin-bottom: 10px;
  color: #303133;
}

.import-actions {
  margin: 20px 0;
  display: flex;
  gap: 10px;
}

.result-card {
  margin-top: 20px;
}

.result-summary {
  margin-bottom: 20px;
}

.linked {
  color: #67c23a;
  display: flex;
  align-items: center;
  gap: 4px;
}

.not-linked {
  color: #909399;
}

.error-list {
  margin-top: 20px;
}

.error-list h4 {
  margin-bottom: 10px;
  color: #f56c6c;
}
</style>
