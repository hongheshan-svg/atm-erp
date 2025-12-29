<template>
  <div class="requisition-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>生产领料管理</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon> 新建领料单
          </el-button>
        </div>
      </template>

      <!-- 搜索区域 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="领料类型">
          <el-select v-model="searchForm.requisition_type" placeholder="全部" clearable style="width: 120px;">
            <el-option label="项目领料" value="PROJECT" />
            <el-option label="售后领料" value="AFTERSALES" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="待备料" value="PENDING" />
            <el-option label="备料中" value="PREPARING" />
            <el-option label="备料完成" value="READY" />
            <el-option label="已出库" value="ISSUED" />
            <el-option label="部分出库" value="PARTIAL" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目">
          <el-select v-model="searchForm.project" placeholder="选择项目" clearable filterable style="width: 180px;">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadList">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 列表 -->
      <el-table :data="list" v-loading="loading" stripe border>
        <el-table-column prop="requisition_no" label="领料单号" width="160" />
        <el-table-column prop="requisition_type_display" label="类型" width="100" />
        <el-table-column label="关联单据" min-width="150">
          <template #default="{ row }">
            <span v-if="row.project_name">{{ row.project_name }}</span>
            <span v-else-if="row.aftersales_order_no">{{ row.aftersales_order_no }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="warehouse_name" label="出库仓库" width="120" />
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
            <el-button size="small" type="warning" @click="handlePrepare(row)" v-if="row.status === 'PENDING'">开始备料</el-button>
            <el-button size="small" type="success" @click="handleReady(row)" v-if="row.status === 'PREPARING'">备料完成</el-button>
            <el-button size="small" type="primary" @click="handleIssue(row)" v-if="['READY', 'PARTIAL'].includes(row.status)">出库</el-button>
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
            <el-form-item label="领料类型" prop="requisition_type">
              <el-radio-group v-model="form.requisition_type" @change="handleTypeChange">
                <el-radio value="PROJECT">项目领料</el-radio>
                <el-radio value="AFTERSALES">售后领料</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="出库仓库" prop="warehouse">
              <el-select v-model="form.warehouse" placeholder="选择仓库" style="width: 100%;">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item v-if="form.requisition_type === 'PROJECT'" label="选择项目" prop="project">
              <el-select v-model="form.project" placeholder="选择项目" filterable style="width: 100%;" @change="loadProjectItems">
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
            <el-form-item label="需求日期">
              <el-date-picker v-model="form.required_date" type="date" placeholder="选择日期" style="width: 100%;" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider>领料物料</el-divider>
        
        <!-- 物料选择区域 -->
        <div class="material-section">
          <div class="material-source">
            <el-tabs v-model="materialTab">
              <el-tab-pane label="项目物料" name="project" v-if="form.requisition_type === 'PROJECT'">
                <el-table :data="projectItems" max-height="200" size="small" @selection-change="handleProjectItemSelect">
                  <el-table-column type="selection" width="40" />
                  <el-table-column prop="item_sku" label="物料编码" width="120" />
                  <el-table-column prop="item_name" label="物料名称" />
                  <el-table-column prop="qty" label="BOM数量" width="80" />
                </el-table>
              </el-tab-pane>
              <el-tab-pane label="仓库库存" name="stock">
                <el-input v-model="stockSearch" placeholder="搜索物料" style="width: 200px; margin-bottom: 10px;" @input="loadStockItems" />
                <el-table :data="stockItems" max-height="200" size="small" @selection-change="handleStockItemSelect">
                  <el-table-column type="selection" width="40" />
                  <el-table-column prop="item_sku" label="物料编码" width="120" />
                  <el-table-column prop="item_name" label="物料名称" />
                  <el-table-column prop="qty_available" label="可用库存" width="80" />
                </el-table>
              </el-tab-pane>
            </el-tabs>
            <el-button type="primary" size="small" @click="addSelectedItems" style="margin-top: 10px;">
              添加选中物料
            </el-button>
          </div>
        </div>

        <!-- 已选物料列表 -->
        <el-table :data="form.lines" style="margin-top: 16px;" border size="small">
          <el-table-column prop="item_name" label="物料名称" />
          <el-table-column prop="item_sku" label="物料编码" width="120" />
          <el-table-column label="申请数量" width="120">
            <template #default="{ row }">
              <el-input-number v-model="row.qty" :min="1" size="small" />
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

    <!-- 出库对话框 -->
    <el-dialog v-model="issueDialogVisible" title="执行出库" width="700px">
      <el-table :data="issueLines" border size="small">
        <el-table-column prop="item_name" label="物料名称" />
        <el-table-column prop="item_sku" label="物料编码" width="120" />
        <el-table-column prop="qty" label="申请数量" width="100" />
        <el-table-column prop="issued_qty" label="已出库" width="80" />
        <el-table-column prop="pending_qty" label="待出库" width="80" />
        <el-table-column label="本次出库" width="120">
          <template #default="{ row }">
            <el-input-number v-model="row.issue_qty" :min="0" :max="row.pending_qty" size="small" />
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="issueDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmIssue" :loading="issuing">确认出库</el-button>
      </template>
    </el-dialog>

    <!-- 详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="领料单详情" width="800px">
      <el-descriptions :column="2" border v-if="currentItem">
        <el-descriptions-item label="领料单号">{{ currentItem.requisition_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentItem.status)">{{ currentItem.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="领料类型">{{ currentItem.requisition_type_display }}</el-descriptions-item>
        <el-descriptions-item label="出库仓库">{{ currentItem.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="关联项目" v-if="currentItem.project_name">{{ currentItem.project_name }}</el-descriptions-item>
        <el-descriptions-item label="售后工单" v-if="currentItem.aftersales_order_no">{{ currentItem.aftersales_order_no }}</el-descriptions-item>
        <el-descriptions-item label="申请人">{{ currentItem.requestor_name }}</el-descriptions-item>
        <el-descriptions-item label="申请日期">{{ currentItem.request_date }}</el-descriptions-item>
        <el-descriptions-item label="需求日期">{{ currentItem.required_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="出库时间">{{ currentItem.issue_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentItem.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
      
      <el-divider>物料明细</el-divider>
      <el-table :data="currentItem?.lines || []" border size="small">
        <el-table-column prop="item_sku" label="物料编码" width="120" />
        <el-table-column prop="item_name" label="物料名称" />
        <el-table-column prop="qty" label="申请数量" width="100" />
        <el-table-column prop="issued_qty" label="已出库" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.issued_qty >= row.qty" type="success">已完成</el-tag>
            <el-tag v-else-if="row.issued_qty > 0" type="warning">部分</el-tag>
            <el-tag v-else type="info">待出库</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const saving = ref(false)
const issuing = ref(false)
const list = ref([])
const projects = ref([])
const warehouses = ref([])
const aftersalesOrders = ref([])
const projectItems = ref([])
const stockItems = ref([])
const stockSearch = ref('')
const materialTab = ref('project')

const selectedProjectItems = ref([])
const selectedStockItems = ref([])

const searchForm = reactive({
  requisition_type: '',
  status: '',
  project: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const dialogVisible = ref(false)
const dialogTitle = ref('新建领料单')
const isEdit = ref(false)

const form = reactive({
  id: null,
  requisition_type: 'PROJECT',
  project: null,
  aftersales_order: null,
  warehouse: null,
  required_date: '',
  notes: '',
  lines: []
})

const formRules = {
  requisition_type: [{ required: true, message: '请选择领料类型' }],
  warehouse: [{ required: true, message: '请选择出库仓库' }]
}

const formRef = ref(null)

const issueDialogVisible = ref(false)
const issueLines = ref([])
const currentRequisitionId = ref(null)

const viewDialogVisible = ref(false)
const currentItem = ref(null)

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'PENDING': 'warning',
    'PREPARING': 'warning',
    'READY': 'success',
    'ISSUED': 'success',
    'PARTIAL': 'warning',
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
    const response = await request.get('/inventory/requisitions/', { params })
    list.value = response.results || response || []
    pagination.total = response.count || list.value.length
  } catch (error) {
    ElMessage.error('加载领料单列表失败')
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    const response = await request.get('/projects/projects/')
    projects.value = response.results || response || []
  } catch (error) {
    console.error('加载项目失败:', error)
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
  try {
    const response = await request.get('/projects/aftersales/')
    aftersalesOrders.value = response.results || response || []
  } catch (error) {
    console.error('加载售后工单失败:', error)
  }
}

const loadProjectItems = async () => {
  if (!form.project) {
    projectItems.value = []
    return
  }
  try {
    const response = await request.get('/projects/bom/', { params: { project: form.project } })
    projectItems.value = (response.results || response || []).map(item => ({
      item: item.item,
      item_sku: item.item_sku,
      item_name: item.item_name,
      qty: item.qty
    }))
  } catch (error) {
    console.error('加载项目BOM失败:', error)
  }
}

const loadStockItems = async () => {
  if (!form.warehouse) {
    stockItems.value = []
    return
  }
  try {
    const params = { warehouse: form.warehouse }
    if (stockSearch.value) {
      params.item_name = stockSearch.value
    }
    const response = await request.get('/inventory/stocks/', { params })
    stockItems.value = (response.results || response || []).map(item => ({
      item: item.item,
      item_sku: item.item_sku,
      item_name: item.item_name,
      qty_available: item.qty_available
    }))
  } catch (error) {
    console.error('加载库存失败:', error)
  }
}

const handleTypeChange = () => {
  form.project = null
  form.aftersales_order = null
  form.lines = []
  projectItems.value = []
  materialTab.value = form.requisition_type === 'PROJECT' ? 'project' : 'stock'
}

const handleProjectItemSelect = (selection) => {
  selectedProjectItems.value = selection
}

const handleStockItemSelect = (selection) => {
  selectedStockItems.value = selection
}

const addSelectedItems = () => {
  const items = materialTab.value === 'project' ? selectedProjectItems.value : selectedStockItems.value
  items.forEach(item => {
    if (!form.lines.find(l => l.item === item.item)) {
      form.lines.push({
        item: item.item,
        item_sku: item.item_sku,
        item_name: item.item_name,
        qty: item.qty || 1,
        notes: ''
      })
    }
  })
}

const removeLine = (index) => {
  form.lines.splice(index, 1)
}

const resetSearch = () => {
  searchForm.requisition_type = ''
  searchForm.status = ''
  searchForm.project = null
  loadList()
}

const handleAdd = () => {
  dialogTitle.value = '新建领料单'
  isEdit.value = false
  Object.assign(form, {
    id: null,
    requisition_type: 'PROJECT',
    project: null,
    aftersales_order: null,
    warehouse: null,
    required_date: '',
    notes: '',
    lines: []
  })
  materialTab.value = 'project'
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑领料单'
  isEdit.value = true
  
  try {
    const response = await request.get(`/inventory/requisitions/${row.id}/`)
    Object.assign(form, {
      id: response.id,
      requisition_type: response.requisition_type,
      project: response.project,
      aftersales_order: response.aftersales_order,
      warehouse: response.warehouse,
      required_date: response.required_date,
      notes: response.notes,
      lines: (response.lines || []).map(l => ({
        id: l.id,
        item: l.item,
        item_sku: l.item_sku,
        item_name: l.item_name,
        qty: l.qty,
        notes: l.notes
      }))
    })
    materialTab.value = form.requisition_type === 'PROJECT' ? 'project' : 'stock'
    if (form.project) loadProjectItems()
    if (form.warehouse) loadStockItems()
    dialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载领料单详情失败')
  }
}

const handleView = async (row) => {
  try {
    const response = await request.get(`/inventory/requisitions/${row.id}/`)
    currentItem.value = response
    viewDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载领料单详情失败')
  }
}

const handleSave = async () => {
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  
  if (form.lines.length === 0) {
    ElMessage.warning('请添加领料物料')
    return
  }
  
  saving.value = true
  try {
    const data = {
      requisition_type: form.requisition_type,
      project: form.project,
      aftersales_order: form.aftersales_order,
      warehouse: form.warehouse,
      required_date: form.required_date || null,
      notes: form.notes,
      lines: form.lines.map(l => ({
        item: l.item,
        qty: l.qty,
        notes: l.notes
      }))
    }
    
    if (isEdit.value) {
      await request.put(`/inventory/requisitions/${form.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/inventory/requisitions/', data)
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
    await ElMessageBox.confirm('确定提交该领料申请？', '确认')
    await request.post(`/inventory/requisitions/${row.id}/submit/`)
    ElMessage.success('提交成功')
    loadList()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('提交失败: ' + (error.response?.data?.error || error.message))
    }
  }
}

const handlePrepare = async (row) => {
  try {
    await request.post(`/inventory/requisitions/${row.id}/start_preparing/`)
    ElMessage.success('开始备料')
    loadList()
  } catch (error) {
    ElMessage.error('操作失败: ' + (error.response?.data?.error || error.message))
  }
}

const handleReady = async (row) => {
  try {
    await request.post(`/inventory/requisitions/${row.id}/ready/`)
    ElMessage.success('备料完成')
    loadList()
  } catch (error) {
    ElMessage.error('操作失败: ' + (error.response?.data?.error || error.message))
  }
}

const handleIssue = async (row) => {
  try {
    const response = await request.get(`/inventory/requisitions/${row.id}/`)
    currentRequisitionId.value = row.id
    issueLines.value = (response.lines || []).filter(l => l.qty > l.issued_qty).map(l => ({
      id: l.id,
      item_name: l.item_name,
      item_sku: l.item_sku,
      qty: l.qty,
      issued_qty: l.issued_qty,
      pending_qty: l.qty - l.issued_qty,
      issue_qty: l.qty - l.issued_qty
    }))
    issueDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载明细失败')
  }
}

const confirmIssue = async () => {
  const lines = issueLines.value.filter(l => l.issue_qty > 0).map(l => ({
    id: l.id,
    issued_qty: l.issue_qty
  }))
  
  if (lines.length === 0) {
    ElMessage.warning('请填写出库数量')
    return
  }
  
  issuing.value = true
  try {
    await request.post(`/inventory/requisitions/${currentRequisitionId.value}/issue/`, { lines })
    ElMessage.success('出库成功')
    issueDialogVisible.value = false
    loadList()
  } catch (error) {
    ElMessage.error('出库失败: ' + (error.response?.data?.error || error.message))
  } finally {
    issuing.value = false
  }
}

onMounted(() => {
  loadList()
  loadProjects()
  loadWarehouses()
  loadAftersalesOrders()
})
</script>

<style scoped>
.requisition-list {
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

