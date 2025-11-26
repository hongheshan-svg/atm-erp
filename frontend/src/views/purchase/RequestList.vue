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
          <el-select v-model="searchForm.project" placeholder="选择项目" clearable style="width: 200px;">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 120px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已提交" value="SUBMITTED" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已拒绝" value="REJECTED" />
            <el-option label="已转订单" value="CONVERTED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadRequests">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="requests" v-loading="loading" stripe border>
        <el-table-column prop="request_no" label="采购申请号" width="150" />
        <el-table-column prop="project_name" label="项目" />
        <el-table-column prop="requestor_name" label="申请人" />
        <el-table-column prop="required_date" label="需求日期" width="120" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_amount" label="金额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.total_amount || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="warning" @click="handleSubmit(row)" v-if="row.status === 'DRAFT'">提交</el-button>
            <el-button size="small" type="success" @click="handleApprove(row)" v-if="row.status === 'SUBMITTED'">批准</el-button>
            <el-button size="small" type="danger" @click="handleReject(row)" v-if="row.status === 'SUBMITTED'">拒绝</el-button>
            <el-button size="small" type="primary" @click="convertToPO(row)" v-if="row.status === 'APPROVED'">转采购订单</el-button>
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
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="关联项目" prop="project">
              <el-select v-model="form.project" placeholder="选择项目" filterable style="width: 100%;">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="需求日期" prop="required_date">
              <el-date-picker v-model="form.required_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%;" />
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
          <el-table-column label="数量" width="120">
            <template #default="{ row }">
              <el-input-number v-model="row.qty" :min="1" :precision="0" size="small" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="预估单价" width="120">
            <template #default="{ row }">
              <el-input-number v-model="row.estimated_price" :min="0" :precision="2" size="small" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="小计" width="120" align="right">
            <template #default="{ row }">
              ¥{{ ((row.qty || 0) * (row.estimated_price || 0)).toFixed(2) }}
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
    
    <!-- 查看详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="采购申请详情" width="800px">
      <el-descriptions :column="2" border v-if="currentRequest">
        <el-descriptions-item label="申请单号">{{ currentRequest.request_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentRequest.status)">{{ getStatusLabel(currentRequest.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="关联项目">{{ currentRequest.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="申请人">{{ currentRequest.requestor_name }}</el-descriptions-item>
        <el-descriptions-item label="需求日期">{{ currentRequest.required_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="总金额">¥{{ parseFloat(currentRequest.total_amount || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ currentRequest.created_at }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentRequest.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
      
      <el-divider content-position="left">申请明细</el-divider>
      <el-table :data="currentRequest?.lines || []" border size="small">
        <el-table-column prop="item_name" label="物料" />
        <el-table-column prop="qty" label="数量" width="100" align="right" />
        <el-table-column label="预估单价" width="120" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.estimated_price || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="小计" width="120" align="right">
          <template #default="{ row }">
            ¥{{ ((row.qty || 0) * (row.estimated_price || 0)).toFixed(2) }}
          </template>
        </el-table-column>
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import request from '@/utils/request'

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
  required_date: '',
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

const handleAdd = () => {
  dialogTitle.value = '创建采购申请'
  isEdit.value = false
  Object.assign(form, {
    id: null,
    project: null,
    required_date: '',
    notes: '',
    lines: [{ item: null, qty: 1, estimated_price: 0 }]
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
      required_date: data.required_date || '',
      notes: data.notes || '',
      lines: (data.lines || []).map(line => ({
        id: line.id,
        item: line.item,
        qty: line.qty,
        estimated_price: parseFloat(line.estimated_price || 0)
      }))
    })
    
    if (form.lines.length === 0) {
      form.lines = [{ item: null, qty: 1, estimated_price: 0 }]
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
  form.lines.push({ item: null, qty: 1, estimated_price: 0 })
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
    line.estimated_price = parseFloat(item.standard_cost || 0)
  }
}

const calculateTotal = () => {
  return form.lines.reduce((sum, line) => {
    return sum + (line.qty || 0) * (line.estimated_price || 0)
  }, 0)
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
      required_date: form.required_date,
      notes: form.notes,
      lines: validLines.map(line => ({
        item: line.item,
        qty: line.qty,
        estimated_price: line.estimated_price
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
    if (error !== 'cancel') {
      ElMessage.error('保存采购申请失败')
      console.error(error)
    }
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

const convertToPO = (row) => {
  currentConvertId.value = row.id
  convertForm.supplier = null
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

onMounted(() => {
  loadRequests()
  loadProjects()
  loadItems()
  loadSuppliers()
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
