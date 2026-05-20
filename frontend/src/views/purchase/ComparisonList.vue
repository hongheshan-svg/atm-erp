<template>
  <div class="comparison-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>报价比价分析</span>
          <div class="header-actions">
            <el-button 
              v-if="isAdmin && selectedRows.length > 0" 
              type="danger" 
              @click="handleBatchDelete"
            >
              <el-icon><Delete /></el-icon>
              批量删除 ({{ selectedRows.length }})
            </el-button>
            <el-button type="primary" v-permission="'purchase:quotation_comparison:create'" @click="handleCreate">
              <el-icon><Plus /></el-icon>
              新建比价
            </el-button>
          </div>
        </div>
      </template>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="询价单号">
          <el-input v-model="searchForm.rfq_no" placeholder="请输入询价单号" clearable />
        </el-form-item>
        <el-form-item label="比价类型">
          <el-select v-model="searchForm.comparison_type" placeholder="全部类型" clearable>
            <el-option label="常规比价" value="NORMAL" />
            <el-option label="样件比价" value="SAMPLE" />
            <el-option label="批量比价" value="BATCH" />
            <el-option label="紧急比价" value="URGENT" />
            <el-option label="变更重新比价" value="CHANGE" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable>
            <el-option label="草稿" value="DRAFT" />
            <el-option label="比价中" value="IN_PROGRESS" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已审批" value="APPROVED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 数据表格 -->
      <el-table 
        :data="tableData" 
        v-loading="loading" 
        stripe 
        border
        @selection-change="handleSelectionChange"
      >
        <el-table-column v-if="isAdmin" type="selection" width="50" />
        <el-table-column prop="comparison_no" label="比价单号" width="160" />
        <el-table-column prop="rfq_no" label="询价单号" width="140" />
        <el-table-column prop="project_name" label="项目" min-width="100" />
        <el-table-column prop="comparison_type_display" label="比价类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getComparisonTypeColor(row.comparison_type)" size="small">
              {{ row.comparison_type_display || row.comparison_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="risk_level" label="风险" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="getRiskLevelColor(row.risk_level)" size="small">
              {{ row.risk_level === 'LOW' ? '低' : (row.risk_level === 'MEDIUM' ? '中' : '高') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="supplier_count" label="供应商数" width="100" align="center" />
        <el-table-column label="报价范围" width="200" align="right">
          <template #default="{ row }">
            <div v-if="row.min_price && row.max_price">
              <span class="price-min">¥{{ formatNumber(row.min_price) }}</span>
              <span class="price-sep"> ~ </span>
              <span class="price-max">¥{{ formatNumber(row.max_price) }}</span>
            </div>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="recommended_supplier" label="推荐供应商" width="150" />
        <el-table-column prop="status_display" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="handleView(row)">
              查看
            </el-button>
            <el-button 
              v-if="row.status === 'IN_PROGRESS'" 
              type="success" size="small" link 
              @click="handleComplete(row)"
            >
              完成
            </el-button>
            <el-button 
              v-if="row.status === 'COMPLETED'" 
              type="warning" size="small" link 
              @click="handleApprove(row)"
            >
              审批
            </el-button>
            <el-button 
              v-if="row.status === 'APPROVED'" 
              type="success" size="small" link 
              @click="handleConvertToPO(row)"
            >
              转采购订单
            </el-button>
            <el-button 
              v-if="isAdmin" 
              type="danger" size="small" link 
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 16px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新建比价对话框 -->
    <el-dialog v-model="createDialogVisible" title="新建比价分析" width="550px">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="100px">
        <el-form-item label="询价单" prop="rfq_id">
          <el-select v-model="createForm.rfq_id" placeholder="选择询价单" filterable style="width: 100%">
            <el-option
              v-for="rfq in availableRFQs"
              :key="rfq.id"
              :label="`${rfq.rfq_no} - ${rfq.project_name || '无项目'} (${rfq.quotation_count}个报价)`"
              :value="rfq.id"
            />
          </el-select>
          <div v-if="availableRFQs.length === 0" class="no-rfq-hint">
            暂无可用询价单，需要询价单至少有2个供应商已提交报价
          </div>
        </el-form-item>
        <el-form-item label="比价类型">
          <el-select v-model="createForm.comparison_type" style="width: 100%">
            <el-option label="常规比价" value="NORMAL" />
            <el-option label="样件比价" value="SAMPLE" />
            <el-option label="批量比价" value="BATCH" />
            <el-option label="紧急比价" value="URGENT" />
            <el-option label="变更重新比价" value="CHANGE" />
          </el-select>
        </el-form-item>
        <el-divider content-position="left">权重配置</el-divider>
        <el-form-item label="权重模板">
          <el-select v-model="createForm.weight_template" @change="applyTemplate" style="width: 100%">
            <el-option label="标准权重 (价格40%)" value="STANDARD" />
            <el-option label="质量优先 (质量40%)" value="QUALITY_FIRST" />
            <el-option label="交期优先 (交期40%)" value="DELIVERY_FIRST" />
            <el-option label="价格优先 (价格55%)" value="PRICE_FIRST" />
            <el-option label="自定义" value="CUSTOM" />
          </el-select>
        </el-form-item>
        <template v-if="createForm.weight_template === 'CUSTOM'">
          <el-row :gutter="10">
            <el-col :span="12">
              <el-form-item label="价格权重">
                <el-input-number v-model="createForm.weight_price" :min="0" :max="100" :step="5" size="small" />
                <span style="margin-left: 4px;">%</span>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="质量权重">
                <el-input-number v-model="createForm.weight_quality" :min="0" :max="100" :step="5" size="small" />
                <span style="margin-left: 4px;">%</span>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="10">
            <el-col :span="12">
              <el-form-item label="交期权重">
                <el-input-number v-model="createForm.weight_delivery" :min="0" :max="100" :step="5" size="small" />
                <span style="margin-left: 4px;">%</span>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="服务权重">
                <el-input-number v-model="createForm.weight_service" :min="0" :max="100" :step="5" size="small" />
                <span style="margin-left: 4px;">%</span>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="10">
            <el-col :span="12">
              <el-form-item label="技术权重">
                <el-input-number v-model="createForm.weight_technical" :min="0" :max="100" :step="5" size="small" />
                <span style="margin-left: 4px;">%</span>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <div class="weight-total-display">
                合计: <span :class="{ 'valid': weightTotal === 100, 'invalid': weightTotal !== 100 }">{{ weightTotal }}%</span>
              </div>
            </el-col>
          </el-row>
          <el-form-item v-if="weightTotal !== 100">
            <el-alert 
              type="warning" 
              :title="`权重总和为 ${weightTotal}%，需要等于 100%`"
              :closable="false"
            />
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item>
            <div class="template-weights">
              <el-tag type="success">价格 {{ templateWeights.price }}%</el-tag>
              <el-tag type="primary">质量 {{ templateWeights.quality }}%</el-tag>
              <el-tag type="warning">交期 {{ templateWeights.delivery }}%</el-tag>
              <el-tag type="info">服务 {{ templateWeights.service }}%</el-tag>
              <el-tag v-if="templateWeights.technical > 0" type="danger">技术 {{ templateWeights.technical }}%</el-tag>
            </div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate" :disabled="createForm.weight_template === 'CUSTOM' && weightTotal !== 100">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import {
  getComparisons, getAvailableRFQsForComparison, createComparisonFromRFQ,
  completeComparison, approveComparison, convertComparisonToPO, batchDeleteComparisons
} from '@/api/purchase'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

// 状态
const loading = ref(false)
const tableData = ref([])
const createDialogVisible = ref(false)
const availableRFQs = ref([])
const createFormRef = ref(null)
const selectedRows = ref([])

// 检查是否管理员
const isAdmin = computed(() => userStore.userInfo?.is_superuser || userStore.userInfo?.is_staff)

// 搜索
const searchForm = reactive({
  rfq_no: '',
  comparison_type: '',
  status: ''
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 权重模板定义
const WEIGHT_TEMPLATES = {
  'STANDARD': { price: 40, quality: 25, delivery: 20, service: 15, technical: 0 },
  'QUALITY_FIRST': { price: 25, quality: 40, delivery: 15, service: 10, technical: 10 },
  'DELIVERY_FIRST': { price: 25, quality: 20, delivery: 40, service: 15, technical: 0 },
  'PRICE_FIRST': { price: 55, quality: 20, delivery: 15, service: 10, technical: 0 },
}

// 新建表单
const createForm = reactive({
  rfq_id: null,
  comparison_type: 'NORMAL',
  weight_template: 'STANDARD',
  weight_price: 40,
  weight_quality: 25,
  weight_delivery: 20,
  weight_service: 15,
  weight_technical: 0
})

const createRules = {
  rfq_id: [{ required: true, message: '请选择询价单', trigger: 'change' }]
}

// 计算权重总和
const weightTotal = computed(() => {
  return createForm.weight_price + createForm.weight_quality + 
         createForm.weight_delivery + createForm.weight_service + createForm.weight_technical
})

// 当前模板权重
const templateWeights = computed(() => {
  return WEIGHT_TEMPLATES[createForm.weight_template] || WEIGHT_TEMPLATES['STANDARD']
})

// 应用权重模板
const applyTemplate = (template) => {
  if (template !== 'CUSTOM') {
    const weights = WEIGHT_TEMPLATES[template]
    if (weights) {
      createForm.weight_price = weights.price
      createForm.weight_quality = weights.quality
      createForm.weight_delivery = weights.delivery
      createForm.weight_service = weights.service
      createForm.weight_technical = weights.technical
    }
  }
}

// 比价类型颜色
const getComparisonTypeColor = (type) => {
  const colors = {
    'NORMAL': 'info',
    'SAMPLE': 'primary',
    'BATCH': 'success',
    'URGENT': 'danger',
    'CHANGE': 'warning'
  }
  return colors[type] || 'info'
}

// 风险等级颜色
const getRiskLevelColor = (level) => {
  const colors = {
    'LOW': 'success',
    'MEDIUM': 'warning',
    'HIGH': 'danger'
  }
  return colors[level] || 'info'
}

// 格式化
const formatNumber = (num) => {
  return parseFloat(num || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'IN_PROGRESS': 'warning',
    'COMPLETED': 'success',
    'APPROVED': 'primary'
  }
  return types[status] || 'info'
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const res = await getComparisons(params)
    tableData.value = res.results || res || []
    pagination.total = res.count || 0
  } catch (error) {
    console.error('加载比价列表失败:', error)
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

// 加载可用于比价的询价单（至少有2个已提交报价）
const loadAvailableRFQs = async () => {
  try {
    const res = await getAvailableRFQsForComparison()
    availableRFQs.value = res || []
    if (availableRFQs.value.length === 0) {
      ElMessage.warning('暂无可用于比价的询价单，需要询价单至少有2个供应商报价')
    }
  } catch (error) {
    console.error('加载询价单失败:', error)
    ElMessage.error('加载可用询价单失败')
  }
}

// 重置搜索
const resetSearch = () => {
  searchForm.rfq_no = ''
  searchForm.comparison_type = ''
  searchForm.status = ''
  pagination.page = 1
  loadData()
}

// 新建比价
const handleCreate = async () => {
  await loadAvailableRFQs()
  createForm.rfq_id = null
  createForm.comparison_type = 'NORMAL'
  createForm.weight_template = 'STANDARD'
  createForm.weight_price = 40
  createForm.weight_quality = 25
  createForm.weight_delivery = 20
  createForm.weight_service = 15
  createForm.weight_technical = 0
  createDialogVisible.value = true
}

// 提交创建
const submitCreate = async () => {
  try {
    await createFormRef.value.validate()
    
    const res = await createComparisonFromRFQ(createForm)
    ElMessage.success('比价分析创建成功')
    createDialogVisible.value = false
    
    // 跳转到比价详情页
    router.push(`/purchase/comparisons/${res.id}`)
  } catch (error) {
    console.error('创建比价失败:', error)
    const errorMsg = error.response?.data?.error || error.response?.data?.detail || '创建失败'
    ElMessage.error(errorMsg)
  }
}

// 查看详情
const handleView = (row) => {
  router.push(`/purchase/comparisons/${row.id}`)
}

// 完成比价
const handleComplete = async (row) => {
  try {
    await ElMessageBox.confirm('确定完成此比价分析？', '确认')
    await completeComparison(row.id)
    ElMessage.success('比价分析已完成')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

// 审批
const handleApprove = async (row) => {
  try {
    await ElMessageBox.confirm('确定审批通过此比价分析？', '确认审批')
    await approveComparison(row.id)
    ElMessage.success('审批通过')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

// 转采购订单
const handleConvertToPO = async (row) => {
  try {
    await ElMessageBox.confirm('确定将推荐报价转换为采购订单？', '确认转换')
    const res = await convertComparisonToPO(row.id)
    ElMessage.success(`采购订单 ${res.order_no} 创建成功`)
    router.push(`/purchase/orders/${res.id}`)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '转换失败')
    }
  }
}

// 选择变化
const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

// 单行删除
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定删除比价单 ${row.comparison_no} 吗？此操作不可恢复。`, 
      '确认删除',
      { type: 'warning' }
    )
    await batchDeleteComparisons({ ids: [row.id] })
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '删除失败')
    }
  }
}

// 批量删除
const handleBatchDelete = async () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的记录')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedRows.value.length} 条比价记录吗？此操作不可恢复。`, 
      '确认批量删除',
      { type: 'warning' }
    )
    const ids = selectedRows.value.map(row => row.id)
    const res = await batchDeleteComparisons({ ids })
    ElMessage.success(res.message || '批量删除成功')
    selectedRows.value = []
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '批量删除失败')
    }
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.comparison-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 16px;
}

.price-min {
  color: #67c23a;
  font-weight: 500;
}

.price-max {
  color: #f56c6c;
  font-weight: 500;
}

.price-sep {
  color: #909399;
}

.text-muted {
  color: #909399;
}

.no-rfq-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #e6a23c;
  line-height: 1.4;
}

.template-weights {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.weight-total-display {
  padding: 8px 12px;
  font-size: 14px;
  color: #606266;
}

.weight-total-display .valid {
  color: #67c23a;
  font-weight: 600;
}

.weight-total-display .invalid {
  color: #f56c6c;
  font-weight: 600;
}
</style>

