<template>
  <div class="quote-version-list">
    <!-- 搜索和筛选 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="客户">
          <el-select v-model="filters.customer" filterable clearable placeholder="选择客户" style="width: 180px">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="状态" style="width: 120px">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已提交" value="SUBMITTED" />
            <el-option label="评审中" value="REVIEWING" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已发送" value="SENT" />
            <el-option label="客户接受" value="ACCEPTED" />
            <el-option label="报价失败" value="LOST" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadQuotes">
            <el-icon><Search /></el-icon>搜索
          </el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 报价列表 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>报价版本管理</span>
          <div>
            <el-button @click="showSimilarDialog = true">
              <el-icon><Search /></el-icon>查找相似项目
            </el-button>
            <el-button type="primary" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon>新建报价
            </el-button>
          </div>
        </div>
      </template>

      <!-- 批量操作 -->

      <div v-if="selectedRows.length > 0" class="batch-toolbar">

        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>

        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>

        <el-button size="small" @click="batchExport">导出选中</el-button>

      </div>

      <el-table :data="quotes" v-loading="loading" stripe @row-click="viewQuote" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="quote_no" label="报价编号" width="140">
          <template #default="{ row }">
            {{ row.quote_no }} V{{ row.version }}
          </template>
        </el-table-column>
        <el-table-column prop="title" label="报价标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="customer_name" label="客户" width="150" show-overflow-tooltip />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="成本" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatMoney(row.total_cost) }}
          </template>
        </el-table-column>
        <el-table-column label="报价金额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatMoney(row.final_amount) }}
          </template>
        </el-table-column>
        <el-table-column label="利润率" width="100" align="center">
          <template #default="{ row }">
            <span :class="getProfitClass(row.profit_margin)">
              {{ toFixedSafe(row.profit_margin, 1, '0.0') }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="estimated_days" label="预计工期" width="100" align="center">
          <template #default="{ row }">
            {{ row.estimated_days }}天
          </template>
        </el-table-column>
        <el-table-column prop="valid_until" label="有效期至" width="110" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click.stop="viewQuote(row)">详情</el-button>
            <el-button size="small" link @click.stop="createNewVersion(row)">新版本</el-button>
            <el-button size="small" link @click.stop="predictProfit(row)">利润预测</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadQuotes"
        @current-change="loadQuotes"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>

    <!-- 新建报价对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建报价" width="700px">
      <el-form :model="quoteForm" :rules="quoteRules" ref="quoteFormRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="客户" prop="customer">
              <el-select v-model="quoteForm.customer" filterable placeholder="选择客户" style="width: 100%">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联商机">
              <el-select v-model="quoteForm.opportunity" filterable clearable placeholder="选择商机" style="width: 100%">
                <el-option v-for="o in opportunities" :key="o.id" :label="o.name" :value="o.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="报价标题" prop="title">
          <el-input v-model="quoteForm.title" placeholder="输入报价标题" />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input v-model="quoteForm.description" type="textarea" :rows="3" placeholder="描述项目需求" />
        </el-form-item>
        
        <el-divider>成本估算</el-divider>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="材料成本">
              <el-input-number v-model="quoteForm.material_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="人工成本">
              <el-input-number v-model="quoteForm.labor_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="外协成本">
              <el-input-number v-model="quoteForm.outsource_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="管理费用">
              <el-input-number v-model="quoteForm.overhead_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="其他成本">
              <el-input-number v-model="quoteForm.other_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="风险预留">
              <el-input-number v-model="quoteForm.contingency" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-divider>报价金额</el-divider>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="报价金额" prop="quote_amount">
              <el-input-number v-model="quoteForm.quote_amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="折扣率%">
              <el-input-number v-model="quoteForm.discount_rate" :min="0" :max="100" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最终报价">
              <el-input-number v-model="quoteForm.final_amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="预计工期(天)">
              <el-input-number v-model="quoteForm.estimated_days" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="有效期至">
              <el-date-picker v-model="quoteForm.valid_until" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="参照项目">
          <el-select v-model="quoteForm.reference_project" filterable clearable placeholder="选择参照项目" 
                     style="width: 100%" @change="handleEstimateFromReference">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createQuote" :loading="submitting">创建</el-button>
      </template>
    </el-dialog>

    <!-- 报价详情抽屉 -->
    <el-drawer v-model="showDetailDrawer" title="报价详情" size="60%">
      <template v-if="currentQuote">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="报价编号">{{ currentQuote.quote_no }} V{{ currentQuote.version }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentQuote.status)">{{ currentQuote.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="报价标题" :span="2">{{ currentQuote.title }}</el-descriptions-item>
          <el-descriptions-item label="客户">{{ currentQuote.customer_name }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ currentQuote.created_by_name }}</el-descriptions-item>
        </el-descriptions>

        <el-divider>成本明细</el-divider>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="材料成本">¥{{ formatMoney(currentQuote.material_cost) }}</el-descriptions-item>
          <el-descriptions-item label="人工成本">¥{{ formatMoney(currentQuote.labor_cost) }}</el-descriptions-item>
          <el-descriptions-item label="外协成本">¥{{ formatMoney(currentQuote.outsource_cost) }}</el-descriptions-item>
          <el-descriptions-item label="管理费用">¥{{ formatMoney(currentQuote.overhead_cost) }}</el-descriptions-item>
          <el-descriptions-item label="其他成本">¥{{ formatMoney(currentQuote.other_cost) }}</el-descriptions-item>
          <el-descriptions-item label="风险预留">¥{{ formatMoney(currentQuote.contingency) }}</el-descriptions-item>
          <el-descriptions-item label="总成本" :span="3">
            <strong style="color: #F56C6C">¥{{ formatMoney(currentQuote.total_cost) }}</strong>
          </el-descriptions-item>
        </el-descriptions>

        <el-divider>报价金额</el-divider>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="报价金额">¥{{ formatMoney(currentQuote.quote_amount) }}</el-descriptions-item>
          <el-descriptions-item label="折扣率">{{ currentQuote.discount_rate }}%</el-descriptions-item>
          <el-descriptions-item label="最终报价">
            <strong style="color: #409EFF">¥{{ formatMoney(currentQuote.final_amount) }}</strong>
          </el-descriptions-item>
          <el-descriptions-item label="预期利润">
            <span :class="getProfitClass(currentQuote.profit_margin)">
              ¥{{ formatMoney(currentQuote.expected_profit) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="利润率">
            <span :class="getProfitClass(currentQuote.profit_margin)">
              {{ toFixedSafe(currentQuote.profit_margin, 1, '0.0') }}%
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="预计工期">{{ currentQuote.estimated_days }}天</el-descriptions-item>
        </el-descriptions>

        <el-divider>成本明细项</el-divider>
        <el-table :data="currentQuote.cost_items" stripe size="small">
          <el-table-column prop="cost_type_display" label="类型" width="80" />
          <el-table-column prop="description" label="描述" min-width="200" />
          <el-table-column prop="quantity" label="数量" width="80" align="right" />
          <el-table-column prop="unit" label="单位" width="60" />
          <el-table-column prop="unit_price" label="单价" width="100" align="right">
            <template #default="{ row }">¥{{ formatMoney(row.unit_price) }}</template>
          </el-table-column>
          <el-table-column prop="amount" label="金额" width="120" align="right">
            <template #default="{ row }">¥{{ formatMoney(row.amount) }}</template>
          </el-table-column>
          <el-table-column prop="confidence" label="置信度" width="80" align="center">
            <template #default="{ row }">{{ row.confidence }}%</template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>

    <!-- 查找相似项目对话框 -->
    <el-dialog v-model="showSimilarDialog" title="查找相似项目" width="700px">
      <el-form :inline="true">
        <el-form-item label="关键词">
          <el-select v-model="similarKeywords" multiple filterable allow-create default-first-option
                     placeholder="输入关键词" style="width: 300px" />
        </el-form-item>
        <el-form-item label="行业">
          <el-input v-model="similarIndustry" placeholder="行业" style="width: 150px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="findSimilar" :loading="searchingSimilar">搜索</el-button>
        </el-form-item>
      </el-form>
      
      <el-table :data="similarProjects" stripe style="margin-top: 16px">
        <el-table-column prop="project_name" label="项目名称" min-width="180" />
        <el-table-column prop="project_type" label="类型" width="100" />
        <el-table-column prop="similarity" label="相似度" width="100" align="center">
          <template #default="{ row }">
            <el-progress :percentage="row.similarity" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column prop="contract_amount" label="合同金额" width="120" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.contract_amount) }}</template>
        </el-table-column>
        <el-table-column prop="actual_cost" label="实际成本" width="120" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.actual_cost) }}</template>
        </el-table-column>
        <el-table-column prop="profit_margin" label="利润率" width="80" align="center">
          <template #default="{ row }">{{ toFixedSafe(row.profit_margin, 1, '0.0') }}%</template>
        </el-table-column>
        <el-table-column prop="actual_days" label="工期" width="80" align="center">
          <template #default="{ row }">{{ row.actual_days }}天</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="useAsReference(row)">参照</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import { toFixedSafe } from '@/utils/number'
import { getQuoteVersions, getQuoteVersion, createQuoteVersion, createNewQuoteVersion, getQuoteVersionProfitPrediction, estimateFromReference, findSimilarQuotes } from '@/api/sales'
import { getCustomerList } from '@/api/masterdata'
import { getProjectList } from '@/api/projects/project'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/sales/')


const loading = ref(false)
const submitting = ref(false)
const searchingSimilar = ref(false)
const showCreateDialog = ref(false)
const showDetailDrawer = ref(false)
const showSimilarDialog = ref(false)

const quotes = ref([])
const customers = ref([])
const opportunities = ref([])
const projects = ref([])
const currentQuote = ref(null)
const similarProjects = ref([])

const similarKeywords = ref([])
const similarIndustry = ref('')

const filters = reactive({
  customer: null,
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const quoteForm = reactive({
  customer: null,
  opportunity: null,
  title: '',
  description: '',
  reference_project: null,
  material_cost: 0,
  labor_cost: 0,
  outsource_cost: 0,
  overhead_cost: 0,
  other_cost: 0,
  contingency: 0,
  quote_amount: 0,
  discount_rate: 0,
  final_amount: 0,
  estimated_days: 30,
  valid_until: ''
})

const quoteRules = {
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  title: [{ required: true, message: '请输入报价标题', trigger: 'blur' }],
  quote_amount: [{ required: true, message: '请输入报价金额', trigger: 'blur' }]
}

const quoteFormRef = ref(null)

const formatMoney = (val) => Number(val || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })

const getStatusType = (status) => {
  const map = {
    DRAFT: 'info', SUBMITTED: 'warning', REVIEWING: 'warning',
    APPROVED: 'success', SENT: 'primary', ACCEPTED: 'success', LOST: 'danger', REJECTED: 'danger'
  }
  return map[status] || 'info'
}

const getProfitClass = (margin) => {
  if (margin < 10) return 'profit-low'
  if (margin < 20) return 'profit-medium'
  return 'profit-high'
}

const loadQuotes = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    if (filters.customer) params.customer = filters.customer
    if (filters.status) params.status = filters.status

    const res = await getQuoteVersions(params)
    quotes.value = res.results || res
    pagination.total = res.count || quotes.value.length
  } catch (e) {
    ElMessage.error('加载报价列表失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const res = await getCustomerList({ page_size: 1000 })
    customers.value = res.results || res
  } catch (e) {
    console.error('加载客户列表失败')
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjectList({ page_size: 1000, status: 'COMPLETED' })
    projects.value = res.results || res
  } catch (e) {
    console.error('加载项目列表失败')
  }
}

const resetFilters = () => {
  filters.customer = null
  filters.status = ''
  loadQuotes()
}

const createQuote = async () => {
  try {
    await quoteFormRef.value.validate()
    submitting.value = true
    await createQuoteVersion(quoteForm)
    ElMessage.success('报价创建成功')
    showCreateDialog.value = false
    loadQuotes()
  } catch (e) {
    if (e !== false) ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

const viewQuote = async (row) => {
  try {
    const res = await getQuoteVersion(row.id)
    currentQuote.value = res
    showDetailDrawer.value = true
  } catch (e) {
    ElMessage.error('加载报价详情失败')
  }
}

const createNewVersion = async (row) => {
  try {
    const res = await createNewQuoteVersion(row.id)
    ElMessage.success(`新版本 V${res.version} 已创建`)
    loadQuotes()
  } catch (e) {
    ElMessage.error('创建新版本失败')
  }
}

const predictProfit = async (row) => {
  try {
    const res = await getQuoteVersionProfitPrediction(row.id)
    const riskColors = { LOW: '#67C23A', MEDIUM: '#E6A23C', HIGH: '#F56C6C' }
    ElMessage({
      message: `预期利润: ¥${formatMoney(res.expected_profit)}, 利润率: ${res.profit_margin}%, 风险: ${res.risk_level}`,
      type: res.risk_level === 'LOW' ? 'success' : (res.risk_level === 'HIGH' ? 'error' : 'warning')
    })
  } catch (e) {
    ElMessage.error('获取利润预测失败')
  }
}

const handleEstimateFromReference = async (projectId) => {
  if (!projectId) return
  try {
    const res = await estimateFromReference(currentQuote.value?.id || 0, {
      reference_project_id: projectId,
      adjustment_factor: 1.0
    })
    if (res) {
      quoteForm.material_cost = res.material_cost || 0
      quoteForm.labor_cost = res.labor_cost || 0
      quoteForm.outsource_cost = res.outsource_cost || 0
      quoteForm.other_cost = res.other_cost || 0
      quoteForm.quote_amount = res.suggested_price || 0
      quoteForm.final_amount = res.suggested_price || 0
      quoteForm.estimated_days = res.estimated_days || 30
      ElMessage.success('已从参照项目估算成本')
    }
  } catch (e) {
    ElMessage.error('估算失败')
  }
}

const findSimilar = async () => {
  searchingSimilar.value = true
  try {
    const res = await findSimilarQuotes({
      keywords: similarKeywords.value,
      industry: similarIndustry.value
    })
    similarProjects.value = res || []
  } catch (e) {
    ElMessage.error('搜索失败')
  } finally {
    searchingSimilar.value = false
  }
}

const useAsReference = (project) => {
  showSimilarDialog.value = false
  showCreateDialog.value = true
  quoteForm.reference_project = project.project_id
  estimateFromReference(project.project_id)
}

onMounted(() => {
  loadQuotes()
  loadCustomers()
  loadProjects()
})
</script>

<style scoped>
.quote-version-list {
  padding: 20px;
}
.filter-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.profit-low {
  color: #F56C6C;
  font-weight: bold;
}
.profit-medium {
  color: #E6A23C;
}
.profit-high {
  color: #67C23A;
  font-weight: bold;
}
</style>
