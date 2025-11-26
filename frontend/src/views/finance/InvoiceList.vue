<template>
  <div class="invoice-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>发票管理</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            登记发票
          </el-button>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="发票类型">
          <el-select v-model="searchForm.invoice_type" placeholder="请选择类型" clearable>
            <el-option label="进项发票" value="INPUT" />
            <el-option label="销项发票" value="OUTPUT" />
          </el-select>
        </el-form-item>
        <el-form-item label="发票号">
          <el-input v-model="searchForm.invoice_no" placeholder="请输入发票号" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择状态" clearable>
            <el-option label="已登记" value="REGISTERED" />
            <el-option label="已认证" value="CERTIFIED" />
            <el-option label="已作废" value="VOID" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadInvoices">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="invoices" v-loading="loading" border stripe>
        <el-table-column prop="invoice_no" label="发票号" width="180" />
        <el-table-column prop="invoice_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.invoice_type === 'INPUT' ? 'success' : 'primary'">
              {{ row.invoice_type === 'INPUT' ? '进项' : '销项' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="invoice_date" label="开票日期" width="120" />
        <el-table-column prop="party_name" label="对方单位" width="200" />
        <el-table-column prop="tax_amount" label="税额" width="120" align="right">
          <template #default="{ row }">¥{{ (row.tax_amount || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="total_amount" label="价税合计" width="130" align="right">
          <template #default="{ row }">¥{{ (row.total_amount || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reference_type" label="关联单据" width="120" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" @click="handleEdit(row)" v-if="row.status === 'REGISTERED'">编辑</el-button>
            <el-button size="small" type="success" @click="handleCertify(row)" v-if="row.status === 'REGISTERED' && row.invoice_type === 'INPUT'">
              认证
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadInvoices"
        @current-change="loadInvoices"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 登记/编辑发票对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="发票类型" prop="invoice_type">
          <el-radio-group v-model="formData.invoice_type">
            <el-radio label="INPUT">进项发票</el-radio>
            <el-radio label="OUTPUT">销项发票</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="发票号" prop="invoice_no">
          <el-input v-model="formData.invoice_no" placeholder="请输入发票号" />
        </el-form-item>
        <el-form-item label="开票日期" prop="invoice_date">
          <el-date-picker v-model="formData.invoice_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="对方单位" prop="party_name">
          <el-input v-model="formData.party_name" placeholder="请输入对方单位名称" />
        </el-form-item>
        <el-form-item label="税号" prop="tax_number">
          <el-input v-model="formData.tax_number" placeholder="请输入税号" />
        </el-form-item>
        <el-form-item label="金额（不含税）" prop="amount_before_tax">
          <el-input-number v-model="formData.amount_before_tax" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="税额" prop="tax_amount">
          <el-input-number v-model="formData.tax_amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="价税合计">
          <span style="font-size: 18px; font-weight: 600; color: #409EFF;">
            ¥{{ ((formData.amount_before_tax || 0) + (formData.tax_amount || 0)).toFixed(2) }}
          </span>
        </el-form-item>
        <el-form-item label="关联单据类型">
          <el-select v-model="formData.reference_type" placeholder="请选择" clearable>
            <el-option label="销售订单" value="SALES_ORDER" />
            <el-option label="采购订单" value="PURCHASE_ORDER" />
            <el-option label="费用报销" value="EXPENSE" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 发票详情对话框 -->
    <el-dialog v-model="detailVisible" title="发票详情" width="600px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="发票号">{{ currentInvoice.invoice_no }}</el-descriptions-item>
        <el-descriptions-item label="类型">
          <el-tag :type="currentInvoice.invoice_type === 'INPUT' ? 'success' : 'primary'">
            {{ currentInvoice.invoice_type === 'INPUT' ? '进项' : '销项' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="开票日期">{{ currentInvoice.invoice_date }}</el-descriptions-item>
        <el-descriptions-item label="对方单位">{{ currentInvoice.party_name }}</el-descriptions-item>
        <el-descriptions-item label="税号" :span="2">{{ currentInvoice.tax_number }}</el-descriptions-item>
        <el-descriptions-item label="金额（不含税）">¥{{ (currentInvoice.amount_before_tax || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="税额">¥{{ (currentInvoice.tax_amount || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="价税合计" :span="2">
          <span style="font-size: 16px; font-weight: 600;">
            ¥{{ (currentInvoice.total_amount || 0).toFixed(2) }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="状态" :span="2">
          <el-tag :type="getStatusType(currentInvoice.status)">
            {{ getStatusLabel(currentInvoice.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="关联单据">{{ currentInvoice.reference_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建人">{{ currentInvoice.created_by_name }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentInvoice.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const invoices = ref([])
const dialogVisible = ref(false)
const detailVisible = ref(false)
const dialogTitle = ref('')
const formRef = ref(null)
const currentInvoice = ref({})
const isEdit = ref(false)
const currentId = ref(null)

const searchForm = reactive({
  invoice_type: null,
  invoice_no: '',
  status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const formData = reactive({
  invoice_type: 'INPUT',
  invoice_no: '',
  invoice_date: new Date().toISOString().split('T')[0],
  party_name: '',
  tax_number: '',
  amount_before_tax: 0,
  tax_amount: 0,
  reference_type: null,
  notes: ''
})

const rules = {
  invoice_type: [{ required: true, message: '请选择发票类型', trigger: 'change' }],
  invoice_no: [{ required: true, message: '请输入发票号', trigger: 'blur' }],
  invoice_date: [{ required: true, message: '请选择开票日期', trigger: 'change' }],
  party_name: [{ required: true, message: '请输入对方单位', trigger: 'blur' }],
  amount_before_tax: [{ required: true, message: '请输入金额', trigger: 'blur' }],
  tax_amount: [{ required: true, message: '请输入税额', trigger: 'blur' }]
}

const getStatusType = (s) => ({ 'REGISTERED': 'info', 'CERTIFIED': 'success', 'VOID': 'danger' }[s] || 'info')
const getStatusLabel = (s) => ({ 'REGISTERED': '已登记', 'CERTIFIED': '已认证', 'VOID': '已作废' }[s] || s)

const loadInvoices = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize, ...searchForm }
    Object.keys(params).forEach(k => { if (params[k] === '' || params[k] === null) delete params[k] })
    const { data } = await request.get('/finance/invoices/', { params })
    invoices.value = data.results || []
    pagination.total = data.count || 0
  } catch (error) {
    ElMessage.error('加载发票失败')
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.invoice_type = null
  searchForm.invoice_no = ''
  searchForm.status = null
  pagination.page = 1
  loadInvoices()
}

const handleCreate = () => {
  isEdit.value = false
  dialogTitle.value = '登记发票'
  resetForm()
  dialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const { data } = await request.get(`/finance/invoices/${row.id}/`)
    currentInvoice.value = data
    detailVisible.value = true
  } catch (error) {
    ElMessage.error('加载发票详情失败')
  }
}

const handleEdit = (row) => {
  isEdit.value = true
  currentId.value = row.id
  dialogTitle.value = '编辑发票'
  Object.assign(formData, {
    invoice_type: row.invoice_type,
    invoice_no: row.invoice_no,
    invoice_date: row.invoice_date,
    party_name: row.party_name,
    tax_number: row.tax_number,
    amount_before_tax: row.amount_before_tax,
    tax_amount: row.tax_amount,
    reference_type: row.reference_type,
    notes: row.notes || ''
  })
  dialogVisible.value = true
}

const handleCertify = async (row) => {
  try {
    await ElMessageBox.confirm('确定要认证此发票吗？', '提示', { type: 'warning' })
    await request.post(`/finance/invoices/${row.id}/certify/`)
    ElMessage.success('发票认证成功')
    loadInvoices()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('发票认证失败')
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      const payload = {
        ...formData,
        total_amount: (formData.amount_before_tax || 0) + (formData.tax_amount || 0)
      }
      if (isEdit.value) {
        await request.put(`/finance/invoices/${currentId.value}/`, payload)
        ElMessage.success('更新成功')
      } else {
        await request.post('/finance/invoices/', payload)
        ElMessage.success('登记成功')
      }
      dialogVisible.value = false
      loadInvoices()
    } catch (error) {
      ElMessage.error(isEdit.value ? '更新失败' : '登记失败')
    }
  })
}

const resetForm = () => {
  Object.assign(formData, {
    invoice_type: 'INPUT',
    invoice_no: '',
    invoice_date: new Date().toISOString().split('T')[0],
    party_name: '',
    tax_number: '',
    amount_before_tax: 0,
    tax_amount: 0,
    reference_type: null,
    notes: ''
  })
  currentId.value = null
  if (formRef.value) formRef.value.clearValidate()
}

onMounted(() => loadInvoices())
</script>

<style scoped>
.invoice-list { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.search-form { margin-bottom: 20px; }
</style>

