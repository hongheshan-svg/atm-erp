<template>
  <div class="item-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>物料主数据</span>
          <div class="header-actions">
            <el-button type="primary" @click="handleAdd">新增物料</el-button>
            <el-dropdown style="margin-left: 10px;">
              <el-button type="success">
                导入/导出 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleExport">
                    <el-icon><Download /></el-icon> 导出Excel
                  </el-dropdown-item>
                  <el-dropdown-item @click="handleImport">
                    <el-icon><Upload /></el-icon> 导入Excel
                  </el-dropdown-item>
                  <el-dropdown-item @click="handleDownloadTemplate">
                    <el-icon><Document /></el-icon> 下载导入模板
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="物料编码">
          <el-input v-model="searchForm.sku" placeholder="搜索物料编码" clearable />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="searchForm.name" placeholder="搜索物料名称" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadItems">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作工具栏 - 仅管理员可见 -->
      <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button 
          type="danger" 
          size="small" 
          @click="batchDelete"
          :loading="loading"
        >
          批量删除
        </el-button>
      </div>
      
      <el-table :data="items" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <!-- 仅管理员显示选择列 -->
        <el-table-column v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column type="index" label="序号" width="60" fixed />
        <el-table-column prop="sku" label="物料编码" width="100" fixed />
        <el-table-column prop="name" label="物料名称" width="150" show-overflow-tooltip />
        <el-table-column prop="specification" label="规格型号" width="120" show-overflow-tooltip />
        <el-table-column label="版本/品牌" width="120">
          <template #default="{ row }">
            {{ row.brand || row.model ? `${row.brand || ''}${row.brand && row.model ? '/' : ''}${row.model || ''}` : '' }}
          </template>
        </el-table-column>
        <el-table-column prop="unit_display" label="单位" width="60" />
        <el-table-column prop="item_type_display" label="物料类型" width="80" />
        <el-table-column label="采购单价" width="90" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.purchase_price || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="销售单价" width="90" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.sale_price || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="标准成本" width="90" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.standard_cost || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="税率(%)" width="70" align="center">
          <template #default="{ row }">
            {{ row.tax_rate }}
          </template>
        </el-table-column>
        <el-table-column prop="manufacturer" label="生产厂家" width="120" show-overflow-tooltip />
        <el-table-column prop="origin_country" label="产地" width="80" show-overflow-tooltip />
        <el-table-column prop="safety_stock" label="安全库存" width="80" align="right" />
        <el-table-column label="采购周期(天)" width="90" align="center">
          <template #default="{ row }">
            {{ row.lead_time || '' }}
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="canDelete ? 180 : 80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <!-- 仅管理员显示删除按钮 -->
            <el-button 
              v-if="canDelete"
              size="small" 
              type="danger" 
              @click="deleteRow(row)"
              :loading="loading"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadItems"
        @current-change="loadItems"
        style="margin-top: 20px; justify-content: center"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-divider content-position="left">基本信息</el-divider>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="物料编码" prop="sku">
              <el-input v-model="form.sku" placeholder="请输入或生成物料编码">
                <template #append>
                  <el-button @click="showCodeGenerator = true" :icon="Setting">生成</el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="物料名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入物料名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="品牌">
              <el-input v-model="form.brand" placeholder="品牌名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="型号">
              <el-input v-model="form.model" placeholder="产品型号" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="生产厂家">
              <el-input v-model="form.manufacturer" placeholder="生产厂家" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="产地">
              <el-input v-model="form.origin_country" placeholder="产地/国家" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="规格型号">
              <el-input v-model="form.specification" placeholder="规格描述" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="条形码">
              <el-input v-model="form.barcode" placeholder="条形码" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="单位" prop="unit">
              <el-select v-model="form.unit" placeholder="选择单位" style="width: 100%">
                <el-option label="个" value="PCS" />
                <el-option label="千克" value="KG" />
                <el-option label="米" value="M" />
                <el-option label="平方米" value="M2" />
                <el-option label="立方米" value="M3" />
                <el-option label="套" value="SET" />
                <el-option label="箱" value="BOX" />
                <el-option label="包" value="PACK" />
                <el-option label="小时" value="HOUR" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="物料类型">
              <el-select v-model="form.item_type" placeholder="选择类型" style="width: 100%">
                <el-option label="原材料" value="MATERIAL" />
                <el-option label="产成品" value="PRODUCT" />
                <el-option label="半成品" value="SEMI" />
                <el-option label="服务" value="SERVICE" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="状态">
              <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">价格与税率</el-divider>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="采购单价">
              <el-input-number v-model="form.purchase_price" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="销售单价">
              <el-input-number v-model="form.sale_price" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="标准成本">
              <el-input-number v-model="form.standard_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="税率">
              <el-select v-model="form.tax_rate" placeholder="选择税率" style="width: 100%">
                <el-option label="0%" :value="0" />
                <el-option label="1%" :value="1" />
                <el-option label="3%" :value="3" />
                <el-option label="6%" :value="6" />
                <el-option label="9%" :value="9" />
                <el-option label="13%" :value="13" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">库存设置</el-divider>
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="最小库存">
              <el-input-number v-model="form.min_stock" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="最大库存">
              <el-input-number v-model="form.max_stock" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="安全库存">
              <el-input-number v-model="form.safety_stock" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="采购周期">
              <el-input-number v-model="form.lead_time" :min="0" style="width: 100%">
                <template #append>天</template>
              </el-input-number>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">其他信息</el-divider>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="重量(kg)">
              <el-input-number v-model="form.weight" :min="0" :precision="3" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="体积(m³)">
              <el-input-number v-model="form.volume" :min="0" :precision="3" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="保质期">
              <el-input-number v-model="form.shelf_life" :min="0" style="width: 100%">
                <template #append>天</template>
              </el-input-number>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="物料描述" />
        </el-form-item>
        
        <!-- 附件上传 -->
        <el-form-item label="相关附件">
          <!-- 编辑时使用完整附件组件 -->
          <AttachmentUpload
            v-if="isEdit && form.id"
            ref="attachmentRef"
            related-model="Item"
            :related-id="form.id"
            title="物料附件"
            accept=".pdf,.doc,.docx,.xls,.xlsx,.dwg,.dxf,.jpg,.jpeg,.png,.gif,.zip,.rar"
          />
          <!-- 新增时使用简化的文件选择 -->
          <div v-else class="temp-upload">
            <el-upload
              ref="tempUploadRef"
              :auto-upload="false"
              :file-list="tempFiles"
              :on-change="handleTempFileChange"
              :on-remove="handleTempFileRemove"
              multiple
              accept=".pdf,.doc,.docx,.xls,.xlsx,.dwg,.dxf,.jpg,.jpeg,.png,.gif,.zip,.rar"
            >
              <el-button type="primary">
                <el-icon><Upload /></el-icon>
                选择附件
              </el-button>
              <template #tip>
                <div class="el-upload__tip">
                  支持图纸(dwg/dxf)、规格书(pdf/doc)、图片等，单个文件不超过50MB
                </div>
              </template>
            </el-upload>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 编码生成器对话框 -->
    <el-dialog v-model="showCodeGenerator" title="生成物料编码" width="500px">
      <el-alert
        title="编码规则说明"
        type="info"
        :closable="false"
        style="margin-bottom: 20px;"
      >
        <p>一级代码(1位) + 二级代码(1位) + 年份(2位) + 流水号(6位)</p>
        <p style="margin-top: 8px; font-size: 12px; color: #909399;">
          • 一级代码：1=有图，2=无图<br/>
          • 年份：有图=当前年份，无图=99<br/>
          • 流水号：根据年份自动累加
        </p>
      </el-alert>

      <el-form label-width="100px">
        <el-form-item label="一级代码">
          <el-radio-group v-model="codeGenForm.level1">
            <el-radio label="1">有图</el-radio>
            <el-radio label="2">无图</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="二级代码">
          <el-select v-model="codeGenForm.level2" placeholder="选择类别" style="width: 100%;">
            <el-option label="1-机加" value="1" />
            <el-option label="2-钣金" value="2" />
            <el-option label="3-特殊工艺" value="3" />
            <el-option label="4-其他" value="4" />
            <el-option label="5-机械类" value="5" />
            <el-option label="6-电气类" value="6" />
            <el-option label="7-耗材辅料" value="7" />
            <el-option label="8-办公用品" value="8" />
          </el-select>
        </el-form-item>

        <el-form-item label="预览编码" v-if="generatedCode">
          <el-tag type="success" size="large">{{ generatedCode }}</el-tag>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCodeGenerator = false">取消</el-button>
        <el-button type="primary" @click="generateCode" :loading="generating">生成编码</el-button>
        <el-button type="success" @click="applyCode" :disabled="!generatedCode">应用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Download, Document, ArrowDown, Setting } from '@element-plus/icons-vue'
import request from '@/utils/request'
import AttachmentUpload from '@/components/AttachmentUpload.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete, isAdmin } = usePermission()

// 批量删除功能
const { selectedRows, loading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/masterdata/items/',
  {
    confirmTitle: '确认删除物料',
    confirmMessage: '此操作将永久删除选中的物料记录，是否继续？',
    successMessage: '删除物料成功',
    errorMessage: '删除物料失败',
    onSuccess: () => loadItems()
  }
)

const attachmentRef = ref(null)
const tempUploadRef = ref(null)
const tempFiles = ref([])

const items = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增物料')
const isEdit = ref(false)
const formRef = ref(null)

// 编码生成器
const showCodeGenerator = ref(false)
const generating = ref(false)
const generatedCode = ref('')
const codeGenForm = reactive({
  level1: '1',  // 默认有图
  level2: ''
})

const searchForm = reactive({
  sku: '',
  name: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  sku: '',
  name: '',
  specification: '',
  // 品牌型号
  brand: '',
  model: '',
  manufacturer: '',
  origin_country: '',
  barcode: '',
  // 类型单位
  item_type: 'MATERIAL',
  unit: 'PCS',
  // 价格税率
  purchase_price: 0,
  sale_price: 0,
  standard_cost: 0,
  tax_rate: 13,
  // 库存
  min_stock: 0,
  max_stock: 0,
  safety_stock: 0,
  lead_time: 0,
  // 其他
  weight: 0,
  volume: 0,
  shelf_life: 0,
  description: '',
  is_active: true
})

const rules = {
  sku: [{ required: true, message: '请输入物料编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入物料名称', trigger: 'blur' }],
  unit: [{ required: true, message: '请输入单位', trigger: 'blur' }]
}

const loadItems = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const response = await request.get('/masterdata/items/', { params })
    items.value = response.results || response || []
    pagination.total = response.count || 0
  } catch (error) {
    ElMessage.error('加载物料失败')
  } finally {
    loading.value = false
  }
}

const handleTempFileChange = (file, fileList) => {
  // 检查文件大小
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.warning(`文件 "${file.name}" 超过50MB限制`)
    fileList.pop()
    return
  }
  tempFiles.value = fileList
}

const handleTempFileRemove = (file, fileList) => {
  tempFiles.value = fileList
}

const uploadTempFiles = async (itemId) => {
  if (!tempFiles.value.length) return
  
  const formData = new FormData()
  formData.append('related_model', 'Item')
  formData.append('related_id', itemId)
  formData.append('category', 'OTHER')
  
  for (const file of tempFiles.value) {
    formData.append('files', file.raw)
  }
  
  try {
    await request.post('/core/attachments/batch_upload/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  } catch (error) {
    console.error('附件上传失败:', error)
    ElMessage.warning('物料已保存，但部分附件上传失败')
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增物料'
  isEdit.value = false
  tempFiles.value = []
  Object.assign(form, {
    id: null,
    sku: '',
    name: '',
    specification: '',
    // 品牌型号
    brand: '',
    model: '',
    manufacturer: '',
    origin_country: '',
    barcode: '',
    // 类型单位
    item_type: 'MATERIAL',
    unit: 'PCS',
    // 价格税率
    purchase_price: 0,
    sale_price: 0,
    standard_cost: 0,
    tax_rate: 13,
    // 库存
    min_stock: 0,
    max_stock: 0,
    safety_stock: 0,
    lead_time: 0,
    // 其他
    weight: 0,
    volume: 0,
    shelf_life: 0,
    description: '',
    is_active: true
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑物料'
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

// 删除功能已迁移到 useBatchDelete composable

// 导出Excel
const handleExport = async () => {
  try {
    const response = await request.get('/masterdata/items/export_excel/', {
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(new Blob([response.data || response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `物料主数据_${new Date().toISOString().slice(0, 10)}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

// 下载导入模板
const handleDownloadTemplate = async () => {
  try {
    const response = await request.get('/masterdata/items/export_template/', {
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(new Blob([response.data || response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', '物料导入模板.xlsx')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    ElMessage.success('模板下载成功')
  } catch (error) {
    ElMessage.error('模板下载失败')
  }
}

// 导入Excel
const handleImport = () => {
  // 创建一个隐藏的文件输入
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.xlsx,.xls'
  input.onchange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    
    const formData = new FormData()
    formData.append('file', file)
    
    try {
      const res = await request.post('/masterdata/items/import_excel/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      const data = res.data || res
      // 构建导入结果提示
      let successMsg = `导入完成：新增 ${data.created || 0} 条`
      if (data.matched_count > 0) {
        successMsg += `，匹配已有 ${data.matched_count} 条`
      }
      if (data.skip_exist_count > 0) {
        successMsg += `，跳过已存在 ${data.skip_exist_count} 条`
      }
      if (data.skip_dup_count > 0) {
        successMsg += `，跳过重复 ${data.skip_dup_count} 条`
      }
      ElMessage.success(successMsg)
      if (data.errors && data.errors.length > 0) {
        ElMessage.warning(`有 ${data.errors.length} 行导入失败，请检查数据`)
      }
      loadItems()
    } catch (error) {
      ElMessage.error('导入失败: ' + (error.response?.data?.error || '未知错误'))
    }
  }
  input.click()
}

// 生成编码
const generateCode = async () => {
  if (!codeGenForm.level2) {
    ElMessage.warning('请选择二级代码')
    return
  }

  generating.value = true
  try {
    const res = await request.post('/masterdata/items/generate_code/', {
      level1_code: codeGenForm.level1,
      level2_code: codeGenForm.level2
    })
    generatedCode.value = res.code
    ElMessage.success('编码生成成功')
  } catch (error) {
    ElMessage.error('生成编码失败')
  } finally {
    generating.value = false
  }
}

// 应用编码
const applyCode = () => {
  form.sku = generatedCode.value
  showCodeGenerator.value = false
  generatedCode.value = ''
  codeGenForm.level2 = ''
  ElMessage.success('编码已应用')
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    if (isEdit.value) {
      await request.put(`/masterdata/items/${form.id}/`, form)
      ElMessage.success('更新物料成功')
    } else {
      const response = await request.post('/masterdata/items/', form)
      // 如果有临时附件，上传附件
      if (tempFiles.value.length && response.id) {
        await uploadTempFiles(response.id)
      }
      ElMessage.success('创建物料成功')
    }
    dialogVisible.value = false
    tempFiles.value = []
    loadItems()
  } catch (error) {
    ElMessage.error('保存物料失败')
  }
}

const resetSearch = () => {
  Object.assign(searchForm, { sku: '', name: '' })
  pagination.page = 1
  loadItems()
}

onMounted(() => {
  loadItems()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.temp-upload {
  width: 100%;
}

.temp-upload .el-upload__tip {
  color: #909399;
  font-size: 12px;
  margin-top: 5px;
}

.table-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding: 8px 12px;
  background: #f0f9eb;
  border-radius: 4px;
}
</style>
