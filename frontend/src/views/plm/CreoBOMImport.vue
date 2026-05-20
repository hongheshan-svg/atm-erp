<template>
  <div class="creo-bom-import">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <div>
            <span style="font-size: 16px; font-weight: bold;">CAD BOM导入</span>
            <el-tag type="info" size="small" style="margin-left: 10px;">支持 CREO / SolidWorks / AutoCAD / Inventor 等</el-tag>
          </div>
          <div>
            <el-button @click="downloadTemplate">
              <el-icon><Download /></el-icon> 下载模板
            </el-button>
            <el-button type="primary" @click="showUploadDialog = true">
              <el-icon><Upload /></el-icon> 上传BOM文件
            </el-button>
          </div>
        </div>
      </template>

      <!-- 统计卡片 -->
      <el-row :gutter="16">
        <el-col :span="4">
          <div class="stat-box">
            <div class="stat-value">{{ sessions.length }}</div>
            <div class="stat-label">导入记录</div>
          </div>
        </el-col>
        <el-col :span="4">
          <div class="stat-box success">
            <div class="stat-value">{{ sessions.filter(s => s.status === 'COMPLETED').length }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </el-col>
        <el-col :span="4">
          <div class="stat-box warning">
            <div class="stat-value">{{ sessions.filter(s => s.status === 'REVIEWING').length }}</div>
            <div class="stat-label">待确认</div>
          </div>
        </el-col>
        <el-col :span="4">
          <div class="stat-box info">
            <div class="stat-value">{{ totalMatched }}</div>
            <div class="stat-label">已匹配物料</div>
          </div>
        </el-col>
        <el-col :span="4">
          <div class="stat-box primary">
            <div class="stat-value">{{ totalCreated }}</div>
            <div class="stat-label">新建物料</div>
          </div>
        </el-col>
        <el-col :span="4">
          <div class="stat-box">
            <div class="stat-value">{{ totalImported }}</div>
            <div class="stat-label">已导入BOM</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 导入记录列表 -->
    <el-card class="list-card">
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="sessions" v-loading="loading" border stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="导入名称" min-width="180" />
        <el-table-column label="CAD软件" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="getCadType(row.detected_software || row.cad_software)">
              {{ getCadName(row.detected_software || row.cad_software) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="file_format" label="格式" width="70" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_rows" label="总行数" width="80" align="center" />
        <el-table-column prop="matched_count" label="已匹配" width="80" align="center">
          <template #default="{ row }">
            <span class="text-success">{{ row.matched_count }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="new_item_count" label="新物料" width="80" align="center">
          <template #default="{ row }">
            <span class="text-warning">{{ row.new_item_count }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="imported_count" label="已导入" width="80" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewSession(row)">查看</el-button>
            <el-button 
              v-if="row.status === 'REVIEWING' && row.new_item_count > 0" 
              size="small" 
              type="warning"
              @click="createItems(row)"
            >创建物料</el-button>
            <el-button 
              v-if="['REVIEWING', 'MATCHED'].includes(row.status)" 
              size="small" 
              type="success"
              @click="importBOM(row)"
            >导入BOM</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传CAD BOM文件" width="650px">
      <el-form :model="uploadForm" label-width="100px">
        <el-form-item label="CAD软件">
          <el-radio-group v-model="uploadForm.cad_software">
            <el-radio label="AUTO">自动识别</el-radio>
            <el-radio label="CREO">Creo/Pro-E</el-radio>
            <el-radio label="SOLIDWORKS">SolidWorks</el-radio>
            <el-radio label="AUTOCAD">AutoCAD</el-radio>
            <el-radio label="INVENTOR">Inventor</el-radio>
            <el-radio label="GENERIC">通用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="文件格式">
          <el-radio-group v-model="uploadForm.file_format">
            <el-radio label="CSV">CSV</el-radio>
            <el-radio label="XML">XML</el-radio>
            <el-radio label="XLSX">Excel</el-radio>
            <el-radio label="TXT">文本</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="BOM文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            accept=".csv,.xml,.xlsx,.xls,.txt,.bom"
            drag
          >
            <el-icon class="el-icon--upload"><Upload /></el-icon>
            <div class="el-upload__text">拖拽文件到此处或 <em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">支持 Creo/SolidWorks/AutoCAD 等CAD软件导出的 CSV, XML, Excel 格式BOM</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="导入名称">
          <el-input v-model="uploadForm.name" placeholder="可选，默认使用文件名" />
        </el-form-item>
        <el-form-item label="目标项目">
          <el-select v-model="uploadForm.project_id" clearable placeholder="选择项目（可选）" style="width: 100%">
            <el-option 
              v-for="p in projects" 
              :key="p.id" 
              :label="p.name" 
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="导入选项">
          <el-checkbox v-model="uploadForm.options.auto_create">自动创建新物料</el-checkbox>
          <el-checkbox v-model="uploadForm.options.match_by_name">按名称匹配</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="doUpload">上传并解析</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="showDetail" title="导入详情" size="80%">
      <template v-if="currentSession">
        <el-descriptions :column="4" border class="mb-4">
          <el-descriptions-item label="名称">{{ currentSession.name }}</el-descriptions-item>
          <el-descriptions-item label="CAD软件">
            <el-tag :type="getCadType(currentSession.detected_software || currentSession.cad_software)">
              {{ getCadName(currentSession.detected_software || currentSession.cad_software) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentSession.status)">{{ currentSession.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="总行数">{{ currentSession.total_rows }}</el-descriptions-item>
          <el-descriptions-item label="已匹配">{{ currentSession.matched_count }}</el-descriptions-item>
          <el-descriptions-item label="新物料">{{ currentSession.new_item_count }}</el-descriptions-item>
          <el-descriptions-item label="已导入">{{ currentSession.imported_count }}</el-descriptions-item>
          <el-descriptions-item label="错误">{{ currentSession.error_count }}</el-descriptions-item>
        </el-descriptions>

        <!-- 操作按钮 -->
        <div class="action-bar">
          <el-button 
            v-if="currentSession.new_item_count > 0" 
            type="warning"
            @click="createItems(currentSession)"
          >
            <el-icon><Plus /></el-icon> 创建新物料 ({{ currentSession.new_item_count }})
          </el-button>
          <el-dropdown split-button type="success" @click="importBOM(currentSession)" v-if="currentSession.status === 'REVIEWING'">
            <el-icon><Download /></el-icon> 导入到项目BOM
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="importBOM(currentSession)">普通导入</el-dropdown-item>
                <el-dropdown-item @click="importHierarchicalBOM(currentSession)">
                  <el-icon><Connection /></el-icon> 层级导入(保留父子关系)
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <!-- 导入项列表 -->
        <el-table :data="currentSession.items" border stripe max-height="500" row-class-name="bom-row">
          <el-table-column prop="row_number" label="行" width="50" />
          <el-table-column label="层级" width="70">
            <template #default="{ row }">
              <span class="level-indicator" :style="{ paddingLeft: (row.level || 0) * 12 + 'px' }">
                <el-tag size="small" :type="row.level === 0 ? 'primary' : 'info'">L{{ row.level }}</el-tag>
              </span>
            </template>
          </el-table-column>
          <el-table-column label="物料编码" width="180">
            <template #default="{ row }">
              <div :style="{ paddingLeft: (row.level || 0) * 12 + 'px' }">
                <span v-if="row.level > 0" class="tree-indent">└ </span>
                <span class="part-number">{{ row.part_number }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="part_name" label="物料名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="quantity" label="数量" width="70" align="right" />
          <el-table-column prop="unit" label="单位" width="50" />
          <el-table-column prop="material" label="材料" width="100" show-overflow-tooltip />
          <el-table-column label="建议属性" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.suggested_item_property" size="small" :type="getPropertyType(row.suggested_item_property)">
                {{ getPropertyLabel(row.suggested_item_property) }}
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="getItemStatusType(row.status)" size="small">
                {{ row.status_display }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="match_score" label="匹配度" width="70">
            <template #default="{ row }">
              <span v-if="row.match_score > 0" :class="getMatchScoreClass(row.match_score)">
                {{ (row.match_score * 100).toFixed(0) }}%
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button 
                v-if="row.status === 'NEW'" 
                size="small" 
                @click="showMatchDialog(row)"
              >手动匹配</el-button>
              <el-button 
                v-if="row.match_candidates && row.match_candidates.length > 0" 
                size="small" 
                type="info"
                @click="showCandidates(row)"
              >候选</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>

    <!-- 手动匹配对话框 -->
    <el-dialog v-model="showManualMatch" title="手动匹配物料" width="600px">
      <el-form v-if="matchingItem">
        <el-form-item label="物料编码">
          <strong>{{ matchingItem.part_number }}</strong>
        </el-form-item>
        <el-form-item label="物料名称">
          <strong>{{ matchingItem.part_name }}</strong>
        </el-form-item>
        <el-form-item label="匹配物料">
          <el-select 
            v-model="selectedMaterialId" 
            filterable 
            remote 
            :remote-method="searchMaterials"
            placeholder="搜索物料"
            style="width: 100%"
          >
            <el-option
              v-for="m in materialSearchResults"
              :key="m.id"
              :label="`${m.sku} - ${m.name}`"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showManualMatch = false">取消</el-button>
        <el-button type="primary" @click="doManualMatch">确认匹配</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getCreoBOMImportList, getCreoBOMImport, uploadCreoBOM, createCreoBOMItems, importCreoBOM, importCreoBOMHierarchy, manualMatchCreoBOM } from '@/api/plm/creo'
import { getProjectList } from '@/api/projects/project'
import { getItemList } from '@/api/masterdata'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Plus, Download, DocumentAdd, Connection } from '@element-plus/icons-vue'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/plm_creo/')


const loading = ref(false)
const uploading = ref(false)
const sessions = ref([])
const projects = ref([])
const showUploadDialog = ref(false)
const showDetail = ref(false)
const showManualMatch = ref(false)
const currentSession = ref(null)
const matchingItem = ref(null)
const selectedMaterialId = ref(null)
const materialSearchResults = ref([])
const uploadRef = ref(null)
const uploadFile = ref(null)

const uploadForm = ref({
  file_format: 'CSV',
  cad_software: 'AUTO',
  name: '',
  project_id: null,
  options: {
    auto_create: false,
    match_by_name: true
  }
})

const cadSoftwareMap = {
  'AUTO': { name: '自动识别', type: 'info' },
  'CREO': { name: 'Creo/Pro-E', type: 'warning' },
  'SOLIDWORKS': { name: 'SolidWorks', type: 'primary' },
  'AUTOCAD': { name: 'AutoCAD', type: 'success' },
  'INVENTOR': { name: 'Inventor', type: '' },
  'CATIA': { name: 'CATIA', type: 'danger' },
  'UG': { name: 'UG/NX', type: '' },
  'FUSION360': { name: 'Fusion 360', type: 'info' },
  'GENERIC': { name: '通用', type: 'info' },
}

const getCadName = (code) => cadSoftwareMap[code]?.name || code
const getCadType = (code) => cadSoftwareMap[code]?.type || 'info'

const totalMatched = computed(() => sessions.value.reduce((sum, s) => sum + (s.matched_count || 0), 0))
const totalCreated = computed(() => sessions.value.reduce((sum, s) => sum + (s.new_item_count || 0), 0))
const totalImported = computed(() => sessions.value.reduce((sum, s) => sum + (s.imported_count || 0), 0))

const getStatusType = (status) => {
  const map = {
    'COMPLETED': 'success',
    'REVIEWING': 'warning',
    'IMPORTING': 'primary',
    'FAILED': 'danger',
    'CANCELLED': 'info'
  }
  return map[status] || 'default'
}

const getItemStatusType = (status) => {
  const map = {
    'MATCHED': 'success',
    'CREATED': 'success',
    'IMPORTED': 'success',
    'NEW': 'warning',
    'PENDING': 'info',
    'ERROR': 'danger',
    'SKIPPED': 'info'
  }
  return map[status] || 'default'
}

const getPropertyType = (prop) => {
  const map = {
    'STANDARD': 'info',
    'PURCHASED': 'primary',
    'OUTSOURCED': 'warning',
    'SELF_MADE': 'success',
    'ASSEMBLY': 'danger'
  }
  return map[prop] || 'info'
}

const getPropertyLabel = (prop) => {
  const map = {
    'STANDARD': '标准件',
    'PURCHASED': '外购件',
    'OUTSOURCED': '外协件',
    'SELF_MADE': '自制件',
    'ASSEMBLY': '组件'
  }
  return map[prop] || prop
}

const getMatchScoreClass = (score) => {
  if (score >= 0.9) return 'match-high'
  if (score >= 0.7) return 'match-medium'
  return 'match-low'
}

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

const loadSessions = async () => {
  loading.value = true
  try {
    const res = await getCreoBOMImportList()
    sessions.value = res.results || res || []
  } catch (e) {
    console.error('加载失败', e)
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjectList()
    projects.value = res.results || res || []
  } catch (e) {
    console.error('加载项目失败', e)
  }
}

const handleFileChange = (file) => {
  uploadFile.value = file.raw
  if (!uploadForm.value.name) {
    uploadForm.value.name = file.name
  }
  // 根据文件扩展名自动设置格式
  const ext = file.name.split('.').pop().toLowerCase()
  const formatMap = { csv: 'CSV', xml: 'XML', xlsx: 'XLSX', xls: 'XLSX', txt: 'TXT' }
  if (formatMap[ext]) {
    uploadForm.value.file_format = formatMap[ext]
  }
}

const doUpload = async () => {
  if (!uploadFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadFile.value)
    formData.append('file_format', uploadForm.value.file_format)
    formData.append('cad_software', uploadForm.value.cad_software)
    if (uploadForm.value.name) formData.append('name', uploadForm.value.name)
    if (uploadForm.value.project_id) formData.append('project_id', uploadForm.value.project_id)
    formData.append('options', JSON.stringify(uploadForm.value.options))
    
    const res = await uploadCreoBOM(formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    ElMessage.success(`解析完成: 总计${res.result.total}行, 匹配${res.result.matched}, 新物料${res.result.new}`)
    showUploadDialog.value = false
    uploadFile.value = null
    uploadForm.value = { file_format: 'CSV', cad_software: 'AUTO', name: '', project_id: null, options: { auto_create: false, match_by_name: true } }
    loadSessions()
    
    // 自动打开详情
    currentSession.value = res.session
    showDetail.value = true
  } catch (e) {
    ElMessage.error('上传失败: ' + (e.response?.data?.error || e.message))
  } finally {
    uploading.value = false
  }
}

const viewSession = async (session) => {
  try {
    const res = await getCreoBOMImport(session.id)
    currentSession.value = res
    showDetail.value = true
  } catch (e) {
    ElMessage.error('加载详情失败')
  }
}

const createItems = async (session) => {
  try {
    await ElMessageBox.confirm(
      `确认为 ${session.new_item_count} 个新物料创建物料主数据？`,
      '创建物料'
    )
    
    const res = await createCreoBOMItems(session.id, {
      options: { sku_prefix: 'CREO-' }
    })
    
    ElMessage.success(`成功创建 ${res.result.created} 个物料`)
    loadSessions()
    if (currentSession.value?.id === session.id) {
      currentSession.value = res.session
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('创建失败: ' + (e.response?.data?.error || e.message))
    }
  }
}

const importBOM = async (session) => {
  if (!session.project_id) {
    // 先选择项目
    const { value } = await ElMessageBox.prompt('请输入项目ID', '选择项目', {
      inputPattern: /^\d+$/,
      inputErrorMessage: '请输入有效的项目ID'
    }).catch(() => ({ value: null }))
    
    if (!value) return
    session.project_id = parseInt(value)
  }
  
  try {
    const res = await importCreoBOM(session.id, {
      project_id: session.project_id
    })
    
    ElMessage.success(`成功导入 ${res.result.imported} 条BOM`)
    loadSessions()
    if (currentSession.value?.id === session.id) {
      currentSession.value = res.session
    }
  } catch (e) {
    ElMessage.error('导入失败: ' + (e.response?.data?.error || e.message))
  }
}

const importHierarchicalBOM = async (session) => {
  if (!session.project_id) {
    // 先选择项目
    const { value } = await ElMessageBox.prompt('请输入项目ID', '选择项目', {
      inputPattern: /^\d+$/,
      inputErrorMessage: '请输入有效的项目ID'
    }).catch(() => ({ value: null }))
    
    if (!value) return
    session.project_id = parseInt(value)
  }
  
  try {
    const res = await importCreoBOMHierarchy(session.id, {
      project_id: session.project_id
    })
    
    ElMessage.success(`成功导入 ${res.result.imported} 条BOM（${res.result.hierarchy_levels || 0}层结构）`)
    loadSessions()
    if (currentSession.value?.id === session.id) {
      currentSession.value = res.session
    }
  } catch (e) {
    ElMessage.error('层级导入失败: ' + (e.response?.data?.error || e.message))
  }
}

const showMatchDialog = (item) => {
  matchingItem.value = item
  selectedMaterialId.value = null
  materialSearchResults.value = []
  showManualMatch.value = true
}

const showCandidates = (item) => {
  materialSearchResults.value = item.match_candidates.map(c => ({
    id: c.id,
    sku: c.sku,
    name: c.name
  }))
  matchingItem.value = item
  selectedMaterialId.value = null
  showManualMatch.value = true
}

const searchMaterials = async (query) => {
  if (query.length < 2) return
  try {
    const res = await getItemList({ search: query, page_size: 20 })
    materialSearchResults.value = res.results || res || []
  } catch (e) {
    console.error('搜索物料失败', e)
  }
}

const doManualMatch = async () => {
  if (!selectedMaterialId.value) {
    ElMessage.warning('请选择物料')
    return
  }
  
  try {
    await manualMatchCreoBOM(currentSession.value.id, {
      item_id: matchingItem.value.id,
      matched_material_id: selectedMaterialId.value
    })
    
    ElMessage.success('匹配成功')
    showManualMatch.value = false
    viewSession(currentSession.value)
  } catch (e) {
    ElMessage.error('匹配失败: ' + (e.response?.data?.error || e.message))
  }
}

const downloadTemplate = () => {
  // 下载CAD BOM导入模板
  window.open('/api/projects/creo-bom-imports/download_template/', '_blank')
}

onMounted(() => {
  loadSessions()
  loadProjects()
})
</script>

<style scoped>
.creo-bom-import {
  padding: 20px;
}

.header-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-box {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}

.stat-box.success { background: #f0f9eb; }
.stat-box.warning { background: #fdf6ec; }
.stat-box.info { background: #f4f4f5; }
.stat-box.primary { background: #ecf5ff; }

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.text-success { color: #67c23a; }
.text-warning { color: #e6a23c; }

.list-card {
  margin-bottom: 20px;
}

.action-bar {
  margin-bottom: 16px;
}

.mb-4 {
  margin-bottom: 16px;
}

/* BOM层级显示样式 */
.tree-indent {
  color: #c0c4cc;
  font-family: monospace;
}

.part-number {
  font-weight: 500;
  color: #409eff;
}

.level-indicator {
  display: inline-block;
}

/* 匹配度颜色 */
.match-high {
  color: #67c23a;
  font-weight: bold;
}

.match-medium {
  color: #e6a23c;
  font-weight: bold;
}

.match-low {
  color: #f56c6c;
}
</style>
