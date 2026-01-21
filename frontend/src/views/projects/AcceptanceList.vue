<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>验收管理 (FAT/SAT)</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon> 新增验收
          </el-button>
        </div>
      </template>
      
      <!-- 统计卡片 -->
      <el-row :gutter="20" class="stats-row">
        <el-col :span="4">
          <el-statistic title="总验收单" :value="stats.total" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="进行中" :value="stats.in_progress" :value-style="{ color: '#409eff' }" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="已通过" :value="stats.passed" :value-style="{ color: '#67c23a' }" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="有条件通过" :value="stats.conditional" :value-style="{ color: '#e6a23c' }" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="不通过" :value="stats.failed" :value-style="{ color: '#f56c6c' }" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="待评审" :value="stats.pending" />
        </el-col>
      </el-row>
      
      <!-- 搜索栏 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="验收类型">
          <el-select v-model="searchForm.acceptance_type" placeholder="选择类型" clearable>
            <el-option label="出厂验收(FAT)" value="FAT" />
            <el-option label="现场验收(SAT)" value="SAT" />
            <el-option label="部分验收" value="PARTIAL" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目">
          <el-select v-model="searchForm.project" placeholder="选择项目" clearable filterable>
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable>
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已计划" value="PLANNED" />
            <el-option label="进行中" value="IN_PROGRESS" />
            <el-option label="待评审" value="PENDING_REVIEW" />
            <el-option label="验收通过" value="PASSED" />
            <el-option label="有条件通过" value="CONDITIONAL" />
            <el-option label="验收不通过" value="FAILED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>
      
      <!-- 数据表格 -->
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="acceptance_no" label="验收单号" width="150" />
        <el-table-column prop="name" label="验收名称" min-width="180" />
        <el-table-column prop="acceptance_type" label="类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.acceptance_type === 'FAT' ? 'primary' : 'success'">
              {{ row.type_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="项目" width="150" />
        <el-table-column prop="customer_name" label="客户" width="120" />
        <el-table-column prop="equipment_no" label="设备编号" width="120" />
        <el-table-column prop="planned_date" label="计划日期" width="110" />
        <el-table-column prop="pass_rate" label="通过率" width="100" align="center">
          <template #default="{ row }">
            <el-progress :percentage="row.pass_rate || 0" :status="getProgressStatus(row.pass_rate)" />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="issue_count" label="待处理问题" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.issue_count > 0" type="danger">{{ row.issue_count }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">详情</el-button>
            <el-button type="primary" link size="small" @click="handleEdit(row)" v-if="['DRAFT', 'PLANNED'].includes(row.status)">编辑</el-button>
            <el-button type="success" link size="small" @click="handleStart(row)" v-if="['DRAFT', 'PLANNED'].includes(row.status)">开始</el-button>
            <el-button type="primary" link size="small" @click="handleReport(row)" v-if="['PASSED', 'CONDITIONAL', 'FAILED'].includes(row.status)">报告</el-button>
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
      <el-form :model="formData" :rules="formRules" ref="formRef" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="验收单号" prop="acceptance_no">
              <el-input v-model="formData.acceptance_no" placeholder="自动生成或手动输入" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="验收类型" prop="acceptance_type">
              <el-select v-model="formData.acceptance_type" placeholder="选择类型" style="width: 100%;">
                <el-option label="出厂验收(FAT)" value="FAT" />
                <el-option label="现场验收(SAT)" value="SAT" />
                <el-option label="部分验收" value="PARTIAL" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="验收名称" prop="name">
          <el-input v-model="formData.name" placeholder="验收名称" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="关联项目" prop="project">
              <el-select v-model="formData.project" placeholder="选择项目" style="width: 100%;" filterable>
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户" prop="customer">
              <el-select v-model="formData.customer" placeholder="选择客户" style="width: 100%;" filterable>
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="设备" prop="equipment">
              <el-select v-model="formData.equipment" placeholder="选择设备" style="width: 100%;" clearable filterable>
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.equipment_no} - ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划日期" prop="planned_date">
              <el-date-picker v-model="formData.planned_date" type="date" placeholder="选择日期" style="width: 100%;" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="验收地点" prop="location">
          <el-input v-model="formData.location" placeholder="验收地点" />
        </el-form-item>
        <el-form-item label="使用模板">
          <el-select v-model="selectedTemplate" placeholder="选择验收模板" style="width: 100%;" @change="applyTemplate">
            <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const tableData = ref([])
const projects = ref([])
const customers = ref([])
const equipments = ref([])
const templates = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增验收')
const formRef = ref(null)
const selectedTemplate = ref(null)

const stats = reactive({
  total: 0,
  in_progress: 0,
  passed: 0,
  conditional: 0,
  failed: 0,
  pending: 0
})

const searchForm = reactive({
  acceptance_type: '',
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
  acceptance_no: '',
  name: '',
  acceptance_type: 'FAT',
  project: null,
  customer: null,
  equipment: null,
  planned_date: '',
  location: ''
})

const formRules = {
  acceptance_no: [{ required: true, message: '请输入验收单号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入验收名称', trigger: 'blur' }],
  acceptance_type: [{ required: true, message: '请选择验收类型', trigger: 'change' }],
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  planned_date: [{ required: true, message: '请选择计划日期', trigger: 'change' }],
  location: [{ required: true, message: '请输入验收地点', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'PLANNED': 'info',
    'IN_PROGRESS': 'warning',
    'PENDING_REVIEW': 'warning',
    'PASSED': 'success',
    'CONDITIONAL': 'warning',
    'FAILED': 'danger',
    'CANCELLED': 'info'
  }
  return types[status] || 'info'
}

const getProgressStatus = (rate) => {
  if (rate >= 90) return 'success'
  if (rate >= 60) return 'warning'
  return 'exception'
}

const loadData = async () => {
  try {
    loading.value = true
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const res = await request.get('/projects/acceptances/', { params })
    tableData.value = res.results || res
    pagination.total = res.count || tableData.value.length
  } catch (error) {
    console.error('加载数据失败:', error)
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const res = await request.get('/projects/acceptances/statistics/')
    stats.total = res.total || 0
    stats.in_progress = res.by_status?.IN_PROGRESS?.count || 0
    stats.passed = res.by_status?.PASSED?.count || 0
    stats.conditional = res.by_status?.CONDITIONAL?.count || 0
    stats.failed = res.by_status?.FAILED?.count || 0
    stats.pending = res.by_status?.PENDING_REVIEW?.count || 0
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const loadProjects = async () => {
  try {
    const res = await request.get('/projects/projects/', { params: { page_size: 1000 } })
    projects.value = res.results || res
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const loadCustomers = async () => {
  try {
    const res = await request.get('/masterdata/customers/', { params: { page_size: 1000 } })
    customers.value = res.results || res
  } catch (error) {
    console.error('加载客户失败:', error)
  }
}

const loadEquipments = async () => {
  try {
    const res = await request.get('/projects/equipment-archives/', { params: { page_size: 1000 } })
    equipments.value = res.results || res
  } catch (error) {
    console.error('加载设备失败:', error)
  }
}

const loadTemplates = async () => {
  try {
    const res = await request.get('/projects/acceptance-templates/active_templates/')
    templates.value = res
  } catch (error) {
    console.error('加载模板失败:', error)
  }
}

const resetSearch = () => {
  searchForm.acceptance_type = ''
  searchForm.project = null
  searchForm.status = ''
  pagination.page = 1
  loadData()
}

const resetForm = () => {
  formData.id = null
  formData.acceptance_no = ''
  formData.name = ''
  formData.acceptance_type = 'FAT'
  formData.project = null
  formData.customer = null
  formData.equipment = null
  formData.planned_date = ''
  formData.location = ''
  selectedTemplate.value = null
}

const handleAdd = () => {
  resetForm()
  dialogTitle.value = '新增验收'
  dialogVisible.value = true
}

const handleEdit = (row) => {
  Object.assign(formData, row)
  dialogTitle.value = '编辑验收'
  dialogVisible.value = true
}

const handleView = (row) => {
  // TODO: 跳转到详情页
  ElMessage.info('查看详情: ' + row.acceptance_no)
}

const handleReport = (row) => {
  // TODO: 生成报告
  ElMessage.info('生成报告: ' + row.acceptance_no)
}

const applyTemplate = async () => {
  if (!selectedTemplate.value || !formData.id) return
  try {
    const res = await request.post(`/projects/acceptances/${formData.id}/apply_template/`, {
      template_id: selectedTemplate.value
    })
    ElMessage.success('模板已应用，检查项已生成')
  } catch (error) {
    ElMessage.error('应用模板失败')
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    if (formData.id) {
      await request.put(`/projects/acceptances/${formData.id}/`, formData)
      ElMessage.success('更新成功')
    } else {
      await request.post('/projects/acceptances/', formData)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
    loadStats()
  } catch (error) {
    console.error('保存失败:', error)
  }
}

const handleStart = async (row) => {
  await ElMessageBox.confirm('确定开始验收？', '提示')
  try {
    await request.post(`/projects/acceptances/${row.id}/start/`)
    ElMessage.success('验收已开始')
    loadData()
    loadStats()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  loadData()
  loadStats()
  loadProjects()
  loadCustomers()
  loadEquipments()
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

.stats-row {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.search-form {
  margin-bottom: 20px;
}
</style>
