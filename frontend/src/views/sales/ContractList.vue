<template>
  <div class="sales-contract-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>销售合同</span>
          <div class="header-actions">
            <el-button type="primary" v-permission="'sales:contract:create'" @click="handleCreate">
              <el-icon><Plus /></el-icon>
              创建合同
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
            <el-option label="待审批" value="PENDING" />
            <el-option label="已审批" value="APPROVED" />
            <el-option label="已拒绝" value="REJECTED" />
            <el-option label="已签署" value="SIGNED" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadContracts">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-permission="'sales:contract:delete'" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" v-permission="'sales:contract:delete'" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <el-table :data="contracts" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column v-permission="'sales:contract:delete'" v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="contract_no" label="合同编号" width="150" />
        <el-table-column prop="title" label="合同标题" min-width="180" />
        <el-table-column prop="customer_name" label="客户" width="150" />
        <el-table-column prop="so_no" label="销售订单" width="140" />
        <el-table-column prop="project_name" label="项目" width="140" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_with_tax" label="含税总额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.total_with_tax || row.total_amount || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="contract_date" label="合同日期" width="110" />
        <el-table-column prop="signed_date" label="签署日期" width="110" />
        <el-table-column label="操作" width="400" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" v-permission="'sales:contract:edit'" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="warning" @click="handleSubmitApproval(row)" v-if="row.status === 'DRAFT' || row.status === 'REJECTED'">提交审批</el-button>
            <el-button size="small" type="info" @click="showWorkflowProgress(row)" v-if="row.status === 'PENDING'">审批进度</el-button>
            <el-button size="small" type="warning" @click="handleApprove(row)" v-if="row.status === 'PENDING'">审批</el-button>
            <el-button size="small" type="success" @click="handleSign(row)" v-if="row.status === 'APPROVED'">签署</el-button>
            <el-button size="small" type="info" @click="handlePrint(row)">打印</el-button>
            <el-button v-if="canDelete && row.status === 'DRAFT'" size="small" type="danger" @click="deleteRow(row)" :loading="deleteLoading">删除</el-button>
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
        @size-change="loadContracts"
        @current-change="loadContracts"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>
    
    <!-- 创建合同对话框（从销售订单创建） -->
    <el-dialog v-model="createDialogVisible" title="创建销售合同" width="500px">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="100px">
        <el-form-item label="销售订单" prop="so_id">
          <el-select 
            v-model="createForm.so_id" 
            placeholder="选择销售订单" 
            filterable
            remote
            :remote-method="searchOrders"
            :loading="searchingOrders"
            style="width: 100%;"
          >
            <el-option 
              v-for="so in salesOrders" 
              :key="so.id" 
              :label="`${so.order_no} - ${so.customer_name}`" 
              :value="so.id"
            >
              <div style="display: flex; justify-content: space-between;">
                <span>{{ so.order_no }}</span>
                <span style="color: #8492a6; font-size: 12px;">{{ so.customer_name }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" v-permission="'sales:contract:create'" @click="handleCreateFromSO" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
    
    <!-- 编辑合同对话框 -->
    <el-dialog v-model="editDialogVisible" :title="dialogTitle" width="800px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="合同标题" prop="title">
              <el-input v-model="form.title" placeholder="输入合同标题" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="合同日期" prop="contract_date">
              <el-date-picker 
                v-model="form.contract_date" 
                type="date" 
                value-format="YYYY-MM-DD" 
                placeholder="选择日期" 
                style="width: 100%;" 
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="生效日期">
              <el-date-picker 
                v-model="form.effective_date" 
                type="date" 
                value-format="YYYY-MM-DD" 
                placeholder="选择日期" 
                style="width: 100%;" 
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="到期日期">
              <el-date-picker 
                v-model="form.expiry_date" 
                type="date" 
                value-format="YYYY-MM-DD" 
                placeholder="选择日期" 
                style="width: 100%;" 
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-divider content-position="left">合同条款</el-divider>
        
        <el-form-item label="付款条款">
          <el-input v-model="form.payment_terms" type="textarea" :rows="2" placeholder="输入付款条款" />
        </el-form-item>
        <el-form-item label="交货条款">
          <el-input v-model="form.delivery_terms" type="textarea" :rows="2" placeholder="输入交货条款" />
        </el-form-item>
        <el-form-item label="质量条款">
          <el-input v-model="form.quality_terms" type="textarea" :rows="2" placeholder="输入质量条款" />
        </el-form-item>
        <el-form-item label="质保条款">
          <el-input v-model="form.warranty_terms" type="textarea" :rows="2" placeholder="输入质保条款" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 查看合同详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="合同详情" width="900px" destroy-on-close>
      <el-descriptions :column="2" border v-if="currentContract">
        <el-descriptions-item label="合同编号">{{ currentContract.contract_no }}</el-descriptions-item>
        <el-descriptions-item label="合同标题">{{ currentContract.title }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ currentContract.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="销售订单">{{ currentContract.so_no }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ currentContract.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentContract.status)">{{ getStatusLabel(currentContract.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="合同日期">{{ currentContract.contract_date }}</el-descriptions-item>
        <el-descriptions-item label="生效日期">{{ currentContract.effective_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="到期日期">{{ currentContract.expiry_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="签署日期">{{ currentContract.signed_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="不含税金额">¥{{ parseFloat(currentContract.total_amount || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="税率">{{ currentContract.tax_rate }}%</el-descriptions-item>
        <el-descriptions-item label="税额">¥{{ parseFloat(currentContract.tax_amount || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="含税总额">
          <span style="color: #f56c6c; font-weight: bold;">¥{{ parseFloat(currentContract.total_with_tax || 0).toFixed(2) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="甲方签署人">{{ currentContract.buyer_signer || '-' }}</el-descriptions-item>
        <el-descriptions-item label="乙方签署人">{{ currentContract.seller_signer || '-' }}</el-descriptions-item>
      </el-descriptions>
      
      <el-divider content-position="left">合同条款</el-divider>
      <el-descriptions :column="1" border v-if="currentContract">
        <el-descriptions-item label="付款条款">{{ currentContract.payment_terms || '-' }}</el-descriptions-item>
        <el-descriptions-item label="交货条款">{{ currentContract.delivery_terms || '-' }}</el-descriptions-item>
        <el-descriptions-item label="质量条款">{{ currentContract.quality_terms || '-' }}</el-descriptions-item>
        <el-descriptions-item label="质保条款">{{ currentContract.warranty_terms || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ currentContract.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
      
      <el-divider content-position="left">订单明细</el-divider>
      <el-table :data="currentContract?.so_lines || []" border size="small">
        <el-table-column prop="item_sku" label="物料编码" width="120" />
        <el-table-column prop="item_name" label="产品名称" min-width="150" />
        <el-table-column prop="item_spec" label="规格型号" width="120" />
        <el-table-column prop="item_unit" label="单位" width="60" />
        <el-table-column prop="qty" label="数量" width="80" align="right" />
        <el-table-column prop="unit_price" label="单价" width="100" align="right">
          <template #default="{ row }">¥{{ parseFloat(row.unit_price || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="line_amount" label="金额" width="120" align="right">
          <template #default="{ row }">¥{{ parseFloat(row.line_amount || 0).toFixed(2) }}</template>
        </el-table-column>
      </el-table>
      
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
    
    <!-- 签署合同对话框 -->
    <el-dialog v-model="signDialogVisible" title="签署合同" width="500px">
      <el-form :model="signForm" :rules="signRules" ref="signFormRef" label-width="100px">
        <el-form-item label="甲方签署人" prop="buyer_signer">
          <el-input v-model="signForm.buyer_signer" placeholder="输入甲方签署人姓名" />
        </el-form-item>
        <el-form-item label="乙方签署人" prop="seller_signer">
          <el-input v-model="signForm.seller_signer" placeholder="输入乙方签署人姓名" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="signDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSignSubmit" :loading="signing">确认签署</el-button>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getSalesContracts, getSalesContract, createContractFromSO, patchSalesContract, submitSalesContract, approveSalesContract, signSalesContract, printPreviewContract, getOrdersForLinking } from '@/api/sales'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'
import { getCustomerList } from '@/api/masterdata'

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/sales/contracts/',
  { onSuccess: () => loadContracts(), confirmTitle: '删除合同', confirmMessage: '确定要删除该合同吗？' }
)

const workflowDialogVisible = ref(false)
const workflowBusinessId = ref(null)
const workflowBusinessType = 'SALES_CONTRACT'

const showWorkflowProgress = (row) => {
  workflowBusinessId.value = row.id
  workflowDialogVisible.value = true
}

const loading = ref(false)
const saving = ref(false)
const creating = ref(false)
const signing = ref(false)
const searchingOrders = ref(false)
const contracts = ref([])
const customers = ref([])
const salesOrders = ref([])
const currentContract = ref(null)

const createDialogVisible = ref(false)
const editDialogVisible = ref(false)
const viewDialogVisible = ref(false)
const signDialogVisible = ref(false)
const dialogTitle = ref('编辑合同')
const formRef = ref(null)
const createFormRef = ref(null)
const signFormRef = ref(null)

const searchForm = reactive({
  customer: null,
  status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const createForm = reactive({
  so_id: null
})

const createRules = {
  so_id: [{ required: true, message: '请选择销售订单', trigger: 'change' }]
}

const form = reactive({
  id: null,
  title: '',
  contract_date: '',
  effective_date: '',
  expiry_date: '',
  payment_terms: '',
  delivery_terms: '',
  quality_terms: '',
  warranty_terms: '',
  notes: ''
})

const rules = {
  title: [{ required: true, message: '请输入合同标题', trigger: 'blur' }],
  contract_date: [{ required: true, message: '请选择合同日期', trigger: 'change' }]
}

const signForm = reactive({
  buyer_signer: '',
  seller_signer: ''
})

const signRules = {
  buyer_signer: [{ required: true, message: '请输入甲方签署人', trigger: 'blur' }],
  seller_signer: [{ required: true, message: '请输入乙方签署人', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const types = { 
    DRAFT: 'info', 
    PENDING: 'warning',
    APPROVED: 'success',
    REJECTED: 'danger',
    SIGNED: 'success',
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
    SIGNED: '已签署',
    COMPLETED: '已完成', 
    CANCELLED: '已取消' 
  }
  return labels[status] || status
}

const loadContracts = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.customer) params.customer = searchForm.customer
    if (searchForm.status) params.status = searchForm.status
    
    const res = await getSalesContracts(params)
    contracts.value = res.data?.results || res.results || res.data || []
    pagination.total = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载销售合同失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const res = await getCustomerList()
    customers.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载客户失败:', error)
  }
}

const searchOrders = async (query) => {
  if (query) {
    searchingOrders.value = true
    try {
      const res = await getOrdersForLinking({ search: query })
      salesOrders.value = res.data || res || []
    } catch (error) {
      console.error('搜索订单失败:', error)
    } finally {
      searchingOrders.value = false
    }
  } else {
    salesOrders.value = []
  }
}

const resetSearch = () => {
  searchForm.customer = null
  searchForm.status = null
  pagination.page = 1
  loadContracts()
}

const handleCreate = () => {
  createForm.so_id = null
  salesOrders.value = []
  createDialogVisible.value = true
}

const handleCreateFromSO = async () => {
  try {
    await createFormRef.value?.validate()
    creating.value = true
    
    const res = await createContractFromSO({ so_id: createForm.so_id })
    
    ElMessage.success('合同创建成功')
    createDialogVisible.value = false
    loadContracts()
    
    // 打开编辑对话框
    const contract = res.data || res
    handleEdit(contract)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '创建合同失败')
    }
  } finally {
    creating.value = false
  }
}

const handleView = async (row) => {
  try {
    const res = await getSalesContract(row.id)
    currentContract.value = res.data || res
    viewDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取合同详情失败')
  }
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑合同'
  
  try {
    const res = await getSalesContract(row.id)
    const data = res.data || res
    
    Object.assign(form, {
      id: data.id,
      title: data.title || '',
      contract_date: data.contract_date || '',
      effective_date: data.effective_date || '',
      expiry_date: data.expiry_date || '',
      payment_terms: data.payment_terms || '',
      delivery_terms: data.delivery_terms || '',
      quality_terms: data.quality_terms || '',
      warranty_terms: data.warranty_terms || '',
      notes: data.notes || ''
    })
    
    editDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取合同详情失败')
  }
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    
    await patchSalesContract(form.id, {
      title: form.title,
      contract_date: form.contract_date,
      effective_date: form.effective_date || null,
      expiry_date: form.expiry_date || null,
      payment_terms: form.payment_terms,
      delivery_terms: form.delivery_terms,
      quality_terms: form.quality_terms,
      warranty_terms: form.warranty_terms,
      notes: form.notes
    })
    
    ElMessage.success('合同保存成功')
    editDialogVisible.value = false
    loadContracts()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('保存合同失败')
    }
  } finally {
    saving.value = false
  }
}

const handleSubmitApproval = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交该合同进行审批吗？', '提交审批', { type: 'warning' })
    const response = await submitSalesContract(row.id)
    const data = response.data || response
    if (data.workflow_started) {
      ElMessage.success(data.message || '已提交审批')
    } else {
      ElMessage.success(data.message || '操作成功')
    }
    loadContracts()
  } catch (error) {
    if (error !== 'cancel') {
      const msg = error.response?.data?.error || '提交失败'
      ElMessage.error(msg)
    }
  }
}

const handleApprove = async (row) => {
  try {
    await ElMessageBox.confirm('确定要审批通过该合同吗？', '审批合同', { type: 'warning' })
    await approveSalesContract(row.id)
    ElMessage.success('合同已审批')
    loadContracts()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('审批合同失败')
    }
  }
}

const handleSign = (row) => {
  currentContract.value = row
  signForm.buyer_signer = ''
  signForm.seller_signer = ''
  signDialogVisible.value = true
}

const handleSignSubmit = async () => {
  try {
    await signFormRef.value?.validate()
    signing.value = true
    
    await signSalesContract(currentContract.value.id, {
      buyer_signer: signForm.buyer_signer,
      seller_signer: signForm.seller_signer
    })
    
    ElMessage.success('合同已签署')
    signDialogVisible.value = false
    loadContracts()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('签署合同失败')
    }
  } finally {
    signing.value = false
  }
}

const handlePrint = async (row) => {
  try {
    const res = await printPreviewContract(row.id)
    const data = res.data || res
    
    // 创建打印窗口
    const printWindow = window.open('', '_blank')
    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>销售合同 - ${data.contract.contract_no}</title>
        <style>
          body { font-family: SimSun, serif; margin: 40px; }
          .header { text-align: center; margin-bottom: 30px; }
          .header h1 { font-size: 24px; margin-bottom: 10px; }
          .header .contract-no { font-size: 14px; color: #666; }
          .section { margin-bottom: 20px; }
          .section-title { font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #ccc; padding-bottom: 5px; }
          .row { display: flex; margin-bottom: 8px; }
          .row .label { width: 100px; color: #666; }
          .row .value { flex: 1; }
          table { width: 100%; border-collapse: collapse; margin: 15px 0; }
          th, td { border: 1px solid #333; padding: 8px; text-align: left; }
          th { background: #f5f5f5; }
          .amount { text-align: right; }
          .total { font-weight: bold; font-size: 16px; color: #c00; }
          .signature { display: flex; justify-content: space-between; margin-top: 50px; }
          .signature .party { width: 45%; }
          .signature .party-title { font-weight: bold; margin-bottom: 20px; }
          .signature .sign-line { border-bottom: 1px solid #333; height: 30px; margin-bottom: 10px; }
          @media print { body { margin: 20px; } }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>销 售 合 同</h1>
          <div class="contract-no">合同编号：${data.contract.contract_no}</div>
        </div>
        
        <div class="section">
          <div class="section-title">甲方（买方）</div>
          <div class="row"><span class="label">单位名称：</span><span class="value">${data.customer.name}</span></div>
          <div class="row"><span class="label">地址：</span><span class="value">${data.customer.address || ''}</span></div>
          <div class="row"><span class="label">联系人：</span><span class="value">${data.customer.contact || ''}</span></div>
          <div class="row"><span class="label">电话：</span><span class="value">${data.customer.phone || ''}</span></div>
        </div>
        
        <div class="section">
          <div class="section-title">乙方（卖方）</div>
          <div class="row"><span class="label">单位名称：</span><span class="value">${data.company.name || ''}</span></div>
          <div class="row"><span class="label">地址：</span><span class="value">${data.company.address || ''}</span></div>
          <div class="row"><span class="label">电话：</span><span class="value">${data.company.phone || ''}</span></div>
        </div>
        
        <div class="section">
          <div class="section-title">产品明细</div>
          <table>
            <thead>
              <tr>
                <th>序号</th>
                <th>产品名称</th>
                <th>规格型号</th>
                <th>单位</th>
                <th>数量</th>
                <th>单价</th>
                <th>金额</th>
              </tr>
            </thead>
            <tbody>
              ${data.lines.map((line, idx) => `
                <tr>
                  <td>${idx + 1}</td>
                  <td>${line.item_name}</td>
                  <td>${line.specification || ''}</td>
                  <td>${line.unit}</td>
                  <td class="amount">${line.qty}</td>
                  <td class="amount">¥${line.unit_price.toFixed(2)}</td>
                  <td class="amount">¥${line.line_amount.toFixed(2)}</td>
                </tr>
              `).join('')}
              <tr>
                <td colspan="6" class="amount"><strong>不含税金额</strong></td>
                <td class="amount">¥${parseFloat(data.contract.total_amount || 0).toFixed(2)}</td>
              </tr>
              <tr>
                <td colspan="6" class="amount"><strong>税额（${data.contract.tax_rate}%）</strong></td>
                <td class="amount">¥${parseFloat(data.contract.tax_amount || 0).toFixed(2)}</td>
              </tr>
              <tr>
                <td colspan="6" class="amount"><strong>含税总额</strong></td>
                <td class="amount total">¥${parseFloat(data.contract.total_with_tax || 0).toFixed(2)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        
        <div class="section">
          <div class="section-title">合同条款</div>
          <p><strong>付款条款：</strong>${data.contract.payment_terms || '-'}</p>
          <p><strong>交货条款：</strong>${data.contract.delivery_terms || '-'}</p>
          <p><strong>质量条款：</strong>${data.contract.quality_terms || '-'}</p>
          <p><strong>质保条款：</strong>${data.contract.warranty_terms || '-'}</p>
        </div>
        
        <div class="signature">
          <div class="party">
            <div class="party-title">甲方（盖章）</div>
            <div class="sign-line"></div>
            <div>授权代表：${data.contract.buyer_signer || '____________'}</div>
            <div>日期：${data.contract.signed_date || '____________'}</div>
          </div>
          <div class="party">
            <div class="party-title">乙方（盖章）</div>
            <div class="sign-line"></div>
            <div>授权代表：${data.contract.seller_signer || '____________'}</div>
            <div>日期：${data.contract.signed_date || '____________'}</div>
          </div>
        </div>
      </body>
      </html>
    `)
    printWindow.document.close()
    printWindow.focus()
    
    setTimeout(() => {
      printWindow.print()
    }, 500)
  } catch (error) {
    ElMessage.error('获取打印数据失败')
  }
}

// handleDelete 已被 useBatchDelete 的 deleteRow 替代

onMounted(() => {
  loadContracts()
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
</style>

