<template>
  <div class="stock-adjustment-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>库存盘点</span>
          <el-button type="primary" v-permission="'inventory:stock_adjustment:create'" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新增盘点
          </el-button>
        </div>
      </template>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-permission="'inventory:stock_adjustment:delete'" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button 
          type="danger" 
          size="small" 
          @click="batchDelete"
          :loading="deleteLoading"
        >
          批量删除
        </el-button>
      </div>

      <el-table :data="adjustments" v-loading="loading" border stripe @selection-change="handleSelectionChange">
        <el-table-column v-permission="'inventory:stock_adjustment:delete'" v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="adjustment_no" label="盘点单号" width="150" />
        <el-table-column prop="warehouse_name" label="仓库" width="150" />
        <el-table-column prop="adjustment_date" label="盘点日期" width="120" />
        <el-table-column prop="reason" label="原因" show-overflow-tooltip />
        <el-table-column prop="cost_impact" label="成本影响" width="130" align="right">
          <template #default="{ row }">
            <span :style="{ color: (row.cost_impact || 0) < 0 ? '#F56C6C' : '#67C23A' }">
              ¥{{ toFixedSafe(row.cost_impact) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="创建人" width="100" />
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" type="warning" @click="handleSubmitApproval(row)" v-if="row.status === 'DRAFT' || row.status === 'REJECTED'">提交审批</el-button>
            <el-button size="small" type="info" @click="showWorkflowProgress(row)" v-if="row.status === 'PENDING'">审批进度</el-button>
            <el-button size="small" type="success" @click="handleConfirm(row)" v-if="row.status === 'DRAFT' || row.status === 'APPROVED'">确认盘点</el-button>
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
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadAdjustments"
        @current-change="loadAdjustments"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新增/编辑盘点 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="80%">
      <el-form :model="adjustmentForm" label-width="100px">
        <el-form-item label="仓库" required>
          <el-select v-model="adjustmentForm.warehouse" placeholder="请选择仓库" @change="loadStockForAdjustment" style="width: 100%">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="盘点日期" required>
          <el-date-picker v-model="adjustmentForm.adjustment_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="原因" required>
          <el-input v-model="adjustmentForm.reason" placeholder="例如：定期盘点、异常盘点" />
        </el-form-item>
        
        <el-divider>盘点明细</el-divider>
        
        <el-table :data="adjustmentForm.lines" border max-height="400">
          <el-table-column prop="item_sku" label="物料编码" width="150" />
          <el-table-column prop="item_name" label="物料名称" />
          <el-table-column prop="qty_system" label="系统数量" width="100" align="right" />
          <el-table-column label="实际数量" width="150">
            <template #default="{ row }">
              <el-input-number v-model="row.qty_actual" :min="0" :precision="2" size="small" style="width: 100%" @change="calculateDiff(row)" />
            </template>
          </el-table-column>
          <el-table-column label="盘点差异" width="100" align="right">
            <template #default="{ row }">
              <span :style="{ color: (row.qty_diff || 0) < 0 ? '#F56C6C' : (row.qty_diff || 0) > 0 ? '#67C23A' : '#909399' }">
                {{ row.qty_diff || 0 }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAdjustment">提交盘点</el-button>
      </template>
    </el-dialog>

    <!-- 查看详情 -->
    <el-dialog v-model="viewDialogVisible" title="盘点详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="盘点单号">{{ viewDetail.adjustment_no }}</el-descriptions-item>
        <el-descriptions-item label="仓库">{{ viewDetail.warehouse_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ viewDetail.status_display || viewDetail.status }}</el-descriptions-item>
        <el-descriptions-item label="盘点类型">{{ viewDetail.adjustment_type_display || viewDetail.adjustment_type }}</el-descriptions-item>
        <el-descriptions-item label="创建人">{{ viewDetail.created_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ viewDetail.created_at }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ viewDetail.remarks || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-table :data="viewDetail.items || []" stripe style="margin-top: 16px">
        <el-table-column prop="material_name" label="物料" />
        <el-table-column prop="system_qty" label="系统数量" width="100" align="right" />
        <el-table-column prop="actual_qty" label="实际数量" width="100" align="right" />
        <el-table-column label="差异" width="100" align="right">
          <template #default="{ row }">
            <span :style="{ color: (row.qty_diff || 0) < 0 ? '#F56C6C' : '#67C23A' }">{{ row.qty_diff || 0 }}</span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>

    <!-- 审批进度弹窗 -->
    <WorkflowProgress
      v-model="workflowDialogVisible"
      :business-type="workflowBusinessType"
      :business-id="workflowBusinessId"
    />
  </template>

<script setup lang="ts">
import WorkflowProgress from '@/components/WorkflowProgress.vue'

import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getAdjustments, getAdjustment, createAdjustment, submitAdjustment as apiSubmitAdjustment, confirmAdjustment, getStocks } from '@/api/inventory'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'
import { getWarehouseList } from '@/api/masterdata'
import { toFixedSafe } from '@/utils/number'

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能 - 使用箭头函数包装避免 TDZ 错误
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/inventory/adjustments/',
  {
    onSuccess: () => loadAdjustments(),
    confirmTitle: '删除盘点单',
    confirmMessage: '确定要删除该盘点单吗？删除后不可恢复！'
  }
)

const workflowDialogVisible = ref(false)
const workflowBusinessId = ref(null)
const workflowBusinessType = 'STOCK_ADJUSTMENT'

const showWorkflowProgress = (row) => {
  workflowBusinessId.value = row.id
  workflowDialogVisible.value = true
}

const loading = ref(false)
const viewDialogVisible = ref(false)
const viewDetail = ref({})
const adjustments = ref([])
const warehouses = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const formRef = ref(null)
const adjustmentForm = reactive({
  warehouse: null,
  adjustment_date: new Date().toISOString().split('T')[0],
  reason: '',
  lines: []
})

const rules = {
  warehouse: [{ required: true, message: '请选择仓库', trigger: 'change' }],
  adjustment_date: [{ required: true, message: '请选择盘点日期', trigger: 'change' }],
  reason: [{ required: true, message: '请输入盘点原因', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const types = {
    DRAFT: 'info',
    PENDING: 'warning',
    APPROVED: 'success',
    REJECTED: 'danger',
    CONFIRMED: 'success',
    COMPLETED: 'success'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    DRAFT: '草稿',
    PENDING: '审批中',
    APPROVED: '已审批',
    REJECTED: '已拒绝',
    CONFIRMED: '已确认',
    COMPLETED: '已完成'
  }
  return labels[status] || status
}

const loadAdjustments = async () => {
  loading.value = true
  try {
    const response = await getAdjustments({ page: pagination.page, page_size: pagination.pageSize })
    adjustments.value = response.results || []
    pagination.total = response.count || 0
  } catch (error) {
    ElMessage.error('加载盘点记录失败')
  } finally {
    loading.value = false
  }
}

const loadWarehouses = async () => {
  try {
    const response = await getWarehouseList({ page_size: 100 })
    warehouses.value = response.results || response || []
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const loadStockForAdjustment = async () => {
  if (!adjustmentForm.warehouse) return
  try {
    const response = await getStocks({ warehouse: adjustmentForm.warehouse, page_size: 500 })
    adjustmentForm.lines = (response.results || response || []).map(s => ({
      item: s.item,
      item_sku: s.item_sku,
      item_name: s.item_name,
      qty_system: s.qty_on_hand || 0,
      qty_actual: s.qty_on_hand || 0,
      qty_diff: 0
    }))
  } catch (error) {
    ElMessage.error('加载库存失败')
  }
}

const calculateDiff = (row) => {
  row.qty_diff = (row.qty_actual || 0) - (row.qty_system || 0)
}

const handleCreate = () => {
  dialogTitle.value = '新增盘点'
  adjustmentForm.warehouse = null
  adjustmentForm.adjustment_date = new Date().toISOString().split('T')[0]
  adjustmentForm.reason = ''
  adjustmentForm.lines = []
  dialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const response = await getAdjustment(row.id)
    viewDetail.value = response.data || response
    viewDialogVisible.value = true
  } catch (error) {
    viewDetail.value = row
    viewDialogVisible.value = true
  }
}

const handleSubmitApproval = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交该盘点单进行审批吗？', '提交审批', { type: 'warning' })
    const response = await apiSubmitAdjustment(row.id)
    const data = response.data || response
    if (data.workflow_started) {
      ElMessage.success(data.message || '已提交审批')
    } else {
      ElMessage.success(data.message || '操作成功')
    }
    loadAdjustments()
  } catch (error) {
    if (error !== 'cancel') {
      const msg = error.response?.data?.error || '提交失败'
      ElMessage.error(msg)
    }
  }
}

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm('确定要确认此盘点吗？确认后将调整库存。', '提示', { type: 'warning' })
    await confirmAdjustment(row.id)
    ElMessage.success('盘点确认成功')
    loadAdjustments()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('确认盘点失败')
  }
}

const submitAdjustment = async () => {
  if (!adjustmentForm.warehouse) return ElMessage.warning('请选择仓库')
  if (!adjustmentForm.reason) return ElMessage.warning('请输入盘点原因')
  if (adjustmentForm.lines.length === 0) return ElMessage.warning('请先加载库存数据')
  
  try {
    await createAdjustment(adjustmentForm)
    ElMessage.success('盘点单创建成功')
    dialogVisible.value = false
    loadAdjustments()
  } catch (error) {
    ElMessage.error('创建盘点单失败')
  }
}

const addLine = () => {
  adjustmentForm.lines.push({ item: null, qty_system: 0, qty_actual: 0, qty_diff: 0 })
}

const removeLine = (index) => {
  adjustmentForm.lines.splice(index, 1)
}

const resetForm = () => {
  adjustmentForm.warehouse = null
  adjustmentForm.adjustment_date = new Date().toISOString().split('T')[0]
  adjustmentForm.reason = ''
  adjustmentForm.lines = []
}

// handleDelete 已被 useBatchDelete 的 deleteRow 替代

onMounted(() => {
  loadAdjustments()
  loadWarehouses()
})
</script>

<style scoped>
.stock-adjustment-list { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
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
.table-toolbar span { font-size: 14px; color: #606266; }
</style>
