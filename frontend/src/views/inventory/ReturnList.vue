<template>
  <div class="return-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>生产退料管理</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon> 新建退料单
          </el-button>
        </div>
      </template>

      <!-- 搜索区域 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="退料类型">
          <el-select v-model="searchForm.return_type" placeholder="全部" clearable style="width: 120px;">
            <el-option label="项目退料" value="PROJECT" />
            <el-option label="售后退料" value="AFTERSALES" />
          </el-select>
        </el-form-item>
        <el-form-item label="退料原因">
          <el-select v-model="searchForm.return_reason" placeholder="全部" clearable style="width: 120px;">
            <el-option label="物料剩余" value="SURPLUS" />
            <el-option label="物料更换" value="REPLACEMENT" />
            <el-option label="物料报废" value="SCRAP" />
            <el-option label="物料不良" value="DEFECTIVE" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="待入库" value="PENDING" />
            <el-option label="检验中" value="INSPECTING" />
            <el-option label="已入库" value="COMPLETED" />
            <el-option label="部分入库" value="PARTIAL" />
            <el-option label="已拒绝" value="REJECTED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadList">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 列表 -->
      <el-table :data="list" v-loading="loading" stripe border>
        <el-table-column prop="return_no" label="退料单号" width="160" />
        <el-table-column prop="return_type_display" label="类型" width="100" />
        <el-table-column prop="return_reason_display" label="退料原因" width="100" />
        <el-table-column label="关联单据" min-width="150">
          <template #default="{ row }">
            <span v-if="row.project_name">{{ row.project_name }}</span>
            <span v-else-if="row.aftersales_order_no">{{ row.aftersales_order_no }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="warehouse_name" label="入库仓库" width="120" />
        <el-table-column prop="requestor_name" label="申请人" width="100" />
        <el-table-column prop="request_date" label="申请日期" width="110" />
        <el-table-column prop="line_count" label="物料数" width="80" align="center" />
        <el-table-column prop="status_display" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" type="primary" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="success" @click="handleSubmit(row)" v-if="row.status === 'DRAFT'">提交</el-button>
            <el-button size="small" type="warning" @click="handleInspect(row)" v-if="row.status === 'PENDING'">开始检验</el-button>
            <el-button size="small" type="primary" @click="handleReceive(row)" v-if="['PENDING', 'INSPECTING', 'PARTIAL'].includes(row.status)">入库</el-button>
            <el-button size="small" type="danger" @click="handleReject(row)" v-if="['PENDING', 'INSPECTING'].includes(row.status)">拒绝</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadList"
        @current-change="loadList"
        style="margin-top: 16px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px" destroy-on-close>
      <el-form :model="form" label-width="100px" :rules="formRules" ref="formRef">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="退料类型" prop="return_type">
              <el-radio-group v-model="form.return_type" @change="handleTypeChange">
                <el-radio value="PROJECT">项目退料</el-radio>
                <el-radio value="AFTERSALES">售后退料</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="退料原因" prop="return_reason">
              <el-select v-model="form.return_reason" placeholder="选择原因" style="width: 100%;">
                <el-option label="物料剩余" value="SURPLUS" />
                <el-option label="物料更换" value="REPLACEMENT" />
                <el-option label="物料报废" value="SCRAP" />
                <el-option label="物料不良" value="DEFECTIVE" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item v-if="form.return_type === 'PROJECT'" label="选择项目" prop="project">
              <el-select v-model="form.project" placeholder="选择项目" filterable style="width: 100%;">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
            <el-form-item v-else label="售后工单" prop="aftersales_order">
              <el-select v-model="form.aftersales_order" placeholder="选择售后工单" filterable style="width: 100%;">
                <el-option v-for="o in aftersalesOrders" :key="o.id" :label="o.order_no + ' - ' + o.title" :value="o.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="入库仓库" prop="warehouse">
              <el-select v-model="form.warehouse" placeholder="选择仓库" style="width: 100%;">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider>退料物料</el-divider>
        
        <!-- 物料选择 -->
        <div class="material-section">
          <el-input v-model="itemSearch" placeholder="搜索物料编码/名称" style="width: 200px; margin-bottom: 10px;" />
          <el-button type="primary" size="small" @click="searchItems" style="margin-left: 10px;">搜索</el-button>
          
          <el-table :data="searchedItems" max-height="200" size="small" style="margin-top: 10px;" @selection-change="handleItemSelect">
            <el-table-column type="selection" width="40" />
            <el-table-column prop="sku" label="物料编码" width="120" />
            <el-table-column prop="name" label="物料名称" />
            <el-table-column prop="spec" label="规格" width="150" />
          </el-table>
          <el-button type="primary" size="small" @click="addSelectedItems" style="margin-top: 10px;">
            添加选中物料
          </el-button>
        </div>

        <!-- 已选物料列表 -->
        <el-table :data="form.lines" style="margin-top: 16px;" border size="small">
          <el-table-column prop="item_name" label="物料名称" />
          <el-table-column prop="item_sku" label="物料编码" width="120" />
          <el-table-column label="退料数量" width="120">
            <template #default="{ row }">
              <el-input-number v-model="row.qty" :min="1" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="物料状态" width="120">
            <template #default="{ row }">
              <el-select v-model="row.condition" size="small">
                <el-option label="良品" value="GOOD" />
                <el-option label="损坏" value="DAMAGED" />
                <el-option label="报废" value="SCRAP" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="备注" width="150">
            <template #default="{ row }">
              <el-input v-model="row.notes" size="small" placeholder="备注" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60">
            <template #default="{ $index }">
              <el-button type="danger" size="small" @click="removeLine($index)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-form-item label="备注" style="margin-top: 16px;">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="备注信息" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 入库对话框 -->
    <el-dialog v-model="receiveDialogVisible" title="执行入库" width="800px">
      <el-table :data="receiveLines" border size="small">
        <el-table-column prop="item_name" label="物料名称" />
        <el-table-column prop="item_sku" label="物料编码" width="120" />
        <el-table-column prop="qty" label="退料数量" width="100" />
        <el-table-column prop="received_qty" label="已入库" width="80" />
        <el-table-column prop="pending_qty" label="待入库" width="80" />
        <el-table-column label="物料状态" width="100">
          <template #default="{ row }">
            <el-select v-model="row.condition" size="small">
              <el-option label="良品" value="GOOD" />
              <el-option label="损坏" value="DAMAGED" />
              <el-option label="报废" value="SCRAP" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="本次入库" width="120">
          <template #default="{ row }">
            <el-input-number v-model="row.receive_qty" :min="0" :max="row.pending_qty" size="small" />
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 10px; color: #909399; font-size: 12px;">
        <el-icon><Warning /></el-icon> 只有状态为"良品"的物料会入库，损坏/报废物料只做记录不增加库存
      </div>
      <template #footer>
        <el-button @click="receiveDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmReceive" :loading="receiving">确认入库</el-button>
      </template>
    </el-dialog>

    <!-- 拒绝对话框 -->
    <el-dialog v-model="rejectDialogVisible" title="拒绝退料" width="500px">
      <el-form>
        <el-form-item label="拒绝原因">
          <el-input v-model="rejectReason" type="textarea" :rows="3" placeholder="请填写拒绝原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="confirmReject" :loading="rejecting">确认拒绝</el-button>
      </template>
    </el-dialog>

    <!-- 详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="退料单详情" width="800px">
      <el-descriptions :column="2" border v-if="currentItem">
        <el-descriptions-item label="退料单号">{{ currentItem.return_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentItem.status)">{{ currentItem.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="退料类型">{{ currentItem.return_type_display }}</el-descriptions-item>
        <el-descriptions-item label="退料原因">{{ currentItem.return_reason_display }}</el-descriptions-item>
        <el-descriptions-item label="入库仓库">{{ currentItem.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="关联项目" v-if="currentItem.project_name">{{ currentItem.project_name }}</el-descriptions-item>
        <el-descriptions-item label="售后工单" v-if="currentItem.aftersales_order_no">{{ currentItem.aftersales_order_no }}</el-descriptions-item>
        <el-descriptions-item label="申请人">{{ currentItem.requestor_name }}</el-descriptions-item>
        <el-descriptions-item label="申请日期">{{ currentItem.request_date }}</el-descriptions-item>
        <el-descriptions-item label="入库时间">{{ currentItem.receive_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentItem.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
      
      <el-divider>物料明细</el-divider>
      <el-table :data="currentItem?.lines || []" border size="small">
        <el-table-column prop="item_sku" label="物料编码" width="120" />
        <el-table-column prop="item_name" label="物料名称" />
        <el-table-column prop="qty" label="退料数量" width="100" />
        <el-table-column prop="received_qty" label="已入库" width="100" />
        <el-table-column prop="condition_display" label="物料状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.condition === 'GOOD' ? 'success' : (row.condition === 'DAMAGED' ? 'warning' : 'danger')">
              {{ row.condition_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="入库状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.received_qty >= row.qty" type="success">已完成</el-tag>
            <el-tag v-else-if="row.received_qty > 0" type="warning">部分</el-tag>
            <el-tag v-else type="info">待入库</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Warning } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { usePermissionStore } from '@/stores/permission'

const loading = ref(false)
const saving = ref(false)
const receiving = ref(false)
const rejecting = ref(false)
const list = ref([])
const projects = ref([])
const warehouses = ref([])
const aftersalesOrders = ref([])
const projectsLoaded = ref(false)
const aftersalesOrdersLoaded = ref(false)
const searchedItems = ref([])
const itemSearch = ref('')
const selectedItems = ref([])
const permissionStore = usePermissionStore()

const searchForm = reactive({
  return_type: '',
  return_reason: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const dialogVisible = ref(false)
const dialogTitle = ref('新建退料单')
const isEdit = ref(false)

const form = reactive({
  id: null,
  return_type: 'PROJECT',
  return_reason: 'SURPLUS',
  project: null,
  aftersales_order: null,
  warehouse: null,
  notes: '',
  lines: []
})

const formRules = {
  return_type: [{ required: true, message: '请选择退料类型' }],
  return_reason: [{ required: true, message: '请选择退料原因' }],
  warehouse: [{ required: true, message: '请选择入库仓库' }]
}

const formRef = ref(null)

const receiveDialogVisible = ref(false)
const receiveLines = ref([])
const currentReturnId = ref(null)

const rejectDialogVisible = ref(false)
const rejectReason = ref('')
const rejectReturnId = ref(null)

const viewDialogVisible = ref(false)
const currentItem = ref(null)

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'PENDING': 'warning',
    'INSPECTING': 'warning',
    'COMPLETED': 'success',
    'PARTIAL': 'warning',
    'REJECTED': 'danger',
    'CANCELLED': 'danger'
  }
  return types[status] || 'info'
}

const loadList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const response = await request.get('/inventory/returns/', { params })
    list.value = response.results || response || []
    pagination.total = response.count || list.value.length
  } catch (error) {
    ElMessage.error('加载退料单列表失败')
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  if (projectsLoaded.value) {
    return true
  }

  try {
    const response = await request.get('/projects/projects/')
    projects.value = response.results || response || []
    projectsLoaded.value = true
    return true
  } catch (error) {
    if (error?.response?.status !== 403) {
      console.error('加载项目失败:', error)
    }
    return false
  }
}

const loadWarehouses = async () => {
  try {
    const response = await request.get('/masterdata/warehouses/')
    warehouses.value = response.results || response || []
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const loadAftersalesOrders = async () => {
  if (aftersalesOrdersLoaded.value) {
    return true
  }

  try {
    const response = await request.get('/projects/aftersales/')
    aftersalesOrders.value = response.results || response || []
    aftersalesOrdersLoaded.value = true
    return true
  } catch (error) {
    if (error?.response?.status !== 403) {
      console.error('加载售后工单失败:', error)
    }
    return false
  }
}

const ensureProjectSelectorsLoaded = async () => {
  if (!permissionStore.hasPermission('projects:list')) {
    projects.value = []
    projectsLoaded.value = false
    return false
  }

  return loadProjects()
}

const ensureAftersalesOrdersLoaded = async () => {
  return loadAftersalesOrders()
}

const searchItems = async () => {
  if (!itemSearch.value) {
    searchedItems.value = []
    return
  }
  try {
    const response = await request.get('/masterdata/items/', { params: { search: itemSearch.value } })
    searchedItems.value = response.results || response || []
  } catch (error) {
    console.error('搜索物料失败:', error)
  }
}

const handleTypeChange = () => {
  form.project = null
  form.aftersales_order = null
}

const handleItemSelect = (selection) => {
  selectedItems.value = selection
}

const addSelectedItems = () => {
  selectedItems.value.forEach(item => {
    if (!form.lines.find(l => l.item === item.id)) {
      form.lines.push({
        item: item.id,
        item_sku: item.sku,
        item_name: item.name,
        qty: 1,
        condition: 'GOOD',
        notes: ''
      })
    }
  })
}

const removeLine = (index) => {
  form.lines.splice(index, 1)
}

const resetSearch = () => {
  searchForm.return_type = ''
  searchForm.return_reason = ''
  searchForm.status = ''
  loadList()
}

const handleAdd = async () => {
  try {
    await Promise.all([ensureProjectSelectorsLoaded(), ensureAftersalesOrdersLoaded()])
  } catch (error) {
    console.error('加载数据失败', error)
    ElMessage.error('加载数据失败')
  }
  dialogTitle.value = '新建退料单'
  isEdit.value = false
  Object.assign(form, {
    id: null,
    return_type: 'PROJECT',
    return_reason: 'SURPLUS',
    project: null,
    aftersales_order: null,
    warehouse: null,
    notes: '',
    lines: []
  })
  searchedItems.value = []
  itemSearch.value = ''
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  try {
    await Promise.all([ensureProjectSelectorsLoaded(), ensureAftersalesOrdersLoaded()])
  } catch (error) {
    console.error('加载数据失败', error)
    ElMessage.error('加载数据失败')
  }
  dialogTitle.value = '编辑退料单'
  isEdit.value = true
  
  try {
    const response = await request.get(`/inventory/returns/${row.id}/`)
    Object.assign(form, {
      id: response.id,
      return_type: response.return_type,
      return_reason: response.return_reason,
      project: response.project,
      aftersales_order: response.aftersales_order,
      warehouse: response.warehouse,
      notes: response.notes,
      lines: (response.lines || []).map(l => ({
        id: l.id,
        item: l.item,
        item_sku: l.item_sku,
        item_name: l.item_name,
        qty: l.qty,
        condition: l.condition,
        notes: l.notes
      }))
    })
    dialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载退料单详情失败')
  }
}

const handleView = async (row) => {
  try {
    const response = await request.get(`/inventory/returns/${row.id}/`)
    currentItem.value = response
    viewDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载退料单详情失败')
  }
}

const handleSave = async () => {
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  
  if (form.lines.length === 0) {
    ElMessage.warning('请添加退料物料')
    return
  }
  
  saving.value = true
  try {
    const data = {
      return_type: form.return_type,
      return_reason: form.return_reason,
      project: form.project,
      aftersales_order: form.aftersales_order,
      warehouse: form.warehouse,
      notes: form.notes,
      lines: form.lines.map(l => ({
        item: l.item,
        qty: l.qty,
        condition: l.condition,
        notes: l.notes
      }))
    }
    
    if (isEdit.value) {
      await request.put(`/inventory/returns/${form.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/inventory/returns/', data)
      ElMessage.success('创建成功')
    }
    
    dialogVisible.value = false
    loadList()
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

const handleSubmit = async (row) => {
  try {
    await ElMessageBox.confirm('确定提交该退料申请？', '确认')
    await request.post(`/inventory/returns/${row.id}/submit/`)
    ElMessage.success('提交成功')
    loadList()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('提交失败: ' + (error.response?.data?.error || error.message))
    }
  }
}

const handleInspect = async (row) => {
  try {
    await request.post(`/inventory/returns/${row.id}/start_inspect/`)
    ElMessage.success('开始检验')
    loadList()
  } catch (error) {
    ElMessage.error('操作失败: ' + (error.response?.data?.error || error.message))
  }
}

const handleReceive = async (row) => {
  try {
    const response = await request.get(`/inventory/returns/${row.id}/`)
    currentReturnId.value = row.id
    receiveLines.value = (response.lines || []).filter(l => l.qty > l.received_qty).map(l => ({
      id: l.id,
      item_name: l.item_name,
      item_sku: l.item_sku,
      qty: l.qty,
      received_qty: l.received_qty,
      pending_qty: l.qty - l.received_qty,
      condition: l.condition,
      receive_qty: l.qty - l.received_qty
    }))
    receiveDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载明细失败')
  }
}

const confirmReceive = async () => {
  const lines = receiveLines.value.filter(l => l.receive_qty > 0).map(l => ({
    id: l.id,
    received_qty: l.receive_qty,
    condition: l.condition
  }))
  
  if (lines.length === 0) {
    ElMessage.warning('请填写入库数量')
    return
  }
  
  receiving.value = true
  try {
    await request.post(`/inventory/returns/${currentReturnId.value}/receive/`, { lines })
    ElMessage.success('入库成功')
    receiveDialogVisible.value = false
    loadList()
  } catch (error) {
    ElMessage.error('入库失败: ' + (error.response?.data?.error || error.message))
  } finally {
    receiving.value = false
  }
}

const handleReject = (row) => {
  rejectReturnId.value = row.id
  rejectReason.value = ''
  rejectDialogVisible.value = true
}

const confirmReject = async () => {
  if (!rejectReason.value) {
    ElMessage.warning('请填写拒绝原因')
    return
  }
  
  rejecting.value = true
  try {
    await request.post(`/inventory/returns/${rejectReturnId.value}/reject/`, { reason: rejectReason.value })
    ElMessage.success('已拒绝')
    rejectDialogVisible.value = false
    loadList()
  } catch (error) {
    ElMessage.error('操作失败: ' + (error.response?.data?.error || error.message))
  } finally {
    rejecting.value = false
  }
}

onMounted(() => {
  loadList()
  loadWarehouses()
})
</script>

<style scoped>
.return-list {
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

.material-section {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
}

.text-muted {
  color: #999;
}
</style>

