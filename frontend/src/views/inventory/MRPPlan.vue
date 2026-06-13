<template>
  <div class="mrp-container">
    <div class="page-header">
      <h2>物料需求计划 (MRP)</h2>
      <el-button type="primary" v-permission="'inventory:stock:create'" @click="handleAdd">创建计划</el-button>
    </div>
    
    <el-card shadow="never">
      <template #header>
        <el-form :inline="true">
          <el-form-item>
            <el-input v-model="queryParams.search" placeholder="搜索计划" clearable @clear="fetchList" />
          </el-form-item>
          <el-form-item>
            <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchList">
              <el-option label="草稿" value="DRAFT" />
              <el-option label="计算中" value="CALCULATING" />
              <el-option label="已完成" value="COMPLETED" />
              <el-option label="已批准" value="APPROVED" />
              <el-option label="执行中" value="EXECUTING" />
              <el-option label="已关闭" value="CLOSED" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="fetchList">查询</el-button>
          </el-form-item>
        </el-form>
      </template>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="planList" v-loading="loading" border stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="plan_no" label="计划编号" width="140" />
        <el-table-column prop="name" label="计划名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="计划周期" width="200">
          <template #default="{ row }">
            {{ row.start_date }} ~ {{ row.end_date }}
          </template>
        </el-table-column>
        <el-table-column prop="total_items" label="物料数" width="90" align="center" />
        <el-table-column prop="shortage_items" label="缺料数" width="90" align="center">
          <template #default="{ row }">
            <span :class="row.shortage_items > 0 ? 'text-danger' : ''">{{ row.shortage_items }}</span>
          </template>
        </el-table-column>
        <el-table-column label="缺料金额" width="130" align="right">
          <template #default="{ row }">
            <span class="amount">¥{{ formatNumber(row.total_shortage_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="calculated_at" label="计算时间" width="160">
          <template #default="{ row }">
            {{ row.calculated_at ? formatDateTime(row.calculated_at) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">查看</el-button>
            <el-button type="success" link size="small" @click="handleCalculate(row)" 
              v-if="row.status === 'DRAFT' || row.status === 'COMPLETED'">计算</el-button>
            <el-button type="warning" link size="small" @click="handleApprove(row)" 
              v-if="row.status === 'COMPLETED'">批准</el-button>
            <el-button type="info" link size="small" @click="handleGeneratePR(row)" 
              v-if="row.status === 'APPROVED'">生成采购</el-button>
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
    
    <!-- 创建计划对话框 -->
    <el-dialog v-model="dialogVisible" title="创建MRP计划" width="600px">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="计划名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入计划名称" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始日期" prop="start_date">
              <el-date-picker v-model="formData.start_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="end_date">
              <el-date-picker v-model="formData.end_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="安全库存系数">
              <el-input-number v-model="formData.safety_stock_factor" :min="0" :max="5" :step="0.1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="提前期系数">
              <el-input-number v-model="formData.lead_time_factor" :min="0" :max="5" :step="0.1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="formData.remarks" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitLoading">创建</el-button>
      </template>
    </el-dialog>
    
    <!-- 计划详情对话框 -->
    <el-dialog v-model="detailDialogVisible" :title="currentPlan?.name" width="90%" top="5vh">
      <div v-if="currentPlan">
        <el-descriptions :column="4" border size="small">
          <el-descriptions-item label="计划编号">{{ currentPlan.plan_no }}</el-descriptions-item>
          <el-descriptions-item label="计划周期">{{ currentPlan.start_date }} ~ {{ currentPlan.end_date }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentPlan.status)">{{ currentPlan.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="计算时间">{{ currentPlan.calculated_at ? formatDateTime(currentPlan.calculated_at) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="物料数">{{ currentPlan.total_items }}</el-descriptions-item>
          <el-descriptions-item label="缺料数">
            <span class="text-danger">{{ currentPlan.shortage_items }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="缺料金额">
            <span class="amount">¥{{ formatNumber(currentPlan.total_shortage_amount) }}</span>
          </el-descriptions-item>
        </el-descriptions>
        
        <el-divider content-position="left">物料明细</el-divider>
        
        <el-table :data="currentPlan.lines" border stripe max-height="400">
          <el-table-column prop="item_code" label="物料编码" width="120" fixed />
          <el-table-column prop="item_name" label="物料名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="item_unit" label="单位" width="60" align="center" />
          <el-table-column prop="gross_requirement" label="毛需求" width="100" align="right" />
          <el-table-column prop="on_hand_qty" label="在库量" width="100" align="right" />
          <el-table-column prop="on_order_qty" label="在途量" width="100" align="right" />
          <el-table-column prop="net_requirement" label="净需求" width="100" align="right">
            <template #default="{ row }">
              <span :class="row.net_requirement > 0 ? 'text-danger' : ''">{{ row.net_requirement }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="action_display" label="建议操作" width="100">
            <template #default="{ row }">
              <el-tag :type="row.suggested_action === 'PURCHASE' ? 'warning' : 'info'" size="small">
                {{ row.action_display }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="suggested_date" label="建议日期" width="110" />
          <el-table-column label="金额" width="120" align="right">
            <template #default="{ row }">
              ¥{{ formatNumber(row.total_amount) }}
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMRPPlans, createMRPPlan, getMRPPlan, calculateMRPPlan, approveMRPPlan, generateMRPPlanPR } from '@/api/inventory'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/inventory/mrp-plans/', { onSuccess: () => fetchList() })


const loading = ref(false)
const submitLoading = ref(false)
const planList = ref<any[]>([])

const queryParams = reactive({
  search: '',
  status: null
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

const dialogVisible = ref(false)
const detailDialogVisible = ref(false)
const formRef = ref(null)
const currentPlan = ref(null)

const formData = reactive({
  name: '',
  start_date: '',
  end_date: '',
  safety_stock_factor: 1.0,
  lead_time_factor: 1.0,
  remarks: ''
})

const rules = {
  name: [{ required: true, message: '请输入计划名称', trigger: 'blur' }],
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }]
}

const fetchList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.size,
      ...queryParams
    }
    const data = await getMRPPlans(params)
    planList.value = data.results || data
    pagination.total = data.count || planList.value.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  const today = new Date()
  const nextMonth = new Date(today.getFullYear(), today.getMonth() + 1, today.getDate())
  
  Object.assign(formData, {
    name: `MRP计划-${today.toISOString().slice(0, 10)}`,
    start_date: today.toISOString().slice(0, 10),
    end_date: nextMonth.toISOString().slice(0, 10),
    safety_stock_factor: 1.0,
    lead_time_factor: 1.0,
    remarks: ''
  })
  dialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    await createMRPPlan(formData)
    ElMessage.success('创建成功')
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error('创建失败')
  } finally {
    submitLoading.value = false
  }
}

const handleView = async (row) => {
  try {
    const data = await getMRPPlan(row.id)
    currentPlan.value = data
    detailDialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载失败')
  }
}

const handleCalculate = async (row) => {
  try {
    await ElMessageBox.confirm('确定要执行MRP计算吗？', '提示', { type: 'warning' })
    
    ElMessage.info('正在计算...')
    const data = await calculateMRPPlan(row.id)
    ElMessage.success(`计算完成，共 ${data.total_items} 个物料，${data.shortage_items} 个缺料`)
    fetchList()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.error || '计算失败')
    }
  }
}

const handleApprove = async (row) => {
  try {
    await approveMRPPlan(row.id)
    ElMessage.success('批准成功')
    fetchList()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '批准失败')
  }
}

const handleGeneratePR = async (row) => {
  try {
    await ElMessageBox.confirm('确定要生成采购申请吗？', '提示', { type: 'warning' })
    
    const data = await generateMRPPlanPR(row.id)
    ElMessage.success(`已生成采购申请: ${data.purchase_request_no}`)
    fetchList()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.error || '生成失败')
    }
  }
}

const formatNumber = (num) => {
  if (!num) return '0.00'
  return parseFloat(num).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getStatusType = (status) => {
  const types = {
    DRAFT: 'info',
    CALCULATING: 'warning',
    COMPLETED: 'success',
    APPROVED: 'primary',
    EXECUTING: '',
    CLOSED: ''
  }
  return types[status] || ''
}

onMounted(() => {
  fetchList()
})
</script>

<style scoped>
.mrp-container {
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

.amount { font-weight: 500; }
.text-danger { color: #f56c6c; }
</style>
