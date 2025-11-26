<template>
  <div class="batch-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>批次管理</span>
          <div class="header-actions">
            <el-radio-group v-model="viewMode" size="small" style="margin-right: 15px;">
              <el-radio-button label="all">全部</el-radio-button>
              <el-radio-button label="expiring">即将过期</el-radio-button>
              <el-radio-button label="expired">已过期</el-radio-button>
            </el-radio-group>
            <el-button type="primary" :icon="Plus" @click="handleAdd">新增批次</el-button>
          </div>
        </div>
      </template>

      <!-- Search Form -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="物料">
          <el-select v-model="searchForm.item" placeholder="选择物料" clearable filterable style="width: 200px;">
            <el-option v-for="item in items" :key="item.id" :label="`${item.sku} - ${item.name}`" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="仓库">
          <el-select v-model="searchForm.warehouse" placeholder="选择仓库" clearable style="width: 150px;">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="质量状态">
          <el-select v-model="searchForm.quality_status" placeholder="质量状态" clearable style="width: 120px;">
            <el-option label="待检" value="PENDING" />
            <el-option label="合格" value="PASSED" />
            <el-option label="不合格" value="FAILED" />
            <el-option label="隔离" value="QUARANTINE" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadBatches">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- Summary Cards -->
      <el-row :gutter="20" class="summary-cards" v-if="viewMode === 'all'">
        <el-col :span="6">
          <el-statistic title="批次总数" :value="summary.total" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="即将过期(30天内)" :value="summary.expiring" class="warning-stat" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="已过期" :value="summary.expired" class="danger-stat" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="待检批次" :value="summary.pending" />
        </el-col>
      </el-row>

      <!-- Data Table -->
      <el-table :data="batches" border v-loading="loading" style="margin-top: 20px;">
        <el-table-column prop="batch_no" label="批次号" width="120" />
        <el-table-column prop="item_sku" label="物料编码" width="120" />
        <el-table-column prop="item_name" label="物料名称" min-width="150" />
        <el-table-column prop="warehouse_name" label="仓库" width="100" />
        <el-table-column prop="qty_on_hand" label="库存数量" width="100" align="right">
          <template #default="{ row }">
            {{ Number(row.qty_on_hand).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="unit_cost" label="单位成本" width="100" align="right">
          <template #default="{ row }">
            ¥{{ Number(row.unit_cost).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="manufacture_date" label="生产日期" width="110" />
        <el-table-column prop="expiry_date" label="到期日期" width="110">
          <template #default="{ row }">
            <span :class="getExpiryClass(row)">
              {{ row.expiry_date || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="days_to_expiry" label="剩余天数" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_expired" type="danger" size="small">已过期</el-tag>
            <el-tag v-else-if="row.days_to_expiry !== null && row.days_to_expiry <= 30" type="warning" size="small">
              {{ row.days_to_expiry }}天
            </el-tag>
            <span v-else-if="row.days_to_expiry !== null">{{ row.days_to_expiry }}天</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="quality_status" label="质量状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getQualityTagType(row.quality_status)" size="small">
              {{ row.quality_status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleView(row)">详情</el-button>
            <el-button type="warning" link @click="handleAdjust(row)">调整</el-button>
            <el-button type="success" link @click="handleStatusChange(row)">状态</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadBatches"
        @current-change="loadBatches"
        style="margin-top: 20px;"
      />
    </el-card>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="dialogVisible" title="新增批次" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="批次号" prop="batch_no">
          <el-input v-model="form.batch_no" placeholder="请输入批次号" />
        </el-form-item>
        <el-form-item label="物料" prop="item">
          <el-select v-model="form.item" placeholder="选择物料" filterable style="width: 100%;">
            <el-option v-for="item in items" :key="item.id" :label="`${item.sku} - ${item.name}`" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="仓库" prop="warehouse">
          <el-select v-model="form.warehouse" placeholder="选择仓库" style="width: 100%;">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="生产日期">
          <el-date-picker v-model="form.manufacture_date" type="date" placeholder="选择生产日期" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="到期日期">
          <el-date-picker v-model="form.expiry_date" type="date" placeholder="选择到期日期" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="供应商批次号">
          <el-input v-model="form.supplier_batch_no" placeholder="供应商批次号（可选）" />
        </el-form-item>
        <el-form-item label="单位成本">
          <el-input-number v-model="form.unit_cost" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="质量状态" prop="quality_status">
          <el-select v-model="form.quality_status" style="width: 100%;">
            <el-option label="待检" value="PENDING" />
            <el-option label="合格" value="PASSED" />
            <el-option label="不合格" value="FAILED" />
            <el-option label="隔离" value="QUARANTINE" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- Adjust Quantity Dialog -->
    <el-dialog v-model="adjustDialogVisible" title="调整批次数量" width="400px">
      <el-form ref="adjustFormRef" :model="adjustForm" label-width="80px">
        <el-form-item label="批次号">
          <el-input :value="currentBatch?.batch_no" disabled />
        </el-form-item>
        <el-form-item label="当前数量">
          <el-input :value="currentBatch?.qty_on_hand" disabled />
        </el-form-item>
        <el-form-item label="新数量" prop="qty">
          <el-input-number v-model="adjustForm.qty" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="调整原因" prop="reason">
          <el-input v-model="adjustForm.reason" type="textarea" rows="2" placeholder="请输入调整原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adjustDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAdjustSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- Status Change Dialog -->
    <el-dialog v-model="statusDialogVisible" title="更改质量状态" width="400px">
      <el-form label-width="80px">
        <el-form-item label="批次号">
          <el-input :value="currentBatch?.batch_no" disabled />
        </el-form-item>
        <el-form-item label="当前状态">
          <el-tag :type="getQualityTagType(currentBatch?.quality_status)">
            {{ currentBatch?.quality_status_display }}
          </el-tag>
        </el-form-item>
        <el-form-item label="新状态">
          <el-select v-model="newStatus" style="width: 100%;">
            <el-option label="待检" value="PENDING" />
            <el-option label="合格" value="PASSED" />
            <el-option label="不合格" value="FAILED" />
            <el-option label="隔离" value="QUARANTINE" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="statusDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleStatusSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- Detail Dialog -->
    <el-dialog v-model="detailDialogVisible" title="批次详情" width="700px">
      <el-descriptions :column="2" border v-if="currentBatch">
        <el-descriptions-item label="批次号">{{ currentBatch.batch_no }}</el-descriptions-item>
        <el-descriptions-item label="物料">{{ currentBatch.item_sku }} - {{ currentBatch.item_name }}</el-descriptions-item>
        <el-descriptions-item label="仓库">{{ currentBatch.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="库存数量">{{ currentBatch.qty_on_hand }}</el-descriptions-item>
        <el-descriptions-item label="单位成本">¥{{ currentBatch.unit_cost }}</el-descriptions-item>
        <el-descriptions-item label="质量状态">
          <el-tag :type="getQualityTagType(currentBatch.quality_status)">{{ currentBatch.quality_status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="生产日期">{{ currentBatch.manufacture_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="到期日期">{{ currentBatch.expiry_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="供应商批次号">{{ currentBatch.supplier_batch_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="剩余天数">
          <span v-if="currentBatch.is_expired" class="text-danger">已过期</span>
          <span v-else-if="currentBatch.days_to_expiry !== null">{{ currentBatch.days_to_expiry }} 天</span>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentBatch.notes || '-' }}</el-descriptions-item>
      </el-descriptions>

      <!-- Move History -->
      <el-divider content-position="left">移动历史</el-divider>
      <el-table :data="batchMoves" border size="small" max-height="300">
        <el-table-column prop="move_type_display" label="类型" width="80" />
        <el-table-column prop="qty" label="数量" width="100" align="right">
          <template #default="{ row }">
            <span :class="row.qty > 0 ? 'text-success' : 'text-danger'">
              {{ row.qty > 0 ? '+' : '' }}{{ row.qty }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="reference_type" label="参考类型" />
        <el-table-column prop="move_date" label="时间" width="160" />
        <el-table-column prop="notes" label="备注" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const batches = ref([])
const items = ref([])
const warehouses = ref([])
const viewMode = ref('all')

const searchForm = reactive({
  item: null,
  warehouse: null,
  quality_status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const summary = reactive({
  total: 0,
  expiring: 0,
  expired: 0,
  pending: 0
})

// Dialog states
const dialogVisible = ref(false)
const adjustDialogVisible = ref(false)
const statusDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const adjustFormRef = ref(null)
const currentBatch = ref(null)
const batchMoves = ref([])
const newStatus = ref('')

const form = reactive({
  batch_no: '',
  item: null,
  warehouse: null,
  manufacture_date: null,
  expiry_date: null,
  supplier_batch_no: '',
  unit_cost: 0,
  quality_status: 'PENDING',
  notes: ''
})

const adjustForm = reactive({
  qty: 0,
  reason: ''
})

const rules = {
  batch_no: [{ required: true, message: '请输入批次号', trigger: 'blur' }],
  item: [{ required: true, message: '请选择物料', trigger: 'change' }],
  warehouse: [{ required: true, message: '请选择仓库', trigger: 'change' }],
  quality_status: [{ required: true, message: '请选择质量状态', trigger: 'change' }]
}

const getExpiryClass = (row) => {
  if (row.is_expired) return 'text-danger'
  if (row.days_to_expiry !== null && row.days_to_expiry <= 30) return 'text-warning'
  return ''
}

const getQualityTagType = (status) => {
  const types = {
    'PENDING': 'warning',
    'PASSED': 'success',
    'FAILED': 'danger',
    'QUARANTINE': 'info'
  }
  return types[status] || 'info'
}

const loadItems = async () => {
  try {
    const { data } = await request.get('/masterdata/items/', { params: { page_size: 500 } })
    items.value = data.results || data || []
  } catch (error) {
    console.error('加载物料失败:', error)
  }
}

const loadWarehouses = async () => {
  try {
    const { data } = await request.get('/masterdata/warehouses/', { params: { is_active: true } })
    warehouses.value = data.results || data || []
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const loadBatches = async () => {
  loading.value = true
  try {
    let url = '/inventory/batches/'
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    
    if (viewMode.value === 'expiring') {
      url = '/inventory/batches/expiring_soon/'
      params.days = 30
    } else if (viewMode.value === 'expired') {
      url = '/inventory/batches/expired/'
    }
    
    const { data } = await request.get(url, { params })
    
    if (viewMode.value === 'all') {
      batches.value = data.results || []
      pagination.total = data.count || 0
    } else {
      batches.value = data || []
      pagination.total = data.length || 0
    }
  } catch (error) {
    console.error('加载批次失败:', error)
  } finally {
    loading.value = false
  }
}

const loadSummary = async () => {
  try {
    // Get total
    const { data: allData } = await request.get('/inventory/batches/', { params: { page_size: 1 } })
    summary.total = allData.count || 0
    
    // Get expiring
    const { data: expiringData } = await request.get('/inventory/batches/expiring_soon/', { params: { days: 30 } })
    summary.expiring = expiringData.length || 0
    
    // Get expired
    const { data: expiredData } = await request.get('/inventory/batches/expired/')
    summary.expired = expiredData.length || 0
    
    // Get pending
    const { data: pendingData } = await request.get('/inventory/batches/', { params: { quality_status: 'PENDING', page_size: 1 } })
    summary.pending = pendingData.count || 0
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const resetSearch = () => {
  searchForm.item = null
  searchForm.warehouse = null
  searchForm.quality_status = null
  loadBatches()
}

const handleAdd = () => {
  form.batch_no = ''
  form.item = null
  form.warehouse = null
  form.manufacture_date = null
  form.expiry_date = null
  form.supplier_batch_no = ''
  form.unit_cost = 0
  form.quality_status = 'PENDING'
  form.notes = ''
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value?.validate()
  
  submitting.value = true
  try {
    await request.post('/inventory/batches/', form)
    ElMessage.success('创建成功')
    dialogVisible.value = false
    loadBatches()
    loadSummary()
  } catch (error) {
    console.error('创建失败:', error)
    ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

const handleView = async (batch) => {
  currentBatch.value = batch
  
  // Load move history
  try {
    const { data } = await request.get('/inventory/batch-moves/by_batch/', { params: { batch_id: batch.id } })
    batchMoves.value = data || []
  } catch (error) {
    console.error('加载移动历史失败:', error)
    batchMoves.value = []
  }
  
  detailDialogVisible.value = true
}

const handleAdjust = (batch) => {
  currentBatch.value = batch
  adjustForm.qty = Number(batch.qty_on_hand)
  adjustForm.reason = ''
  adjustDialogVisible.value = true
}

const handleAdjustSubmit = async () => {
  submitting.value = true
  try {
    await request.post(`/inventory/batches/${currentBatch.value.id}/adjust_qty/`, {
      qty: adjustForm.qty,
      reason: adjustForm.reason
    })
    ElMessage.success('调整成功')
    adjustDialogVisible.value = false
    loadBatches()
  } catch (error) {
    console.error('调整失败:', error)
    ElMessage.error('调整失败')
  } finally {
    submitting.value = false
  }
}

const handleStatusChange = (batch) => {
  currentBatch.value = batch
  newStatus.value = batch.quality_status
  statusDialogVisible.value = true
}

const handleStatusSubmit = async () => {
  submitting.value = true
  try {
    await request.patch(`/inventory/batches/${currentBatch.value.id}/`, {
      quality_status: newStatus.value
    })
    ElMessage.success('状态更新成功')
    statusDialogVisible.value = false
    loadBatches()
    loadSummary()
  } catch (error) {
    console.error('状态更新失败:', error)
    ElMessage.error('状态更新失败')
  } finally {
    submitting.value = false
  }
}

watch(viewMode, () => {
  pagination.page = 1
  loadBatches()
})

onMounted(() => {
  loadItems()
  loadWarehouses()
  loadBatches()
  loadSummary()
})
</script>

<style scoped>
.batch-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
}

.search-form {
  margin-bottom: 10px;
}

.summary-cards {
  margin-bottom: 10px;
}

.warning-stat :deep(.el-statistic__number) {
  color: #e6a23c;
}

.danger-stat :deep(.el-statistic__number) {
  color: #f56c6c;
}

.text-danger {
  color: #f56c6c;
}

.text-warning {
  color: #e6a23c;
}

.text-success {
  color: #67c23a;
}
</style>

