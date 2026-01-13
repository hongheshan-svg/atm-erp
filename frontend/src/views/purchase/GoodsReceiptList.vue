<template>
  <div class="goods-receipt-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>收货管理</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            创建收货单
          </el-button>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="收货单号">
          <el-input v-model="searchForm.receipt_no" placeholder="请输入收货单号" clearable style="width: 150px;" />
        </el-form-item>
        <el-form-item label="采购订单">
          <el-select v-model="searchForm.purchase_order" placeholder="选择采购订单" clearable filterable style="width: 180px;">
            <el-option v-for="po in purchaseOrders" :key="po.id" :label="po.order_no" :value="po.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择状态" clearable style="width: 120px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已确认" value="CONFIRMED" />
            <el-option label="已完成" value="COMPLETED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadReceipts">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
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

      <el-table :data="receipts" v-loading="loading" border stripe @selection-change="handleSelectionChange">
        <el-table-column v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="receipt_no" label="收货单号" width="150" />
        <el-table-column prop="purchase_order_no" label="采购订单号" width="150" />
        <el-table-column prop="supplier_name" label="供应商" min-width="150" />
        <el-table-column prop="warehouse_name" label="收货仓库" width="120" />
        <el-table-column prop="receipt_date" label="收货日期" width="110" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="创建人" width="100" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" type="primary" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="success" @click="handleConfirm(row)" v-if="row.status === 'DRAFT'">确认入库</el-button>
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
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadReceipts"
        @current-change="loadReceipts"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 创建/编辑收货单对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="采购订单" prop="po">
              <el-select 
                v-model="form.po" 
                placeholder="选择采购订单" 
                filterable 
                style="width: 100%;"
                @change="onPurchaseOrderChange"
                :disabled="isEdit"
              >
                <el-option 
                  v-for="po in confirmedPurchaseOrders" 
                  :key="po.id" 
                  :label="`${po.order_no} - ${po.supplier_name}`" 
                  :value="po.id" 
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="收货仓库" prop="warehouse">
              <el-select v-model="form.warehouse" placeholder="选择仓库" filterable style="width: 100%;">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="收货日期" prop="receipt_date">
              <el-date-picker 
                v-model="form.receipt_date" 
                type="date" 
                value-format="YYYY-MM-DD" 
                placeholder="选择日期" 
                style="width: 100%;" 
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="备注">
              <el-input v-model="form.notes" placeholder="请输入备注" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 收货明细 -->
        <el-divider content-position="left">收货明细</el-divider>
        <el-table :data="form.lines" border size="small">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="item_sku" label="物料编码" width="120" />
          <el-table-column prop="item_name" label="物料名称" min-width="150" />
          <el-table-column prop="ordered_qty" label="订购数量" width="100" align="right" />
          <el-table-column prop="received_qty" label="已收数量" width="100" align="right" />
          <el-table-column label="本次收货" width="120">
            <template #default="{ row }">
              <el-input-number 
                v-model="row.qty" 
                :min="0" 
                :max="row.ordered_qty - row.received_qty"
                :precision="0" 
                size="small" 
                style="width: 100%;" 
              />
            </template>
          </el-table-column>
          <el-table-column label="质检状态" width="120">
            <template #default="{ row }">
              <el-select v-model="row.quality_status" size="small" style="width: 100%;">
                <el-option label="待检" value="PENDING" />
                <el-option label="合格" value="PASSED" />
                <el-option label="不合格" value="FAILED" />
              </el-select>
            </template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 收货单详情 -->
    <el-dialog v-model="detailVisible" title="收货单详情" width="80%">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="收货单号">{{ current.receipt_no }}</el-descriptions-item>
        <el-descriptions-item label="采购订单">{{ current.purchase_order_no }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ current.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="收货仓库">{{ current.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="收货日期">{{ current.receipt_date }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(current.status)">{{ getStatusLabel(current.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">{{ current.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-divider>收货明细</el-divider>
      <el-table :data="current.lines || []" border>
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="item_sku" label="物料编码" width="150" />
        <el-table-column prop="item_name" label="物料名称" min-width="150" />
        <el-table-column prop="qty" label="收货数量" width="100" align="right" />
        <el-table-column prop="quality_status" label="质检状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.quality_status === 'PASSED' ? 'success' : row.quality_status === 'FAILED' ? 'danger' : 'info'">
              {{ row.quality_status === 'PASSED' ? '合格' : row.quality_status === 'FAILED' ? '不合格' : '待检' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

const route = useRoute()

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/purchase/receipts/',
  {
    onSuccess: loadReceipts,
    confirmTitle: '删除收货单',
    confirmMessage: '确定要删除该收货单吗？删除后不可恢复！'
  }
)

const loading = ref(false)
const saving = ref(false)
const receipts = ref([])
const purchaseOrders = ref([])
const warehouses = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('创建收货单')
const isEdit = ref(false)
const detailVisible = ref(false)
const current = ref({})
const formRef = ref(null)

const searchForm = reactive({ 
  receipt_no: '', 
  purchase_order: null, 
  status: null 
})

const pagination = reactive({ 
  page: 1, 
  pageSize: 20, 
  total: 0 
})

const form = reactive({
  id: null,
  po: null,
  warehouse: null,
  receipt_date: new Date().toISOString().split('T')[0],
  notes: '',
  lines: []
})

const rules = {
  po: [{ required: true, message: '请选择采购订单', trigger: 'change' }],
  warehouse: [{ required: true, message: '请选择收货仓库', trigger: 'change' }],
  receipt_date: [{ required: true, message: '请选择收货日期', trigger: 'change' }]
}

// 只显示已确认或部分收货的采购订单
const confirmedPurchaseOrders = computed(() => 
  purchaseOrders.value.filter(po => po.status === 'CONFIRMED' || po.status === 'PARTIAL')
)

const getStatusType = (s) => ({ 'DRAFT': 'info', 'CONFIRMED': 'warning', 'COMPLETED': 'success' }[s] || 'info')
const getStatusLabel = (s) => ({ 'DRAFT': '草稿', 'CONFIRMED': '已确认', 'COMPLETED': '已完成' }[s] || s)

const loadReceipts = async () => {
  loading.value = true
  try {
    const params = { 
      page: pagination.page, 
      page_size: pagination.pageSize 
    }
    if (searchForm.receipt_no) params.receipt_no = searchForm.receipt_no
    if (searchForm.purchase_order) params.purchase_order = searchForm.purchase_order
    if (searchForm.status) params.status = searchForm.status
    
    const response = await request.get('/purchase/receipts/', { params })
    receipts.value = response.data?.results || response.results || response.data || []
    pagination.total = response.data?.count || response.count || 0
  } catch (error) {
    ElMessage.error('加载收货单失败')
  } finally {
    loading.value = false
  }
}

const loadPurchaseOrders = async () => {
  try {
    const response = await request.get('/purchase/orders/', { params: { page_size: 1000 } })
    purchaseOrders.value = response.data?.results || response.results || response.data || []
  } catch (error) {
    console.error('加载采购订单失败:', error)
  }
}

const loadWarehouses = async () => {
  try {
    const response = await request.get('/masterdata/warehouses/')
    warehouses.value = response.data?.results || response.results || response.data || []
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const resetSearch = () => {
  searchForm.receipt_no = ''
  searchForm.purchase_order = null
  searchForm.status = null
  pagination.page = 1
  loadReceipts()
}

const resetForm = () => {
  form.id = null
  form.po = null
  form.warehouse = null
  form.receipt_date = new Date().toISOString().split('T')[0]
  form.notes = ''
  form.lines = []
}

const handleAdd = () => {
  dialogTitle.value = '创建收货单'
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑收货单'
  isEdit.value = true
  try {
    const response = await request.get(`/purchase/receipts/${row.id}/`)
    const data = response.data || response
    Object.assign(form, {
      id: data.id,
      po: data.po,
      warehouse: data.warehouse,
      receipt_date: data.receipt_date,
      notes: data.notes || '',
      lines: (data.lines || []).map(line => ({
        id: line.id,
        po_line: line.po_line,
        item: line.item,
        item_sku: line.item_sku,
        item_name: line.item_name,
        ordered_qty: line.ordered_qty || 0,
        received_qty: line.received_qty || 0,
        qty: line.qty,
        quality_status: line.quality_status || 'PENDING'
      }))
    })
    dialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载收货单详情失败')
  }
}

const onPurchaseOrderChange = async (poId) => {
  if (!poId) {
    form.lines = []
    return
  }
  
  try {
    const response = await request.get(`/purchase/orders/${poId}/`)
    const po = response.data || response
    
    // 从采购订单明细生成收货明细
    form.lines = (po.lines || []).map(line => ({
      po_line: line.id, // 采购订单明细ID
      item: line.item,
      item_sku: line.item_sku || line.sku,
      item_name: line.item_name || line.name,
      ordered_qty: parseFloat(line.qty) || 0,
      received_qty: parseFloat(line.received_qty) || 0,
      qty: Math.max(0, (parseFloat(line.qty) || 0) - (parseFloat(line.received_qty) || 0)), // 默认填充未收货数量
      quality_status: 'PENDING'
    }))
  } catch (error) {
    ElMessage.error('加载采购订单详情失败')
  }
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    
    const validLines = form.lines.filter(line => line.qty > 0)
    if (validLines.length === 0) {
      ElMessage.warning('请至少输入一行有效的收货数量')
      return
    }
    
    saving.value = true
    
    const payload = {
      po: form.po,
      warehouse: form.warehouse,
      receipt_date: form.receipt_date,
      notes: form.notes,
      lines: validLines.map(line => ({
        po_line: line.po_line,
        item: line.item,
        qty: line.qty,
        quality_status: line.quality_status
      }))
    }
    
    if (isEdit.value) {
      await request.put(`/purchase/receipts/${form.id}/`, payload)
      ElMessage.success('更新收货单成功')
    } else {
      await request.post('/purchase/receipts/', payload)
      ElMessage.success('创建收货单成功')
    }
    
    dialogVisible.value = false
    loadReceipts()
    loadPurchaseOrders() // 刷新采购订单状态
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('保存收货单失败')
      console.error(error)
    }
  } finally {
    saving.value = false
  }
}

const handleView = async (row) => {
  try {
    const response = await request.get(`/purchase/receipts/${row.id}/`)
    current.value = response.data || response
    detailVisible.value = true
  } catch (error) {
    ElMessage.error('加载详情失败')
  }
}

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm('确定要确认收货吗？确认后将生成入库记录。', '提示', { type: 'warning' })
    await request.post(`/purchase/receipts/${row.id}/confirm/`)
    ElMessage.success('收货确认成功，已生成入库记录')
    loadReceipts()
    loadPurchaseOrders()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('确认收货失败')
  }
}

// handleDelete 已被 useBatchDelete 的 deleteRow 替代

// 处理从采购订单页面跳转过来的情况
const handleUrlParams = () => {
  const poId = route.query.po_id
  if (poId) {
    // 自动打开创建收货单对话框并选择采购订单
    dialogTitle.value = '创建收货单'
    isEdit.value = false
    resetForm()
    form.po = parseInt(poId)
    onPurchaseOrderChange(parseInt(poId))
    dialogVisible.value = true
  }
}

onMounted(() => {
  loadReceipts()
  loadPurchaseOrders()
  loadWarehouses()
  
  // 延迟处理URL参数，确保数据加载完成
  setTimeout(() => {
    handleUrlParams()
  }, 500)
})
</script>

<style scoped>
.goods-receipt-list { 
  padding: 20px; 
}

.card-header { 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
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

.search-form { 
  margin-bottom: 20px; 
}
</style>
