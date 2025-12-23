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
        <el-table-column prop="total_with_tax" label="含税总额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.total_with_tax || row.total_amount || 0).toFixed(2) }}
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
              <el-input v-model="form.payment_terms" placeholder="如：预付30%，发货前付清" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="备注">
              <el-input v-model="form.notes" placeholder="请输入备注" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <!-- 订单明细 -->
        <el-divider content-position="left">订单明细（非标定制产品可直接填写）</el-divider>
        <div style="margin-bottom: 10px; display: flex; gap: 10px;">
          <el-button type="primary" size="small" @click="addLine">
            <el-icon><Plus /></el-icon>
            添加产品
          </el-button>
        </div>
        
        <el-table :data="form.lines" border size="small">
          <el-table-column label="产品名称 *" min-width="180">
            <template #default="{ row, $index }">
              <el-input 
                v-model="row.custom_name" 
                placeholder="输入产品名称" 
                size="small"
              />
            </template>
          </el-table-column>
          <el-table-column label="规格型号" min-width="150">
            <template #default="{ row }">
              <el-input 
                v-model="row.custom_spec" 
                placeholder="如：φ20×100mm" 
                size="small"
              />
            </template>
          </el-table-column>
          <el-table-column label="单位" width="80">
            <template #default="{ row }">
              <el-input v-model="row.custom_unit" placeholder="件" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="数量" width="100">
            <template #default="{ row }">
              <el-input-number v-model="row.qty" :min="1" :precision="0" size="small" controls-position="right" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="单价" width="110">
            <template #default="{ row }">
              <el-input-number v-model="row.unit_price" :min="0" :precision="2" size="small" controls-position="right" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="小计" width="100" align="right">
            <template #default="{ row }">
              ¥{{ ((row.qty || 0) * (row.unit_price || 0)).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60" align="center">
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
            <span class="value">¥{{ calculateTotal().toFixed(2) }}</span>
          </div>
          <div class="total-row">
            <span class="label">税额 ({{ form.tax_rate }}%)：</span>
            <span class="value">¥{{ calculateTax().toFixed(2) }}</span>
          </div>
          <div class="total-row total">
            <span class="label">含税总额：</span>
            <span class="amount">¥{{ calculateTotalWithTax().toFixed(2) }}</span>
          </div>
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

  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import request from '@/utils/request'
import AttachmentUpload from '@/components/AttachmentUpload.vue'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const orders = ref([])
const customers = ref([])
const projects = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('创建销售订单')
const isEdit = ref(false)
const formRef = ref(null)
const attachmentDialogVisible = ref(false)
const currentOrder = ref(null)

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
  tax_rate: 13,
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
    tax_rate: 13,
    payment_terms: '',
    notes: '',
    lines: [{ custom_name: '', custom_spec: '', custom_unit: '件', qty: 1, unit_price: 0 }]
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
      tax_rate: data.tax_rate ?? 13,
      payment_terms: data.payment_terms || '',
      notes: data.notes || '',
      lines: (data.lines || []).map(line => ({
        id: line.id,
        item: line.item,
        custom_name: line.custom_name || line.item_name || '',
        custom_spec: line.custom_spec || line.item_spec || '',
        custom_unit: line.custom_unit || line.item_unit || '件',
        qty: parseFloat(line.qty || 1),
        unit_price: parseFloat(line.unit_price || 0)
      }))
    })
    
    if (form.lines.length === 0) {
      form.lines = [{ custom_name: '', custom_spec: '', custom_unit: '件', qty: 1, unit_price: 0 }]
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
  form.lines.push({ custom_name: '', custom_spec: '', custom_unit: '件', qty: 1, unit_price: 0 })
}

const removeLine = (index) => {
  if (form.lines.length > 1) {
    form.lines.splice(index, 1)
  } else {
    ElMessage.warning('至少保留一行明细')
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
    
    // 验证：至少有一行填写了产品名称
    const validLines = form.lines.filter(line => line.custom_name && line.qty > 0)
    if (validLines.length === 0) {
      ElMessage.warning('请至少添加一行产品明细（需填写产品名称）')
      return
    }
    
    saving.value = true
    
    const payload = {
      customer: form.customer,
      project: form.project,
      delivery_date: form.delivery_date,
      tax_rate: form.tax_rate,
      payment_terms: form.payment_terms,
      notes: form.notes,
      lines: validLines.map(line => ({
        item: line.item || null,
        custom_name: line.custom_name,
        custom_spec: line.custom_spec || '',
        custom_unit: line.custom_unit || '件',
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
</style>
