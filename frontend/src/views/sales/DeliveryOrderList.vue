<template>
  <div class="delivery-order-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>发货单管理</span>
        </div>
      </template>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="发货单号">
          <el-input v-model="searchForm.delivery_no" placeholder="请输入发货单号" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择状态" clearable style="width: 160px;">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadDeliveryOrders">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-permission="'sales:delivery:delete'" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" v-permission="'sales:delivery:delete'" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <!-- 发货单列表 -->
      <el-table :data="deliveryOrders" v-loading="loading" border stripe @selection-change="handleSelectionChange">
        <el-table-column v-permission="'sales:delivery:delete'" v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="delivery_no" label="发货单号" width="150" />
        <el-table-column prop="so_no" label="销售订单" width="150" />
        <el-table-column prop="customer_name" label="客户" width="180" />
        <el-table-column prop="project_name" label="项目" width="150" />
        <el-table-column prop="warehouse_name" label="发货仓库" width="120" />
        <el-table-column prop="delivery_date" label="计划发货日期" width="120" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            
            <!-- 草稿/已拒绝: 可提交 -->
            <el-button size="small" type="warning" @click="handleSubmit(row)" 
                       v-if="['DRAFT', 'REJECTED'].includes(row.status)">
              提交审批
            </el-button>
            
            <!-- 审批中: 查看审批进度 -->
            <el-button size="small" type="info" @click="viewWorkflow(row)" 
                       v-if="['SUBMITTED', 'PENDING'].includes(row.status)">
              审批进度
            </el-button>
            
            <!-- 已审批/备货中: 确认备货 -->
            <el-button size="small" type="primary" @click="handleConfirmPrepared(row)" 
                       v-if="['APPROVED', 'PREPARING'].includes(row.status)">
              备货完成
            </el-button>
            
            <!-- 预约物流中: 确认物流 -->
            <el-button size="small" type="primary" @click="handleConfirmLogistics(row)" 
                       v-if="row.status === 'LOGISTICS_BOOKING'">
              确认物流
            </el-button>
            
            <!-- 待签收: 确认签收 -->
            <el-button size="small" type="primary" @click="handleConfirmSigned(row)" 
                       v-if="row.status === 'CUSTOMER_SIGNING'">
              确认签收
            </el-button>
            
            <!-- 待上传: 上传送货单 -->
            <el-button size="small" type="primary" @click="handleUploadReceipt(row)" 
                       v-if="row.status === 'UPLOADING_RECEIPT'">
              上传送货单
            </el-button>
            
            <!-- 待项目确认: 项目确认 -->
            <el-button size="small" type="success" @click="handleProjectConfirm(row)" 
                       v-if="row.status === 'PROJECT_CONFIRMING'">
              项目确认
            </el-button>
            
            <!-- 草稿/已拒绝: 可删除 -->
            <el-button 
              v-if="canDelete && ['DRAFT', 'REJECTED'].includes(row.status)"
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

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadDeliveryOrders"
        @current-change="loadDeliveryOrders"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 发货单详情对话框 -->
    <el-dialog v-model="detailVisible" title="发货单详情" width="90%" top="3vh" destroy-on-close>
      <el-tabs v-model="activeTab">
        <!-- 基本信息 -->
        <el-tab-pane label="基本信息" name="basic">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="发货单号">{{ currentDelivery.delivery_no }}</el-descriptions-item>
            <el-descriptions-item label="销售订单">{{ currentDelivery.so_no }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(currentDelivery.status)">
                {{ getStatusLabel(currentDelivery.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="计划发货日期">{{ currentDelivery.delivery_date }}</el-descriptions-item>
            <el-descriptions-item label="实际发货日期">{{ currentDelivery.actual_delivery_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="发货仓库">{{ currentDelivery.warehouse_name }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <!-- 客户信息 -->
        <el-tab-pane label="客户信息" name="customer">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="客户名称">{{ currentDelivery.customer_name }}</el-descriptions-item>
            <el-descriptions-item label="项目名称">{{ currentDelivery.project_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="客户联系人">{{ currentDelivery.customer_contact || '-' }}</el-descriptions-item>
            <el-descriptions-item label="客户电话">{{ currentDelivery.customer_phone || '-' }}</el-descriptions-item>
            <el-descriptions-item label="客户地址" :span="2">{{ currentDelivery.customer_address || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <!-- 收货信息 -->
        <el-tab-pane label="收货信息" name="receiver">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="收货人">{{ currentDelivery.receiver_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="收货电话">{{ currentDelivery.receiver_phone || '-' }}</el-descriptions-item>
            <el-descriptions-item label="收货地址" :span="2">{{ currentDelivery.receiver_address || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <!-- 产品信息 -->
        <el-tab-pane label="产品信息" name="products">
          <el-table :data="currentDelivery.lines || []" border>
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="item_sku" label="物料编码" width="150" />
            <el-table-column prop="item_name" label="物料名称" />
            <el-table-column prop="specification" label="规格" />
            <el-table-column prop="qty" label="发货数量" width="100" align="right" />
            <el-table-column prop="unit" label="单位" width="80" />
            <el-table-column prop="notes" label="备注" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>

        <!-- 包装/保险/物流 -->
        <el-tab-pane label="物流要求" name="logistics">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="包装方式">{{ currentDelivery.packaging_type_display || '-' }}</el-descriptions-item>
            <el-descriptions-item label="包装要求">{{ currentDelivery.packaging_notes || '-' }}</el-descriptions-item>
            <el-descriptions-item label="需要保险">{{ currentDelivery.needs_insurance ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item label="保险金额">{{ currentDelivery.insurance_amount ? `¥${currentDelivery.insurance_amount}` : '-' }}</el-descriptions-item>
            <el-descriptions-item label="物流公司">{{ currentDelivery.logistics_company || '-' }}</el-descriptions-item>
            <el-descriptions-item label="物流联系人">{{ currentDelivery.logistics_contact || '-' }}</el-descriptions-item>
            <el-descriptions-item label="物流电话">{{ currentDelivery.logistics_phone || '-' }}</el-descriptions-item>
            <el-descriptions-item label="物流单号">{{ currentDelivery.tracking_number || '-' }}</el-descriptions-item>
            <el-descriptions-item label="物流费用">{{ currentDelivery.logistics_cost ? `¥${currentDelivery.logistics_cost}` : '-' }}</el-descriptions-item>
            <el-descriptions-item label="物流要求">{{ currentDelivery.logistics_notes || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <!-- 签收信息 -->
        <el-tab-pane label="签收信息" name="receipt">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="签收人">{{ currentDelivery.signed_by || '-' }}</el-descriptions-item>
            <el-descriptions-item label="签收日期">{{ currentDelivery.signed_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="签收单据" :span="2">
              <template v-if="currentDelivery.signed_receipt">
                <el-link type="primary" :href="currentDelivery.signed_receipt" target="_blank">查看签收单</el-link>
              </template>
              <template v-else>-</template>
            </el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
      </el-tabs>

      <template v-if="currentDelivery.rejection_reason">
        <el-divider content-position="left">拒绝原因</el-divider>
        <el-alert :title="currentDelivery.rejection_reason" type="error" show-icon :closable="false" />
      </template>

      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="handlePrint(currentDelivery)">打印发货单</el-button>
      </template>
    </el-dialog>

    <!-- 物流信息对话框 -->
    <el-dialog v-model="logisticsDialogVisible" title="填写物流信息" width="500px">
      <el-form :model="logisticsForm" label-width="100px">
        <el-form-item label="物流公司" required>
          <el-input v-model="logisticsForm.logistics_company" placeholder="请输入物流公司名称" />
        </el-form-item>
        <el-form-item label="物流单号">
          <el-input v-model="logisticsForm.tracking_number" placeholder="请输入物流单号" />
        </el-form-item>
        <el-form-item label="物流费用">
          <el-input-number v-model="logisticsForm.logistics_cost" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="logisticsDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitLogistics" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 签收信息对话框 -->
    <el-dialog v-model="signedDialogVisible" title="确认签收信息" width="500px">
      <el-form :model="signedForm" label-width="100px">
        <el-form-item label="签收人" required>
          <el-input v-model="signedForm.signed_by" placeholder="请输入签收人姓名" />
        </el-form-item>
        <el-form-item label="签收日期" required>
          <el-date-picker v-model="signedForm.signed_date" type="date" value-format="YYYY-MM-DD" 
                          placeholder="选择签收日期" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="signedDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitSigned" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 上传送货单对话框 -->
    <el-dialog v-model="uploadDialogVisible" title="上传签收送货单" width="500px">
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        :on-change="handleFileChange"
        accept=".jpg,.jpeg,.png,.pdf"
        drag
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 jpg/png/pdf 格式文件
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitUpload" :loading="submitting">确定上传</el-button>
      </template>
    </el-dialog>

    <!-- 拒绝原因对话框 -->
    <el-dialog v-model="rejectDialogVisible" title="拒绝原因" width="500px">
      <el-form :model="rejectForm" label-width="100px">
        <el-form-item label="拒绝原因" required>
          <el-input v-model="rejectForm.reason" type="textarea" :rows="4" placeholder="请输入拒绝原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="submitReject" :loading="submitting">确定拒绝</el-button>
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
import { UploadFilled } from '@element-plus/icons-vue'
import { getDeliveryOrders, getDeliveryOrder, submitDeliveryOrder, confirmDeliveryPrepared, confirmDeliveryLogistics, confirmDeliverySigned, uploadDeliveryReceipt, projectConfirmDelivery, rejectDeliveryOrder } from '@/api/sales'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

const router = useRouter()

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/sales/delivery-orders/',
  { onSuccess: () => loadDeliveryOrders(), confirmTitle: '删除发货单', confirmMessage: '确定要删除该发货单吗？' }
)

const workflowDialogVisible = ref(false)
const workflowBusinessId = ref(null)
const workflowBusinessType = 'DELIVERY_ORDER'

const showWorkflowProgress = (row) => {
  workflowBusinessId.value = row.id
  workflowDialogVisible.value = true
}

const loading = ref(false)
const submitting = ref(false)
const deliveryOrders = ref<any[]>([])
const detailVisible = ref(false)
const currentDelivery = ref<Record<string, any>>({})
const activeTab = ref('basic')

// 对话框状态
const logisticsDialogVisible = ref(false)
const signedDialogVisible = ref(false)
const uploadDialogVisible = ref(false)
const rejectDialogVisible = ref(false)
const currentRowId = ref(null)
const uploadFile = ref(null)

// 表单
const logisticsForm = reactive({
  logistics_company: '',
  tracking_number: '',
  logistics_cost: null
})

const signedForm = reactive({
  signed_by: '',
  signed_date: ''
})

const rejectForm = reactive({
  reason: ''
})

const searchForm = reactive({
  delivery_no: '',
  status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const statusOptions = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'SUBMITTED', label: '已提交' },
  { value: 'PENDING', label: '审批中' },
  { value: 'APPROVED', label: '已审批' },
  { value: 'PREPARING', label: '备货中' },
  { value: 'LOGISTICS_BOOKING', label: '预约物流中' },
  { value: 'CUSTOMER_SIGNING', label: '待客户签收' },
  { value: 'UPLOADING_RECEIPT', label: '待上传送货单' },
  { value: 'PROJECT_CONFIRMING', label: '待项目确认' },
  { value: 'COMPLETED', label: '已完成' },
  { value: 'REJECTED', label: '已拒绝' }
]

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'SUBMITTED': 'warning',
    'PENDING': 'warning',
    'APPROVED': 'success',
    'PREPARING': 'primary',
    'LOGISTICS_BOOKING': 'primary',
    'CUSTOMER_SIGNING': 'primary',
    'UPLOADING_RECEIPT': 'primary',
    'PROJECT_CONFIRMING': 'primary',
    'COMPLETED': 'success',
    'REJECTED': 'danger'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const option = statusOptions.find(s => s.value === status)
  return option ? option.label : status
}

const loadDeliveryOrders = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    
    Object.keys(params).forEach(key => {
      if (params[key] === '' || params[key] === null) {
        delete params[key]
      }
    })

    const response = await getDeliveryOrders(params)
    deliveryOrders.value = response.results || response.data?.results || []
    pagination.total = response.count || response.data?.count || 0
  } catch (error) {
    console.error('加载发货单失败:', error)
    ElMessage.error('加载发货单失败')
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.delivery_no = ''
  searchForm.status = null
  pagination.page = 1
  loadDeliveryOrders()
}

const handleView = async (row) => {
  try {
    const response = await getDeliveryOrder(row.id)
    currentDelivery.value = response.data || response
    activeTab.value = 'basic'
    detailVisible.value = true
  } catch (error) {
    console.error('加载发货单详情失败:', error)
    ElMessage.error('加载发货单详情失败')
  }
}

// 提交发货申请
const handleSubmit = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交发货申请吗？', '提交确认', { type: 'info' })
    await submitDeliveryOrder(row.id)
    ElMessage.success('已提交发货申请')
    loadDeliveryOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '提交失败')
    }
  }
}

// 查看审批进度
const viewWorkflow = (row) => {
  showWorkflowProgress(row)
}

// 确认备货完成
const handleConfirmPrepared = async (row) => {
  try {
    await ElMessageBox.confirm('确定备货已完成吗？确认后将扣减库存。', '确认备货', { type: 'warning' })
    await confirmDeliveryPrepared(row.id)
    ElMessage.success('备货完成，已扣减库存')
    loadDeliveryOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '操作失败')
    }
  }
}

// 确认物流信息
const handleConfirmLogistics = (row) => {
  currentRowId.value = row.id
  logisticsForm.logistics_company = row.logistics_company || ''
  logisticsForm.tracking_number = row.tracking_number || ''
  logisticsForm.logistics_cost = row.logistics_cost || null
  logisticsDialogVisible.value = true
}

const submitLogistics = async () => {
  if (!logisticsForm.logistics_company) {
    ElMessage.warning('请填写物流公司')
    return
  }
  submitting.value = true
  try {
    await confirmDeliveryLogistics(currentRowId.value, logisticsForm)
    ElMessage.success('物流信息已确认')
    logisticsDialogVisible.value = false
    loadDeliveryOrders()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '操作失败')
  } finally {
    submitting.value = false
  }
}

// 确认签收
const handleConfirmSigned = (row) => {
  currentRowId.value = row.id
  signedForm.signed_by = ''
  signedForm.signed_date = ''
  signedDialogVisible.value = true
}

const submitSigned = async () => {
  if (!signedForm.signed_by || !signedForm.signed_date) {
    ElMessage.warning('请填写完整签收信息')
    return
  }
  submitting.value = true
  try {
    await confirmDeliverySigned(currentRowId.value, signedForm)
    ElMessage.success('签收信息已确认')
    signedDialogVisible.value = false
    loadDeliveryOrders()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '操作失败')
  } finally {
    submitting.value = false
  }
}

// 上传送货单
const handleUploadReceipt = (row) => {
  currentRowId.value = row.id
  uploadFile.value = null
  uploadDialogVisible.value = true
}

const handleFileChange = (file) => {
  uploadFile.value = file.raw
}

const submitUpload = async () => {
  submitting.value = true
  try {
    const formData = new FormData()
    if (uploadFile.value) {
      formData.append('signed_receipt', uploadFile.value)
    }
    await uploadDeliveryReceipt(currentRowId.value, formData)
    ElMessage.success('送货单上传成功')
    uploadDialogVisible.value = false
    loadDeliveryOrders()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '上传失败')
  } finally {
    submitting.value = false
  }
}

// 项目确认
const handleProjectConfirm = async (row) => {
  try {
    await ElMessageBox.confirm('确定项目已确认完成吗？', '项目确认', { type: 'success' })
    await projectConfirmDelivery(row.id)
    ElMessage.success('发货流程已完成')
    loadDeliveryOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '操作失败')
    }
  }
}

// 拒绝
const handleReject = (row) => {
  currentRowId.value = row.id
  rejectForm.reason = ''
  rejectDialogVisible.value = true
}

const submitReject = async () => {
  if (!rejectForm.reason) {
    ElMessage.warning('请填写拒绝原因')
    return
  }
  submitting.value = true
  try {
    await rejectDeliveryOrder(currentRowId.value, rejectForm)
    ElMessage.success('已拒绝')
    rejectDialogVisible.value = false
    loadDeliveryOrders()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '操作失败')
  } finally {
    submitting.value = false
  }
}

// 删除
// handleDelete 已被 useBatchDelete 的 deleteRow 替代

// 打印
const handlePrint = (row) => {
  if (!row) {
    ElMessage.warning('请选择要打印的发货单')
    return
  }
  
  const printContent = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>发货单 - ${row.delivery_no}</title>
      <style>
        body { font-family: 'Microsoft YaHei', Arial, sans-serif; padding: 20px; }
        .header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { margin: 0; font-size: 28px; }
        .info-section { margin-bottom: 20px; }
        .info-section h3 { margin: 0 0 10px 0; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 5px; }
        .info-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        .info-table td { padding: 8px; border: 1px solid #ddd; }
        .info-table td:first-child { width: 20%; background: #f5f5f5; font-weight: bold; }
        .items-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        .items-table th, .items-table td { padding: 8px; border: 1px solid #ddd; text-align: left; }
        .items-table th { background: #f5f5f5; font-weight: bold; }
        .items-table td.number { text-align: right; }
        .footer { margin-top: 40px; }
        @media print { body { padding: 0; } .no-print { display: none; } }
      </style>
    </head>
    <body>
      <div class="header">
        <h1>发货单</h1>
        <p>Delivery Order</p>
      </div>
      
      <div class="info-section">
        <h3>基本信息</h3>
        <table class="info-table">
          <tr><td>发货单号</td><td>${row.delivery_no}</td><td>销售订单</td><td>${row.so_no || '-'}</td></tr>
          <tr><td>客户名称</td><td>${row.customer_name || '-'}</td><td>项目名称</td><td>${row.project_name || '-'}</td></tr>
          <tr><td>计划发货日期</td><td>${row.delivery_date}</td><td>发货仓库</td><td>${row.warehouse_name || '-'}</td></tr>
        </table>
      </div>

      <div class="info-section">
        <h3>收货信息</h3>
        <table class="info-table">
          <tr><td>收货人</td><td>${row.receiver_name || '-'}</td><td>收货电话</td><td>${row.receiver_phone || '-'}</td></tr>
          <tr><td>收货地址</td><td colspan="3">${row.receiver_address || '-'}</td></tr>
        </table>
      </div>

      <div class="info-section">
        <h3>物流信息</h3>
        <table class="info-table">
          <tr><td>物流公司</td><td>${row.logistics_company || '-'}</td><td>物流单号</td><td>${row.tracking_number || '-'}</td></tr>
          <tr><td>包装方式</td><td>${row.packaging_type_display || '-'}</td><td>需要保险</td><td>${row.needs_insurance ? '是' : '否'}</td></tr>
        </table>
      </div>
      
      <div class="info-section">
        <h3>产品明细</h3>
        <table class="items-table">
          <thead>
            <tr><th>序号</th><th>物料编码</th><th>物料名称</th><th>规格</th><th>单位</th><th class="number">数量</th><th>备注</th></tr>
          </thead>
          <tbody>
            ${(row.lines || []).map((line, index) => `
              <tr>
                <td>${index + 1}</td>
                <td>${line.item_sku || '-'}</td>
                <td>${line.item_name || '-'}</td>
                <td>${line.specification || '-'}</td>
                <td>${line.unit || '-'}</td>
                <td class="number">${line.qty}</td>
                <td>${line.notes || ''}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
      
      ${row.notes ? `<div style="margin: 20px 0;"><strong>备注：</strong>${row.notes}</div>` : ''}
      
      <div class="footer">
        <div style="display: flex; justify-content: space-between;">
          <div><p>发货人：____________</p><p>日期：____________</p></div>
          <div><p>收货人：____________</p><p>日期：____________</p></div>
        </div>
      </div>
      
      <div class="no-print" style="text-align: center; margin-top: 20px;">
        <button onclick="window.print()" style="padding: 10px 30px; font-size: 16px;">打印</button>
        <button onclick="window.close()" style="padding: 10px 30px; font-size: 16px; margin-left: 10px;">关闭</button>
      </div>
    </body>
    </html>
  `
  
  const printWindow = window.open('', '_blank')
  printWindow.document.write(printContent)
  printWindow.document.close()
  printWindow.focus()
}

onMounted(() => {
  loadDeliveryOrders()
})
</script>

<style scoped>
.delivery-order-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}
</style>
