<template>
  <div class="bom-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>项目BOM清单</span>
          <div class="header-actions">
            <el-select v-model="selectedProject" placeholder="选择项目" clearable filterable style="width: 250px; margin-right: 10px;">
              <el-option
                v-for="project in projects"
                :key="project.id"
                :label="project.name"
                :value="project.id"
              />
            </el-select>
            <el-button type="primary" @click="handleAdd" :disabled="!selectedProject">
              <el-icon><Plus /></el-icon>
              添加物料
            </el-button>
            <el-dropdown style="margin-left: 10px;" :disabled="!selectedProject">
              <el-button type="success">
                导入/导出 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleExportExcel" :disabled="!bomItems.length">
                    <el-icon><Download /></el-icon> 导出Excel
                  </el-dropdown-item>
                  <el-dropdown-item @click="handleImport">
                    <el-icon><Upload /></el-icon> 导入Excel
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="handleDownloadTemplate">
                    <el-icon><Document /></el-icon> 下载导入模板
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="handleCopyFromProject">
                    <el-icon><CopyDocument /></el-icon> 从其他项目复制
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button type="warning" @click="handleGeneratePR" :disabled="!selectedProject || !bomItems.length" style="margin-left: 10px;">
              <el-icon><Document /></el-icon>
              生成采购申请
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- BOM统计 -->
      <el-row :gutter="20" class="stats-row" v-if="selectedProject">
        <el-col :span="6">
          <el-statistic title="物料种类" :value="bomItems.length" suffix="种" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="计划总量" :value="totalPlannedQty" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="已领用" :value="totalActualQty" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="预估成本" :value="totalEstimatedCost" :precision="2" prefix="¥" />
        </el-col>
      </el-row>
      
      <!-- 搜索栏 -->
      <div class="search-bar" v-if="selectedProject">
        <el-input 
          v-model="searchKeyword" 
          placeholder="搜索物料编码/名称/规格" 
          clearable 
          style="width: 300px; margin-right: 15px;"
          @input="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <span v-if="selectedRows.length > 0" class="selection-info">
          已选择 <el-tag type="primary" size="small">{{ selectedRows.length }}</el-tag> 项
          <el-button type="warning" size="small" @click="handleGeneratePRFromSelected" style="margin-left: 10px;">
            <el-icon><Document /></el-icon>
            生成选中项采购申请
          </el-button>
          <el-button type="danger" size="small" @click="handleBatchDelete" style="margin-left: 5px;">
            <el-icon><Delete /></el-icon>
            批量删除
          </el-button>
          <el-button size="small" @click="clearSelection" style="margin-left: 5px;">
            取消选择
          </el-button>
        </span>
      </div>
      
      <!-- BOM列表 -->
      <el-table 
        :data="filteredBomItems" 
        border 
        stripe 
        v-loading="loading"
        ref="tableRef"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="item_code" label="物料编码" width="100" />
        <el-table-column prop="item_name" label="物料名称" width="150" />
        <el-table-column prop="specification" label="规格型号" width="100" />
        <el-table-column prop="version_brand" label="版本/品牌" width="100" />
        <el-table-column prop="unit" label="单位" width="60" />
        <el-table-column prop="planned_qty" label="计划数量" width="90" align="right" />
        <el-table-column prop="actual_qty" label="已领用" width="80" align="right">
          <template #default="{ row }">
            <span :class="row.actual_qty > row.planned_qty ? 'text-danger' : ''">
              {{ row.actual_qty || 0 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="剩余需求" width="80" align="right">
          <template #default="{ row }">
            {{ Math.max(0, (row.planned_qty || 0) - (row.actual_qty || 0)) }}
          </template>
        </el-table-column>
        <el-table-column prop="estimated_cost" label="预估单价" width="90" align="right">
          <template #default="{ row }">
            ¥{{ row.estimated_cost || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="预估成本" width="100" align="right">
          <template #default="{ row }">
            ¥{{ ((row.planned_qty || 0) * (row.estimated_cost || 0)).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="has_drawing_display" label="有图/无图" width="80" />
        <el-table-column prop="item_type" label="物料类型" width="80" />
        <el-table-column prop="required_date" label="需求日期" width="100" />
        <el-table-column prop="requester_name" label="申请人" width="80" />
        <el-table-column prop="notes" label="备注" width="120" />
        <el-table-column prop="description" label="说明" width="120" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 添加/编辑物料对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="所属项目">
          <el-input :value="currentProjectName" disabled>
            <template #prefix>
              <el-icon><Folder /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="选择物料" prop="item" v-if="!form.id">
          <el-select v-model="form.item" placeholder="选择物料" filterable style="width: 100%;" @change="handleItemChange">
            <el-option
              v-for="item in items"
              :key="item.id"
              :label="`${item.sku} - ${item.name}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="物料" v-else>
          <el-input :value="`${form.item_code} - ${form.item_name}`" disabled />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="规格型号">
              <el-input v-model="form.specification" disabled />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="单位">
              <el-input v-model="form.unit" disabled />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="物料类型">
              <el-input v-model="form.item_type" disabled />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="计划数量" prop="planned_qty">
              <el-input-number v-model="form.planned_qty" :min="1" :max="999999" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="预估单价">
              <el-input-number v-model="form.estimated_cost" :min="0" :precision="2" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="版本/品牌">
              <el-input v-model="form.version_brand" placeholder="版本号或品牌" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="有图/无图">
              <el-select v-model="form.has_drawing" style="width: 100%;">
                <el-option label="有图" value="YES" />
                <el-option label="无图" value="NO" />
                <el-option label="待定" value="PENDING" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="需求日期">
              <el-date-picker 
                v-model="form.required_date" 
                type="date" 
                placeholder="选择日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                style="width: 100%;"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="申请人">
              <el-select v-model="form.requester" placeholder="选择申请人" filterable clearable style="width: 100%;">
                <el-option
                  v-for="user in users"
                  :key="user.id"
                  :label="user.name"
                  :value="user.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="备注信息" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="详细说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
    
    <!-- 导入BOM对话框 -->
    <el-dialog v-model="importDialogVisible" title="导入BOM" width="550px">
      <el-alert
        title="导入说明"
        type="info"
        show-icon
        :closable="false"
        class="mb-15"
      >
        <template #default>
          <div>1. 请先下载导入模板，按模板格式填写数据</div>
          <div>2. 物料编码必须与系统中的物料编码一致</div>
          <div>3. 计划数量为必填项，单价可选</div>
        </template>
      </el-alert>
      
      <el-upload
        ref="uploadRef"
        class="upload-area"
        drag
        action="#"
        :auto-upload="false"
        :limit="1"
        :on-change="handleFileChange"
        :on-exceed="handleExceed"
        accept=".xlsx,.xls"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将Excel文件拖到此处，或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">只支持 .xlsx 或 .xls 格式文件</div>
        </template>
      </el-upload>
      
      <el-checkbox v-model="importOptions.updateExisting" class="mt-15">
        更新已存在的物料（不勾选则跳过已存在的物料）
      </el-checkbox>
      
      <!-- 导入结果 -->
      <div v-if="importResult" class="import-result">
        <el-divider content-position="left">导入结果</el-divider>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="新增">
            <el-tag type="success">{{ importResult.created }} 条</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="更新">
            <el-tag type="primary">{{ importResult.updated }} 条</el-tag>
          </el-descriptions-item>
        </el-descriptions>
        
        <div v-if="importResult.errors && importResult.errors.length > 0" class="error-list">
          <el-alert title="导入错误" type="error" show-icon :closable="false">
            <template #default>
              <div v-for="error in importResult.errors" :key="error.row" class="error-item">
                第 {{ error.row }} 行: {{ error.error }}
              </div>
            </template>
          </el-alert>
        </div>
      </div>
      
      <template #footer>
        <el-button @click="handleDownloadTemplate">下载模板</el-button>
        <el-button @click="importDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleConfirmImport" :loading="importing" :disabled="!importFile">
          开始导入
        </el-button>
      </template>
    </el-dialog>
    
    <!-- 从其他项目复制对话框 -->
    <el-dialog v-model="copyDialogVisible" title="从其他项目复制BOM" width="450px">
      <el-form label-width="100px">
        <el-form-item label="源项目">
          <el-select v-model="copySourceProject" placeholder="选择源项目" filterable style="width: 100%;">
            <el-option
              v-for="project in projects.filter(p => p.id !== selectedProject)"
              :key="project.id"
              :label="`${project.code} - ${project.name}`"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标项目">
          <el-input :value="currentProjectName" disabled />
        </el-form-item>
      </el-form>
      <el-alert
        title="提示：已存在的物料将被跳过，不会覆盖"
        type="info"
        show-icon
        :closable="false"
      />
      <template #footer>
        <el-button @click="copyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmCopy" :loading="copying" :disabled="!copySourceProject">
          确定复制
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Document, Download, Upload, ArrowDown, CopyDocument, UploadFilled, Search, Delete, Folder } from '@element-plus/icons-vue'
import request from '@/utils/request'

const router = useRouter()

const loading = ref(false)
const selectedProject = ref(null)
const projects = ref([])
const bomItems = ref([])
const items = ref([])
const users = ref([])
const dialogVisible = ref(false)
const formRef = ref(null)
const tableRef = ref(null)

// 搜索和多选
const searchKeyword = ref('')
const selectedRows = ref([])

// Import/Export related
const importDialogVisible = ref(false)
const copyDialogVisible = ref(false)
const uploadRef = ref(null)
const importFile = ref(null)
const importing = ref(false)
const copying = ref(false)
const copySourceProject = ref(null)
const importResult = ref(null)
const importOptions = reactive({
  updateExisting: false
})

const form = reactive({
  id: null,
  item: null,
  item_code: '',
  item_name: '',
  specification: '',
  unit: '',
  item_type: '',
  planned_qty: 1,
  estimated_cost: 0,
  version_brand: '',
  has_drawing: 'PENDING',
  required_date: null,
  requester: null,
  notes: '',
  description: ''
})

const rules = {
  item: [{ required: true, message: '请选择物料', trigger: 'change' }],
  planned_qty: [{ required: true, message: '请输入计划数量', trigger: 'blur' }]
}

const dialogTitle = computed(() => form.id ? '编辑物料' : '添加物料')

const currentProjectName = computed(() => {
  const project = projects.value.find(p => p.id === selectedProject.value)
  return project ? `${project.code} - ${project.name}` : ''
})

const totalPlannedQty = computed(() => 
  bomItems.value.reduce((sum, item) => sum + (item.planned_qty || 0), 0)
)

const totalActualQty = computed(() => 
  bomItems.value.reduce((sum, item) => sum + (item.actual_qty || 0), 0)
)

const totalEstimatedCost = computed(() => 
  bomItems.value.reduce((sum, item) => sum + (item.planned_qty || 0) * (item.estimated_cost || 0), 0)
)

// 搜索过滤后的 BOM 列表
const filteredBomItems = computed(() => {
  if (!searchKeyword.value.trim()) {
    return bomItems.value
  }
  const keyword = searchKeyword.value.toLowerCase().trim()
  return bomItems.value.filter(item => {
    return (item.item_code && item.item_code.toLowerCase().includes(keyword)) ||
           (item.item_name && item.item_name.toLowerCase().includes(keyword)) ||
           (item.specification && item.specification.toLowerCase().includes(keyword))
  })
})

const getProgressStatus = (row) => {
  const percentage = ((row.actual_qty || 0) / (row.planned_qty || 1)) * 100
  if (percentage >= 100) return 'success'
  if (percentage >= 50) return ''
  return 'warning'
}

const fetchProjects = async () => {
  try {
    const res = await request.get('/projects/projects/')
    projects.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取项目列表失败:', error)
  }
}

const fetchBOM = async () => {
  if (!selectedProject.value) {
    bomItems.value = []
    return
  }
  
  loading.value = true
  try {
    // 使用查询参数过滤项目BOM
    const res = await request.get('/projects/bom/', {
      params: { project: selectedProject.value }
    })
    bomItems.value = res.data?.results || res.results || res.data || res || []
  } catch (error) {
    console.error('获取BOM列表失败:', error)
    bomItems.value = []
    ElMessage.error('获取BOM列表失败')
  } finally {
    loading.value = false
  }
}

const fetchItems = async () => {
  try {
    const res = await request.get('/masterdata/items/')
    items.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取物料列表失败:', error)
  }
}

const fetchUsers = async () => {
  try {
    const res = await request.get('/auth/users/')
    const userList = res.data?.results || res.results || res.data || []
    users.value = userList.map(u => ({
      id: u.id,
      name: `${u.last_name || ''}${u.first_name || ''}`.trim() || u.username || `用户${u.id}`
    }))
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

const resetForm = () => {
  form.id = null
  form.item = null
  form.item_code = ''
  form.item_name = ''
  form.specification = ''
  form.unit = ''
  form.item_type = ''
  form.planned_qty = 1
  form.estimated_cost = 0
  form.version_brand = ''
  form.has_drawing = 'PENDING'
  form.required_date = null
  form.requester = null
  form.notes = ''
  form.description = ''
}

const handleItemChange = (itemId) => {
  const item = items.value.find(i => i.id === itemId)
  if (item) {
    form.item_code = item.sku
    form.item_name = item.name
    form.specification = item.specification || ''
    form.unit = item.unit_display || item.unit || ''
    form.item_type = item.item_type_display || item.item_type || ''
    form.estimated_cost = item.standard_cost || 0
    form.version_brand = item.brand || ''
  }
}

const handleAdd = () => {
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定要删除物料 ${row.item_name} 吗？`, '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await request.delete(`/projects/bom/${row.id}/`)
      ElMessage.success('删除成功')
      fetchBOM()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    const data = { ...form, project: selectedProject.value }
    
    if (form.id) {
      await request.put(`/projects/bom/${form.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/projects/bom/', data)
      ElMessage.success('添加成功')
    }
    
    dialogVisible.value = false
    fetchBOM()
  } catch (error) {
    if (error !== 'cancel') {
      const errData = error.response?.data
      if (errData?.non_field_errors) {
        ElMessage.error('该物料已在BOM中存在，请勿重复添加')
      } else if (errData?.item) {
        ElMessage.error(errData.item[0] || '物料错误')
      } else {
        ElMessage.error('操作失败')
      }
    }
  }
}

// 搜索处理
const handleSearch = () => {
  // 搜索时清空选择
  selectedRows.value = []
  if (tableRef.value) {
    tableRef.value.clearSelection()
  }
}

// 多选处理
const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

// 清除选择
const clearSelection = () => {
  selectedRows.value = []
  if (tableRef.value) {
    tableRef.value.clearSelection()
  }
}

// 批量删除
const handleBatchDelete = async () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的物料')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 项物料吗？此操作不可恢复！`,
      '批量删除',
      { type: 'warning' }
    )
    
    // 逐个删除选中的物料
    for (const row of selectedRows.value) {
      await request.delete(`/projects/bom/${row.id}/`)
    }
    
    ElMessage.success(`成功删除 ${selectedRows.value.length} 项物料`)
    clearSelection()
    fetchBOM()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 根据选中项生成采购申请
const handleGeneratePRFromSelected = () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要生成采购申请的物料')
    return
  }
  
  // 使用选中的物料生成采购申请
  generatePurchaseRequest(selectedRows.value)
}

const handleGeneratePR = () => {
  // 筛选出需要采购的物料（剩余需求 > 0）
  const itemsToOrder = bomItems.value.filter(item => {
    const remaining = (item.planned_qty || 0) - (item.actual_qty || 0)
    return remaining > 0
  })
  
  if (itemsToOrder.length === 0) {
    ElMessage.warning('所有物料已满足需求，无需生成采购申请')
    return
  }
  
  generatePurchaseRequest(itemsToOrder)
}

// 通用的生成采购申请函数
const generatePurchaseRequest = (itemsToOrder) => {
  ElMessageBox.confirm(
    `将根据选中物料生成采购申请，包含 ${itemsToOrder.length} 种物料。确定继续？`, 
    '生成采购申请', 
    { type: 'info' }
  ).then(() => {
    // 将需要采购的物料信息存储到sessionStorage
    const prData = {
      project: selectedProject.value,
      projectName: currentProjectName.value,
      lines: itemsToOrder.map(item => ({
        item: item.item,
        item_sku: item.item_code,
        item_name: item.item_name,
        qty: Math.max(1, (item.planned_qty || 0) - (item.actual_qty || 0)),
        estimated_price: item.estimated_cost || 0
      }))
    }
    sessionStorage.setItem('bom_to_pr', JSON.stringify(prData))
    
    // 跳转到采购申请页面
    router.push('/purchase/requests?from_bom=1')
  }).catch(() => {})
}

// ========== 导入导出功能 ==========

const handleExportExcel = async () => {
  if (!selectedProject.value || !bomItems.value.length) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  
  try {
    const response = await request.get('/projects/bom/export_excel/', {
      params: { project: selectedProject.value },
      responseType: 'blob'
    })
    
    // 获取实际的blob数据
    const blobData = response.data || response
    const blob = new Blob([blobData], { 
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
    })
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `BOM_${currentProjectName.value.split(' - ')[0]}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败')
  }
}

const handleDownloadTemplate = async () => {
  try {
    const response = await request.get('/projects/bom/export_template/', {
      responseType: 'blob'
    })
    
    // 获取实际的blob数据
    const blobData = response.data || response
    const blob = new Blob([blobData], { 
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
    })
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'BOM_import_template.xlsx')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('模板下载成功')
  } catch (error) {
    console.error('下载模板失败:', error)
    ElMessage.error('下载模板失败')
  }
}

const handleImport = () => {
  importFile.value = null
  importResult.value = null
  importOptions.updateExisting = false
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  importDialogVisible.value = true
}

const handleFileChange = (file) => {
  importFile.value = file.raw
  importResult.value = null
}

const handleExceed = () => {
  ElMessage.warning('只能上传一个文件，请先删除已选文件')
}

const handleConfirmImport = async () => {
  if (!importFile.value) {
    ElMessage.warning('请选择要导入的文件')
    return
  }
  
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)
    formData.append('project', selectedProject.value)
    formData.append('update_existing', importOptions.updateExisting.toString())
    
    const response = await request.post('/projects/bom/import_excel/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    const data = response.data || response
    importResult.value = data
    
    if (data.created > 0 || data.updated > 0) {
      ElMessage.success(data.message || `导入成功：新增${data.created}条，更新${data.updated}条`)
      fetchBOM()
    } else if (data.errors && data.errors.length > 0) {
      ElMessage.warning('导入完成，但存在错误，请查看详情')
    }
  } catch (error) {
    console.error('导入失败:', error)
    ElMessage.error(error.response?.data?.error || '导入失败')
  } finally {
    importing.value = false
  }
}

const handleCopyFromProject = () => {
  copySourceProject.value = null
  copyDialogVisible.value = true
}

const handleConfirmCopy = async () => {
  if (!copySourceProject.value) {
    ElMessage.warning('请选择源项目')
    return
  }
  
  copying.value = true
  try {
    const response = await request.post('/projects/bom/copy_from_project/', {
        source_project: copySourceProject.value,
        target_project: selectedProject.value
    })
    
    const data = response.data || response
    ElMessage.success(data.message || '复制成功')
    copyDialogVisible.value = false
    fetchBOM()
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error(error.response?.data?.error || '复制失败')
  } finally {
    copying.value = false
  }
}

watch(selectedProject, () => {
  fetchBOM()
})

onMounted(() => {
  fetchProjects()
  fetchItems()
  fetchUsers()
})
</script>

<style scoped>
.bom-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
}

.header-actions {
  display: flex;
  align-items: center;
}

.stats-row {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.text-danger {
  color: #f56c6c;
}

.search-bar {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
  padding: 10px 0;
}

.selection-info {
  display: flex;
  align-items: center;
  font-size: 14px;
  color: #606266;
}

.mb-15 {
  margin-bottom: 15px;
}

.mt-15 {
  margin-top: 15px;
}

.upload-area {
  width: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  width: 100%;
}

.import-result {
  margin-top: 20px;
}

.error-list {
  margin-top: 15px;
  max-height: 200px;
  overflow-y: auto;
}

.error-item {
  padding: 2px 0;
  font-size: 12px;
}
</style>

