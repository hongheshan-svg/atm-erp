<template>
  <div class="lead-container">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>销售线索管理</span>
          <el-button type="primary" v-permission="'sales:quotation:create'" @click="handleCreate"><el-icon><Plus /></el-icon> 新建线索</el-button>
        </div>
      </template>

      <!-- 统计 -->
      <el-row :gutter="16" class="stat-row">
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-value">{{ statistics.total }}</div>
            <div class="stat-label">总线索</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item new">
            <div class="stat-value">{{ statistics.by_status?.NEW || 0 }}</div>
            <div class="stat-label">新线索</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item success">
            <div class="stat-value">{{ statistics.by_status?.CONVERTED || 0 }}</div>
            <div class="stat-label">已转化</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-value">{{ statistics.conversion_rate }}%</div>
            <div class="stat-label">转化率</div>
          </div>
        </el-col>
      </el-row>

      <!-- 筛选 -->
      <div class="filter-area">
        <el-input v-model="queryParams.search" placeholder="搜索公司/联系人/电话" style="width: 240px" clearable @keyup.enter="handleSearch">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="queryParams.status" placeholder="状态" clearable @change="handleSearch">
          <el-option label="新线索" value="NEW" />
          <el-option label="已联系" value="CONTACTED" />
          <el-option label="已确认" value="QUALIFIED" />
          <el-option label="已转化" value="CONVERTED" />
          <el-option label="已作废" value="DISQUALIFIED" />
        </el-select>
        <el-select v-model="queryParams.source" placeholder="来源" clearable @change="handleSearch">
          <el-option v-for="s in sourceOptions" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </div>

      <!-- 表格 -->
      <el-table :data="leads" v-loading="loading" stripe style="width: 100%; margin-top: 16px">
        <el-table-column prop="lead_no" label="线索编号" width="140" />
        <el-table-column prop="company_name" label="公司名称" min-width="180" />
        <el-table-column prop="contact_name" label="联系人" width="100" />
        <el-table-column prop="contact_phone" label="电话" width="130" />
        <el-table-column prop="industry" label="行业" width="100" />
        <el-table-column prop="source_name" label="来源" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="owner_name" label="负责人" width="100" />
        <el-table-column prop="score" label="评分" width="80">
          <template #default="{ row }">
            <el-rate v-model="row.score" :max="5" disabled size="small" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="canDelete ? 250 : 180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" v-permission="'sales:quotation:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="success" @click="handleConvert(row)" v-if="row.status !== 'CONVERTED' && row.status !== 'DISQUALIFIED'">转化</el-button>
            <!-- 仅管理员显示删除按钮 -->
            <el-button 
              v-if="canDelete"
              size="small" 
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
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" destroy-on-close>
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="公司名称" prop="company_name">
              <el-input v-model="formData.company_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系人" prop="contact_name">
              <el-input v-model="formData.contact_name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="formData.contact_phone" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="formData.contact_email" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="行业">
              <el-input v-model="formData.industry" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="线索来源">
              <el-select v-model="formData.source" placeholder="选择来源" style="width: 100%">
                <el-option v-for="s in sourceOptions" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="预算范围">
              <el-input v-model="formData.budget_range" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预期交期">
              <el-date-picker v-model="formData.expected_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="需求描述">
          <el-input v-model="formData.requirement" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="formData.address" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- 转化对话框 -->
    <el-dialog v-model="convertDialogVisible" title="线索转化" width="500px">
      <el-form :model="convertData" label-width="120px">
        <el-form-item label="创建新客户">
          <el-switch v-model="convertData.create_customer" />
        </el-form-item>
        <el-form-item label="创建商机">
          <el-switch v-model="convertData.create_opportunity" />
        </el-form-item>
        <el-form-item label="商机名称" v-if="convertData.create_opportunity">
          <el-input v-model="convertData.opportunity_name" />
        </el-form-item>
        <el-form-item label="预估金额" v-if="convertData.create_opportunity">
          <el-input-number v-model="convertData.estimated_amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="convertDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitConvert" :loading="converting">确认转化</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import {
  getLeadList,
  getLeadStatistics,
  getLeadSourceList,
  createLead,
  updateLead,
  convertLead
} from '@/api/sales/crm'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/sales/leads/',
  {
    confirmTitle: '确认删除销售线索',
    confirmMessage: '此操作将永久删除选中的线索记录，是否继续？',
    successMessage: '删除线索成功',
    errorMessage: '删除线索失败',
    onSuccess: () => fetchData()
  }
)

const loading = ref(false)
const submitting = ref(false)
const converting = ref(false)
const dialogVisible = ref(false)
const convertDialogVisible = ref(false)
const dialogTitle = ref('新建线索')
const leads = ref([])
const total = ref(0)
const sourceOptions = ref([])
const statistics = reactive({
  total: 0,
  by_status: {},
  conversion_rate: 0
})

const queryParams = reactive({
  search: '',
  status: '',
  source: '',
  page: 1,
  page_size: 20
})

const formRef = ref(null)
const formData = reactive({
  id: null,
  company_name: '',
  contact_name: '',
  contact_phone: '',
  contact_email: '',
  industry: '',
  source: null,
  budget_range: '',
  expected_date: null,
  requirement: '',
  address: ''
})

const convertData = reactive({
  lead_id: null,
  create_customer: true,
  create_opportunity: true,
  opportunity_name: '',
  estimated_amount: 0
})

const formRules = {
  company_name: [{ required: true, message: '请输入公司名称', trigger: 'blur' }],
  contact_name: [{ required: true, message: '请输入联系人', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const map = { NEW: 'info', CONTACTED: '', QUALIFIED: 'warning', CONVERTED: 'success', DISQUALIFIED: 'danger' }
  return map[status] || ''
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const fetchData = async () => {
  loading.value = true
  try {
    const [listRes, statsRes] = await Promise.all([
      getLeadList(queryParams),
      getLeadStatistics()
    ])
    // request.js已返回response.data，无需再访问.data
    leads.value = listRes.results || listRes || []
    total.value = listRes.count || leads.value.length
    Object.assign(statistics, statsRes || {})
  } catch (error) {
    console.error('获取数据失败', error)
  } finally {
    loading.value = false
  }
}

const fetchSources = async () => {
  try {
    const res = await getLeadSourceList({ is_active: true })
    // request.js已返回response.data，无需再访问.data
    sourceOptions.value = res.results || res || []
  } catch (error) {
    console.error('获取来源失败', error)
  }
}

const handleSearch = () => {
  queryParams.page = 1
  fetchData()
}

const handleCreate = () => {
  dialogTitle.value = '新建线索'
  Object.assign(formData, {
    id: null,
    company_name: '',
    contact_name: '',
    contact_phone: '',
    contact_email: '',
    industry: '',
    source: null,
    budget_range: '',
    expected_date: null,
    requirement: '',
    address: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑线索'
  Object.assign(formData, row)
  dialogVisible.value = true
}

const handleSubmit = async () => {
  const valid = await formRef.value.validate()
  if (!valid) return

  submitting.value = true
  try {
    if (formData.id) {
      await updateLead(formData.id, formData)
      ElMessage.success('更新成功')
    } else {
      await createLead(formData)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

const handleConvert = (row) => {
  convertData.lead_id = row.id
  convertData.opportunity_name = `${row.company_name}商机`
  convertData.create_customer = true
  convertData.create_opportunity = true
  convertData.estimated_amount = 0
  convertDialogVisible.value = true
}

const submitConvert = async () => {
  converting.value = true
  try {
    await convertLead(convertData.lead_id, convertData)
    ElMessage.success('转化成功')
    convertDialogVisible.value = false
    fetchData()
  } catch (error) {
    ElMessage.error('转化失败')
  } finally {
    converting.value = false
  }
}

onMounted(() => {
  fetchData()
  fetchSources()
})
</script>

<style scoped lang="scss">
.lead-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-row {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  
  .stat-value {
    font-size: 28px;
    font-weight: 600;
    color: #303133;
  }
  
  .stat-label {
    font-size: 13px;
    color: #909399;
    margin-top: 4px;
  }
  
  &.new {
    background: #ecf5ff;
    .stat-value { color: #409EFF; }
  }
  
  &.success {
    background: #f0f9eb;
    .stat-value { color: #67C23A; }
  }
}

.filter-area {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 10px;
  border: 1px solid #e4e7ed;
}
.table-toolbar span {
  font-size: 14px;
  color: #606266;
}

</style>
