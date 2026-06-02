<template>
  <div class="sales-order-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>销售订单</span>
          <div class="header-actions">
            <el-button @click="downloadTemplate">
              <el-icon><Download /></el-icon>
              下载模板
            </el-button>
            <el-upload
              :show-file-list="false"
              :before-upload="handleImport"
              accept=".xlsx,.xls"
              style="display: inline-block; margin: 0 8px;"
            >
              <el-button type="success">
                <el-icon><Upload /></el-icon>
                导入
              </el-button>
            </el-upload>
            <el-button @click="handleExport">
              <el-icon><Download /></el-icon>
              导出
            </el-button>
            <el-button type="primary" v-permission="'sales:order:create'" @click="handleAdd">
              <el-icon><Plus /></el-icon>
              创建订单
            </el-button>
          </div>
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
            <el-option label="已提交" value="SUBMITTED" />
            <el-option label="审批中" value="PENDING" />
            <el-option label="已审批" value="APPROVED" />
            <el-option label="备货中" value="PREPARING" />
            <el-option label="预约物流中" value="LOGISTICS_BOOKING" />
            <el-option label="待客户签收" value="CUSTOMER_SIGNING" />
            <el-option label="待上传送货单" value="UPLOADING_RECEIPT" />
            <el-option label="待项目确认" value="PROJECT_CONFIRMING" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已拒绝" value="REJECTED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadOrders">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作 -->
      <div v-if="selectedOrders.length > 0" style="margin-bottom: 10px;">
        <el-button type="danger" size="small" @click="handleBulkDelete">
          <el-icon><Delete /></el-icon>
          批量删除 ({{ selectedOrders.length }})
        </el-button>
        <span style="margin-left: 10px; color: #909399; font-size: 12px;">
          提示：只能删除草稿/已取消/已拒绝状态的订单
        </span>
      </div>

      <el-table :data="orders" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="order_no" label="销售订单号" width="150" />
        <el-table-column prop="customer_order_no" label="客户订单号" width="140" />
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
        <el-table-column label="操作" width="400" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" v-permission="'sales:order:edit'" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="warning" @click="handleSubmitApproval(row)" v-if="row.status === 'DRAFT' || row.status === 'REJECTED'">提交审批</el-button>
            <el-button size="small" type="info" @click="showWorkflowProgress(row)" v-if="row.status === 'PENDING'">审批进度</el-button>
            <el-button size="small" type="warning" @click="handleConfirm(row)" v-if="row.status === 'APPROVED'">确认</el-button>
            <el-button size="small" type="warning" @click="handleViewAttachments(row)">附件</el-button>
            <el-button size="small" type="success" @click="createDelivery(row)" v-if="row.status === 'APPROVED' || row.status === 'PARTIAL_DELIVERY'">发货</el-button>
            <el-button size="small" type="danger" @click="handleCancel(row)" v-if="row.status === 'DRAFT' || row.status === 'CONFIRMED'">取消</el-button>
            <el-button size="small" type="danger" v-permission="'sales:order:delete'" @click="handleDelete(row)" v-if="['DRAFT', 'CANCELLED', 'REJECTED'].includes(row.status)">删除</el-button>
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
      <el-form :model="form" :rules="rules" ref="formRef" label-width="110px">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="销售订单号">
              <el-input v-model="form.order_no" placeholder="留空则自动生成" :disabled="isEdit" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="客户订单号">
              <el-input v-model="form.customer_order_no" placeholder="客户的订单编号（可选）" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="客户" prop="customer">
              <el-select v-model="form.customer" placeholder="选择客户" filterable style="width: 100%;">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
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
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="付款条款">
              <el-select v-model="form.payment_terms" placeholder="选择付款条款" style="width: 100%;">
                <el-option value="FULL_PREPAY" label="全款预付" />
                <el-option value="COD" label="货到付款" />
                <el-option value="NET30" label="月结30天" />
                <el-option value="NET60" label="月结60天" />
                <el-option value="NET90" label="月结90天" />
                <el-option value="M_30_70" label="30%预付/70%发货前" />
                <el-option value="M_30_30_40" label="30%预付/30%发货前/40%验收后" />
                <el-option value="M_30_30_30_10" label="30%预付/30%发货前/30%验收/10%质保" />
                <el-option value="M_30_60_10" label="30%预付/60%验收/10%质保" />
                <el-option value="M_50_40_10" label="50%预付/40%验收/10%质保" />
                <el-option value="M_40_50_10" label="40%预付/50%验收/10%质保" />
                <el-option value="M_20_70_10" label="20%预付/70%验收/10%质保" />
                <el-option value="CUSTOM" label="自定义分期" />
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
              <el-input v-model="form.payment_terms_detail" placeholder="付款条款补充说明（自定义分期时填写）" />
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
            <template #default="{ row, $index: _$index }">
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

    <!-- 导入错误对话框 -->
    <el-dialog v-model="importErrorDialogVisible" title="导入失败 - 数据校验错误" width="800px">
      <el-alert type="error" :closable="false" show-icon style="margin-bottom: 15px;">
        <template #title>
          共 {{ importErrors.length }} 处错误，请修正Excel文件后重新导入
        </template>
      </el-alert>
      <el-table :data="importErrors" max-height="400" border size="small">
        <el-table-column prop="row" label="行号" width="80" align="center" />
        <el-table-column prop="sheet" label="工作表" width="100">
          <template #default="{ row }">
            {{ row.sheet || '销售订单' }}
          </template>
        </el-table-column>
        <el-table-column prop="order_no" label="订单号" width="120">
          <template #default="{ row }">
            {{ row.order_no || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="customer" label="客户" width="150">
          <template #default="{ row }">
            {{ row.customer || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="error" label="错误信息" min-width="250">
          <template #default="{ row }">
            <span style="color: #f56c6c;">{{ row.error }}</span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button type="primary" @click="importErrorDialogVisible = false">我知道了</el-button>
      </template>
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
import { Plus, Delete, Download, Upload } from '@element-plus/icons-vue'
import { getSalesOrders, getSalesOrder, createSalesOrder, updateSalesOrder, deleteSalesOrder, submitSalesOrder, confirmSalesOrder, cancelSalesOrder, downloadOrderTemplate, importSalesOrders, exportSalesOrders, bulkDeleteSalesOrders } from '@/api/sales'
import AttachmentUpload from '@/components/AttachmentUpload.vue'
import { usePermissionStore } from '@/stores/permission'
import { getCustomerList } from '@/api/masterdata'
import { getProjectList } from '@/api/projects/project'

const router = useRouter()
const permissionStore = usePermissionStore()
const workflowDialogVisible = ref(false)
const workflowBusinessId = ref(null)
const workflowBusinessType = 'SALES_ORDER'

const showWorkflowProgress = (row) => {
  workflowBusinessId.value = row.id
  workflowDialogVisible.value = true
}

const loading = ref(false)
const saving = ref(false)
const orders = ref<any[]>([])
const customers = ref<any[]>([])
const projects = ref<any[]>([])
const projectsLoaded = ref(false)
const selectedOrders = ref<any[]>([])
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
  order_no: '',
  customer_order_no: '',
  customer: null,
  project: null,
  delivery_date: '',
  tax_rate: 13,
  payment_terms: 'M_30_30_30_10',
  payment_method: 'WIRE',
  payment_terms_detail: '',
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
    SUBMITTED: 'warning',
    PENDING: 'warning',
    APPROVED: 'success',
    PREPARING: 'primary',
    LOGISTICS_BOOKING: 'primary',
    CUSTOMER_SIGNING: 'primary',
    UPLOADING_RECEIPT: 'primary',
    PROJECT_CONFIRMING: 'primary',
    COMPLETED: '',
    REJECTED: 'danger'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    DRAFT: '草稿',
    SUBMITTED: '已提交',
    PENDING: '审批中',
    APPROVED: '已审批',
    PREPARING: '备货中',
    LOGISTICS_BOOKING: '预约物流中',
    CUSTOMER_SIGNING: '待客户签收',
    UPLOADING_RECEIPT: '待上传送货单',
    PROJECT_CONFIRMING: '待项目确认',
    COMPLETED: '已完成',
    REJECTED: '已拒绝'
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
    
    const res = await getSalesOrders(params)
    orders.value = res.results || res.results || res || []
    pagination.total = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载销售订单失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const res = await getCustomerList()
    customers.value = res.results || res.results || res || []
  } catch (error) {
    console.error('加载客户失败:', error)
  }
}

const loadProjects = async () => {
  if (projectsLoaded.value) {
    return true
  }

  try {
    const res = await getProjectList()
    projects.value = res.results || res.results || res || []
    projectsLoaded.value = true
    return true
  } catch (error) {
    if (error?.response?.status !== 403) {
      console.error('加载项目失败:', error)
    }
    return false
  }
}

const ensureProjectsLoaded = async () => {
  if (!permissionStore.hasPermission('projects:list')) {
    projects.value = []
    projectsLoaded.value = false
    return false
  }

  return loadProjects()
}

const resetSearch = () => {
  searchForm.customer = null
  searchForm.status = null
  pagination.page = 1
  loadOrders()
}

const handleAdd = async () => {
  dialogTitle.value = '创建销售订单'
  isEdit.value = false
  await ensureProjectsLoaded()
  Object.assign(form, {
    id: null,
    order_no: '',
    customer_order_no: '',
    customer: null,
    project: null,
    delivery_date: '',
    tax_rate: 13,
    payment_terms: 'M_30_30_30_10',
    payment_method: 'WIRE',
    payment_terms_detail: '',
    notes: '',
    lines: [{ custom_name: '', custom_spec: '', custom_unit: '件', qty: 1, unit_price: 0 }]
  })
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑销售订单'
  isEdit.value = true
  await ensureProjectsLoaded()
  
  try {
    const res = await getSalesOrder(row.id)
    const data = res
    
    Object.assign(form, {
      id: data.id,
      order_no: data.order_no || '',
      customer_order_no: data.customer_order_no || '',
      customer: data.customer,
      project: data.project,
      delivery_date: data.delivery_date || '',
      tax_rate: data.tax_rate ?? 13,
      payment_terms: data.payment_terms || 'M_30_30_30_10',
      payment_method: data.payment_method || 'WIRE',
      payment_terms_detail: data.payment_terms_detail || '',
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
      customer_order_no: form.customer_order_no || '',
      project: form.project,
      delivery_date: form.delivery_date,
      tax_rate: form.tax_rate,
      payment_terms: form.payment_terms,
      payment_method: form.payment_method,
      payment_terms_detail: form.payment_terms_detail,
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
    
    // 创建时如果用户填写了销售订单号，则使用用户输入的
    if (!isEdit.value && form.order_no) {
      payload.order_no = form.order_no
    }
    
    if (isEdit.value) {
      await updateSalesOrder(form.id, payload)
      ElMessage.success('更新销售订单成功')
    } else {
      await createSalesOrder(payload)
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

const handleSubmitApproval = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交该销售订单进行审批吗？', '提交审批', { type: 'warning' })
    const response = await submitSalesOrder(row.id)
    const data = response.data || response
    if (data.workflow_started) {
      ElMessage.success(data.message || '已提交审批')
    } else {
      ElMessage.success(data.message || '订单已确认')
    }
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      const msg = error.response?.data?.error || '提交失败'
      ElMessage.error(msg)
    }
  }
}

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm('确定要确认该销售订单吗？确认后将无法修改。', '确认订单', { type: 'warning' })
    await confirmSalesOrder(row.id)
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
    await cancelSalesOrder(row.id)
    ElMessage.success('订单已取消')
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('取消订单失败')
    }
  }
}

const createDelivery = (row) => {
  // 导航到销售订单详情页面，带上创建发货单参数
  router.push(`/sales/orders/${row.id}?action=create_delivery`)
}

const handleViewAttachments = (row) => {
  currentOrder.value = row
  attachmentDialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除销售订单 ${row.order_no} 吗？此操作不可恢复！`, 
      '删除订单', 
      { type: 'warning' }
    )
    await deleteSalesOrder(row.id)
    ElMessage.success('订单已删除')
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除订单失败')
    }
  }
}

// 下载模板
const downloadTemplate = async () => {
  try {
    const response = await downloadOrderTemplate()
    const url = window.URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = 'sales_order_template.xlsx'
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }, 100)
  } catch (error) {
    ElMessage.error('下载模板失败')
  }
}

// 导入错误对话框
const importErrorDialogVisible = ref(false)
const importErrors = ref<any[]>([])

// 导入
const handleImport = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  
  try {
    const res = await importSalesOrders(formData)
    
    ElMessage.success(res.message || `导入完成！新增 ${res.success_count} 条，更新 ${res.update_count} 条`)
    loadOrders()
  } catch (error) {
    const errData = error.response?.data
    if (errData?.errors && errData.errors.length > 0) {
      // 有详细错误信息，显示错误对话框
      importErrors.value = errData.errors
      importErrorDialogVisible.value = true
    } else {
      ElMessage.error(errData?.error || '导入失败')
    }
  }
  
  return false // 阻止默认上传
}

// 导出
const handleExport = async () => {
  try {
    const params = {
      customer: searchForm.customer,
      status: searchForm.status
    }
    
    const response = await exportSalesOrders(params)
    
    const url = window.URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = `sales_orders_${new Date().toISOString().slice(0, 10)}.xlsx`
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }, 100)
    
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

// 选择变化
const handleSelectionChange = (selection) => {
  selectedOrders.value = selection
}

// 批量删除
const handleBulkDelete = async () => {
  if (selectedOrders.value.length === 0) {
    ElMessage.warning('请选择要删除的订单')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedOrders.value.length} 个订单吗？只有草稿/已取消/已拒绝状态的订单会被删除。`,
      '批量删除',
      { type: 'warning' }
    )
    
    const ids = selectedOrders.value.map(order => order.id)
    const res = await bulkDeleteSalesOrders({ ids })
    
    ElMessage.success(res.message || '批量删除成功')
    selectedOrders.value = []
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '批量删除失败')
    }
  }
}

onMounted(() => {
  loadOrders()
  loadCustomers()
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
