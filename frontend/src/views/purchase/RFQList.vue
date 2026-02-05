<template>
  <div class="rfq-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>询价单管理</span>
          <div class="header-actions">
            <el-dropdown @command="handleQuickCreate" style="margin-right: 10px;">
              <el-button type="success">
                快速创建 <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="from-bom">从项目BOM创建</el-dropdown-item>
                  <el-dropdown-item command="from-template">从模板创建</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button type="primary" @click="handleCreate">
              <el-icon><Plus /></el-icon>
              新建询价单
            </el-button>
          </div>
        </div>
      </template>

      <!-- 操作提示 -->
      <el-alert 
        type="info" 
        :closable="false" 
        style="margin-bottom: 20px;"
      >
        <template #title>
          <strong>新询价流程说明</strong>
        </template>
        <template #default>
          <div style="line-height: 1.8;">
            <p>1. 在<strong>「项目BOM」</strong>页面筛选物料，导出物料需求清单</p>
            <p>2. 线下向供应商询价，填写单价、供应商、付款方式等信息</p>
            <p>3. 在<strong>「采购申请」</strong>页面导入已询价的清单，自动生成采购申请</p>
          </div>
        </template>
      </el-alert>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="询价单号">
          <el-input v-model="searchForm.rfq_no" placeholder="请输入询价单号" clearable />
        </el-form-item>
        <el-form-item label="询价类型">
          <el-select v-model="searchForm.rfq_type" placeholder="全部类型" clearable>
            <el-option label="常规询价" value="NORMAL" />
            <el-option label="样件询价" value="SAMPLE" />
            <el-option label="批量询价" value="BATCH" />
            <el-option label="紧急询价" value="URGENT" />
            <el-option label="框架协议" value="FRAMEWORK" />
          </el-select>
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

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <!-- 数据表格 -->
      <el-table :data="tableData" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="rfq_no" label="询价单号" width="150" />
        <el-table-column prop="project_name" label="项目" min-width="120">
          <template #default="{ row }">
            {{ row.project_name || '无项目' }}
          </template>
        </el-table-column>
        <el-table-column prop="rfq_type_display" label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getRFQTypeColor(row.rfq_type)" size="small">
              {{ row.rfq_type_display || row.rfq_type || '常规' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority_display" label="优先级" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="getPriorityColor(row.priority)" size="small" v-if="row.priority !== 'NORMAL'">
              {{ row.priority_display || row.priority }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="物料/供应商" width="100" align="center">
          <template #default="{ row }">
            <span>{{ row.line_count || row.lines?.length || 0 }}</span>
            <span class="text-muted">/</span>
            <span>{{ row.supplier_count || row.supplier_rfqs?.length || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="附件" width="60" align="center">
          <template #default="{ row }">
            <el-badge v-if="row.attachment_count > 0" :value="row.attachment_count" type="info" />
            <span v-else>-</span>
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
              v-if="canDelete && row.status === 'DRAFT'" 
              type="danger" size="small" link 
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
    
    <!-- 导入已报价BOM对话框 -->
    <el-dialog v-model="quoteImportDialogVisible" title="导入已报价BOM" width="550px">
      <el-alert
        title="导入说明"
        type="warning"
        show-icon
        :closable="false"
        style="margin-bottom: 15px;"
      >
        <template #default>
          <div>1. 请先导出询价BOM清单，将报价信息填写完整后再导入</div>
          <div>2. 物料编码必须与项目BOM清单中的物料编码一致</div>
          <div>3. 含税单价或未税单价至少填写一项</div>
          <div>4. 导入成功后，物料将标记为"已询价"状态</div>
        </template>
      </el-alert>
      
      <el-upload
        ref="quoteUploadRef"
        class="upload-area"
        drag
        action="#"
        :auto-upload="false"
        :limit="1"
        :on-change="handleQuoteFileChange"
        :on-exceed="handleQuoteFileExceed"
        accept=".xlsx,.xls"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将已报价的Excel文件拖到此处，或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">只支持 .xlsx 或 .xls 格式文件</div>
        </template>
      </el-upload>
      
      <template #footer>
        <el-button @click="handleExportQuoteBOM">先导出询价BOM</el-button>
        <el-button @click="quoteImportDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmQuoteImport" :loading="quoteImporting" :disabled="!quoteImportFile">
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <!-- 从项目BOM创建询价单对话框 -->
    <el-dialog v-model="bomRFQDialogVisible" title="从项目BOM创建询价单" width="900px" destroy-on-close>
      <el-form :model="bomRFQForm" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="选择项目" required>
              <el-select v-model="bomRFQForm.project_id" placeholder="选择项目" filterable style="width: 100%"
                @change="loadProjectBOM">
                <el-option
                  v-for="project in projects"
                  :key="project.id"
                  :label="`${project.code} - ${project.name}`"
                  :value="project.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="询价类型">
              <el-select v-model="bomRFQForm.rfq_type" style="width: 100%">
                <el-option label="常规询价" value="NORMAL" />
                <el-option label="样件询价" value="SAMPLE" />
                <el-option label="批量询价" value="BATCH" />
                <el-option label="紧急询价" value="URGENT" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="优先级">
              <el-select v-model="bomRFQForm.priority" style="width: 100%">
                <el-option label="低" value="LOW" />
                <el-option label="普通" value="NORMAL" />
                <el-option label="高" value="HIGH" />
                <el-option label="紧急" value="URGENT" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="报价截止">
              <el-date-picker
                v-model="bomRFQForm.deadline_days"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-checkbox v-model="bomRFQForm.auto_match_suppliers">自动匹配供应商</el-checkbox>
        </el-form-item>
      </el-form>

      <el-divider content-position="left">选择BOM物料</el-divider>
      
      <el-table 
        :data="projectBOMItems" 
        v-loading="bomLoading" 
        stripe 
        border 
        max-height="350"
        @selection-change="handleBOMSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="item_sku" label="物料编码" width="120" />
        <el-table-column prop="item_name" label="物料名称" min-width="150" />
        <el-table-column prop="planned_qty" label="需求数量" width="100" align="right" />
        <el-table-column prop="drawing_no" label="图号" width="120" />
        <el-table-column label="属性" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.is_critical" type="danger" size="small" style="margin-right: 4px;">关键</el-tag>
            <el-tag v-if="row.is_long_lead" type="warning" size="small">长周期</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="bom-selection-info" v-if="selectedBOMItems.length > 0">
        已选择 {{ selectedBOMItems.length }} 项物料
      </div>

      <template #footer>
        <el-button @click="bomRFQDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreateFromBOM" :disabled="selectedBOMItems.length === 0">
          创建询价单 ({{ selectedBOMItems.length }})
        </el-button>
      </template>
    </el-dialog>

    <!-- 从模板创建询价单对话框 -->
    <el-dialog v-model="templateRFQDialogVisible" title="从模板创建询价单" width="600px">
      <el-form :model="templateRFQForm" label-width="100px">
        <el-form-item label="选择模板" required>
          <el-select v-model="templateRFQForm.template_id" placeholder="选择模板" filterable style="width: 100%">
            <el-option
              v-for="template in rfqTemplates"
              :key="template.id"
              :label="`${template.name} (${template.items_count}项)`"
              :value="template.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关联项目">
          <el-select v-model="templateRFQForm.project_id" placeholder="选择项目" filterable clearable style="width: 100%">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="`${project.code} - ${project.name}`"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="templateRFQDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreateFromTemplate" :disabled="!templateRFQForm.template_id">
          创建询价单
        </el-button>
      </template>
    </el-dialog>

    <!-- 供应商匹配推荐对话框 -->
    <el-dialog v-model="supplierMatchDialogVisible" title="供应商匹配推荐" width="700px">
      <el-alert type="info" :closable="false" style="margin-bottom: 15px;">
        系统根据物料能力需求，自动匹配推荐供应商
      </el-alert>
      
      <el-table :data="matchedSuppliers" v-loading="matchLoading" stripe border>
        <el-table-column type="selection" width="50" />
        <el-table-column prop="supplier_name" label="供应商" min-width="150" />
        <el-table-column label="匹配度" width="120" align="center">
          <template #default="{ row }">
            <el-progress 
              :percentage="row.overall_score" 
              :format="() => row.overall_score + '%'"
              :stroke-width="6"
              :color="getMatchScoreColor(row.overall_score)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="coverage" label="物料覆盖" width="100" align="center">
          <template #default="{ row }">
            {{ row.coverage }}%
          </template>
        </el-table-column>
        <el-table-column prop="matched_items" label="匹配物料数" width="100" align="center" />
      </el-table>
      
      <template #footer>
        <el-button @click="supplierMatchDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="addMatchedSuppliers">
          添加选中供应商
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, ArrowDown, Download, Upload, UploadFilled, ShoppingCart, Document, List } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

const router = useRouter()

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能 - 使用箭头函数包装避免 TDZ 错误
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/purchase/rfqs/',
  { onSuccess: () => loadData(), confirmTitle: '删除询价单', confirmMessage: '确定要删除该询价单吗？' }
)

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

// 询价BOM导入导出相关
const selectedProject = ref(null)
const pendingQuoteCount = ref(0)
const quoteImportDialogVisible = ref(false)
const quoteImportFile = ref(null)
const quoteImporting = ref(false)
const quoteUploadRef = ref(null)

// 待询价物料相关
const activeCollapse = ref(['pending', 'purchasable'])
const pendingQuoteItems = ref([])
const pendingQuoteLoading = ref(false)

// 待采购申请物料相关
const purchasableItems = ref([])
const purchasableLoading = ref(false)
const selectedPurchasableItems = ref([])
const selectAllPurchasable = ref(false)

// 搜索
const searchForm = reactive({
  rfq_no: '',
  rfq_type: '',
  status: ''
})

// 从BOM创建询价
const bomRFQDialogVisible = ref(false)
const bomRFQForm = reactive({
  project_id: null,
  rfq_type: 'NORMAL',
  priority: 'NORMAL',
  deadline_days: '',
  auto_match_suppliers: true
})
const projectBOMItems = ref([])
const selectedBOMItems = ref([])
const bomLoading = ref(false)

// 从模板创建询价
const templateRFQDialogVisible = ref(false)
const templateRFQForm = reactive({
  template_id: null,
  project_id: null
})
const rfqTemplates = ref([])

// 供应商匹配
const supplierMatchDialogVisible = ref(false)
const matchedSuppliers = ref([])
const matchLoading = ref(false)

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
    const res = await request.get('/projects/projects/', { params: { page_size: 200 } })
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

// ========== 询价BOM导入导出功能 ==========

// 获取待询价数量
const fetchPendingQuoteCount = async () => {
  if (!selectedProject.value) {
    pendingQuoteCount.value = 0
    return
  }
  try {
    const res = await request.get('/projects/bom/pending_quote_count/', {
      params: { project: selectedProject.value }
    })
    pendingQuoteCount.value = res.data?.count || res.count || 0
  } catch (error) {
    console.error('获取待询价数量失败:', error)
    pendingQuoteCount.value = 0
  }
}

// 项目选择变化
const handleProjectChange = () => {
  fetchPendingQuoteCount()
  fetchPendingQuoteItems()
  fetchPurchasableItems()
}

// 获取待询价物料列表（未询价的）
const fetchPendingQuoteItems = async () => {
  if (!selectedProject.value) {
    pendingQuoteItems.value = []
    return
  }
  
  pendingQuoteLoading.value = true
  try {
    const res = await request.get('/projects/bom/', {
      params: { 
        project: selectedProject.value,
        quote_status: 'NOT_QUOTED',
        is_deleted: false
      }
    })
    const items = res.data?.results || res.results || res.data || []
    pendingQuoteItems.value = items.map(item => ({
      ...item,
      item_sku: item.item_sku || item.item?.sku,
      item_name: item.item_name || item.item?.name,
      specification: item.specification || item.item_specification || item.item?.specification,
      version_brand: item.version_brand || item.version_brand_display,
      unit: item.unit || item.item_unit,
      planned_qty: item.planned_qty,
      required_date: item.required_date
    }))
  } catch (error) {
    console.error('获取待询价物料失败:', error)
    pendingQuoteItems.value = []
  } finally {
    pendingQuoteLoading.value = false
  }
}

// 获取待采购申请物料列表
const fetchPurchasableItems = async () => {
  if (!selectedProject.value) {
    purchasableItems.value = []
    return
  }
  
  purchasableLoading.value = true
  try {
    const res = await request.get('/projects/bom/purchasable_items/', {
      params: { project: selectedProject.value }
    })
    purchasableItems.value = res.data?.items || res.items || []
  } catch (error) {
    console.error('获取待采购申请物料失败:', error)
    purchasableItems.value = []
  } finally {
    purchasableLoading.value = false
  }
}

// 待采购物料选择变化
const handlePurchasableSelectionChange = (selection) => {
  selectedPurchasableItems.value = selection
  selectAllPurchasable.value = selection.length === purchasableItems.value.length && purchasableItems.value.length > 0
}

// 全选/取消全选
const handleSelectAllPurchasable = (val) => {
  if (val) {
    selectedPurchasableItems.value = [...purchasableItems.value]
  } else {
    selectedPurchasableItems.value = []
  }
}

// 生成采购申请
const handleGeneratePR = async () => {
  if (selectedPurchasableItems.value.length === 0) {
    ElMessage.warning('请选择要生成采购申请的物料')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要为选中的 ${selectedPurchasableItems.value.length} 项物料生成采购申请吗？`,
      '生成采购申请',
      { type: 'warning' }
    )
    
    const itemIds = selectedPurchasableItems.value.map(item => item.item_id)
    
    const res = await request.post('/projects/bom/generate_purchase_request/', {
      project: selectedProject.value,
      item_ids: itemIds
    })
    
    const data = res.data || res
    ElMessage.success(data.message || '采购申请生成成功')
    
    // 刷新数据
    fetchPurchasableItems()
    fetchPendingQuoteCount()
    
    // 跳转到采购申请页面
    router.push('/purchase/requests')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('生成采购申请失败:', error)
      const errMsg = error.response?.data?.error || '生成采购申请失败'
      ElMessage.error(errMsg)
    }
  }
}

// 导出询价BOM
const handleExportQuoteBOM = async () => {
  if (!selectedProject.value) {
    ElMessage.warning('请先选择项目')
    return
  }
  
  if (!pendingQuoteCount.value) {
    ElMessage.warning('该项目没有待询价的物料')
    return
  }
  
  try {
    const response = await request.get('/projects/bom/export_quote_bom/', {
      params: { project: selectedProject.value },
      responseType: 'blob'
    })
    
    const blobData = response.data || response
    const blob = new Blob([blobData], { 
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
    })
    
    const project = projects.value.find(p => p.id === selectedProject.value)
    const projectCode = project?.code || selectedProject.value
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `询价BOM_${projectCode}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success(`导出成功，共 ${pendingQuoteCount.value} 项待询价物料`)
  } catch (error) {
    console.error('导出询价BOM失败:', error)
    ElMessage.error('导出询价BOM失败')
  }
}

// 打开导入对话框
const handleImportQuoteBOM = () => {
  if (!selectedProject.value) {
    ElMessage.warning('请先选择项目')
    return
  }
  quoteImportFile.value = null
  if (quoteUploadRef.value) {
    quoteUploadRef.value.clearFiles()
  }
  quoteImportDialogVisible.value = true
}

// 文件变化
const handleQuoteFileChange = (file) => {
  quoteImportFile.value = file.raw
}

// 文件超出限制
const handleQuoteFileExceed = () => {
  ElMessage.warning('只能上传一个文件，请先删除已选文件')
}

// 确认导入
const handleConfirmQuoteImport = async () => {
  if (!quoteImportFile.value) {
    ElMessage.warning('请选择要导入的文件')
    return
  }
  
  if (!selectedProject.value) {
    ElMessage.warning('请先选择项目')
    return
  }
  
  quoteImporting.value = true
  try {
    const formData = new FormData()
    formData.append('file', quoteImportFile.value)
    formData.append('project', String(selectedProject.value))
    
    const response = await request.post('/projects/bom/import_quote_bom/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    const data = response.data || response
    
    ElMessage.success(data.message || `询价导入成功，已更新 ${data.updated} 条物料的报价信息`)
    quoteImportDialogVisible.value = false
    fetchPendingQuoteCount()
  } catch (error) {
    console.error('询价导入失败:', error)
    const errData = error.response?.data
    if (errData?.errors?.length) {
      const preview = errData.errors.slice(0, 3).map(e => `行${e.row}: ${e.error}`).join('；')
      ElMessage.error(`导入失败: ${errData.error || preview}`)
    } else {
      ElMessage.error(errData?.error || '询价导入失败')
    }
  } finally {
    quoteImporting.value = false
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
  searchForm.rfq_type = ''
  searchForm.status = ''
  pagination.page = 1
  loadData()
}

// 询价类型颜色
const getRFQTypeColor = (type) => {
  const colors = {
    'NORMAL': 'info',
    'SAMPLE': 'primary',
    'BATCH': 'success',
    'URGENT': 'danger',
    'FRAMEWORK': 'warning'
  }
  return colors[type] || 'info'
}

// 优先级颜色
const getPriorityColor = (priority) => {
  const colors = {
    'LOW': 'info',
    'NORMAL': '',
    'HIGH': 'warning',
    'URGENT': 'danger'
  }
  return colors[priority] || ''
}

// 匹配得分颜色
const getMatchScoreColor = (score) => {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

// 快速创建菜单
const handleQuickCreate = async (command) => {
  if (command === 'from-bom') {
    await loadProjects()
    bomRFQForm.project_id = null
    bomRFQForm.rfq_type = 'NORMAL'
    bomRFQForm.priority = 'NORMAL'
    bomRFQForm.auto_match_suppliers = true
    projectBOMItems.value = []
    selectedBOMItems.value = []
    bomRFQDialogVisible.value = true
  } else if (command === 'from-template') {
    await loadProjects()
    await loadRFQTemplates()
    templateRFQForm.template_id = null
    templateRFQForm.project_id = null
    templateRFQDialogVisible.value = true
  }
}

// 加载项目BOM
const loadProjectBOM = async () => {
  if (!bomRFQForm.project_id) {
    projectBOMItems.value = []
    return
  }
  
  bomLoading.value = true
  try {
    const res = await request.get('/projects/bom/', {
      params: { 
        project: bomRFQForm.project_id, 
        is_deleted: false,
        page_size: 500
      }
    })
    const items = res.results || res || []
    projectBOMItems.value = items.map(item => ({
      ...item,
      item_sku: item.item_sku || item.item?.sku,
      item_name: item.item_name || item.item?.name,
      is_critical: item.is_critical || false,
      is_long_lead: item.is_long_lead || false
    }))
  } catch (error) {
    console.error('加载项目BOM失败:', error)
    projectBOMItems.value = []
  } finally {
    bomLoading.value = false
  }
}

// BOM选择变化
const handleBOMSelectionChange = (selection) => {
  selectedBOMItems.value = selection
}

// 从BOM创建询价单
const handleCreateFromBOM = async () => {
  if (selectedBOMItems.value.length === 0) {
    ElMessage.warning('请选择要询价的物料')
    return
  }
  
  try {
    const bomItemIds = selectedBOMItems.value.map(item => item.id)
    
    const res = await request.post('/purchase/rfqs/create-from-bom/', {
      project_id: bomRFQForm.project_id,
      bom_item_ids: bomItemIds,
      rfq_type: bomRFQForm.rfq_type,
      priority: bomRFQForm.priority,
      deadline_days: 7,
      auto_match_suppliers: bomRFQForm.auto_match_suppliers
    })
    
    ElMessage.success(`询价单 ${res.rfq_no} 创建成功`)
    bomRFQDialogVisible.value = false
    loadData()
  } catch (error) {
    console.error('创建询价单失败:', error)
    ElMessage.error(error.response?.data?.error || '创建失败')
  }
}

// 加载询价模板
const loadRFQTemplates = async () => {
  try {
    const res = await request.get('/purchase/rfq-templates/', { params: { page_size: 100 } })
    rfqTemplates.value = res.results || res || []
  } catch (error) {
    console.error('加载询价模板失败:', error)
  }
}

// 从模板创建询价单
const handleCreateFromTemplate = async () => {
  if (!templateRFQForm.template_id) {
    ElMessage.warning('请选择模板')
    return
  }
  
  try {
    const res = await request.post('/purchase/rfqs/create-from-template/', {
      template_id: templateRFQForm.template_id,
      project_id: templateRFQForm.project_id
    })
    
    ElMessage.success(`询价单 ${res.rfq_no} 创建成功`)
    templateRFQDialogVisible.value = false
    loadData()
  } catch (error) {
    console.error('创建询价单失败:', error)
    ElMessage.error(error.response?.data?.error || '创建失败')
  }
}

// 打开供应商匹配对话框
const openSupplierMatch = async (rfq) => {
  currentRFQ.value = rfq
  matchLoading.value = true
  supplierMatchDialogVisible.value = true
  
  try {
    const res = await request.get(`/purchase/rfqs/${rfq.id}/match-suppliers/`)
    matchedSuppliers.value = res.recommended_suppliers || []
  } catch (error) {
    console.error('匹配供应商失败:', error)
    matchedSuppliers.value = []
  } finally {
    matchLoading.value = false
  }
}

// 添加匹配的供应商
const addMatchedSuppliers = () => {
  // 将匹配的供应商添加到已选择列表
  const matchedIds = matchedSuppliers.value.filter(s => s.selected).map(s => s.supplier_id)
  if (matchedIds.length > 0) {
    selectedSuppliers.value = [...new Set([...selectedSuppliers.value, ...matchedIds])]
  }
  supplierMatchDialogVisible.value = false
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
// handleDelete 已被 useBatchDelete 的 deleteRow 替代

onMounted(() => {
  loadData()
  loadProjects()  // 加载项目列表用于询价BOM导入导出
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

.header-actions {
  display: flex;
  align-items: center;
}

.search-form {
  margin-bottom: 16px;
}

.text-danger {
  color: #f56c6c;
}

.text-muted {
  color: #999;
}

.tip-box {
  padding: 10px 0;
}

.upload-area {
  width: 100%;
}

.upload-area :deep(.el-upload) {
  width: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  width: 100%;
}

.bom-selection-info {
  margin-top: 10px;
  padding: 8px 12px;
  background: #f0f9eb;
  border-radius: 4px;
  color: #67c23a;
  font-weight: 500;
}

.table-toolbar {
  margin-bottom: 10px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>

