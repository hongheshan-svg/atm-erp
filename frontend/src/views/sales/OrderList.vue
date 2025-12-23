<template>
  <div class="sales-order-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>销售订单</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            创建订单
          </el-button>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="客户">
          <el-select v-model="searchForm.customer" placeholder="选择客户" clearable filterable style="width: 180px;">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 120px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已确认" value="CONFIRMED" />
            <el-option label="部分发货" value="PARTIAL" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadOrders">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="orders" v-loading="loading" stripe border>
        <el-table-column prop="order_no" label="销售订单号" width="150" />
        <el-table-column prop="customer_name" label="客户" />
        <el-table-column prop="project_name" label="项目" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_amount" label="总金额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.total_amount || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="order_date" label="订单日期" width="120" />
        <el-table-column prop="delivery_date" label="交货日期" width="120" />
        <el-table-column label="操作" width="350" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="warning" @click="handleConfirm(row)" v-if="row.status === 'DRAFT'">确认</el-button>
            <el-button size="small" type="warning" @click="handleViewAttachments(row)">附件</el-button>
            <el-button size="small" type="success" @click="createDelivery(row)" v-if="row.status === 'CONFIRMED' || row.status === 'PARTIAL'">发货</el-button>
            <el-button size="small" type="danger" @click="handleCancel(row)" v-if="row.status === 'DRAFT' || row.status === 'CONFIRMED'">取消</el-button>
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
            <el-form-item label="客户" prop="customer">
              <el-select v-model="form.customer" placeholder="选择客户" filterable style="width: 100%;">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="关联项目">
              <el-select v-model="form.project" placeholder="可选，后续可关联" filterable clearable style="width: 100%;">
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
          <el-col :span="12">
            <el-form-item label="付款条款">
              <el-input v-model="form.payment_terms" placeholder="如：预付30%，发货前付清" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="备注">
              <el-input v-model="form.notes" placeholder="请输入备注" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <!-- 订单明细 -->
        <el-divider content-position="left">订单明细</el-divider>
        <div style="margin-bottom: 10px; display: flex; gap: 10px;">
          <el-button type="primary" size="small" @click="addLine">
            <el-icon><Plus /></el-icon>
            添加产品
          </el-button>
          <el-button type="success" size="small" @click="showStockDialog">
            <el-icon><Box /></el-icon>
            从库存选择
          </el-button>
        </div>
        
        <el-table :data="form.lines" border size="small">
          <el-table-column label="产品/物料" min-width="200">
            <template #default="{ row, $index }">
              <el-select v-model="row.item" placeholder="选择产品" filterable style="width: 100%;" @change="onItemChange($index)">
                <el-option v-for="item in items" :key="item.id" :label="`${item.sku} - ${item.name}`" :value="item.id">
                  <div style="display: flex; justify-content: space-between;">
                    <span>{{ item.sku }} - {{ item.name }}</span>
                    <span style="color: #67c23a; font-size: 12px; margin-left: 10px;">
                      库存: {{ getItemStock(item.id) }}
                    </span>
                  </div>
                </el-option>
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
              ¥{{ ((row.qty || 0) * (row.unit_price || 0)).toFixed(2) }}
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
        
        <div class="total-amount">
          合计金额：<span class="amount">¥{{ calculateTotal().toFixed(2) }}</span>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 附件管理对话框 -->
    <el-dialog v-model="attachmentDialogVisible" :title="`销售订单 ${currentOrder?.order_no || ''} - 附件管理`" width="900px" destroy-on-close>
      <AttachmentUpload
        v-if="currentOrder"
        related-model="SalesOrder"
        :related-id="currentOrder.id"
        title="销售订单附件（合同、发票等）"
      />
    </el-dialog>

    <!-- 从库存选择对话框 -->
    <el-dialog v-model="stockDialogVisible" title="从库存选择产品" width="900px" destroy-on-close>
      <el-table
        :data="stockItems"
        v-loading="loadingStock"
        @selection-change="handleStockSelection"
        max-height="400"
        border
        stripe
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="item_sku" label="产品编码" width="120" />
        <el-table-column prop="item_name" label="产品名称" />
        <el-table-column prop="warehouse_name" label="仓库" width="120" />
        <el-table-column prop="qty_on_hand" label="可用库存" width="100" align="right">
          <template #default="{ row }">
            <span style="color: #67c23a; font-weight: 600;">{{ parseFloat(row.qty_on_hand).toFixed(0) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="weighted_avg_cost" label="参考成本" width="100" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.weighted_avg_cost || 0).toFixed(2) }}
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="stockDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmStockSelection">确定添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Box } from '@element-plus/icons-vue'
import request from '@/utils/request'
import AttachmentUpload from '@/components/AttachmentUpload.vue'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const orders = ref([])
const customers = ref([])
const projects = ref([])
const items = ref([])
const stocks = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('创建销售订单')
const isEdit = ref(false)
const formRef = ref(null)
const attachmentDialogVisible = ref(false)
const currentOrder = ref(null)
const stockDialogVisible = ref(false)
const stockItems = ref([])
const loadingStock = ref(false)
const selectedStockItems = ref([])

const searchForm = reactive({
  customer: null,
  status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  customer: null,
  project: null,
  delivery_date: '',
  payment_terms: '',
  notes: '',
  lines: []
})

const rules = {
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  delivery_date: [{ required: true, message: '请选择交货日期', trigger: 'change' }]
}

const getStatusType = (status) => {
  const types = { 
    DRAFT: 'info', 
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
    CONFIRMED: '已确认', 
    PARTIAL: '部分发货',
    COMPLETED: '已完成', 
    CANCELLED: '已取消' 
  }
  return labels[status] || status
}

const loadOrders = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.customer) params.customer = searchForm.customer
    if (searchForm.status) params.status = searchForm.status
    
    const res = await request.get('/sales/orders/', { params })
    orders.value = res.data?.results || res.results || res.data || []
    pagination.total = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载销售订单失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const res = await request.get('/masterdata/customers/')
    customers.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载客户失败:', error)
  }
}

const loadProjects = async () => {
  try {
    const res = await request.get('/projects/projects/')
    projects.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const loadItems = async () => {
  try {
    const res = await request.get('/masterdata/items/')
    items.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载物料失败:', error)
  }
}

const loadStocks = async () => {
  try {
    const res = await request.get('/inventory/stocks/', { params: { page_size: 500 } })
    stocks.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载库存失败:', error)
  }
}

// 获取物料库存
const getItemStock = (itemId) => {
  const stock = stocks.value.find(s => s.item === itemId)
  return stock ? parseFloat(stock.qty_on_hand).toFixed(0) : '0'
}

// 显示库存选择对话框
const showStockDialog = async () => {
  loadingStock.value = true
  stockDialogVisible.value = true
  try {
    const res = await request.get('/inventory/stocks/', { params: { page_size: 200 } })
    stockItems.value = (res.data?.results || res.results || res.data || [])
      .filter(s => parseFloat(s.qty_on_hand) > 0)
  } catch (error) {
    console.error('加载库存失败:', error)
  } finally {
    loadingStock.value = false
  }
}

// 库存选择变化
const handleStockSelection = (selection) => {
  selectedStockItems.value = selection
}

// 确认库存选择
const confirmStockSelection = () => {
  if (selectedStockItems.value.length === 0) {
    ElMessage.warning('请选择至少一个产品')
    return
  }

  selectedStockItems.value.forEach(stock => {
    const exists = form.lines.some(line => line.item === stock.item)
    if (!exists) {
      const item = items.value.find(i => i.id === stock.item)
      form.lines.push({
        item: stock.item,
        qty: 1,
        unit_price: parseFloat(stock.weighted_avg_cost || 0) * 1.3
      })
    }
  })

  // 移除空行
  form.lines = form.lines.filter(line => line.item !== null)
  if (form.lines.length === 0) {
    form.lines.push({ item: null, qty: 1, unit_price: 0 })
  }

  stockDialogVisible.value = false
  ElMessage.success('已添加所选产品')
}

const resetSearch = () => {
  searchForm.customer = null
  searchForm.status = null
  pagination.page = 1
  loadOrders()
}

const handleAdd = () => {
  dialogTitle.value = '创建销售订单'
  isEdit.value = false
  Object.assign(form, {
    id: null,
    customer: null,
    project: null,
    delivery_date: '',
    payment_terms: '',
    notes: '',
    lines: [{ item: null, qty: 1, unit_price: 0 }]
  })
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑销售订单'
  isEdit.value = true
  
  try {
    const res = await request.get(`/sales/orders/${row.id}/`)
    const data = res.data || res
    
    Object.assign(form, {
      id: data.id,
      customer: data.customer,
      project: data.project,
      delivery_date: data.delivery_date || '',
      payment_terms: data.payment_terms || '',
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
    ElMessage.error('获取销售订单详情失败')
  }
}

const handleView = (row) => {
  router.push(`/sales/orders/${row.id}`)
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
    // 销售价格可以基于成本加成
    line.unit_price = parseFloat(item.standard_cost || 0) * 1.3 // 默认30%加成
  }
}

const calculateTotal = () => {
  return form.lines.reduce((sum, line) => {
    return sum + (line.qty || 0) * (line.unit_price || 0)
  }, 0)
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
      customer: form.customer,
      project: form.project,
      delivery_date: form.delivery_date,
      payment_terms: form.payment_terms,
      notes: form.notes,
      lines: validLines.map(line => ({
        item: line.item,
        qty: line.qty,
        unit_price: line.unit_price
      }))
    }
    
    if (isEdit.value) {
      await request.put(`/sales/orders/${form.id}/`, payload)
      ElMessage.success('更新销售订单成功')
    } else {
      await request.post('/sales/orders/', payload)
      ElMessage.success('创建销售订单成功')
    }
    
    dialogVisible.value = false
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('保存销售订单失败')
      console.error(error)
    }
  } finally {
    saving.value = false
  }
}

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm('确定要确认该销售订单吗？确认后将无法修改。', '确认订单', { type: 'warning' })
    await request.post(`/sales/orders/${row.id}/confirm/`)
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
    await ElMessageBox.confirm('确定要取消该销售订单吗？', '取消订单', { type: 'warning' })
    await request.post(`/sales/orders/${row.id}/cancel/`)
    ElMessage.success('订单已取消')
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('取消订单失败')
    }
  }
}

const createDelivery = (row) => {
  router.push(`/sales/deliveries?so_id=${row.id}`)
}

const handleViewAttachments = (row) => {
  currentOrder.value = row
  attachmentDialogVisible.value = true
}

onMounted(() => {
  loadOrders()
  loadCustomers()
  loadProjects()
  loadItems()
  loadStocks()
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

.total-amount {
  text-align: right;
  margin-top: 15px;
  font-size: 16px;
}

.total-amount .amount {
  color: #f56c6c;
  font-weight: bold;
  font-size: 18px;
}
</style>
