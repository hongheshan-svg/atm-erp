<template>
  <div class="rfq-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>询价管理</span>
          <div class="header-actions">
            <el-button type="primary" @click="handleCreate">
              <el-icon><Plus /></el-icon>
              新建询价
            </el-button>
          </div>
        </div>
      </template>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="询价单号">
          <el-input v-model="searchForm.rfq_no" placeholder="请输入询价单号" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable>
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已发送" value="SENT" />
            <el-option label="已报价" value="QUOTED" />
            <el-option label="已接受" value="ACCEPTED" />
            <el-option label="已拒绝" value="REJECTED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 数据表格 -->
      <el-table :data="tableData" v-loading="loading" stripe border>
        <el-table-column prop="rfq_no" label="询价单号" width="160" />
        <el-table-column prop="project_name" label="项目" min-width="150">
          <template #default="{ row }">
            {{ row.project_name || '无项目' }}
          </template>
        </el-table-column>
        <el-table-column label="物料数" width="80" align="center">
          <template #default="{ row }">
            {{ row.lines?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="供应商数" width="100" align="center">
          <template #default="{ row }">
            {{ row.supplier_rfqs?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="request_date" label="询价日期" width="120">
          <template #default="{ row }">
            {{ formatDate(row.request_date) }}
          </template>
        </el-table-column>
        <el-table-column prop="response_deadline" label="报价截止" width="120">
          <template #default="{ row }">
            <span :class="{ 'text-danger': isExpired(row.response_deadline) }">
              {{ formatDate(row.response_deadline) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="handleView(row)">
              查看
            </el-button>
            <el-button 
              v-if="row.status === 'DRAFT'" 
              type="success" size="small" link 
              @click="handleSendToSuppliers(row)"
            >
              发送询价
            </el-button>
            <el-button 
              v-if="row.status === 'QUOTED'" 
              type="warning" size="small" link 
              @click="handleStartComparison(row)"
            >
              比价分析
            </el-button>
            <el-button 
              v-if="row.status === 'DRAFT'" 
              type="danger" size="small" link 
              @click="handleDelete(row)"
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
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 16px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新建询价对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目" prop="project">
              <el-select v-model="form.project" placeholder="选择项目" clearable filterable style="width: 100%">
                <el-option
                  v-for="project in projects"
                  :key="project.id"
                  :label="project.name"
                  :value="project.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="报价截止" prop="response_deadline">
              <el-date-picker
                v-model="form.response_deadline"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" />
        </el-form-item>

        <el-divider content-position="left">询价物料</el-divider>
        
        <el-table :data="form.lines" border size="small">
          <el-table-column label="物料" min-width="200">
            <template #default="{ row }">
              <el-select 
                v-model="row.item" 
                placeholder="选择物料" 
                filterable 
                remote 
                :remote-method="searchItems"
                style="width: 100%"
              >
                <el-option
                  v-for="item in items"
                  :key="item.id"
                  :label="`${item.sku} - ${item.name}`"
                  :value="item.id"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="数量" width="120">
            <template #default="{ row }">
              <el-input-number v-model="row.qty" :min="0" :precision="2" size="small" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="需求日期" width="160">
            <template #default="{ row }">
              <el-date-picker
                v-model="row.required_date"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                size="small"
                style="width: 100%"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template #default="{ $index }">
              <el-button type="danger" size="small" link @click="removeLine($index)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-button type="primary" link @click="addLine" style="margin-top: 10px;">
          <el-icon><Plus /></el-icon>
          添加物料
        </el-button>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 发送询价对话框 -->
    <el-dialog v-model="sendDialogVisible" title="发送询价给供应商" width="500px">
      <el-form label-width="100px">
        <el-form-item label="选择供应商">
          <el-select 
            v-model="selectedSuppliers" 
            multiple 
            placeholder="选择供应商" 
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="supplier in suppliers"
              :key="supplier.id"
              :label="supplier.name"
              :value="supplier.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sendDialogVisible = false">取消</el-button>
        <el-button 
          type="primary" 
          @click="confirmSendToSuppliers" 
          :disabled="selectedSuppliers.length === 0"
        >
          发送 ({{ selectedSuppliers.length }})
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const router = useRouter()

// 状态
const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新建询价')
const sendDialogVisible = ref(false)
const projects = ref([])
const items = ref([])
const suppliers = ref([])
const selectedSuppliers = ref([])
const currentRFQ = ref(null)
const formRef = ref(null)

// 搜索
const searchForm = reactive({
  rfq_no: '',
  status: ''
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 表单
const form = reactive({
  project: null,
  response_deadline: '',
  notes: '',
  lines: []
})

const rules = {
  response_deadline: [{ required: true, message: '请选择报价截止日期', trigger: 'change' }]
}

// 格式化
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const isExpired = (dateStr) => {
  if (!dateStr) return false
  return new Date(dateStr) < new Date()
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'SENT': 'warning',
    'QUOTED': 'success',
    'ACCEPTED': 'primary',
    'REJECTED': 'danger',
    'CANCELLED': 'info'
  }
  return types[status] || 'info'
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      search: searchForm.rfq_no,
      status: searchForm.status
    }
    const res = await request.get('/purchase/rfqs/', { params })
    tableData.value = res.results || res || []
    pagination.total = res.count || 0
  } catch (error) {
    console.error('加载询价列表失败:', error)
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

// 加载项目
const loadProjects = async () => {
  try {
    const res = await request.get('/projects/', { params: { page_size: 200 } })
    projects.value = res.results || res || []
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

// 加载供应商
const loadSuppliers = async () => {
  try {
    const res = await request.get('/masterdata/suppliers/', { params: { page_size: 200 } })
    suppliers.value = res.results || res || []
  } catch (error) {
    console.error('加载供应商失败:', error)
  }
}

// 搜索物料
const searchItems = async (query) => {
  if (!query) return
  try {
    const res = await request.get('/masterdata/items/', { params: { search: query, page_size: 50 } })
    items.value = res.results || res || []
  } catch (error) {
    console.error('搜索物料失败:', error)
  }
}

// 重置搜索
const resetSearch = () => {
  searchForm.rfq_no = ''
  searchForm.status = ''
  pagination.page = 1
  loadData()
}

// 新建
const handleCreate = async () => {
  await loadProjects()
  form.project = null
  form.response_deadline = ''
  form.notes = ''
  form.lines = [{ item: null, qty: 1, required_date: '' }]
  dialogTitle.value = '新建询价'
  dialogVisible.value = true
}

// 添加行
const addLine = () => {
  form.lines.push({ item: null, qty: 1, required_date: '' })
}

// 删除行
const removeLine = (index) => {
  form.lines.splice(index, 1)
}

// 保存
const handleSave = async () => {
  try {
    await formRef.value.validate()
    
    // 过滤有效行
    const validLines = form.lines.filter(l => l.item && l.qty > 0)
    if (validLines.length === 0) {
      ElMessage.warning('请至少添加一个物料')
      return
    }
    
    const data = {
      project: form.project,
      response_deadline: form.response_deadline,
      notes: form.notes
    }
    
    const rfqRes = await request.post('/purchase/rfqs/', data)
    
    // 添加明细
    for (const line of validLines) {
      await request.post('/purchase/rfq-lines/', {
        rfq: rfqRes.id,
        item: line.item,
        qty: line.qty,
        required_date: line.required_date || form.response_deadline
      })
    }
    
    ElMessage.success('询价单创建成功')
    dialogVisible.value = false
    loadData()
  } catch (error) {
    console.error('保存失败:', error)
    ElMessage.error('保存失败')
  }
}

// 查看
const handleView = (row) => {
  // 可以导航到详情页或打开对话框
  ElMessage.info(`查看询价单: ${row.rfq_no}`)
}

// 发送询价
const handleSendToSuppliers = async (row) => {
  await loadSuppliers()
  currentRFQ.value = row
  selectedSuppliers.value = []
  sendDialogVisible.value = true
}

const confirmSendToSuppliers = async () => {
  try {
    await request.post(`/purchase/rfqs/${currentRFQ.value.id}/send_to_suppliers/`, {
      supplier_ids: selectedSuppliers.value
    })
    ElMessage.success(`已发送给 ${selectedSuppliers.value.length} 个供应商`)
    sendDialogVisible.value = false
    loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '发送失败')
  }
}

// 开始比价
const handleStartComparison = (row) => {
  router.push({
    path: '/purchase/comparisons',
    query: { rfq_id: row.id }
  })
}

// 删除
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除此询价单？', '确认删除', { type: 'warning' })
    await request.delete(`/purchase/rfqs/${row.id}/`)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.rfq-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 16px;
}

.text-danger {
  color: #f56c6c;
}
</style>

