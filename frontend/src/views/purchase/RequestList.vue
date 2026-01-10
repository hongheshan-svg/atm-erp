<template>
  <div class="purchase-request-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>采购申请</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            创建申请
          </el-button>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="项目">
          <el-select 
            v-model="searchForm.project" 
            placeholder="选择项目" 
            clearable 
            filterable
            style="width: 250px;"
            @change="loadRequests"
          >
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select 
            v-model="searchForm.status" 
            placeholder="选择状态" 
            clearable 
            style="width: 120px;"
            @change="loadRequests"
          >
            <el-option label="全部" :value="null" />
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已提交" value="SUBMITTED" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已拒绝" value="REJECTED" />
            <el-option label="已转订单" value="CONVERTED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadRequests">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetSearch">
            <el-icon><RefreshLeft /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
      
      <!-- 过滤提示 -->
      <el-alert
        v-if="searchForm.project || searchForm.status"
        :title="getFilterTip()"
        type="info"
        :closable="false"
        style="margin-bottom: 15px;"
      />

      <el-table :data="requests" v-loading="loading" stripe border>
        <el-table-column prop="request_no" label="采购申请号" width="150" />
        <el-table-column prop="project_name" label="项目" />
        <el-table-column prop="supplier_name" label="供应商" />
        <el-table-column prop="requestor_name" label="申请人" width="100" />
        <el-table-column prop="required_date" label="需求日期" width="110" />
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
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="420" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="warning" @click="handleSubmit(row)" v-if="row.status === 'DRAFT'">提交</el-button>
            <el-button size="small" type="success" @click="handleApprove(row)" v-if="row.status === 'SUBMITTED'">批准</el-button>
            <el-button size="small" type="danger" @click="handleReject(row)" v-if="row.status === 'SUBMITTED'">拒绝</el-button>
            <el-button size="small" type="info" @click="handleWithdraw(row)" v-if="row.status === 'SUBMITTED' || row.status === 'APPROVED'">撤回</el-button>
            <el-button size="small" type="primary" @click="convertToPO(row)" v-if="row.status === 'APPROVED'">转采购订单</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
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
        @size-change="loadRequests"
        @current-change="loadRequests"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="1100px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="关联项目" prop="project">
              <el-select v-model="form.project" placeholder="选择项目" filterable clearable style="width: 100%;">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="供应商">
              <el-select v-model="form.supplier" placeholder="选择供应商" filterable clearable style="width: 100%;">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="需求日期" prop="required_date">
              <el-date-picker v-model="form.required_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
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
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="请输入备注" />
        </el-form-item>
        
        <!-- 申请明细 -->
        <el-divider content-position="left">申请明细</el-divider>
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
          <el-table-column label="数量" width="90">
            <template #default="{ row }">
              <el-input-number v-model="row.qty" :min="0.01" :precision="2" size="small" controls-position="right" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="单位" width="60" align="center">
            <template #default="{ row }">
              {{ getItemUnit(row.item) }}
            </template>
          </el-table-column>
          <el-table-column label="单价" width="100">
            <template #default="{ row }">
              <el-input-number v-model="row.estimated_price" :min="0" :precision="2" size="small" controls-position="right" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="金额" width="90" align="right">
            <template #default="{ row }">
              ¥{{ getLineAmount(row).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="税额" width="80" align="right">
            <template #default="{ row }">
              ¥{{ getLineTax(row).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="含税价" width="90" align="right">
            <template #default="{ row }">
              ¥{{ getLineTotalWithTax(row).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="交期" width="130">
            <template #default="{ row }">
              <el-date-picker v-model="row.required_date" type="date" value-format="YYYY-MM-DD" placeholder="交期" size="small" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="120">
            <template #default="{ row }">
              <el-input v-model="row.notes" placeholder="备注" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="50" align="center" fixed="right">
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
    
    <!-- 查看详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="采购申请详情" width="900px">
      <el-descriptions :column="3" border v-if="currentRequest">
        <el-descriptions-item label="申请单号">{{ currentRequest.request_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentRequest.status)">{{ getStatusLabel(currentRequest.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="申请人">{{ currentRequest.requestor_name }}</el-descriptions-item>
        <el-descriptions-item label="关联项目">{{ currentRequest.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ currentRequest.supplier_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="需求日期">{{ currentRequest.required_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="不含税金额">¥{{ parseFloat(currentRequest.total_amount || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="税额">¥{{ parseFloat(currentRequest.tax_amount || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="含税总额">¥{{ parseFloat(currentRequest.total_with_tax || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="3">{{ currentRequest.created_at }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">{{ currentRequest.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
      
      <el-divider content-position="left">申请明细</el-divider>
      <el-table :data="currentRequest?.lines || []" border size="small">
        <el-table-column prop="item_name" label="物料" min-width="150" />
        <el-table-column prop="qty" label="数量" width="70" align="right" />
        <el-table-column prop="item_unit" label="单位" width="60" align="center" />
        <el-table-column label="单价" width="90" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.estimated_price || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="金额" width="90" align="right">
          <template #default="{ row }">
            ¥{{ ((row.qty || 0) * (row.estimated_price || 0)).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="税额" width="80" align="right">
          <template #default="{ row }">
            ¥{{ (((row.qty || 0) * (row.estimated_price || 0)) * (currentRequest?.tax_rate || 0) / 100).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="含税价" width="90" align="right">
          <template #default="{ row }">
            ¥{{ (((row.qty || 0) * (row.estimated_price || 0)) * (1 + (currentRequest?.tax_rate || 0) / 100)).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="required_date" label="交期" width="100" />
        <el-table-column prop="notes" label="备注" min-width="100" />
      </el-table>
    </el-dialog>
    
    <!-- 转采购订单对话框 -->
    <el-dialog v-model="convertDialogVisible" title="转换为采购订单" width="500px">
      <el-form :model="convertForm" label-width="100px">
        <el-form-item label="选择供应商" required>
          <el-select v-model="convertForm.supplier" placeholder="请选择供应商" filterable style="width: 100%;">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="convertDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doConvertToPO" :loading="converting">确定转换</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Search, RefreshLeft } from '@element-plus/icons-vue'
import request from '@/utils/request'

const route = useRoute()

const loading = ref(false)
const saving = ref(false)
const converting = ref(false)
const requests = ref([])
const projects = ref([])
const items = ref([])
const suppliers = ref([])
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const convertDialogVisible = ref(false)
const dialogTitle = ref('创建采购申请')
const isEdit = ref(false)
const formRef = ref(null)
const currentRequest = ref(null)
const currentConvertId = ref(null)

const searchForm = reactive({
  project: null,
  status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  project: null,
  supplier: null,
  required_date: '',
  tax_rate: 13,
  notes: '',
  lines: []
})

const convertForm = reactive({
  supplier: null
})

const rules = {
  required_date: [{ required: true, message: '请选择需求日期', trigger: 'change' }]
}

const getStatusType = (status) => {
  const types = { 
    DRAFT: 'info', 
    SUBMITTED: 'warning', 
    PENDING: 'warning',
    APPROVED: 'success', 
    REJECTED: 'danger', 
    CONVERTED: '' 
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = { 
    DRAFT: '草稿', 
    SUBMITTED: '已提交', 
    PENDING: '审批中',
    APPROVED: '已批准', 
    REJECTED: '已拒绝', 
    CONVERTED: '已转订单' 
  }
  return labels[status] || status
}

const loadRequests = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.project) params.project = searchForm.project
    if (searchForm.status) params.status = searchForm.status
    
    const res = await request.get('/purchase/requests/', { params })
    requests.value = res.data?.results || res.results || res.data || []
    pagination.total = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载采购申请失败')
  } finally {
    loading.value = false
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

const loadSuppliers = async () => {
  try {
    const res = await request.get('/masterdata/suppliers/')
    suppliers.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载供应商失败:', error)
  }
}

const resetSearch = () => {
  searchForm.project = null
  searchForm.status = null
  pagination.page = 1
  loadRequests()
}

// 获取过滤提示文本
const getFilterTip = () => {
  const tips = []
  if (searchForm.project) {
    const proj = projects.value.find(p => p.id === searchForm.project)
    if (proj) {
      tips.push(`项目: ${proj.name}`)
    }
  }
  if (searchForm.status) {
    const statusMap = {
      DRAFT: '草稿',
      SUBMITTED: '已提交',
      APPROVED: '已批准',
      REJECTED: '已拒绝',
      CONVERTED: '已转订单'
    }
    tips.push(`状态: ${statusMap[searchForm.status]}`)
  }
  return `当前过滤条件：${tips.join(' | ')} （共 ${pagination.total} 条记录）`
}

const handleAdd = () => {
  dialogTitle.value = '创建采购申请'
  isEdit.value = false
  Object.assign(form, {
    id: null,
    project: null,
    supplier: null,
    required_date: '',
    tax_rate: 13,
    notes: '',
    lines: [{ item: null, qty: 1, estimated_price: 0, required_date: '', notes: '' }]
  })
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑采购申请'
  isEdit.value = true
  
  try {
    // 获取详情包括明细
    const res = await request.get(`/purchase/requests/${row.id}/`)
    const data = res.data || res
    
    Object.assign(form, {
      id: data.id,
      project: data.project,
      supplier: data.supplier,
      required_date: data.required_date || '',
      tax_rate: data.tax_rate ?? 13,
      notes: data.notes || '',
      lines: (data.lines || []).map(line => ({
        id: line.id,
        item: line.item,
        qty: line.qty,
        estimated_price: parseFloat(line.estimated_price || 0),
        required_date: line.required_date || '',
        notes: line.notes || ''
      }))
    })
    
    if (form.lines.length === 0) {
      form.lines = [{ item: null, qty: 1, estimated_price: 0, required_date: '', notes: '' }]
    }
    
    dialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取采购申请详情失败')
  }
}

const handleView = async (row) => {
  try {
    const res = await request.get(`/purchase/requests/${row.id}/`)
    currentRequest.value = res.data || res
    viewDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取采购申请详情失败')
  }
}

const addLine = () => {
  form.lines.push({ item: null, qty: 1, estimated_price: 0, required_date: '', notes: '' })
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
    line.estimated_price = parseFloat(item.purchase_price || item.standard_cost || 0)
  }
}

// 获取物料单位
const getItemUnit = (itemId) => {
  if (!itemId) return '-'
  const item = items.value.find(i => i.id === itemId)
  return item?.unit_display || item?.unit || '-'
}

// 计算行金额（不含税）
const getLineAmount = (row) => {
  return (row.qty || 0) * (row.estimated_price || 0)
}

// 计算行税额
const getLineTax = (row) => {
  return getLineAmount(row) * (form.tax_rate || 0) / 100
}

// 计算行含税价
const getLineTotalWithTax = (row) => {
  return getLineAmount(row) + getLineTax(row)
}

const calculateTotal = () => {
  return form.lines.reduce((sum, line) => {
    return sum + getLineAmount(line)
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
    
    // 验证明细
    const validLines = form.lines.filter(line => line.item && line.qty > 0)
    if (validLines.length === 0) {
      ElMessage.warning('请至少添加一行有效的物料明细')
      return
    }
    
    saving.value = true
    
    const payload = {
      project: form.project,
      supplier: form.supplier,
      required_date: form.required_date,
      tax_rate: form.tax_rate,
      notes: form.notes,
      lines: validLines.map(line => ({
        item: line.item,
        qty: line.qty,
        estimated_price: line.estimated_price,
        required_date: line.required_date || null,
        notes: line.notes || ''
      }))
    }
    
    if (isEdit.value) {
      await request.put(`/purchase/requests/${form.id}/`, payload)
      ElMessage.success('更新采购申请成功')
    } else {
      await request.post('/purchase/requests/', payload)
      ElMessage.success('创建采购申请成功')
    }
    
    dialogVisible.value = false
    loadRequests()
  } catch (error) {
    console.error('保存失败详情:', error.response?.data || error)
    const errData = error.response?.data
    let errMsg = '保存采购申请失败'
    if (errData) {
      if (errData.required_date) errMsg = '请选择需求日期'
      else if (errData.detail) errMsg = errData.detail
      else if (typeof errData === 'object') errMsg = JSON.stringify(errData)
    }
    ElMessage.error(errMsg)
  } finally {
    saving.value = false
  }
}

const handleSubmit = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交该采购申请吗？提交后将进入审批流程。', '提交确认', { type: 'warning' })
    await request.post(`/purchase/requests/${row.id}/submit/`)
    ElMessage.success('提交成功')
    loadRequests()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('提交失败')
    }
  }
}

const handleApprove = async (row) => {
  try {
    await ElMessageBox.confirm('确定要批准该采购申请吗？', '批准确认', { type: 'warning' })
    await request.post(`/purchase/requests/${row.id}/approve/`)
    ElMessage.success('批准成功')
    loadRequests()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('批准失败')
    }
  }
}

const handleReject = async (row) => {
  try {
    await ElMessageBox.confirm('确定要拒绝该采购申请吗？', '拒绝确认', { type: 'warning' })
    await request.post(`/purchase/requests/${row.id}/reject/`)
    ElMessage.success('已拒绝')
    loadRequests()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const handleWithdraw = async (row) => {
  try {
    await ElMessageBox.confirm('确定要撤回该采购申请吗？撤回后将恢复为草稿状态。', '撤回确认', { type: 'warning' })
    await request.post(`/purchase/requests/${row.id}/withdraw/`)
    ElMessage.success('已撤回')
    loadRequests()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '撤回失败')
    }
  }
}

const convertToPO = (row) => {
  currentConvertId.value = row.id
  // 预填充采购申请中的供应商
  convertForm.supplier = row.supplier || null
  convertDialogVisible.value = true
}

const doConvertToPO = async () => {
  if (!convertForm.supplier) {
    ElMessage.warning('请选择供应商')
    return
  }
  
  converting.value = true
  try {
    await request.post(`/purchase/requests/${currentConvertId.value}/convert_to_po/`, {
      supplier: convertForm.supplier
    })
    ElMessage.success('成功转换为采购订单')
    convertDialogVisible.value = false
    loadRequests()
  } catch (error) {
    ElMessage.error('转换为采购订单失败')
  } finally {
    converting.value = false
  }
}

// 处理从BOM页面传递过来的数据
const handleBomData = () => {
  if (route.query.from_bom === '1') {
    const bomData = sessionStorage.getItem('bom_to_pr')
    if (bomData) {
      try {
        const data = JSON.parse(bomData)
        sessionStorage.removeItem('bom_to_pr') // 清除已使用的数据
        
        // 预填充表单
        dialogTitle.value = '创建采购申请（来自BOM）'
        isEdit.value = false
        Object.assign(form, {
          id: null,
          project: data.project,
          required_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 默认7天后
          tax_rate: 13,
          notes: `根据项目 ${data.projectName} 的BOM清单生成`,
          lines: data.lines.map(line => ({
            item: line.item,
            qty: line.qty,
            estimated_price: line.estimated_price || 0
          }))
        })
        dialogVisible.value = true
        
        ElMessage.success(`已导入 ${data.lines.length} 种物料，请确认后保存`)
      } catch (e) {
        console.error('解析BOM数据失败:', e)
      }
    }
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除采购申请 ${row.request_no} 吗？此操作不可恢复！`, 
      '删除申请', 
      { type: 'warning' }
    )
    await request.delete(`/purchase/requests/${row.id}/`)
    ElMessage.success('采购申请已删除')
    loadRequests()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除采购申请失败')
    }
  }
}

onMounted(async () => {
  // 首先加载项目和其他数据
  await Promise.all([
    loadProjects(),
    loadItems(),
    loadSuppliers()
  ])
  
  // 检查URL参数中是否有项目过滤
  if (route.query.project) {
    const projectId = parseInt(route.query.project)
    if (!isNaN(projectId)) {
      searchForm.project = projectId
    }
  }
  
  // 加载采购申请列表
  loadRequests()
  
  // 延迟处理BOM数据，确保其他数据加载完成
  setTimeout(() => {
    handleBomData()
  }, 300)
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
