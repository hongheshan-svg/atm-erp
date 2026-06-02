<template>
  <div class="purchase-order-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>采购订单</span>
          <el-button type="primary" v-permission="'purchase:purchase_order:create'" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            创建订单
          </el-button>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="供应商">
          <el-select v-model="searchForm.supplier" placeholder="选择供应商" clearable filterable style="width: 180px;">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 120px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="待审批" value="PENDING" />
            <el-option label="已审批" value="APPROVED" />
            <el-option label="已拒绝" value="REJECTED" />
            <el-option label="已确认" value="CONFIRMED" />
            <el-option label="部分收货" value="PARTIAL" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadOrders">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-permission="'purchase:purchase_order:delete'" v-if="canDelete && selectedRows.length > 0">
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

      <el-table :data="orders" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column v-permission="'purchase:purchase_order:delete'" v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="order_no" label="采购订单号" width="140" fixed />
        <el-table-column prop="project_name" label="项目" width="150" show-overflow-tooltip />
        <el-table-column label="物料名称" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.item_summary">{{ row.item_summary.item_name }}</span>
            <span v-else class="text-muted">-</span>
            <el-tag v-if="row.lines_count > 1" size="small" type="info" style="margin-left: 4px;">+{{ row.lines_count - 1 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="规格/图纸号" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.item_summary?.specification || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="单价" width="90" align="right">
          <template #default="{ row }">
            <span v-if="row.item_summary">¥{{ formatMoney(row.item_summary.unit_price) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="单位" width="60" align="center">
          <template #default="{ row }">
            {{ row.item_summary?.unit || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="数量" width="80" align="right">
          <template #default="{ row }">
            {{ row.total_qty || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="supplier_name" label="供应商" width="140" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_with_tax" label="含税总额" width="100" align="right">
          <template #default="{ row }">
            ¥{{ formatMoney(row.total_with_tax || row.total_amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="order_date" label="订单日期" width="100" />
        <el-table-column prop="delivery_date" label="交货日期" width="100" />
        <el-table-column label="操作" width="480" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" v-permission="'purchase:purchase_order:edit'" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="warning" @click="handleSubmit(row)" v-if="row.status === 'DRAFT' || row.status === 'REJECTED'">提交审批</el-button>
            <el-button size="small" type="info" @click="showWorkflowProgress(row)" v-if="row.status === 'PENDING'">审批进度</el-button>
            <el-button size="small" type="success" @click="handleConfirm(row)" v-if="row.status === 'APPROVED'">确认</el-button>
            <el-button size="small" type="info" @click="handleWithdraw(row)" v-if="row.status === 'CONFIRMED'">撤回</el-button>
            <el-button size="small" type="primary" @click="handleContract(row)" v-if="row.status === 'CONFIRMED'">合同</el-button>
            <el-button size="small" type="warning" @click="handleViewAttachments(row)">附件</el-button>
            <el-button size="small" type="success" @click="receiveGoods(row)" v-if="row.status === 'CONFIRMED' || row.status === 'PARTIAL'">收货</el-button>
            <el-button size="small" type="danger" @click="handleCancel(row)" v-if="row.status === 'DRAFT' || row.status === 'CONFIRMED'">取消</el-button>
            <el-button size="small" type="danger" v-permission="'purchase:purchase_order:delete'" @click="handleDelete(row)" v-if="['DRAFT', 'CANCELLED', 'REJECTED'].includes(row.status)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadOrders"
        @current-change="loadOrders"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>
    
    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="950px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="供应商" prop="supplier">
              <el-select v-model="form.supplier" placeholder="选择供应商" filterable style="width: 100%;">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="关联项目">
              <el-select v-model="form.project" placeholder="选择项目" filterable clearable style="width: 100%;">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="交货日期" prop="delivery_date">
              <el-date-picker v-model="form.delivery_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="增值税率">
              <el-select v-model="form.tax_rate" placeholder="选择税率" style="width: 100%;">
                <el-option :value="0" label="0% (免税)" />
                <el-option :value="1" label="1%" />
                <el-option :value="3" label="3%" />
                <el-option :value="6" label="6%" />
                <el-option :value="9" label="9%" />
                <el-option :value="13" label="13%" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="付款条款">
              <el-select v-model="form.payment_terms" placeholder="选择付款条款" style="width: 100%;">
                <el-option value="PREPAY" label="预付款" />
                <el-option value="COD" label="货到付款" />
                <el-option value="NET15" label="月结15天" />
                <el-option value="NET30" label="月结30天" />
                <el-option value="NET45" label="月结45天" />
                <el-option value="NET60" label="月结60天" />
                <el-option value="NET90" label="月结90天" />
                <el-option value="NET120" label="月结120天" />
                <el-option value="MILESTONE" label="分期付款" />
                <el-option value="OTHER" label="其他" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="付款方式">
              <el-select v-model="form.payment_method" placeholder="选择付款方式" style="width: 100%;">
                <el-option value="WIRE" label="电汇" />
                <el-option value="ACCEPTANCE" label="承兑汇票" />
                <el-option value="CHECK" label="支票" />
                <el-option value="CASH" label="现金" />
                <el-option value="LC" label="信用证" />
                <el-option value="OTHER" label="其他" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="付款说明">
              <el-input v-model="form.payment_terms_detail" placeholder="付款条款补充说明" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="备注">
              <el-input v-model="form.notes" placeholder="请输入备注" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <!-- 订单明细 -->
        <el-divider content-position="left">订单明细</el-divider>
        <el-button type="primary" size="small" @click="addLine" style="margin-bottom: 10px;">
          <el-icon><Plus /></el-icon>
          添加物料
        </el-button>
        
        <el-table :data="form.lines" border size="small">
          <el-table-column label="物料" min-width="200">
            <template #default="{ row, $index }">
              <el-select v-model="row.item" placeholder="选择物料" filterable style="width: 100%;" @change="onItemChange($index)">
                <el-option v-for="item in items" :key="item.id" :label="`${item.sku} - ${item.name}`" :value="item.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="数量" width="120">
            <template #default="{ row }">
              <el-input-number v-model="row.qty" :min="1" :precision="0" size="small" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="单价" width="120">
            <template #default="{ row }">
              <el-input-number v-model="row.unit_price" :min="0" :precision="2" size="small" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="小计" width="120" align="right">
          <template #default="{ row }">
              ¥{{ formatMoney((row.qty || 0) * (row.unit_price || 0)) }}
          </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template #default="{ $index }">
              <el-button type="danger" size="small" link @click="removeLine($index)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        
        <div class="total-section">
          <div class="total-row">
            <span class="label">不含税金额：</span>
            <span class="value">¥{{ formatMoney(calculateTotal()) }}</span>
          </div>
          <div class="total-row">
            <span class="label">税额 ({{ form.tax_rate }}%)：</span>
            <span class="value">¥{{ formatMoney(calculateTax()) }}</span>
          </div>
          <div class="total-row total">
            <span class="label">含税总额：</span>
            <span class="amount">¥{{ formatMoney(calculateTotalWithTax()) }}</span>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 附件管理对话框 -->
    <el-dialog v-model="attachmentDialogVisible" :title="`采购订单 ${currentOrder?.order_no || ''} - 附件管理`" width="900px" destroy-on-close>
      <AttachmentUpload
        v-if="currentOrder"
        related-model="PurchaseOrder"
        :related-id="currentOrder.id"
        title="采购订单附件（合同、发票等）"
      />
    </el-dialog>

    <!-- 审批进度弹窗 -->
    <WorkflowProgress
      v-model="workflowDialogVisible"
      :business-type="workflowBusinessType"
      :business-id="workflowBusinessId"
    />
  </div>
</template>

<script setup lang="ts">
import WorkflowProgress from '@/components/WorkflowProgress.vue'

import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import {
  getPurchaseOrders, getPurchaseOrder, createPurchaseOrder, updatePurchaseOrder, deletePurchaseOrder,
  submitPurchaseOrder, confirmPurchaseOrder, cancelPurchaseOrder, withdrawPurchaseOrder,
  getPurchaseContracts, createContractFromPO, printPreviewContract
} from '@/api/purchase'
import AttachmentUpload from '@/components/AttachmentUpload.vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'
import { getItemList, getSupplierList } from '@/api/masterdata'
import { getProjectList } from '@/api/projects/project'

const router = useRouter()

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/purchase/orders/',
  {
    confirmTitle: '确认删除采购订单',
    confirmMessage: '此操作将永久删除选中的采购订单，是否继续？',
    successMessage: '删除成功',
    errorMessage: '删除失败',
    onSuccess: () => loadOrders()
  }
)
const workflowDialogVisible = ref(false)
const workflowBusinessId = ref(null)
const workflowBusinessType = 'PURCHASE_ORDER'

const showWorkflowProgress = (row) => {
  workflowBusinessId.value = row.id
  workflowDialogVisible.value = true
}

const loading = ref(false)
const saving = ref(false)
const orders = ref<any[]>([])
const suppliers = ref<any[]>([])
const projects = ref<any[]>([])
const items = ref<any[]>([])
const dialogVisible = ref(false)
const dialogTitle = ref('创建采购订单')
const isEdit = ref(false)
const formRef = ref(null)
const attachmentDialogVisible = ref(false)
const currentOrder = ref(null)

const searchForm = reactive({
  supplier: null,
  status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  supplier: null,
  project: null,
  delivery_date: '',
  tax_rate: 13,
  payment_terms: 'NET30',
  payment_method: 'WIRE',
  payment_terms_detail: '',
  notes: '',
  lines: []
})

const rules = {
  supplier: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  delivery_date: [{ required: true, message: '请选择交货日期', trigger: 'change' }]
}

const getStatusType = (status) => {
  const types = { 
    DRAFT: 'info', 
    PENDING: 'warning',
    APPROVED: 'primary',
    REJECTED: 'danger',
    CONFIRMED: 'success', 
    PARTIAL: 'warning',
    COMPLETED: '', 
    CANCELLED: 'danger' 
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = { 
    DRAFT: '草稿', 
    PENDING: '待审批',
    APPROVED: '已审批',
    REJECTED: '已拒绝',
    CONFIRMED: '已确认', 
    PARTIAL: '部分收货',
    COMPLETED: '已完成', 
    CANCELLED: '已取消' 
  }
  return labels[status] || status
}

const formatMoney = (value) => {
  const amount = Number.parseFloat(value ?? 0)
  return Number.isFinite(amount) ? amount.toFixed(2) : '0.00'
}

const loadOrders = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.supplier) params.supplier = searchForm.supplier
    if (searchForm.status) params.status = searchForm.status
    
    const res = await getPurchaseOrders(params)
    orders.value = res.results || res.results || res || []
    pagination.total = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载采购订单失败')
  } finally {
    loading.value = false
  }
}

const loadSuppliers = async () => {
  try {
    const res = await getSupplierList()
    suppliers.value = res.results || res.results || res || []
  } catch (error) {
    console.error('加载供应商失败:', error)
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjectList()
    projects.value = res.results || res.results || res || []
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const loadItems = async () => {
  try {
    const res = await getItemList()
    items.value = res.results || res.results || res || []
  } catch (error) {
    console.error('加载物料失败:', error)
  }
}

const resetSearch = () => {
  searchForm.supplier = null
  searchForm.status = null
  pagination.page = 1
  loadOrders()
}

const handleAdd = () => {
  dialogTitle.value = '创建采购订单'
  isEdit.value = false
  Object.assign(form, {
    id: null,
    supplier: null,
    project: null,
    delivery_date: '',
    tax_rate: 13,
    payment_terms: 'NET30',
    payment_method: 'WIRE',
    payment_terms_detail: '',
    notes: '',
    lines: [{ item: null, qty: 1, unit_price: 0 }]
  })
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑采购订单'
  isEdit.value = true
  
  try {
    const res = await getPurchaseOrder(row.id)
    const data = res
    
    Object.assign(form, {
      id: data.id,
      supplier: data.supplier,
      project: data.project,
      delivery_date: data.delivery_date || '',
      tax_rate: data.tax_rate ?? 13,
      payment_terms: data.payment_terms || 'NET30',
      payment_method: data.payment_method || 'WIRE',
      payment_terms_detail: data.payment_terms_detail || '',
      notes: data.notes || '',
      lines: (data.lines || []).map(line => ({
        id: line.id,
        item: line.item,
        qty: line.qty,
        unit_price: parseFloat(line.unit_price || 0)
      }))
    })
    
    if (form.lines.length === 0) {
      form.lines = [{ item: null, qty: 1, unit_price: 0 }]
    }
    
    dialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取采购订单详情失败')
  }
}

const handleView = (row) => {
  router.push(`/purchase/orders/${row.id}`)
}

const addLine = () => {
  form.lines.push({ item: null, qty: 1, unit_price: 0 })
}

const removeLine = (index) => {
  if (form.lines.length > 1) {
    form.lines.splice(index, 1)
  } else {
    ElMessage.warning('至少保留一行明细')
  }
}

const onItemChange = (index) => {
  const line = form.lines[index]
  const item = items.value.find(i => i.id === line.item)
  if (item) {
    line.unit_price = parseFloat(item.standard_cost || 0)
  }
}

const calculateTotal = () => {
  return form.lines.reduce((sum, line) => {
    return sum + (line.qty || 0) * (line.unit_price || 0)
  }, 0)
}

const calculateTax = () => {
  return calculateTotal() * (form.tax_rate || 0) / 100
}

const calculateTotalWithTax = () => {
  return calculateTotal() + calculateTax()
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    
    const validLines = form.lines.filter(line => line.item && line.qty > 0)
    if (validLines.length === 0) {
      ElMessage.warning('请至少添加一行有效的物料明细')
      return
    }
    
    saving.value = true
    
    const payload = {
      supplier: form.supplier,
      project: form.project,
      delivery_date: form.delivery_date,
      tax_rate: form.tax_rate,
      payment_terms: form.payment_terms,
      payment_method: form.payment_method,
      payment_terms_detail: form.payment_terms_detail,
      notes: form.notes,
      lines: validLines.map(line => ({
        item: line.item,
        qty: line.qty,
        unit_price: line.unit_price
      }))
    }
    
    if (isEdit.value) {
      await updatePurchaseOrder(form.id, payload)
      ElMessage.success('更新采购订单成功')
    } else {
      await createPurchaseOrder(payload)
      ElMessage.success('创建采购订单成功')
    }
    
    dialogVisible.value = false
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('保存采购订单失败')
      console.error(error)
    }
  } finally {
    saving.value = false
  }
}

const handleSubmit = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交该采购订单审批吗？', '提交审批', { type: 'warning' })
    const res = await submitPurchaseOrder(row.id)
    if (res.workflow_started) {
      ElMessage.success(res.message || '已提交审批')
    } else {
      ElMessage.warning(res.message || '未配置审批流程，订单已直接确认')
    }
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '提交审批失败')
    }
  }
}

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm('确定要确认该采购订单吗？确认后将无法修改。', '确认订单', { type: 'warning' })
    await confirmPurchaseOrder(row.id)
    ElMessage.success('订单已确认')
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('确认订单失败')
    }
  }
}

const handleCancel = async (row) => {
  try {
    await ElMessageBox.confirm('确定要取消该采购订单吗？', '取消订单', { type: 'warning' })
    await cancelPurchaseOrder(row.id)
    ElMessage.success('订单已取消')
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('取消订单失败')
    }
  }
}

const handleWithdraw = async (row) => {
  try {
    await ElMessageBox.confirm('确定要撤回该采购订单吗？撤回后将恢复为草稿状态，关联的应付账款和付款计划将被删除。', '撤回确认', { type: 'warning' })
    await withdrawPurchaseOrder(row.id)
    ElMessage.success('订单已撤回')
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '撤回失败')
    }
  }
}

const handleContract = async (row) => {
  try {
    // 检查是否已有合同
    const contractRes = await getPurchaseContracts({ po: row.id })
    const contracts = contractRes.results || contractRes || []
    
    if (contracts.length > 0) {
      // 已有合同，打开打印预览
      const contract = contracts[0]
      handlePrintContract(contract)
    } else {
      // 创建新合同
      await ElMessageBox.confirm('该订单尚未生成合同，是否现在生成？', '生成合同', { type: 'info' })
      const res = await createContractFromPO(row.id)
      ElMessage.success(`合同 ${res.contract_no} 创建成功`)
      handlePrintContract(res)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '合同操作失败')
    }
  }
}

const handlePrintContract = async (contract) => {
  try {
    const res = await printPreviewContract(contract.id)
    // 打开打印预览窗口
    const printWindow = window.open('', '_blank')
    printWindow.document.write(generateContractHtml(res))
    printWindow.document.close()
    printWindow.focus()
  } catch (error) {
    ElMessage.error('获取合同详情失败')
  }
}

const generateContractHtml = (data) => {
  const { contract, company, supplier, lines, po } = data
  const totalAmount = lines.reduce((sum, l) => sum + l.line_amount, 0)
  const taxRate = contract.tax_rate || 13
  
  // 金额大写转换
  const toChineseMoney = (n) => {
    const fraction = ['角', '分']
    const digit = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
    const unit = [['元', '万', '亿'], ['', '拾', '佰', '仟']]
    let s = ''
    n = Math.abs(n)
    for (let i = 0; i < fraction.length; i++) {
      s += (digit[Math.floor(n * 10 * Math.pow(10, i)) % 10] + fraction[i]).replace(/零./, '')
    }
    s = s || '整'
    n = Math.floor(n)
    for (let i = 0; i < unit[0].length && n > 0; i++) {
      let p = ''
      for (let j = 0; j < unit[1].length && n > 0; j++) {
        p = digit[n % 10] + unit[1][j] + p
        n = Math.floor(n / 10)
      }
      s = p.replace(/(零.)*零$/, '').replace(/^$/, '零') + unit[0][i] + s
    }
    return s.replace(/(零.)*零元/, '元').replace(/(零.)+/g, '零').replace(/^整$/, '零元整')
  }
  
  const formatDate = (dateStr) => {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
  }
  
  const today = new Date()
  const contractDate = formatDate(contract.created_at) || `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  
  // 动态计算空行数，根据实际数据行填充到合适行数
  const targetRows = 10
  const emptyRows = Math.max(0, targetRows - lines.length)
  
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>采购合同 - ${contract.contract_no}</title>
<style>
@page { size: A4; margin: 8mm 12mm; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: '宋体', 'SimSun', serif; padding: 8px 15px; font-size: 10.5px; line-height: 1.5; color: #000; }
.print-btn { position: fixed; top: 10px; right: 10px; padding: 8px 16px; background: #409eff; color: white; border: none; border-radius: 4px; cursor: pointer; z-index: 100; font-size: 14px; }
.header { text-align: center; margin-bottom: 12px; }
.header .company { font-size: 18px; font-weight: bold; letter-spacing: 4px; }
.header .title { font-size: 14px; font-weight: bold; margin-top: 6px; }
.info-row { display: flex; justify-content: space-between; font-size: 10.5px; margin: 5px 0; }
.parties { display: flex; gap: 30px; margin: 10px 0; font-size: 10.5px; }
.party { flex: 1; line-height: 1.7; }
.party-label { font-weight: bold; }
.section-title { font-weight: bold; font-size: 10.5px; margin: 10px 0 5px 0; }
table.items { width: 100%; border-collapse: collapse; font-size: 9.5px; }
table.items th, table.items td { border: 1px solid #000; padding: 3px 4px; text-align: center; height: 22px; }
table.items th { background: #f0f0f0; font-weight: bold; }
table.items .left { text-align: left; }
table.items .right { text-align: right; }
.summary-row { font-weight: bold; }
.terms { font-size: 9px; line-height: 1.5; margin: 8px 0; text-align: justify; }
.terms p { margin: 2px 0; text-indent: 0; }
.signature { display: flex; gap: 50px; margin-top: 15px; font-size: 10.5px; }
.sig-box { flex: 1; line-height: 2.5; }
.sig-box .label { font-weight: bold; }
.note-line { font-size: 10.5px; margin: 8px 0; }
@media print { .print-btn { display: none; } body { padding: 0; } }
</style>
</head>
<body>
<button class="print-btn" onclick="window.print()">打印</button>

<div class="header">
  <div class="company">深圳市奥特迈智能装备有限公司</div>
  <div class="title">采购合同（Purchase order）</div>
</div>

<div class="info-row">
  <span>项目号/负责人：${po?.project_name || ''}</span>
  <span>合同编号：${contract.contract_no}</span>
  <span>合同日期：${contractDate}</span>
</div>

<div class="parties">
  <div class="party">
    <div class="party-label">采购方（甲方）：深圳市奥特迈智能装备有限公司</div>
    <div>地址：广东省深圳市光明区玉塘街道玉律社区寮光路55号德永佳工业园1栋1楼（奥特迈）</div>
    <div>联系人：吴远明 &nbsp;&nbsp;&nbsp;&nbsp; 联系方式：19129305737</div>
  </div>
  <div class="party">
    <div class="party-label">供货方（乙方）：${supplier.name || ''}</div>
    <div>地址：${supplier.address || ''}</div>
    <div>联系人：${supplier.contact || ''} &nbsp;&nbsp;&nbsp;&nbsp; 联系方式：${supplier.phone || ''}</div>
  </div>
</div>

<div class="section-title">一、货物清单：产品名称、规格、数量、单价、金额（单位：人民币元）</div>
<table class="items">
  <tr>
    <th style="width:30px;">序号</th>
    <th>产品名称</th>
    <th style="width:100px;">规格型号</th>
    <th style="width:38px;">版本</th>
    <th style="width:35px;">单位</th>
    <th style="width:40px;">数量</th>
    <th style="width:60px;">单价</th>
    <th style="width:70px;">金额</th>
    <th style="width:70px;">交货日期</th>
    <th style="width:60px;">项目号</th>
    <th style="width:60px;">备注</th>
  </tr>
  ${lines.map((line, idx) => `<tr>
    <td>${idx + 1}</td>
    <td class="left">${line.item_name || ''}</td>
    <td class="left">${line.specification || ''}</td>
    <td></td>
    <td>${line.unit || ''}</td>
    <td>${line.qty || ''}</td>
    <td class="right">${line.unit_price ? line.unit_price.toFixed(2) : ''}</td>
    <td class="right">${line.line_amount ? line.line_amount.toFixed(2) : ''}</td>
    <td>${formatDate(po?.delivery_date)}</td>
    <td>${po?.project_name || ''}</td>
    <td>按图纸制作</td>
  </tr>`).join('')}
  ${emptyRows > 0 ? Array(emptyRows).fill(0).map((_, i) => `<tr>
    <td>${lines.length + i + 1}</td>
    <td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
  </tr>`).join('') : ''}
  <tr class="summary-row">
    <td colspan="6" style="text-align:left;padding-left:10px;">以下空白</td>
    <td colspan="5"></td>
  </tr>
  <tr class="summary-row">
    <td colspan="6" style="text-align:left;padding-left:10px;">合计（小写）：</td>
    <td class="right" colspan="2">¥${totalAmount.toFixed(2)}</td>
    <td colspan="3"></td>
  </tr>
  <tr class="summary-row">
    <td colspan="6" style="text-align:left;padding-left:10px;">金额（大写）：</td>
    <td colspan="5" style="text-align:left;padding-left:5px;">人民币${toChineseMoney(totalAmount)}</td>
  </tr>
</table>

<div class="note-line">产品按甲方提供图纸，负责包工、包料、表面处理等全部加工。价格含税${taxRate}%。</div>

<div class="terms">
<p><b>二、合同条款：</b></p>
<p>1. 乙方收到本合同后，务必于24小时内签字盖章回传确认，急件1小时内回传，逾期甲方有权取消订购合同。</p>
<p>2. 票据：${taxRate}％增值税专用发票。&nbsp;&nbsp;&nbsp;&nbsp;3. 付款方式：${po?.payment_terms || '月结60天'}。</p>
<p>4. 收货地址：吴远明，19129305737，深圳市光明区玉塘街道玉律社区寮光路55号德永佳工业园1栋1楼（奥特迈）。</p>
<p>5. 收货方式：运费由乙方承担，附送货单，注明合同号、品名、规格型号、数量并盖章，包装符合甲方要求，否则拒收。</p>
<p>6. 交期违约：逾期每天按订单总金额3%支付延误费用，超5天甲方可解约，因乙方延期导致甲方被索赔由乙方承担。</p>
<p>7. 质量要求：验收合格后24个月免费质保，质保期内包修包换包退。产品须符合材质、规格、精度等要求及图纸资料要求，来料不良率须≤3‰，超出双倍赔偿。如发现不合格商品，甲方有权退货并索赔相关费用。</p>
<p>8. 违约责任：按中华人民共和国经济合同法执行，争议协商不成向甲方所在地法院起诉。</p>
<p>9. 本合同经双方代表人签字或盖章生效，扫描件、传真件同样有效。</p>
</div>

<div class="signature">
  <div class="sig-box">
    <div class="label">甲方（盖章）：深圳市奥特迈智能装备有限公司</div>
    <div>代表人签字：</div>
  </div>
  <div class="sig-box">
    <div class="label">乙方（盖章）：${supplier.name || ''}</div>
    <div>代表人签字：</div>
  </div>
</div>
</body>
</html>`
}

const receiveGoods = (row) => {
  router.push(`/purchase/goods-receipts?po_id=${row.id}`)
}

const handleViewAttachments = (row) => {
  currentOrder.value = row
  attachmentDialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除采购订单 ${row.order_no} 吗？此操作不可恢复！`, 
      '删除订单', 
      { type: 'warning' }
    )
    await deletePurchaseOrder(row.id)
    ElMessage.success('订单已删除')
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除订单失败')
    }
  }
}

onMounted(() => {
  loadOrders()
  loadSuppliers()
  loadProjects()
  loadItems()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.total-section {
  text-align: right;
  margin-top: 15px;
  padding: 10px;
  background: #fafafa;
  border-radius: 4px;
}

.total-row {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 5px;
}

.total-row .label {
  color: #606266;
  margin-right: 10px;
}

.total-row .value {
  min-width: 100px;
  text-align: right;
}

.total-row.total {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #dcdfe6;
}

.total-row .amount {
  color: #f56c6c;
  font-weight: bold;
  font-size: 18px;
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
