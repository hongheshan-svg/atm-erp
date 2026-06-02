<template>
  <div class="supplier-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>供应商管理</span>
          <div class="header-actions">
            <el-button @click="downloadTemplate">
              <el-icon><Document /></el-icon> 下载模板
            </el-button>
            <el-upload
              ref="uploadRef"
              :action="uploadUrl"
              :headers="uploadHeaders"
              :on-success="handleUploadSuccess"
              :on-error="handleUploadError"
              :before-upload="beforeUpload"
              :show-file-list="false"
              accept=".xlsx,.xls"
            >
              <el-button type="success">
                <el-icon><Upload /></el-icon> 导入
              </el-button>
            </el-upload>
            <el-button @click="handleExport">
              <el-icon><Download /></el-icon> 导出
            </el-button>
            <el-button type="primary" v-permission="'masterdata:supplier:create'" @click="handleAdd">
              <el-icon><Plus /></el-icon> 新增供应商
            </el-button>
          </div>
        </div>
      </template>

      <!-- 搜索条件 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="供应商名称">
          <el-input v-model="searchForm.search" placeholder="搜索名称/编码/联系人/电话" clearable style="width: 220px;" @keyup.enter="loadSuppliers" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 100px;">
            <el-option label="激活" value="ACTIVE" />
            <el-option label="停用" value="INACTIVE" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadSuppliers">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作工具栏 - 仅管理员可见 -->
      <div class="table-toolbar" v-permission="'masterdata:supplier:delete'" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button 
          type="danger" 
          size="small" 
          @click="batchDelete"
          :loading="deleteLoading"
        >
          批量删除
        </el-button>
      </div>
      
      <el-table :data="suppliers" v-loading="loading" stripe border @selection-change="handleSelectionChange" :table-layout="'auto'" style="width: 100%;">
        <!-- 仅管理员显示选择列 -->
        <el-table-column v-permission="'masterdata:supplier:delete'" v-if="canDelete" type="selection" width="45" fixed />
        <el-table-column prop="code" label="编码" width="110" />
        <el-table-column prop="name" label="供应商名称" min-width="200" />
        <el-table-column prop="contact_person" label="联系人" width="80" />
        <el-table-column prop="phone" label="电话" width="120" />
        <el-table-column prop="tax_number" label="税号" min-width="180" />
        <el-table-column prop="bank_name" label="开户银行" min-width="180" />
        <el-table-column prop="bank_account" label="银行账号" min-width="180" />
        <el-table-column prop="settlement_method_display" label="结款方式" width="90" />
        <el-table-column prop="address" label="地址" min-width="250" />
        <el-table-column prop="status" label="状态" width="70">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ACTIVE' ? 'success' : 'info'" size="small">{{ row.status === 'ACTIVE' ? '激活' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="canDelete ? 200 : 140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" v-permission="'masterdata:supplier:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" link type="success" @click="handleViewAttachments(row)">附件</el-button>
            <!-- 仅管理员显示删除按钮 -->
            <el-button 
              v-if="canDelete"
              size="small" 
              link
              type="danger" 
              @click="deleteRow(row)"
              :loading="deleteLoading"
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
        layout="total, sizes, prev, pager, next"
        @size-change="loadSuppliers"
        @current-change="loadSuppliers"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px">
      <el-form :model="form" ref="formRef" label-width="120px" :rules="formRules">
        <el-tabs v-model="activeFormTab">
          <el-tab-pane label="基本信息" name="basic">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="编码" prop="code">
                  <el-input v-model="form.code" :disabled="isEdit" placeholder="留空自动生成" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="供应商名称" prop="name">
                  <el-input v-model="form.name" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="简称">
                  <el-input v-model="form.short_name" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="状态">
                  <el-select v-model="form.status" style="width: 100%;">
                    <el-option label="激活" value="ACTIVE" />
                    <el-option label="停用" value="INACTIVE" />
                    <el-option label="潜在供应商" value="POTENTIAL" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="联系人">
                  <el-input v-model="form.contact_person" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="电话">
                  <el-input v-model="form.phone" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="邮箱">
              <el-input v-model="form.email" />
            </el-form-item>
            <el-form-item label="结款方式">
              <el-select v-model="form.settlement_method" placeholder="请选择结款方式" clearable style="width: 100%;">
                <el-option label="预付款" value="PREPAY" />
                <el-option label="货到付款" value="COD" />
                <el-option label="月结15天" value="NET15" />
                <el-option label="月结30天" value="NET30" />
                <el-option label="月结45天" value="NET45" />
                <el-option label="月结60天" value="NET60" />
                <el-option label="月结90天" value="NET90" />
                <el-option label="月结120天" value="NET120" />
                <el-option label="承兑汇票" value="ACCEPTANCE" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
            <el-form-item label="地址">
              <el-input v-model="form.address" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="form.notes" type="textarea" :rows="2" />
            </el-form-item>
          </el-tab-pane>

          <el-tab-pane label="开票信息" name="invoice">
            <el-alert type="info" :closable="false" style="margin-bottom: 20px;">
              开票信息用于接收增值税发票，请确保信息准确完整。
            </el-alert>
            <el-form-item label="开票名称" prop="invoice_title">
              <el-input v-model="form.invoice_title" placeholder="公司全称（与营业执照一致）" />
            </el-form-item>
            <el-form-item label="税号" prop="tax_number">
              <el-input v-model="form.tax_number" placeholder="纳税人识别号/统一社会信用代码" />
            </el-form-item>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="开户银行">
                  <el-input v-model="form.bank_name" placeholder="开户银行全称" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="银行账号">
                  <el-input v-model="form.bank_account" placeholder="银行账号" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="注册地址">
              <el-input v-model="form.registered_address" type="textarea" :rows="2" placeholder="营业执照上的注册地址" />
            </el-form-item>
            <el-form-item label="注册电话">
              <el-input v-model="form.registered_phone" placeholder="公司注册电话" />
            </el-form-item>
          </el-tab-pane>
        </el-tabs>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">提交</el-button>
      </template>
    </el-dialog>
    
    <!-- 附件管理对话框 -->
    <el-dialog v-model="attachmentDialogVisible" :title="`${currentSupplier?.name || ''} - 附件管理`" width="900px" destroy-on-close>
      <AttachmentUpload
        v-if="currentSupplier"
        related-model="Supplier"
        :related-id="currentSupplier.id"
        title="供应商相关资料"
      />
    </el-dialog>

    <!-- 导入结果对话框 -->
    <el-dialog v-model="importResultVisible" title="导入结果" width="500px">
      <el-descriptions :column="2" border v-if="importResult">
        <el-descriptions-item label="新增供应商">
          <span class="text-success">{{ importResult.success_count }} 个</span>
        </el-descriptions-item>
        <el-descriptions-item label="更新供应商">
          <span class="text-primary">{{ importResult.update_count }} 个</span>
        </el-descriptions-item>
        <el-descriptions-item label="错误数">
          <span :class="importResult.error_count > 0 ? 'text-danger' : ''">{{ importResult.error_count }} 个</span>
        </el-descriptions-item>
      </el-descriptions>
      <div v-if="importResult?.errors?.length > 0" style="margin-top: 15px;">
        <el-alert title="导入错误详情" type="error" :closable="false">
          <div v-for="(err, idx) in importResult.errors" :key="idx">
            第 {{ err.row }} 行: {{ err.error }}
          </div>
        </el-alert>
      </div>
      <template #footer>
        <el-button type="primary" @click="importResultVisible = false; loadSuppliers()">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload, Download, Document } from '@element-plus/icons-vue'
import { getSupplierList, createSupplier, updateSupplier, exportSuppliers, downloadSupplierTemplate } from '@/api/masterdata'
import AttachmentUpload from '@/components/AttachmentUpload.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/purchase/suppliers/',
  {
    confirmTitle: '确认删除供应商',
    confirmMessage: '此操作将永久删除选中的供应商记录，是否继续？',
    successMessage: '删除供应商成功',
    errorMessage: '删除供应商失败',
    onSuccess: () => loadSuppliers()
  }
)

const loading = ref(false)
const submitting = ref(false)
const suppliers = ref<any[]>([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增供应商')
const isEdit = ref(false)
const formRef = ref(null)
const attachmentDialogVisible = ref(false)
const currentSupplier = ref(null)
const activeFormTab = ref('basic')
const importResultVisible = ref(false)
const importResult = ref(null)
const uploadRef = ref(null)

const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const searchForm = reactive({ search: '', status: null })

// Upload configuration
const uploadUrl = computed(() => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
  return `${baseUrl}/masterdata/suppliers/import_excel/`
})
const uploadHeaders = computed(() => {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
})

const form = reactive({
  id: null,
  code: '',
  name: '',
  short_name: '',
  contact_person: '',
  phone: '',
  email: '',
  address: '',
  settlement_method: '',
  // 开票信息
  invoice_title: '',
  tax_number: '',
  bank_name: '',
  bank_account: '',
  registered_address: '',
  registered_phone: '',
  status: 'ACTIVE',
  notes: ''
})

const formRules = {
  name: [{ required: true, message: '请输入供应商名称', trigger: 'blur' }]
}

const loadSuppliers = async () => {
  loading.value = true
  try {
    const params = { 
      page: pagination.page, 
      page_size: pagination.pageSize,
      ...searchForm
    }
    Object.keys(params).forEach(k => { if (params[k] === null || params[k] === '') delete params[k] })
    const response = await getSupplierList(params)
    suppliers.value = response.results || response || []
    pagination.total = response.count || 0
  } catch (error) {
    ElMessage.error('加载供应商失败')
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.search = ''
  searchForm.status = null
  pagination.page = 1
  loadSuppliers()
}

const handleAdd = () => {
  dialogTitle.value = '新增供应商'
  isEdit.value = false
  activeFormTab.value = 'basic'
  Object.assign(form, { 
    id: null, code: '', name: '', short_name: '', contact_person: '', phone: '', 
    email: '', address: '', settlement_method: '',
    invoice_title: '', tax_number: '', bank_name: '', bank_account: '',
    registered_address: '', registered_phone: '', status: 'ACTIVE', notes: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑供应商'
  isEdit.value = true
  activeFormTab.value = 'basic'
  Object.assign(form, row)
  dialogVisible.value = true
}

// 删除功能已迁移到 useBatchDelete composable

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true
    if (isEdit.value) {
      await updateSupplier(form.id, form)
      ElMessage.success('更新供应商成功')
    } else {
      await createSupplier(form)
      ElMessage.success('创建供应商成功')
    }
    dialogVisible.value = false
    loadSuppliers()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('保存供应商失败: ' + (error.response?.data?.error || error.message))
  } finally {
    submitting.value = false
  }
}

const handleViewAttachments = (row) => {
  currentSupplier.value = row
  attachmentDialogVisible.value = true
}

const beforeUpload = (file) => {
  const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls')
  if (!isExcel) {
    ElMessage.error('只支持Excel文件格式(.xlsx, .xls)')
    return false
  }
  return true
}

const handleUploadSuccess = (response) => {
  importResult.value = response
  importResultVisible.value = true
  ElMessage.success(`导入完成：新增 ${response.success_count} 个，更新 ${response.update_count} 个`)
}

const handleUploadError = (error) => {
  console.error('Upload error:', error)
  ElMessage.error('导入失败，请检查文件格式')
}

const handleExport = async () => {
  try {
    const params = { ...searchForm }
    Object.keys(params).forEach(k => { if (params[k] === null || params[k] === '') delete params[k] })
    
    const response = await exportSuppliers(params)
    
    const filename = `供应商列表_${new Date().toISOString().split('T')[0]}.xlsx`
    const blob = response.data
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.style.display = 'none'
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    
    setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }, 100)
    
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

const downloadTemplate = async () => {
  try {
    const response = await downloadSupplierTemplate()
    
    if (!response || !response.data) {
      ElMessage.error('下载失败：没有收到响应数据')
      return
    }
    
    const contentDisposition = response.headers?.['content-disposition'] || ''
    let filename = '供应商导入模板.xlsx'
    const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
    if (filenameMatch && filenameMatch[1]) {
      filename = filenameMatch[1].replace(/['"]/g, '')
    }
    
    const blob = response.data
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.style.display = 'none'
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    
    setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }, 100)
    
    ElMessage.success('模板下载成功')
  } catch (error) {
    console.error('下载模板失败:', error)
    ElMessage.error('下载模板失败: ' + (error.message || '未知错误'))
  }
}

onMounted(() => {
  loadSuppliers()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}
.search-form {
  margin-bottom: 15px;
}
.text-success { color: #67c23a; font-weight: bold; }
.text-primary { color: #409eff; font-weight: bold; }
.text-danger { color: #f56c6c; font-weight: bold; }
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
