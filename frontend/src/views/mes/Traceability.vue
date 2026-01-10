<template>
  <div class="traceability-container">
    <div class="page-header">
      <h2>追溯管理</h2>
      <el-button type="primary" @click="handleAddBatch">新建批次</el-button>
    </div>
    
    <!-- 快速搜索 -->
    <el-card shadow="never" class="search-card">
      <el-row :gutter="20">
        <el-col :span="16">
          <el-input 
            v-model="searchQuery" 
            placeholder="输入批次号、项目名称或物料批次进行追溯查询"
            size="large"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #prepend>
              <el-select v-model="searchType" style="width: 120px">
                <el-option label="全部" value="all" />
                <el-option label="产品批次" value="batch" />
                <el-option label="物料批次" value="material" />
              </el-select>
            </template>
            <template #append>
              <el-button :icon="Search" @click="handleSearch" />
            </template>
          </el-input>
        </el-col>
        <el-col :span="8">
          <el-button-group>
            <el-button @click="scanBarcode">扫码追溯</el-button>
            <el-button @click="exportTrace">导出报告</el-button>
          </el-button-group>
        </el-col>
      </el-row>
    </el-card>
    
    <el-row :gutter="16">
      <!-- 批次列表 -->
      <el-col :span="16">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>产品批次</span>
              <el-radio-group v-model="listFilter" size="small" @change="fetchList">
                <el-radio-button label="all">全部</el-radio-button>
                <el-radio-button label="ACTIVE">生产中</el-radio-button>
                <el-radio-button label="HOLD">暂扣</el-radio-button>
                <el-radio-button label="RELEASED">已放行</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          
          <el-table :data="batchList" v-loading="loading" border stripe @row-click="handleRowClick">
            <el-table-column prop="batch_no" label="批次号" width="140" />
            <el-table-column prop="project_name" label="项目" min-width="180" show-overflow-tooltip />
            <el-table-column prop="item_name" label="产品" width="150" show-overflow-tooltip />
            <el-table-column prop="production_date" label="生产日期" width="110" />
            <el-table-column prop="quantity" label="数量" width="80" align="right" />
            <el-table-column prop="status_display" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="quality_grade" label="质量等级" width="90" />
            <el-table-column prop="operation_count" label="操作数" width="80" align="center" />
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click.stop="handleTrace(row)">追溯</el-button>
                <el-button type="success" link size="small" @click.stop="handleRelease(row)" 
                  v-if="row.status !== 'RELEASED'">放行</el-button>
                <el-button type="warning" link size="small" @click.stop="handleHold(row)" 
                  v-if="row.status !== 'HOLD'">暂扣</el-button>
              </template>
            </el-table-column>
          </el-table>
          
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.size"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next"
            @size-change="fetchList"
            @current-change="fetchList"
            style="margin-top: 16px; justify-content: flex-end"
          />
        </el-card>
      </el-col>
      
      <!-- 追溯详情 -->
      <el-col :span="8">
        <el-card shadow="never" v-if="selectedBatch" class="trace-card">
          <template #header>
            <div class="trace-header">
              <span>追溯详情: {{ selectedBatch.batch_no }}</span>
              <el-button type="primary" link @click="showFullTrace">完整追溯</el-button>
            </div>
          </template>
          
          <el-timeline>
            <el-timeline-item
              v-for="op in traceData.operations?.slice(0, 10)"
              :key="op.id"
              :timestamp="formatDateTime(op.operation_time)"
              :type="getOperationType(op.operation_type)"
            >
              <div class="op-content">
                <div class="op-type">{{ op.operation_type_display }}</div>
                <div class="op-operator">操作人: {{ op.operator_name || '-' }}</div>
                <div class="op-result" v-if="op.result">结果: {{ op.result }}</div>
              </div>
            </el-timeline-item>
          </el-timeline>
          
          <el-divider content-position="left" v-if="traceData.materials?.length">物料来源</el-divider>
          <div v-if="traceData.materials?.length" class="material-list">
            <div v-for="mat in traceData.materials" :key="mat.id" class="material-item">
              <div class="mat-batch">{{ mat.material_batch }}</div>
              <div class="mat-info">
                <span>{{ mat.item_name }}</span>
                <span>x{{ mat.quantity }}</span>
              </div>
              <div class="mat-supplier">{{ mat.supplier_name || '-' }}</div>
            </div>
          </div>
          
          <el-divider content-position="left" v-if="traceData.quality?.length">质量记录</el-divider>
          <div v-if="traceData.quality?.length" class="quality-list">
            <div v-for="qr in traceData.quality" :key="qr.id" class="quality-item">
              <el-tag :type="qr.result === 'PASS' ? 'success' : 'danger'" size="small">
                {{ qr.result_display }}
              </el-tag>
              <span class="qr-item">{{ qr.inspection_item }}</span>
              <span class="qr-value">{{ qr.actual_value || '-' }}</span>
            </div>
          </div>
        </el-card>
        
        <el-card shadow="never" v-else class="empty-trace">
          <el-empty description="选择批次查看追溯信息" />
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 新建批次对话框 -->
    <el-dialog v-model="dialogVisible" title="新建批次" width="600px">
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="项目" prop="project">
          <el-select v-model="formData.project" style="width: 100%" filterable placeholder="选择项目">
            <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="产品">
          <el-select v-model="formData.item" style="width: 100%" filterable clearable placeholder="选择产品">
            <el-option v-for="i in itemList" :key="i.id" :label="i.name" :value="i.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="生产日期">
          <el-date-picker v-model="formData.production_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="formData.quantity" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="来源批次">
          <el-select v-model="formData.source_batches" multiple style="width: 100%" filterable placeholder="选择来源批次">
            <el-option v-for="b in batchList" :key="b.id" :label="b.batch_no" :value="b.batch_no" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.remarks" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 完整追溯对话框 -->
    <el-dialog v-model="fullTraceVisible" title="完整追溯链" width="900px">
      <div v-if="fullTraceData" class="full-trace">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="批次号">{{ fullTraceData.batch?.batch_no }}</el-descriptions-item>
          <el-descriptions-item label="项目">{{ fullTraceData.batch?.project_name }}</el-descriptions-item>
          <el-descriptions-item label="产品">{{ fullTraceData.batch?.item_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="生产日期">{{ fullTraceData.batch?.production_date }}</el-descriptions-item>
          <el-descriptions-item label="数量">{{ fullTraceData.batch?.quantity }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ fullTraceData.batch?.status_display }}</el-descriptions-item>
        </el-descriptions>
        
        <el-tabs style="margin-top: 20px">
          <el-tab-pane label="操作记录">
            <el-table :data="fullTraceData.operations" size="small" border>
              <el-table-column prop="operation_time" label="时间" width="160">
                <template #default="{ row }">{{ formatDateTime(row.operation_time) }}</template>
              </el-table-column>
              <el-table-column prop="operation_type_display" label="操作类型" width="100" />
              <el-table-column prop="process_name" label="工序" width="120" />
              <el-table-column prop="operator_name" label="操作人" width="100" />
              <el-table-column prop="result" label="结果" width="100" />
              <el-table-column prop="remarks" label="备注" />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="物料追溯">
            <el-table :data="fullTraceData.materials" size="small" border>
              <el-table-column prop="material_batch" label="物料批次" width="140" />
              <el-table-column prop="item_name" label="物料名称" />
              <el-table-column prop="supplier_name" label="供应商" width="150" />
              <el-table-column prop="quantity" label="用量" width="100" />
              <el-table-column prop="use_time" label="使用时间" width="160">
                <template #default="{ row }">{{ formatDateTime(row.use_time) }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="质量记录">
            <el-table :data="fullTraceData.quality" size="small" border>
              <el-table-column prop="inspection_type" label="检验类型" width="100" />
              <el-table-column prop="inspection_item" label="检验项目" />
              <el-table-column prop="standard_value" label="标准值" width="100" />
              <el-table-column prop="actual_value" label="实测值" width="100" />
              <el-table-column prop="result_display" label="结果" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.result === 'PASS' ? 'success' : 'danger'" size="small">{{ row.result_display }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="inspector_name" label="检验员" width="100" />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="来源批次" v-if="fullTraceData.source_details?.length">
            <el-table :data="fullTraceData.source_details" size="small" border>
              <el-table-column prop="batch_no" label="批次号" width="140" />
              <el-table-column prop="project_name" label="项目" />
              <el-table-column prop="item_name" label="产品" width="150" />
              <el-table-column prop="status_display" label="状态" width="100" />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const submitLoading = ref(false)
const batchList = ref([])
const projectList = ref([])
const itemList = ref([])

const searchQuery = ref('')
const searchType = ref('all')
const listFilter = ref('all')

const selectedBatch = ref(null)
const traceData = ref({})
const fullTraceData = ref(null)

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

const dialogVisible = ref(false)
const fullTraceVisible = ref(false)
const formRef = ref(null)

const formData = reactive({
  project: null,
  item: null,
  production_date: new Date().toISOString().slice(0, 10),
  quantity: 1,
  source_batches: [],
  remarks: ''
})

const rules = {
  project: [{ required: true, message: '请选择项目', trigger: 'change' }]
}

const fetchList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.size
    }
    if (listFilter.value !== 'all') {
      params.status = listFilter.value
    }
    const { data } = await request.get('/production/product-lots/', { params })
    batchList.value = data.results || data
    pagination.total = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchProjects = async () => {
  try {
    const { data } = await request.get('/projects/projects/', { params: { page_size: 100 } })
    projectList.value = data.results || data
  } catch (e) {
    console.error(e)
  }
}

const fetchItems = async () => {
  try {
    const { data } = await request.get('/masterdata/items/', { params: { page_size: 500 } })
    itemList.value = data.results || data
  } catch (e) {
    console.error(e)
  }
}

const handleSearch = async () => {
  if (!searchQuery.value) return
  
  try {
    const { data } = await request.get('/production/traceability/search/', {
      params: { q: searchQuery.value, type: searchType.value }
    })
    
    if (data.batches?.length) {
      batchList.value = data.batches
      pagination.total = data.batches.length
    } else {
      ElMessage.info('未找到匹配的追溯记录')
    }
  } catch (e) {
    ElMessage.error('搜索失败')
  }
}

const handleRowClick = (row) => {
  selectedBatch.value = row
  fetchTraceData(row.id)
}

const handleTrace = (row) => {
  selectedBatch.value = row
  fetchTraceData(row.id)
}

const fetchTraceData = async (batchId) => {
  try {
    const { data } = await request.get(`/production/product-lots/${batchId}/trace/`)
    traceData.value = data
  } catch (e) {
    console.error(e)
  }
}

const showFullTrace = async () => {
  if (!selectedBatch.value) return
  
  try {
    const { data } = await request.get(`/production/product-lots/${selectedBatch.value.id}/trace/`)
    fullTraceData.value = data
    fullTraceVisible.value = true
  } catch (e) {
    ElMessage.error('加载追溯数据失败')
  }
}

const handleRelease = async (row) => {
  try {
    await request.post(`/production/product-lots/${row.id}/release/`)
    ElMessage.success('已放行')
    fetchList()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleHold = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入暂扣原因', '暂扣批次')
    await request.post(`/production/product-lots/${row.id}/hold/`, { reason: value })
    ElMessage.success('已暂扣')
    fetchList()
  } catch (e) {
    // 取消
  }
}

const handleAddBatch = () => {
  Object.assign(formData, {
    project: null,
    item: null,
    production_date: new Date().toISOString().slice(0, 10),
    quantity: 1,
    source_batches: [],
    remarks: ''
  })
  dialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    await request.post('/production/product-lots/', formData)
    ElMessage.success('创建成功')
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error('创建失败')
  } finally {
    submitLoading.value = false
  }
}

const scanBarcode = () => {
  ElMessage.info('请使用扫码枪扫描条码')
}

const exportTrace = () => {
  if (!selectedBatch.value) {
    ElMessage.warning('请先选择批次')
    return
  }
  ElMessage.success('正在生成追溯报告...')
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  return dateStr.replace('T', ' ').slice(0, 19)
}

const getStatusType = (status) => {
  const types = {
    ACTIVE: '',
    COMPLETED: 'info',
    HOLD: 'danger',
    RELEASED: 'success',
    SCRAPPED: 'info'
  }
  return types[status] || ''
}

const getOperationType = (type) => {
  const types = {
    CREATE: 'primary',
    PRODUCE: '',
    INSPECT: 'warning',
    PACK: 'info',
    SHIP: 'success',
    INSTALL: 'success',
    REWORK: 'warning',
    SCRAP: 'danger'
  }
  return types[type] || ''
}

onMounted(() => {
  fetchList()
  fetchProjects()
  fetchItems()
})
</script>

<style scoped>
.traceability-container {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.search-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.trace-card {
  height: calc(100vh - 300px);
  overflow-y: auto;
}

.trace-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-trace {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.op-content {
  padding: 4px 0;
}

.op-type {
  font-weight: 500;
}

.op-operator, .op-result {
  font-size: 12px;
  color: #909399;
}

.material-list, .quality-list {
  max-height: 200px;
  overflow-y: auto;
}

.material-item {
  padding: 8px 0;
  border-bottom: 1px solid #ebeef5;
}

.mat-batch {
  font-weight: 500;
  font-size: 13px;
}

.mat-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #606266;
}

.mat-supplier {
  font-size: 12px;
  color: #909399;
}

.quality-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

.qr-item {
  flex: 1;
  font-size: 13px;
}

.qr-value {
  font-size: 12px;
  color: #909399;
}
</style>
