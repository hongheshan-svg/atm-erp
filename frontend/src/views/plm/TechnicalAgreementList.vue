<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>技术协议管理</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon> 新增协议
          </el-button>
        </div>
      </template>
      
      <!-- 搜索栏 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="协议编号">
          <el-input v-model="searchForm.agreement_no" placeholder="协议编号" clearable />
        </el-form-item>
        <el-form-item label="项目">
          <el-select v-model="searchForm.project" placeholder="选择项目" clearable>
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable>
            <el-option label="草稿" value="DRAFT" />
            <el-option label="内部评审" value="INTERNAL_REVIEW" />
            <el-option label="客户评审" value="CUSTOMER_REVIEW" />
            <el-option label="客户确认" value="CUSTOMER_CONFIRMED" />
            <el-option label="已签署" value="SIGNED" />
            <el-option label="已生效" value="EFFECTIVE" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>
      
      <!-- 数据表格 -->
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="agreement_no" label="协议编号" width="150" />
        <el-table-column prop="name" label="协议名称" min-width="200" />
        <el-table-column prop="project_name" label="项目" width="180" />
        <el-table-column prop="customer_name" label="客户" width="150" />
        <el-table-column prop="version" label="版本" width="80" align="center" />
        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="change_count" label="变更次数" width="100" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">查看</el-button>
            <el-button type="primary" link size="small" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-dropdown trigger="click" v-if="row.status !== 'EFFECTIVE'">
              <el-button type="primary" link size="small">更多</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleSubmitReview(row)" v-if="row.status === 'DRAFT'">提交评审</el-dropdown-item>
                  <el-dropdown-item @click="handleSendToCustomer(row)" v-if="row.status === 'INTERNAL_REVIEW'">发送客户</el-dropdown-item>
                  <el-dropdown-item @click="handleCustomerConfirm(row)" v-if="row.status === 'CUSTOMER_REVIEW'">客户确认</el-dropdown-item>
                  <el-dropdown-item @click="handleSign(row)" v-if="row.status === 'CUSTOMER_CONFIRMED'">签署</el-dropdown-item>
                  <el-dropdown-item @click="handleMakeEffective(row)" v-if="row.status === 'SIGNED'">生效</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 20px;"
      />
    </el-card>
    
    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px">
      <el-form :model="formData" :rules="formRules" ref="formRef" label-width="120px" :disabled="isViewMode">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="协议编号" prop="agreement_no">
              <el-input v-model="formData.agreement_no" placeholder="请输入协议编号" :disabled="isViewMode" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="版本号" prop="version">
              <el-input v-model="formData.version" placeholder="V1.0" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="协议名称" prop="name">
          <el-input v-model="formData.name" placeholder="技术协议名称" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="关联项目" prop="project">
              <el-select v-model="formData.project" placeholder="选择项目" style="width: 100%;">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户" prop="customer">
              <el-select v-model="formData.customer" placeholder="选择客户" style="width: 100%;">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="使用模板">
          <el-select v-model="selectedTemplate" placeholder="选择模板自动填充" style="width: 100%;" @change="applyTemplate">
            <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="协议内容" prop="content">
          <el-input v-model="formData.content" type="textarea" :rows="6" placeholder="协议内容" />
        </el-form-item>
        <el-form-item label="交付条款">
          <el-input v-model="formData.delivery_terms" type="textarea" :rows="3" placeholder="交付条款" />
        </el-form-item>
        <el-form-item label="质保条款">
          <el-input v-model="formData.warranty_terms" type="textarea" :rows="3" placeholder="质保条款" />
        </el-form-item>
        <el-form-item label="特殊要求">
          <el-input v-model="formData.special_requirements" type="textarea" :rows="3" placeholder="特殊要求" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ isViewMode ? '关闭' : '取消' }}</el-button>
        <el-button v-if="!isViewMode" type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { getAgreementList, getAgreement, createAgreement, updateAgreement, createAgreementFromTemplate, submitAgreementReview, sendAgreementToCustomer, confirmAgreement, signAgreement, makeAgreementEffective, getActiveAgreementTemplates } from '@/api/plm/agreement'
import { getProjectList } from '@/api/projects/project'
import { getCustomerList } from '@/api/masterdata'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects/agreements/', { onSuccess: () => loadData() })


const loading = ref(false)
const tableData = ref<any[]>([])
const projects = ref<any[]>([])
const customers = ref<any[]>([])
const templates = ref<any[]>([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增技术协议')
const formRef = ref(null)
const selectedTemplate = ref(null)
const isViewMode = ref(false)

const searchForm = reactive({
  agreement_no: '',
  project: null,
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const formData = reactive({
  id: null,
  agreement_no: '',
  name: '',
  version: 'V1.0',
  project: null,
  customer: null,
  content: '',
  delivery_terms: '',
  warranty_terms: '',
  special_requirements: ''
})

const formRules = {
  agreement_no: [{ required: true, message: '请输入协议编号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入协议名称', trigger: 'blur' }],
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  content: [{ required: true, message: '请输入协议内容', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'INTERNAL_REVIEW': 'warning',
    'CUSTOMER_REVIEW': 'warning',
    'CUSTOMER_CONFIRMED': 'success',
    'SIGNED': 'success',
    'EFFECTIVE': 'success',
    'CHANGED': 'warning',
    'CANCELLED': 'danger'
  }
  return types[status] || 'info'
}

const formatDate = (date) => {
  if (!date) return ''
  return new Date(date).toLocaleString('zh-CN')
}

const loadData = async () => {
  try {
    loading.value = true
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const res = await getAgreementList(params)
    tableData.value = res.results || res
    pagination.total = res.count || tableData.value.length
  } catch (error) {
    console.error('加载数据失败:', error)
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjectList({ page_size: 1000 })
    projects.value = res.results || res
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const loadCustomers = async () => {
  try {
    const res = await getCustomerList({ page_size: 1000 })
    customers.value = res.results || res
  } catch (error) {
    console.error('加载客户失败:', error)
  }
}

const loadTemplates = async () => {
  try {
    const res = await getActiveAgreementTemplates()
    templates.value = res
  } catch (error) {
    console.error('加载模板失败:', error)
  }
}

const resetSearch = () => {
  searchForm.agreement_no = ''
  searchForm.project = null
  searchForm.status = ''
  pagination.page = 1
  loadData()
}

const resetForm = () => {
  formData.id = null
  formData.agreement_no = ''
  formData.name = ''
  formData.version = 'V1.0'
  formData.project = null
  formData.customer = null
  formData.content = ''
  formData.delivery_terms = ''
  formData.warranty_terms = ''
  formData.special_requirements = ''
  selectedTemplate.value = null
}

const handleAdd = () => {
  resetForm()
  isViewMode.value = false
  dialogTitle.value = '新增技术协议'
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  try {
    // 用完整详情序列化器回填，避免列表精简序列化器丢失 content/条款等字段
    const data = await getAgreement(row.id)
    resetForm()
    Object.assign(formData, {
      id: data.id,
      agreement_no: data.agreement_no || '',
      name: data.name || '',
      version: data.version || 'V1.0',
      project: data.project ?? null,
      customer: data.customer ?? null,
      content: data.content || '',
      delivery_terms: data.delivery_terms || '',
      warranty_terms: data.warranty_terms || '',
      special_requirements: data.special_requirements || ''
    })
    isViewMode.value = false
    dialogTitle.value = '编辑技术协议'
    dialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载详情失败')
  }
}

const handleView = async (row) => {
  try {
    const data = await getAgreement(row.id)
    resetForm()
    Object.assign(formData, {
      id: data.id,
      agreement_no: data.agreement_no || '',
      name: data.name || '',
      version: data.version || 'V1.0',
      project: data.project ?? null,
      customer: data.customer ?? null,
      content: data.content || '',
      delivery_terms: data.delivery_terms || '',
      warranty_terms: data.warranty_terms || '',
      special_requirements: data.special_requirements || ''
    })
    isViewMode.value = true
    dialogTitle.value = '查看技术协议'
    dialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载详情失败')
  }
}

const applyTemplate = async () => {
  if (!selectedTemplate.value) return
  const tpl = templates.value.find((t) => t.id === selectedTemplate.value)
  if (formData.id) {
    // 已存在协议：调用后端 action 持久化套用模板
    try {
      const res = await createAgreementFromTemplate(formData.id, {
        template_id: selectedTemplate.value
      })
      Object.assign(formData, res)
      ElMessage.success('模板已应用')
    } catch (error) {
      ElMessage.error('应用模板失败')
    }
  } else if (tpl) {
    // 新建态：本地把模板内容填入表单（后端 action 需已存在 id）
    formData.content = tpl.content || formData.content
    formData.delivery_terms = tpl.delivery_terms || formData.delivery_terms
    formData.warranty_terms = tpl.warranty_terms || formData.warranty_terms
    ElMessage.success('模板内容已填入')
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    if (formData.id) {
      await updateAgreement(formData.id, formData)
      ElMessage.success('更新成功')
    } else {
      await createAgreement(formData)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    console.error('保存失败:', error)
  }
}

const handleSubmitReview = async (row) => {
  await ElMessageBox.confirm('确定提交内部评审？', '提示')
  try {
    await submitAgreementReview(row.id)
    ElMessage.success('已提交评审')
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleSendToCustomer = async (row) => {
  await ElMessageBox.confirm('确定发送给客户评审？', '提示')
  try {
    await sendAgreementToCustomer(row.id)
    ElMessage.success('已发送客户')
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleCustomerConfirm = async (row) => {
  await ElMessageBox.confirm('确定客户已确认？', '提示')
  try {
    await confirmAgreement(row.id, {
      customer_sign_date: new Date().toISOString().split('T')[0]
    })
    ElMessage.success('客户已确认')
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleSign = async (row) => {
  await ElMessageBox.confirm('确定签署协议？', '提示')
  try {
    await signAgreement(row.id, {
      sign_date: new Date().toISOString().split('T')[0]
    })
    ElMessage.success('已签署')
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleMakeEffective = async (row) => {
  await ElMessageBox.confirm('确定使协议生效？', '提示')
  try {
    await makeAgreementEffective(row.id)
    ElMessage.success('协议已生效')
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  loadData()
  loadProjects()
  loadCustomers()
  loadTemplates()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}
</style>
