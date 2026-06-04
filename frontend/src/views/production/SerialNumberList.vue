<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>序列号管理与追溯</span>
          <div>
            <el-button type="success" @click="handleBatchGenerate">
              <el-icon><Collection /></el-icon> 批量生成
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 快速搜索 -->
      <el-card class="search-card" shadow="never">
        <el-input
          v-model="quickSearch"
          placeholder="输入序列号、批次号、物料名称快速搜索（至少3个字符）"
          size="large"
          clearable
          @keyup.enter="handleQuickSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
          <template #append>
            <el-button type="primary" @click="handleQuickSearch">追溯查询</el-button>
          </template>
        </el-input>
      </el-card>
      
      <!-- 统计卡片 -->
      <el-row :gutter="20" class="stats-row">
        <el-col :span="4">
          <el-statistic title="序列号总数" :value="stats.total" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="已生成" :value="stats.generated" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="生产中" :value="stats.in_production" :value-style="{ color: '#409eff' }" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="已完工" :value="stats.completed" :value-style="{ color: '#67c23a' }" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="已发货" :value="stats.delivered" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="已安装" :value="stats.installed" />
        </el-col>
      </el-row>
      
      <!-- 搜索栏 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="物料">
          <el-select v-model="searchForm.item" placeholder="选择物料" clearable filterable>
            <el-option v-for="i in items" :key="i.id" :label="`${i.sku} - ${i.name}`" :value="i.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目">
          <el-select v-model="searchForm.project" placeholder="选择项目" clearable filterable>
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable>
            <el-option label="已生成" value="GENERATED" />
            <el-option label="已分配" value="ASSIGNED" />
            <el-option label="生产中" value="IN_PRODUCTION" />
            <el-option label="已完工" value="COMPLETED" />
            <el-option label="已发货" value="DELIVERED" />
            <el-option label="已安装" value="INSTALLED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>
      
      <!-- 数据表格 -->
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" stripe @row-click="handleRowClick" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="serial_number" label="序列号" width="180">
          <template #default="{ row }">
            <el-link type="primary" @click.stop="handleTrace(row)">{{ row.serial_number }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="batch_no" label="批次号" width="120" />
        <el-table-column prop="item_sku" label="物料编码" width="120" />
        <el-table-column prop="item_name" label="物料名称" min-width="180" />
        <el-table-column prop="project_code" label="项目" width="120" />
        <el-table-column prop="customer_name" label="客户" width="120" />
        <el-table-column prop="production_date" label="生产日期" width="110" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="handleTrace(row)">追溯</el-button>
            <el-button type="primary" link size="small" @click.stop="handleAddTrace(row)">记录</el-button>
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
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 20px;"
      />
    </el-card>
    
    <!-- 批量生成对话框 -->
    <el-dialog v-model="generateDialogVisible" title="批量生成序列号" width="500px">
      <el-form :model="generateForm" :rules="generateRules" ref="generateFormRef" label-width="100px">
        <el-form-item label="序列号规则" prop="rule_id">
          <el-select v-model="generateForm.rule_id" placeholder="选择规则" style="width: 100%;">
            <el-option v-for="r in snRules" :key="r.id" :label="`${r.code} - ${r.name}`" :value="r.id">
              <span>{{ r.code }} - {{ r.name }}</span>
              <span style="color: #999; font-size: 12px; margin-left: 10px;">示例: {{ r.example_sn }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="物料" prop="item_id">
          <el-select v-model="generateForm.item_id" placeholder="选择物料" style="width: 100%;" filterable>
            <el-option v-for="i in items" :key="i.id" :label="`${i.sku} - ${i.name}`" :value="i.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目">
          <el-select v-model="generateForm.project_id" placeholder="选择项目（可选）" style="width: 100%;" clearable filterable>
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="批次号">
          <el-input v-model="generateForm.batch_no" placeholder="批次号（可选）" />
        </el-form-item>
        <el-form-item label="数量" prop="quantity">
          <el-input-number v-model="generateForm.quantity" :min="1" :max="100" style="width: 100%;" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleGenerate">生成</el-button>
      </template>
    </el-dialog>
    
    <!-- 追溯详情对话框 -->
    <el-dialog v-model="traceDialogVisible" title="序列号追溯" width="900px">
      <div v-if="traceData">
        <!-- 基本信息 -->
        <el-descriptions title="基本信息" :column="3" border>
          <el-descriptions-item label="序列号">{{ traceData.serial_number?.serial_number }}</el-descriptions-item>
          <el-descriptions-item label="批次号">{{ traceData.serial_number?.batch_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(traceData.serial_number?.status)">{{ traceData.serial_number?.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="物料编码">{{ traceData.serial_number?.item_sku }}</el-descriptions-item>
          <el-descriptions-item label="物料名称">{{ traceData.serial_number?.item_name }}</el-descriptions-item>
          <el-descriptions-item label="项目">{{ traceData.serial_number?.project_name || '-' }}</el-descriptions-item>
        </el-descriptions>
        
        <!-- 追溯时间线 -->
        <el-divider>追溯时间线</el-divider>
        <el-timeline>
          <el-timeline-item
            v-for="record in traceData.timeline"
            :key="record.id"
            :timestamp="formatDate(record.operation_time)"
            :type="getTimelineType(record.operation)"
            placement="top"
          >
            <el-card shadow="hover">
              <div class="timeline-content">
                <el-tag size="small" :type="getTimelineType(record.operation)">{{ record.operation_display }}</el-tag>
                <span class="timeline-desc">{{ record.description }}</span>
              </div>
              <div class="timeline-meta" v-if="record.operator_name || record.location">
                <span v-if="record.operator_name">操作人: {{ record.operator_name }}</span>
                <span v-if="record.location">地点: {{ record.location }}</span>
              </div>
              <div class="timeline-meta" v-if="record.related_doc_no">
                关联单据: {{ record.related_doc_type }} - {{ record.related_doc_no }}
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        
        <!-- 组件绑定 -->
        <div v-if="traceData.components?.children?.length > 0">
          <el-divider>子组件</el-divider>
          <el-table :data="traceData.components.children" size="small">
            <el-table-column prop="child_sn_no" label="组件序列号" />
            <el-table-column prop="child_item_name" label="组件名称" />
            <el-table-column prop="position" label="安装位置" />
            <el-table-column prop="binding_time" label="绑定时间">
              <template #default="{ row }">
                {{ formatDate(row.binding_time) }}
              </template>
            </el-table-column>
          </el-table>
        </div>
        
        <!-- 质量汇总 -->
        <div v-if="traceData.quality_summary">
          <el-divider>质量检验汇总</el-divider>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-statistic title="检验次数" :value="traceData.quality_summary.inspection_count" />
            </el-col>
            <el-col :span="8">
              <el-statistic title="通过次数" :value="traceData.quality_summary.pass_count" :value-style="{ color: '#67c23a' }" />
            </el-col>
            <el-col :span="8">
              <el-statistic title="不通过次数" :value="traceData.quality_summary.fail_count" :value-style="{ color: '#f56c6c' }" />
            </el-col>
          </el-row>
        </div>
      </div>
      <template #footer>
        <el-button @click="traceDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="printTrace">打印</el-button>
      </template>
    </el-dialog>
    
    <!-- 添加追溯记录对话框 -->
    <el-dialog v-model="addTraceDialogVisible" title="添加追溯记录" width="500px">
      <el-form :model="traceForm" :rules="traceRules" ref="traceFormRef" label-width="100px">
        <el-form-item label="操作类型" prop="operation">
          <el-select v-model="traceForm.operation" placeholder="选择操作类型" style="width: 100%;">
            <el-option label="分配" value="ASSIGN" />
            <el-option label="开始生产" value="PRODUCTION_START" />
            <el-option label="完成生产" value="PRODUCTION_COMPLETE" />
            <el-option label="工序完成" value="PROCESS_COMPLETE" />
            <el-option label="质量检验" value="INSPECTION" />
            <el-option label="返工" value="REWORK" />
            <el-option label="包装" value="PACKAGING" />
            <el-option label="发货" value="DELIVERY" />
            <el-option label="安装" value="INSTALLATION" />
            <el-option label="维护" value="MAINTENANCE" />
            <el-option label="转移" value="TRANSFER" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作描述" prop="description">
          <el-input v-model="traceForm.description" type="textarea" :rows="3" placeholder="操作描述" />
        </el-form-item>
        <el-form-item label="操作地点">
          <el-input v-model="traceForm.location" placeholder="操作地点（可选）" />
        </el-form-item>
        <el-form-item label="关联单据类型">
          <el-input v-model="traceForm.related_doc_type" placeholder="如: 生产计划、发货单" />
        </el-form-item>
        <el-form-item label="关联单据号">
          <el-input v-model="traceForm.related_doc_no" placeholder="关联单据号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addTraceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitTrace">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Collection, Search } from '@element-plus/icons-vue'
import { getItemList } from '@/api/masterdata'
import { getProjectList } from '@/api/projects/project'
import {
getSerialNumbers, getSerialNumberStatistics, searchSerialNumbers,
  generateSerialNumberBatch, getSerialNumberFullTrace, addSerialNumberTrace, getSnRules
} from '@/api/production'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/production/serial-numbers/', { onSuccess: () => loadData() })


const loading = ref(false)
const tableData = ref<any[]>([])
const projects = ref<any[]>([])
const items = ref<any[]>([])
const snRules = ref<any[]>([])
const quickSearch = ref('')
const generateDialogVisible = ref(false)
const traceDialogVisible = ref(false)
const addTraceDialogVisible = ref(false)
const generateFormRef = ref(null)
const traceFormRef = ref(null)
const traceData = ref(null)
const currentSN = ref(null)

const stats = reactive({
  total: 0,
  generated: 0,
  in_production: 0,
  completed: 0,
  delivered: 0,
  installed: 0
})

const searchForm = reactive({
  item: null,
  project: null,
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const generateForm = reactive({
  rule_id: null,
  item_id: null,
  project_id: null,
  batch_no: '',
  quantity: 1
})

const generateRules = {
  rule_id: [{ required: true, message: '请选择序列号规则', trigger: 'change' }],
  item_id: [{ required: true, message: '请选择物料', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }]
}

const traceForm = reactive({
  operation: '',
  description: '',
  location: '',
  related_doc_type: '',
  related_doc_no: ''
})

const traceRules = {
  operation: [{ required: true, message: '请选择操作类型', trigger: 'change' }],
  description: [{ required: true, message: '请输入操作描述', trigger: 'blur' }]
}

const getStatusType = (status) => {
  const types = {
    'GENERATED': 'info',
    'ASSIGNED': 'info',
    'IN_PRODUCTION': 'warning',
    'COMPLETED': 'success',
    'DELIVERED': 'success',
    'INSTALLED': 'success',
    'RETURNED': 'warning',
    'SCRAPPED': 'danger'
  }
  return types[status] || 'info'
}

const getTimelineType = (operation) => {
  const types = {
    'GENERATE': 'primary',
    'ASSIGN': 'info',
    'PRODUCTION_START': 'warning',
    'PRODUCTION_COMPLETE': 'success',
    'PROCESS_COMPLETE': 'success',
    'INSPECTION': 'primary',
    'REWORK': 'warning',
    'PACKAGING': 'info',
    'DELIVERY': 'success',
    'INSTALLATION': 'success',
    'MAINTENANCE': 'warning',
    'RETURN': 'danger',
    'SCRAP': 'danger'
  }
  return types[operation] || 'info'
}

const formatDate = (date) => {
  if (!date) return ''
  return new Date(date).toLocaleString('zh-CN')
}

const loadData = async () => {
  try {
    loading.value = true
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const res = await getSerialNumbers(params)
    tableData.value = res.results || res
    pagination.total = res.count || tableData.value.length
  } catch (error) {
    console.error('加载数据失败:', error)
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const res = await getSerialNumberStatistics()
    stats.total = res.total || 0
    stats.generated = res.by_status?.GENERATED?.count || 0
    stats.in_production = res.by_status?.IN_PRODUCTION?.count || 0
    stats.completed = res.by_status?.COMPLETED?.count || 0
    stats.delivered = res.by_status?.DELIVERED?.count || 0
    stats.installed = res.by_status?.INSTALLED?.count || 0
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjectList({ page_size: 1000 })
    projects.value = res.results || res
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const loadItems = async () => {
  try {
    const res = await getItemList({ page_size: 1000 })
    items.value = res.results || res
  } catch (error) {
    console.error('加载物料失败:', error)
  }
}

const loadSNRules = async () => {
  try {
    const res = await getSnRules({ is_active: true, page_size: 100 })
    snRules.value = res.results || res
  } catch (error) {
    console.error('加载规则失败:', error)
  }
}

const resetSearch = () => {
  searchForm.item = null
  searchForm.project = null
  searchForm.status = ''
  pagination.page = 1
  loadData()
}

const handleQuickSearch = async () => {
  if (quickSearch.value.length < 3) {
    ElMessage.warning('请输入至少3个字符')
    return
  }
  try {
    const res = await searchSerialNumbers({ q: quickSearch.value })
    tableData.value = res
    pagination.total = res.length
  } catch (error) {
    console.error('搜索失败:', error)
  }
}

const handleRowClick = (row) => {
  handleTrace(row)
}

const handleBatchGenerate = () => {
  generateForm.rule_id = null
  generateForm.item_id = null
  generateForm.project_id = null
  generateForm.batch_no = ''
  generateForm.quantity = 1
  generateDialogVisible.value = true
}

const handleGenerate = async () => {
  try {
    await generateFormRef.value.validate()
    const res = await generateSerialNumberBatch(generateForm)
    ElMessage.success(res.message || '生成成功')
    generateDialogVisible.value = false
    loadData()
    loadStats()
  } catch (error) {
    console.error('生成失败:', error)
  }
}

const handleTrace = async (row) => {
  try {
    const res = await getSerialNumberFullTrace(row.id)
    traceData.value = res
    traceDialogVisible.value = true
  } catch (error) {
    console.error('获取追溯信息失败:', error)
  }
}

const handleAddTrace = (row) => {
  currentSN.value = row
  traceForm.operation = ''
  traceForm.description = ''
  traceForm.location = ''
  traceForm.related_doc_type = ''
  traceForm.related_doc_no = ''
  addTraceDialogVisible.value = true
}

const handleSubmitTrace = async () => {
  try {
    await traceFormRef.value.validate()
    await addSerialNumberTrace(currentSN.value.id, traceForm)
    ElMessage.success('记录添加成功')
    addTraceDialogVisible.value = false
    loadData()
  } catch (error) {
    console.error('添加失败:', error)
  }
}

const printTrace = () => {
  window.print()
}

onMounted(() => {
  loadData()
  loadStats()
  loadProjects()
  loadItems()
  loadSNRules()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-card {
  margin-bottom: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

.search-card :deep(.el-input__wrapper) {
  background: white;
}

.stats-row {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.search-form {
  margin-bottom: 20px;
}

.timeline-content {
  display: flex;
  align-items: center;
  gap: 10px;
}

.timeline-desc {
  color: #666;
}

.timeline-meta {
  margin-top: 8px;
  font-size: 12px;
  color: #999;
}

.timeline-meta span {
  margin-right: 15px;
}
</style>
