<template>
  <div class="opportunity-container">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic :value="statistics.total" title="商机总数">
            <template #prefix><el-icon><Opportunity /></el-icon></template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic :value="statistics.total_amount" :precision="0" title="预估总金额">
            <template #prefix>¥</template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic :value="statistics.weighted_amount" :precision="0" title="加权金额">
            <template #prefix>¥</template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card success">
          <el-statistic :value="statistics.win_rate" :precision="1" title="赢单率">
            <template #suffix>%</template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作区 -->
    <el-card class="filter-card">
      <div class="filter-area">
        <el-input v-model="queryParams.search" placeholder="搜索商机..." style="width: 240px" clearable @keyup.enter="handleSearch">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="queryParams.stage" placeholder="阶段" clearable style="width: 140px" @change="handleSearch">
          <el-option v-for="s in stageOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select v-model="queryParams.priority" placeholder="优先级" clearable style="width: 120px" @change="handleSearch">
          <el-option v-for="p in priorityOptions" :key="p.value" :label="p.label" :value="p.value" />
        </el-select>
        <el-button type="primary" @click="handleCreate"><el-icon><Plus /></el-icon> 新建商机</el-button>
      </div>
    </el-card>

    <!-- 看板视图 -->
    <div class="kanban-container">
      <div v-for="stage in kanbanStages" :key="stage.value" class="kanban-column">
        <div class="column-header" :style="{ borderColor: stage.color }">
          <span class="stage-name">{{ stage.label }}</span>
          <el-badge :value="getStageOpportunities(stage.value).length" :type="stage.type" />
        </div>
        <div class="column-body">
          <div
            v-for="opp in getStageOpportunities(stage.value)"
            :key="opp.id"
            class="opportunity-card"
            @click="handleView(opp)"
          >
            <div class="card-header">
              <span class="opp-name">{{ opp.name }}</span>
              <el-tag :type="getPriorityType(opp.priority)" size="small">{{ opp.priority_display }}</el-tag>
            </div>
            <div class="card-body">
              <div class="customer">{{ opp.customer_name }}</div>
              <div class="amount">¥{{ formatNumber(opp.estimated_amount) }}</div>
            </div>
            <div class="card-footer">
              <span class="probability">{{ opp.probability }}%</span>
              <span class="date">{{ opp.expected_close_date || '未设置' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" destroy-on-close>
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="商机名称" prop="name">
              <el-input v-model="formData.name" placeholder="请输入商机名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户" prop="customer">
              <el-select v-model="formData.customer" filterable placeholder="选择客户" style="width: 100%">
                <el-option v-for="c in customerOptions" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-input v-model="formData.contact_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="formData.contact_phone" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="预估金额" prop="estimated_amount">
              <el-input-number v-model="formData.estimated_amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="成功概率">
              <el-slider v-model="formData.probability" :step="10" show-stops />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="阶段">
              <el-select v-model="formData.stage" style="width: 100%">
                <el-option v-for="s in stageOptions" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级">
              <el-select v-model="formData.priority" style="width: 100%">
                <el-option v-for="p in priorityOptions" :key="p.value" :label="p.label" :value="p.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="预计成交日">
              <el-date-picker v-model="formData.expected_close_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="产品类型">
              <el-input v-model="formData.product_type" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="需求描述">
          <el-input v-model="formData.requirement" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="竞争对手">
          <el-input v-model="formData.competitors" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Plus, Opportunity } from '@element-plus/icons-vue'
import {
  getOpportunityList,
  getOpportunityStatistics,
  createOpportunity,
  updateOpportunity
} from '@/api/sales/crm'
import { getCustomerList } from '@/api/masterdata/customer'

// 状态
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('新建商机')
const opportunities = ref([])
const customerOptions = ref([])
const statistics = reactive({
  total: 0,
  total_amount: 0,
  weighted_amount: 0,
  win_rate: 0
})

const queryParams = reactive({
  search: '',
  stage: '',
  priority: '',
  page: 1,
  page_size: 200
})

const formRef = ref(null)
const formData = reactive({
  id: null,
  name: '',
  customer: null,
  contact_name: '',
  contact_phone: '',
  stage: 'QUALIFICATION',
  priority: 'MEDIUM',
  probability: 20,
  estimated_amount: 0,
  expected_close_date: null,
  product_type: '',
  requirement: '',
  competitors: ''
})

const formRules = {
  name: [{ required: true, message: '请输入商机名称', trigger: 'blur' }],
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  estimated_amount: [{ required: true, message: '请输入预估金额', trigger: 'blur' }]
}

const stageOptions = [
  { value: 'QUALIFICATION', label: '需求确认' },
  { value: 'NEEDS_ANALYSIS', label: '需求分析' },
  { value: 'PROPOSAL', label: '方案报价' },
  { value: 'NEGOTIATION', label: '商务谈判' },
  { value: 'CLOSED_WON', label: '赢单' },
  { value: 'CLOSED_LOST', label: '丢单' }
]

const priorityOptions = [
  { value: 'LOW', label: '低' },
  { value: 'MEDIUM', label: '中' },
  { value: 'HIGH', label: '高' },
  { value: 'CRITICAL', label: '紧急' }
]

const kanbanStages = [
  { value: 'QUALIFICATION', label: '需求确认', color: '#909399', type: 'info' },
  { value: 'NEEDS_ANALYSIS', label: '需求分析', color: '#E6A23C', type: 'warning' },
  { value: 'PROPOSAL', label: '方案报价', color: '#409EFF', type: '' },
  { value: 'NEGOTIATION', label: '商务谈判', color: '#67C23A', type: 'success' }
]

// 方法
const getStageOpportunities = (stage) => {
  return opportunities.value.filter(o => o.stage === stage)
}

const getPriorityType = (priority) => {
  const map = { LOW: 'info', MEDIUM: '', HIGH: 'warning', CRITICAL: 'danger' }
  return map[priority] || ''
}

const formatNumber = (num) => {
  return num ? num.toLocaleString() : '0'
}

const fetchData = async () => {
  loading.value = true
  try {
    const [listRes, statsRes] = await Promise.all([
      getOpportunityList(queryParams),
      getOpportunityStatistics(queryParams)
    ])
    opportunities.value = listRes.results || listRes || []
    Object.assign(statistics, statsRes || {})
  } catch (error) {
    console.error('获取数据失败', error)
  } finally {
    loading.value = false
  }
}

const fetchCustomers = async () => {
  try {
    const res = await getCustomerList({ page_size: 500 })
    customerOptions.value = res.results || res || []
  } catch (error) {
    console.error('获取客户列表失败', error)
  }
}

const handleSearch = () => {
  queryParams.page = 1
  fetchData()
}

const handleCreate = () => {
  dialogTitle.value = '新建商机'
  Object.assign(formData, {
    id: null,
    name: '',
    customer: null,
    contact_name: '',
    contact_phone: '',
    stage: 'QUALIFICATION',
    priority: 'MEDIUM',
    probability: 20,
    estimated_amount: 0,
    expected_close_date: null,
    product_type: '',
    requirement: '',
    competitors: ''
  })
  dialogVisible.value = true
}

const handleView = (opp) => {
  dialogTitle.value = '编辑商机'
  Object.assign(formData, opp)
  dialogVisible.value = true
}

const handleSubmit = async () => {
  const valid = await formRef.value.validate()
  if (!valid) return

  submitting.value = true
  try {
    if (formData.id) {
      await updateOpportunity(formData.id, formData)
      ElMessage.success('更新成功')
    } else {
      await createOpportunity(formData)
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

onMounted(() => {
  fetchData()
  fetchCustomers()
})
</script>

<style scoped lang="scss">
.opportunity-container {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
}

.stat-cards {
  margin-bottom: 20px;
}

.stat-card {
  border-radius: 8px;
  
  &.success {
    border-left: 4px solid #67C23A;
  }
}

.filter-card {
  margin-bottom: 20px;
  border-radius: 8px;
}

.filter-area {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.kanban-container {
  display: flex;
  gap: 16px;
  overflow-x: auto;
  padding-bottom: 20px;
}

.kanban-column {
  min-width: 280px;
  width: 280px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.column-header {
  padding: 12px 16px;
  border-bottom: 3px solid;
  display: flex;
  justify-content: space-between;
  align-items: center;
  
  .stage-name {
    font-weight: 600;
    color: #303133;
  }
}

.column-body {
  padding: 12px;
  max-height: 600px;
  overflow-y: auto;
}

.opportunity-card {
  background: #fafafa;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #ebeef5;
  
  &:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    transform: translateY(-2px);
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
  
  .opp-name {
    font-weight: 500;
    color: #303133;
    font-size: 14px;
    flex: 1;
    margin-right: 8px;
  }
}

.card-body {
  margin-bottom: 8px;
  
  .customer {
    color: #606266;
    font-size: 13px;
    margin-bottom: 4px;
  }
  
  .amount {
    color: #E6A23C;
    font-weight: 600;
    font-size: 15px;
  }
}

.card-footer {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
  
  .probability {
    color: #67C23A;
  }
}
</style>
