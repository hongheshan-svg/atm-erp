<template>
  <div class="requirement-container">
    <div class="page-header">
      <h2>需求管理</h2>
      <el-button type="primary" @click="handleAdd">新增需求</el-button>
    </div>
    
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.total || 0 }}</div>
          <div class="stat-label">总需求数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card pending">
          <div class="stat-value">{{ stats.pending || 0 }}</div>
          <div class="stat-label">待处理</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card progress">
          <div class="stat-value">{{ stats.in_progress || 0 }}</div>
          <div class="stat-label">实施中</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card new">
          <div class="stat-value">{{ stats.new_this_month || 0 }}</div>
          <div class="stat-label">本月新增</div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-card shadow="never">
      <template #header>
        <el-form :inline="true">
          <el-form-item>
            <el-input v-model="queryParams.search" placeholder="搜索需求" clearable @clear="fetchList" />
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchList">
              <el-option label="草稿" value="DRAFT" />
              <el-option label="已提交" value="SUBMITTED" />
              <el-option label="评审中" value="REVIEWING" />
              <el-option label="已批准" value="APPROVED" />
              <el-option label="实施中" value="IN_PROGRESS" />
              <el-option label="已完成" value="COMPLETED" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.priority" placeholder="优先级" clearable @change="fetchList">
              <el-option label="低" value="LOW" />
              <el-option label="中" value="MEDIUM" />
              <el-option label="高" value="HIGH" />
              <el-option label="紧急" value="CRITICAL" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="fetchList">查询</el-button>
          </el-form-item>
        </el-form>
      </template>
      
      <el-table :data="requirementList" v-loading="loading" border stripe>
        <el-table-column prop="req_no" label="需求编号" width="130" fixed />
        <el-table-column prop="title" label="需求标题" min-width="250" show-overflow-tooltip />
        <el-table-column prop="type_display" label="类型" width="100" />
        <el-table-column prop="priority_display" label="优先级" width="80">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)" size="small">{{ row.priority_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="customer_name" label="客户" width="150" show-overflow-tooltip />
        <el-table-column prop="project_name" label="项目" width="150" show-overflow-tooltip />
        <el-table-column prop="owner_name" label="负责人" width="100" />
        <el-table-column prop="due_date" label="期望日期" width="110" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">详情</el-button>
            <el-button type="success" link size="small" @click="handleSubmit(row)" 
              v-if="row.status === 'DRAFT'">提交</el-button>
            <el-button type="warning" link size="small" @click="handleApprove(row)" 
              v-if="row.status === 'SUBMITTED' || row.status === 'REVIEWING'">批准</el-button>
            <el-button type="info" link size="small" @click="handleDecompose(row)">分解</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchList"
        @current-change="fetchList"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>
    
    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑需求' : '新增需求'" width="800px">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="需求标题" prop="title">
              <el-input v-model="formData.title" placeholder="请输入需求标题" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="需求类型" prop="req_type">
              <el-select v-model="formData.req_type" style="width: 100%">
                <el-option label="功能需求" value="FUNCTIONAL" />
                <el-option label="性能需求" value="PERFORMANCE" />
                <el-option label="接口需求" value="INTERFACE" />
                <el-option label="安全需求" value="SAFETY" />
                <el-option label="质量需求" value="QUALITY" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="formData.priority" style="width: 100%">
                <el-option label="低" value="LOW" />
                <el-option label="中" value="MEDIUM" />
                <el-option label="高" value="HIGH" />
                <el-option label="紧急" value="CRITICAL" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="期望日期">
              <el-date-picker v-model="formData.due_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="需求描述" prop="description">
          <el-input v-model="formData.description" type="textarea" :rows="4" placeholder="详细描述需求内容" />
        </el-form-item>
        <el-form-item label="验收标准">
          <el-input v-model="formData.acceptance_criteria" type="textarea" :rows="3" placeholder="需求验收标准" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="预估工时">
              <el-input-number v-model="formData.estimated_hours" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预估成本">
              <el-input-number v-model="formData.estimated_cost" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 详情对话框 -->
    <el-dialog v-model="detailDialogVisible" :title="currentReq?.title" width="900px">
      <el-descriptions v-if="currentReq" :column="3" border>
        <el-descriptions-item label="需求编号">{{ currentReq.req_no }}</el-descriptions-item>
        <el-descriptions-item label="需求类型">{{ currentReq.type_display }}</el-descriptions-item>
        <el-descriptions-item label="优先级">
          <el-tag :type="getPriorityType(currentReq.priority)">{{ currentReq.priority_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentReq.status)">{{ currentReq.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="客户">{{ currentReq.customer_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ currentReq.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="负责人">{{ currentReq.owner_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="提出日期">{{ currentReq.request_date }}</el-descriptions-item>
        <el-descriptions-item label="期望日期">{{ currentReq.due_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="需求描述" :span="3">{{ currentReq.description }}</el-descriptions-item>
        <el-descriptions-item label="验收标准" :span="3">{{ currentReq.acceptance_criteria || '-' }}</el-descriptions-item>
      </el-descriptions>
      
      <el-divider content-position="left" v-if="currentReq?.traces?.length">追溯关联</el-divider>
      <el-table :data="currentReq?.traces" v-if="currentReq?.traces?.length" border size="small">
        <el-table-column prop="trace_type_display" label="类型" width="100" />
        <el-table-column prop="target_name" label="名称" />
        <el-table-column prop="description" label="说明" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const submitLoading = ref(false)
const requirementList = ref([])
const stats = ref({})

const queryParams = reactive({
  search: '',
  status: null,
  priority: null
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

const dialogVisible = ref(false)
const detailDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const currentReq = ref(null)

const formData = reactive({
  title: '',
  req_type: 'FUNCTIONAL',
  priority: 'MEDIUM',
  due_date: '',
  description: '',
  acceptance_criteria: '',
  estimated_hours: null,
  estimated_cost: null
})

const rules = {
  title: [{ required: true, message: '请输入需求标题', trigger: 'blur' }],
  req_type: [{ required: true, message: '请选择需求类型', trigger: 'change' }],
  description: [{ required: true, message: '请输入需求描述', trigger: 'blur' }]
}

const fetchList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.size,
      ...queryParams
    }
    const { data } = await request.get('/projects/requirements/', { params })
    requirementList.value = data.results || data
    pagination.total = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    const { data } = await request.get('/projects/requirements/statistics/')
    stats.value = data
    
    // 计算待处理和实施中数量
    const byStatus = data.by_status || []
    stats.value.pending = byStatus.filter(s => 
      ['SUBMITTED', 'REVIEWING', 'APPROVED'].includes(s.status)
    ).reduce((sum, s) => sum + s.count, 0)
    stats.value.in_progress = byStatus.find(s => s.status === 'IN_PROGRESS')?.count || 0
  } catch (e) {
    console.error(e)
  }
}

const handleAdd = () => {
  isEdit.value = false
  Object.assign(formData, {
    title: '',
    req_type: 'FUNCTIONAL',
    priority: 'MEDIUM',
    due_date: '',
    description: '',
    acceptance_criteria: '',
    estimated_hours: null,
    estimated_cost: null
  })
  dialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await request.patch(`/projects/requirements/${currentReq.value.id}/`, formData)
    } else {
      await request.post('/projects/requirements/', formData)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    fetchList()
    fetchStats()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    submitLoading.value = false
  }
}

const handleView = async (row) => {
  try {
    const { data } = await request.get(`/projects/requirements/${row.id}/`)
    currentReq.value = data
    detailDialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

const handleSubmit = async (row) => {
  try {
    await request.post(`/projects/requirements/${row.id}/submit/`)
    ElMessage.success('已提交')
    fetchList()
    fetchStats()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  }
}

const handleApprove = async (row) => {
  try {
    await request.post(`/projects/requirements/${row.id}/approve/`)
    ElMessage.success('已批准')
    fetchList()
    fetchStats()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  }
}

const handleDecompose = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入子需求标题(多个用逗号分隔)', '分解需求', {
      inputPlaceholder: '子需求1, 子需求2'
    })
    
    if (!value) return
    
    const children = value.split(',').map(t => ({ title: t.trim(), description: '' }))
    await request.post(`/projects/requirements/${row.id}/decompose/`, { children })
    ElMessage.success('分解成功')
    fetchList()
  } catch (e) {
    // 取消
  }
}

const getPriorityType = (priority) => {
  const types = { LOW: 'info', MEDIUM: '', HIGH: 'warning', CRITICAL: 'danger' }
  return types[priority] || ''
}

const getStatusType = (status) => {
  const types = {
    DRAFT: 'info',
    SUBMITTED: 'warning',
    REVIEWING: 'warning',
    APPROVED: 'success',
    IN_PROGRESS: '',
    COMPLETED: 'success',
    CANCELLED: 'info'
  }
  return types[status] || ''
}

onMounted(() => {
  fetchList()
  fetchStats()
})
</script>

<style scoped>
.requirement-container {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 16px 0;
}

.stat-card .stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}

.stat-card .stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.stat-card.pending .stat-value { color: #e6a23c; }
.stat-card.progress .stat-value { color: #67c23a; }
.stat-card.new .stat-value { color: #909399; }
</style>

