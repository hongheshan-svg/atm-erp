<template>
  <div class="proposal-container">
    <div class="page-header">
      <h2>方案设计</h2>
      <el-button type="primary" @click="handleAdd">新建方案</el-button>
    </div>
    
    <!-- 统计 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.total || 0 }}</div>
          <div class="stat-label">方案总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card pending">
          <div class="stat-value">{{ stats.pending_review || 0 }}</div>
          <div class="stat-label">待评审</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card approved">
          <div class="stat-value">{{ approvedCount }}</div>
          <div class="stat-label">已批准</div>
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
            <el-input v-model="queryParams.search" placeholder="搜索方案" clearable @clear="fetchList" />
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchList">
              <el-option label="草稿" value="DRAFT" />
              <el-option label="已提交" value="SUBMITTED" />
              <el-option label="评审中" value="REVIEWING" />
              <el-option label="需修改" value="REVISION" />
              <el-option label="已批准" value="APPROVED" />
              <el-option label="已拒绝" value="REJECTED" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.proposal_type" placeholder="方案类型" clearable @change="fetchList">
              <el-option label="整体方案" value="SCHEME" />
              <el-option label="机械方案" value="MECHANICAL" />
              <el-option label="电气方案" value="ELECTRICAL" />
              <el-option label="软件方案" value="SOFTWARE" />
              <el-option label="集成方案" value="INTEGRATION" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="fetchList">查询</el-button>
          </el-form-item>
        </el-form>
      </template>
      
      <el-table :data="proposalList" v-loading="loading" border stripe>
        <el-table-column prop="proposal_no" label="方案编号" width="130" fixed />
        <el-table-column prop="title" label="方案名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="type_display" label="类型" width="100" />
        <el-table-column prop="version" label="版本" width="80" align="center" />
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="customer_name" label="客户" width="150" show-overflow-tooltip />
        <el-table-column prop="project_name" label="项目" width="150" show-overflow-tooltip />
        <el-table-column prop="author_name" label="编制人" width="100" />
        <el-table-column prop="estimated_cost" label="预估成本" width="120" align="right">
          <template #default="{ row }">
            {{ row.estimated_cost ? `¥${Number(row.estimated_cost).toLocaleString()}` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="estimated_days" label="预估工期" width="100" align="center">
          <template #default="{ row }">
            {{ row.estimated_days ? `${row.estimated_days}天` : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">详情</el-button>
            <el-button type="success" link size="small" @click="handleSubmit(row)" 
              v-if="row.status === 'DRAFT'">提交</el-button>
            <el-button type="warning" link size="small" @click="handleStartReview(row)" 
              v-if="row.status === 'SUBMITTED'">评审</el-button>
            <el-button type="success" link size="small" @click="handleApprove(row)" 
              v-if="row.status === 'REVIEWING'">批准</el-button>
            <el-button type="info" link size="small" @click="handleNewVersion(row)" 
              v-if="row.status === 'APPROVED'">新版本</el-button>
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
    
    <!-- 新增对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑方案' : '新建方案'" width="900px">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="方案名称" prop="title">
              <el-input v-model="formData.title" placeholder="请输入方案名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="方案类型" prop="proposal_type">
              <el-select v-model="formData.proposal_type" style="width: 100%">
                <el-option label="整体方案" value="SCHEME" />
                <el-option label="机械方案" value="MECHANICAL" />
                <el-option label="电气方案" value="ELECTRICAL" />
                <el-option label="软件方案" value="SOFTWARE" />
                <el-option label="集成方案" value="INTEGRATION" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="预估成本">
              <el-input-number v-model="formData.estimated_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预估工期">
              <el-input-number v-model="formData.estimated_days" :min="0" style="width: 100%">
                <template #suffix>天</template>
              </el-input-number>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="方案概述">
          <el-input v-model="formData.summary" type="textarea" :rows="3" placeholder="方案概述" />
        </el-form-item>
        <el-form-item label="技术要求">
          <el-input v-model="formData.technical_requirements" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="方案描述">
          <el-input v-model="formData.solution_description" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="关键技术">
          <el-input v-model="formData.key_technologies" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="风险分析">
          <el-input v-model="formData.risk_analysis" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 详情对话框 -->
    <el-dialog v-model="detailDialogVisible" :title="currentProposal?.title" width="1000px">
      <el-tabs v-if="currentProposal">
        <el-tab-pane label="基本信息">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="方案编号">{{ currentProposal.proposal_no }}</el-descriptions-item>
            <el-descriptions-item label="方案类型">{{ currentProposal.type_display }}</el-descriptions-item>
            <el-descriptions-item label="版本">{{ currentProposal.version }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(currentProposal.status)">{{ currentProposal.status_display }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="客户">{{ currentProposal.customer_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="项目">{{ currentProposal.project_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="编制人">{{ currentProposal.author_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="预估成本">
              {{ currentProposal.estimated_cost ? `¥${Number(currentProposal.estimated_cost).toLocaleString()}` : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="预估工期">
              {{ currentProposal.estimated_days ? `${currentProposal.estimated_days}天` : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="方案概述" :span="3">{{ currentProposal.summary || '-' }}</el-descriptions-item>
            <el-descriptions-item label="技术要求" :span="3">{{ currentProposal.technical_requirements || '-' }}</el-descriptions-item>
            <el-descriptions-item label="方案描述" :span="3">{{ currentProposal.solution_description || '-' }}</el-descriptions-item>
            <el-descriptions-item label="关键技术" :span="3">{{ currentProposal.key_technologies || '-' }}</el-descriptions-item>
            <el-descriptions-item label="风险分析" :span="3">{{ currentProposal.risk_analysis || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        <el-tab-pane label="评审记录" v-if="currentProposal.reviews?.length">
          <el-table :data="currentProposal.reviews" size="small" border>
            <el-table-column prop="review_date" label="评审日期" width="120" />
            <el-table-column prop="review_type" label="评审类型" width="120" />
            <el-table-column prop="result_display" label="结论" width="100">
              <template #default="{ row }">
                <el-tag :type="row.result === 'APPROVED' ? 'success' : 'warning'" size="small">
                  {{ row.result_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="conclusion" label="结论说明" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="关联文档" v-if="currentProposal.documents?.length">
          <el-table :data="currentProposal.documents" size="small" border>
            <el-table-column prop="name" label="文档名称" />
            <el-table-column prop="doc_type_display" label="类型" width="120" />
            <el-table-column prop="version" label="版本" width="80" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { getProposalList, getProposal, createProposal, patchProposal, getProposalStatistics, submitProposal, startProposalReview, approveProposal, createProposalVersion } from '@/api/plm/proposal'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const submitLoading = ref(false)
const proposalList = ref([])
const stats = ref({})

const queryParams = reactive({
  search: '',
  status: null,
  proposal_type: null
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
const currentProposal = ref(null)

const formData = reactive({
  title: '',
  proposal_type: 'SCHEME',
  estimated_cost: null,
  estimated_days: null,
  summary: '',
  technical_requirements: '',
  solution_description: '',
  key_technologies: '',
  risk_analysis: ''
})

const rules = {
  title: [{ required: true, message: '请输入方案名称', trigger: 'blur' }],
  proposal_type: [{ required: true, message: '请选择方案类型', trigger: 'change' }]
}

const approvedCount = computed(() => {
  const byStatus = stats.value.by_status || []
  return byStatus.find(s => s.status === 'APPROVED')?.count || 0
})

const fetchList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.size,
      ...queryParams
    }
    const data = await getProposalList(params)
    proposalList.value = data.results || data
    pagination.total = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    const data = await getProposalStatistics()
    stats.value = data
  } catch (e) {
    console.error(e)
  }
}

const handleAdd = () => {
  isEdit.value = false
  Object.assign(formData, {
    title: '',
    proposal_type: 'SCHEME',
    estimated_cost: null,
    estimated_days: null,
    summary: '',
    technical_requirements: '',
    solution_description: '',
    key_technologies: '',
    risk_analysis: ''
  })
  dialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await patchProposal(currentProposal.value.id, formData)
    } else {
      await createProposal(formData)
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
    const data = await getProposal(row.id)
    currentProposal.value = data
    detailDialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

const handleSubmit = async (row) => {
  try {
    await submitProposal(row.id)
    ElMessage.success('已提交')
    fetchList()
    fetchStats()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  }
}

const handleStartReview = async (row) => {
  try {
    await startProposalReview(row.id, { review_type: '技术评审' })
    ElMessage.success('已开始评审')
    fetchList()
    fetchStats()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  }
}

const handleApprove = async (row) => {
  try {
    await approveProposal(row.id)
    ElMessage.success('已批准')
    fetchList()
    fetchStats()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  }
}

const handleNewVersion = async (row) => {
  try {
    await ElMessageBox.confirm('确定创建新版本吗?', '提示')
    await createProposalVersion(row.id)
    ElMessage.success('新版本已创建')
    fetchList()
  } catch (e) {
    console.error('ProposalList fetchList error:', e)
  }
}

const getStatusType = (status) => {
  const types = {
    DRAFT: 'info',
    SUBMITTED: 'warning',
    REVIEWING: 'warning',
    REVISION: 'danger',
    APPROVED: 'success',
    REJECTED: 'danger',
    ARCHIVED: 'info'
  }
  return types[status] || ''
}

onMounted(() => {
  fetchList()
  fetchStats()
})
</script>

<style scoped>
.proposal-container {
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
.stat-card.approved .stat-value { color: #67c23a; }
.stat-card.new .stat-value { color: #909399; }
</style>
