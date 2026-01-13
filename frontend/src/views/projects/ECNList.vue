<template>
  <div class="ecn-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>工程变更管理 (ECN)</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新建ECN
          </el-button>
        </div>
      </template>

      <!-- 搜索区域 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="项目">
          <el-select v-model="searchForm.project" placeholder="选择项目" clearable style="width: 200px">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="`${project.code} - ${project.name}`"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="变更类型">
          <el-select v-model="searchForm.change_type" placeholder="选择类型" clearable style="width: 120px">
            <el-option label="设计变更" value="DESIGN" />
            <el-option label="工艺变更" value="PROCESS" />
            <el-option label="材料替换" value="MATERIAL" />
            <el-option label="规格变更" value="SPEC" />
            <el-option label="图纸变更" value="DRAWING" />
            <el-option label="其他变更" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 120px">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="待评审" value="PENDING" />
            <el-option label="评审中" value="REVIEWING" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已拒绝" value="REJECTED" />
            <el-option label="实施中" value="IMPLEMENTING" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="searchForm.priority" placeholder="选择优先级" clearable style="width: 100px">
            <el-option label="紧急" value="URGENT" />
            <el-option label="高" value="HIGH" />
            <el-option label="中" value="MEDIUM" />
            <el-option label="低" value="LOW" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadECNList">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <!-- 表格 -->
      <el-table :data="ecnList" v-loading="loading" border stripe @selection-change="handleSelectionChange">
        <el-table-column v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="ecn_no" label="ECN编号" width="160" fixed />
        <el-table-column prop="title" label="变更标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="project_code" label="项目编号" width="120" />
        <el-table-column prop="change_type_display" label="变更类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getChangeTypeTagType(row.change_type)" size="small">
              {{ row.change_type_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority_display" label="优先级" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="getPriorityTagType(row.priority)" size="small">
              {{ row.priority_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="items_count" label="变更项" width="80" align="center" />
        <el-table-column prop="requested_by_name" label="申请人" width="100" />
        <el-table-column prop="requested_date" label="申请日期" width="110" />
        <el-table-column prop="approved_date" label="批准日期" width="110" />
        <el-table-column label="操作" width="380" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="primary" @click="handleSubmit(row)" v-if="row.status === 'DRAFT'">提交审批</el-button>
            <el-button size="small" type="info" @click="viewWorkflow(row)" v-if="row.status === 'PENDING' || row.status === 'REVIEWING'">审批进度</el-button>
            <el-button size="small" type="warning" @click="handleImplement(row)" v-if="row.status === 'APPROVED'">开始实施</el-button>
            <el-button size="small" type="success" @click="handleComplete(row)" v-if="row.status === 'IMPLEMENTING'">完成</el-button>
            <el-button v-if="canDelete && row.status === 'DRAFT'" size="small" type="danger" @click="deleteRow(row)" :loading="deleteLoading">删除</el-button>
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
        style="margin-top: 20px; justify-content: flex-end;"
        @size-change="loadECNList"
        @current-change="loadECNList"
      />
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑ECN' : '新建ECN'"
      width="900px"
      destroy-on-close
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目" prop="project">
              <el-select v-model="form.project" placeholder="选择项目" style="width: 100%">
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
            <el-form-item label="变更标题" prop="title">
              <el-input v-model="form.title" placeholder="请输入变更标题" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="变更类型" prop="change_type">
              <el-select v-model="form.change_type" placeholder="选择类型" style="width: 100%">
                <el-option label="设计变更" value="DESIGN" />
                <el-option label="工艺变更" value="PROCESS" />
                <el-option label="材料替换" value="MATERIAL" />
                <el-option label="规格变更" value="SPEC" />
                <el-option label="图纸变更" value="DRAWING" />
                <el-option label="其他变更" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="form.priority" placeholder="选择优先级" style="width: 100%">
                <el-option label="紧急" value="URGENT" />
                <el-option label="高" value="HIGH" />
                <el-option label="中" value="MEDIUM" />
                <el-option label="低" value="LOW" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="申请日期" prop="requested_date">
              <el-date-picker
                v-model="form.requested_date"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="变更原因" prop="reason">
          <el-input v-model="form.reason" type="textarea" :rows="2" placeholder="请输入变更原因" />
        </el-form-item>
        <el-form-item label="变更描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请详细描述变更内容" />
        </el-form-item>
        <el-form-item label="影响分析">
          <el-input v-model="form.impact_analysis" type="textarea" :rows="2" placeholder="请分析此变更对项目的影响" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="成本影响">
              <el-input-number v-model="form.cost_impact" :precision="2" :step="100" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="进度影响">
              <el-input v-model="form.schedule_impact" placeholder="如：延期2周" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 变更明细 -->
        <el-divider content-position="left">变更明细</el-divider>
        <el-button type="primary" size="small" @click="addItem" style="margin-bottom: 10px;">
          <el-icon><Plus /></el-icon>
          添加变更项
        </el-button>
        <el-table :data="form.items" border size="small">
          <el-table-column prop="change_type" label="操作类型" width="120">
            <template #default="{ row, $index }">
              <el-select v-model="row.change_type" size="small" @change="onItemChangeTypeChange(row)">
                <el-option label="新增" value="ADD" />
                <el-option label="删除" value="DELETE" />
                <el-option label="修改" value="MODIFY" />
                <el-option label="替换" value="REPLACE" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="原物料" width="200">
            <template #default="{ row }">
              <el-select
                v-model="row.item"
                filterable
                remote
                :remote-method="searchItems"
                placeholder="搜索物料"
                size="small"
                clearable
                :disabled="row.change_type === 'ADD'"
                style="width: 100%"
              >
                <el-option
                  v-for="item in itemOptions"
                  :key="item.id"
                  :label="`${item.sku} - ${item.name}`"
                  :value="item.id"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="新物料" width="200" v-if="hasReplaceItem">
            <template #default="{ row }">
              <el-select
                v-model="row.new_item"
                filterable
                remote
                :remote-method="searchItems"
                placeholder="搜索物料"
                size="small"
                clearable
                :disabled="row.change_type !== 'REPLACE' && row.change_type !== 'ADD'"
                style="width: 100%"
              >
                <el-option
                  v-for="item in itemOptions"
                  :key="item.id"
                  :label="`${item.sku} - ${item.name}`"
                  :value="item.id"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="原数量" width="100">
            <template #default="{ row }">
              <el-input-number v-model="row.old_qty" :min="0" size="small" :disabled="row.change_type === 'ADD'" controls-position="right" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="新数量" width="100">
            <template #default="{ row }">
              <el-input-number v-model="row.new_qty" :min="0" size="small" :disabled="row.change_type === 'DELETE'" controls-position="right" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="150">
            <template #default="{ row }">
              <el-input v-model="row.notes" size="small" placeholder="备注" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60" fixed="right">
            <template #default="{ $index }">
              <el-button type="danger" size="small" :icon="Delete" circle @click="removeItem($index)" />
            </template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 查看详情对话框 -->
    <el-dialog v-model="detailVisible" title="ECN详情" width="900px">
      <template v-if="currentECN">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="ECN编号">{{ currentECN.ecn_no }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTagType(currentECN.status)">{{ currentECN.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="getPriorityTagType(currentECN.priority)">{{ currentECN.priority_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="项目">{{ currentECN.project_code }} - {{ currentECN.project_name }}</el-descriptions-item>
          <el-descriptions-item label="变更类型">{{ currentECN.change_type_display }}</el-descriptions-item>
          <el-descriptions-item label="申请日期">{{ currentECN.requested_date }}</el-descriptions-item>
          <el-descriptions-item label="变更标题" :span="3">{{ currentECN.title }}</el-descriptions-item>
          <el-descriptions-item label="变更原因" :span="3">{{ currentECN.reason }}</el-descriptions-item>
          <el-descriptions-item label="变更描述" :span="3">{{ currentECN.description }}</el-descriptions-item>
          <el-descriptions-item label="影响分析" :span="3">{{ currentECN.impact_analysis || '-' }}</el-descriptions-item>
          <el-descriptions-item label="成本影响">¥{{ currentECN.cost_impact }}</el-descriptions-item>
          <el-descriptions-item label="进度影响">{{ currentECN.schedule_impact || '-' }}</el-descriptions-item>
          <el-descriptions-item label="申请人">{{ currentECN.requested_by_name }}</el-descriptions-item>
          <el-descriptions-item label="批准人" v-if="currentECN.approved_by">{{ currentECN.approved_by_name }}</el-descriptions-item>
          <el-descriptions-item label="批准日期" v-if="currentECN.approved_date">{{ currentECN.approved_date }}</el-descriptions-item>
          <el-descriptions-item label="实施人" v-if="currentECN.implemented_by">{{ currentECN.implemented_by_name }}</el-descriptions-item>
          <el-descriptions-item label="实施日期" v-if="currentECN.implemented_date">{{ currentECN.implemented_date }}</el-descriptions-item>
          <el-descriptions-item label="实施说明" :span="3" v-if="currentECN.implementation_notes">{{ currentECN.implementation_notes }}</el-descriptions-item>
        </el-descriptions>

        <!-- 变更明细 -->
        <el-divider content-position="left">变更明细</el-divider>
        <el-table :data="currentECN.items" border size="small">
          <el-table-column prop="change_type_display" label="操作类型" width="100">
            <template #default="{ row }">
              <el-tag :type="getItemChangeTypeTagType(row.change_type)" size="small">
                {{ row.change_type_display }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="原物料" min-width="150">
            <template #default="{ row }">
              {{ row.item_sku ? `${row.item_sku} - ${row.item_name}` : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="新物料" min-width="150">
            <template #default="{ row }">
              {{ row.new_item_sku ? `${row.new_item_sku} - ${row.new_item_name}` : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="old_qty" label="原数量" width="80" align="right" />
          <el-table-column prop="new_qty" label="新数量" width="80" align="right" />
          <el-table-column prop="notes" label="备注" min-width="120" show-overflow-tooltip />
        </el-table>

        <!-- 审批记录 -->
        <el-divider content-position="left">审批记录</el-divider>
        <el-timeline>
          <el-timeline-item
            v-for="approval in currentECN.approvals"
            :key="approval.id"
            :timestamp="approval.created_at"
            placement="top"
          >
            <el-card>
              <h4>{{ approval.approver_name }} - {{ approval.action_display }}</h4>
              <p v-if="approval.comment">{{ approval.comment }}</p>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </template>
    </el-dialog>

    <!-- 审批意见对话框 -->
    <el-dialog v-model="approvalDialogVisible" :title="approvalDialogTitle" width="500px">
      <el-form>
        <el-form-item label="审批意见">
          <el-input v-model="approvalComment" type="textarea" :rows="3" placeholder="请输入审批意见" />
        </el-form-item>
        <el-form-item label="实施说明" v-if="approvalAction === 'complete'">
          <el-input v-model="implementationNotes" type="textarea" :rows="3" placeholder="请输入实施说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approvalDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmApproval" :loading="approving">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

const router = useRouter()

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/projects/ecns/',
  { onSuccess: () => loadECNList(), confirmTitle: '删除ECN', confirmMessage: '确定要删除该ECN吗？' }
)

// 数据
const loading = ref(false)
const saving = ref(false)
const approving = ref(false)
const ecnList = ref([])
const projects = ref([])
const itemOptions = ref([])
const dialogVisible = ref(false)
const detailVisible = ref(false)
const approvalDialogVisible = ref(false)
const isEdit = ref(false)
const currentECN = ref(null)
const formRef = ref(null)

// 搜索表单
const searchForm = reactive({
  project: null,
  change_type: '',
  status: '',
  priority: ''
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 表单
const form = reactive({
  id: null,
  project: null,
  title: '',
  change_type: 'DESIGN',
  priority: 'MEDIUM',
  requested_date: new Date().toISOString().split('T')[0],
  reason: '',
  description: '',
  impact_analysis: '',
  cost_impact: 0,
  schedule_impact: '',
  items: []
})

// 审批相关
const approvalAction = ref('')
const approvalComment = ref('')
const implementationNotes = ref('')
const approvalDialogTitle = ref('')
const approvalECN = ref(null)

// 表单验证规则
const rules = {
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  title: [{ required: true, message: '请输入变更标题', trigger: 'blur' }],
  change_type: [{ required: true, message: '请选择变更类型', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  requested_date: [{ required: true, message: '请选择申请日期', trigger: 'change' }],
  reason: [{ required: true, message: '请输入变更原因', trigger: 'blur' }],
  description: [{ required: true, message: '请输入变更描述', trigger: 'blur' }]
}

// 计算属性
const hasReplaceItem = computed(() => {
  return form.items.some(item => item.change_type === 'REPLACE' || item.change_type === 'ADD')
})

// 加载ECN列表
const loadECNList = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    // 过滤空值
    Object.keys(params).forEach(key => {
      if (params[key] === '' || params[key] === null) {
        delete params[key]
      }
    })
    
    const response = await request.get('/projects/ecn/', { params })
    const data = response.data || response
    ecnList.value = data.results || data
    pagination.total = data.count || ecnList.value.length
  } catch (error) {
    console.error('加载ECN列表失败:', error)
    ElMessage.error('加载ECN列表失败')
  } finally {
    loading.value = false
  }
}

// 加载项目列表
const loadProjects = async () => {
  try {
    const response = await request.get('/projects/projects/', { params: { page_size: 1000 } })
    const data = response.data || response
    projects.value = data.results || data
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

// 搜索物料
const searchItems = async (query) => {
  if (!query) {
    itemOptions.value = []
    return
  }
  try {
    const response = await request.get('/masterdata/items/', { params: { search: query, page_size: 20 } })
    const data = response.data || response
    itemOptions.value = data.results || data
  } catch (error) {
    console.error('搜索物料失败:', error)
  }
}

// 重置搜索
const resetSearch = () => {
  searchForm.project = null
  searchForm.change_type = ''
  searchForm.status = ''
  searchForm.priority = ''
  loadECNList()
}

// 重置表单
const resetForm = () => {
  form.id = null
  form.project = null
  form.title = ''
  form.change_type = 'DESIGN'
  form.priority = 'MEDIUM'
  form.requested_date = new Date().toISOString().split('T')[0]
  form.reason = ''
  form.description = ''
  form.impact_analysis = ''
  form.cost_impact = 0
  form.schedule_impact = ''
  form.items = []
}

// 新建ECN
const handleCreate = () => {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

// 编辑ECN
const handleEdit = async (row) => {
  isEdit.value = true
  try {
    const response = await request.get(`/projects/ecn/${row.id}/`)
    const data = response.data || response
    Object.assign(form, {
      id: data.id,
      project: data.project,
      title: data.title,
      change_type: data.change_type,
      priority: data.priority,
      requested_date: data.requested_date,
      reason: data.reason,
      description: data.description,
      impact_analysis: data.impact_analysis || '',
      cost_impact: data.cost_impact || 0,
      schedule_impact: data.schedule_impact || '',
      items: data.items.map(item => ({
        change_type: item.change_type,
        item: item.item,
        new_item: item.new_item,
        old_qty: item.old_qty,
        new_qty: item.new_qty,
        notes: item.notes || ''
      }))
    })
    dialogVisible.value = true
  } catch (error) {
    console.error('加载ECN详情失败:', error)
    ElMessage.error('加载ECN详情失败')
  }
}

// 查看ECN
const handleView = async (row) => {
  try {
    const response = await request.get(`/projects/ecn/${row.id}/`)
    currentECN.value = response.data || response
    detailVisible.value = true
  } catch (error) {
    console.error('加载ECN详情失败:', error)
    ElMessage.error('加载ECN详情失败')
  }
}

// 添加变更项
const addItem = () => {
  form.items.push({
    change_type: 'MODIFY',
    item: null,
    new_item: null,
    old_qty: null,
    new_qty: null,
    notes: ''
  })
}

// 移除变更项
const removeItem = (index) => {
  form.items.splice(index, 1)
}

// 变更项类型变化
const onItemChangeTypeChange = (row) => {
  if (row.change_type === 'ADD') {
    row.item = null
    row.old_qty = null
  } else if (row.change_type === 'DELETE') {
    row.new_item = null
    row.new_qty = null
  } else if (row.change_type === 'MODIFY') {
    row.new_item = null
  }
}

// 保存ECN
const handleSave = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    
    saving.value = true
    try {
      const payload = {
        project: form.project,
        title: form.title,
        change_type: form.change_type,
        priority: form.priority,
        requested_date: form.requested_date,
        reason: form.reason,
        description: form.description,
        impact_analysis: form.impact_analysis,
        cost_impact: form.cost_impact,
        schedule_impact: form.schedule_impact,
        items: form.items.filter(item => {
          // 过滤无效的变更项
          if (item.change_type === 'ADD') return item.new_item || item.item
          if (item.change_type === 'DELETE') return item.item
          if (item.change_type === 'MODIFY') return item.item
          if (item.change_type === 'REPLACE') return item.item && item.new_item
          return false
        }).map(item => ({
          change_type: item.change_type,
          item: item.change_type === 'ADD' ? (item.new_item || item.item) : item.item,
          new_item: item.change_type === 'REPLACE' ? item.new_item : (item.change_type === 'ADD' ? item.new_item : null),
          old_qty: item.old_qty,
          new_qty: item.new_qty,
          notes: item.notes
        }))
      }
      
      if (isEdit.value) {
        await request.put(`/projects/ecn/${form.id}/`, payload)
        ElMessage.success('更新成功')
      } else {
        await request.post('/projects/ecn/', payload)
        ElMessage.success('创建成功')
      }
      
      dialogVisible.value = false
      loadECNList()
    } catch (error) {
      console.error('保存ECN失败:', error)
      ElMessage.error('保存ECN失败')
    } finally {
      saving.value = false
    }
  })
}

// 提交审批
const handleSubmit = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交此ECN进行评审吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    })
    const response = await request.post(`/projects/ecn/${row.id}/submit/`)
    const data = response.data || response
    
    if (data.workflow_instance_id) {
      ElMessage.success('已提交审批流程')
      // 询问是否查看审批进度
      try {
        await ElMessageBox.confirm('已提交审批流程，是否查看审批进度？', '提交成功', {
          confirmButtonText: '查看进度',
          cancelButtonText: '稍后查看',
          type: 'success'
        })
        router.push('/workflow/my-submissions')
      } catch {
        // 用户选择稍后查看
      }
    } else {
      ElMessage.success('提交成功')
    }
    loadECNList()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('提交失败:', error)
      ElMessage.error('提交失败')
    }
  }
}

// 查看审批进度
const viewWorkflow = (row) => {
  router.push('/workflow/my-submissions')
}

// 批准
const handleApprove = (row) => {
  approvalAction.value = 'approve'
  approvalDialogTitle.value = '批准ECN'
  approvalComment.value = ''
  approvalECN.value = row
  approvalDialogVisible.value = true
}

// 拒绝
const handleReject = (row) => {
  approvalAction.value = 'reject'
  approvalDialogTitle.value = '拒绝ECN'
  approvalComment.value = ''
  approvalECN.value = row
  approvalDialogVisible.value = true
}

// 开始实施
const handleImplement = async (row) => {
  try {
    await ElMessageBox.confirm('确定要开始实施此ECN吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    })
    await request.post(`/projects/ecn/${row.id}/start_implementation/`)
    ElMessage.success('已开始实施')
    loadECNList()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('操作失败:', error)
      ElMessage.error('操作失败')
    }
  }
}

// 完成实施
const handleComplete = (row) => {
  approvalAction.value = 'complete'
  approvalDialogTitle.value = '完成实施'
  approvalComment.value = ''
  implementationNotes.value = ''
  approvalECN.value = row
  approvalDialogVisible.value = true
}

// 确认审批
const confirmApproval = async () => {
  approving.value = true
  try {
    const payload = { comment: approvalComment.value }
    if (approvalAction.value === 'complete') {
      payload.implementation_notes = implementationNotes.value
    }
    
    let url = ''
    switch (approvalAction.value) {
      case 'approve':
        url = `/projects/ecn/${approvalECN.value.id}/approve/`
        break
      case 'reject':
        url = `/projects/ecn/${approvalECN.value.id}/reject/`
        break
      case 'complete':
        url = `/projects/ecn/${approvalECN.value.id}/complete/`
        break
    }
    
    await request.post(url, payload)
    ElMessage.success('操作成功')
    approvalDialogVisible.value = false
    loadECNList()
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error('操作失败')
  } finally {
    approving.value = false
  }
}

// 标签类型
const getStatusTagType = (status) => {
  const types = {
    'DRAFT': 'info',
    'PENDING': 'warning',
    'REVIEWING': 'warning',
    'APPROVED': 'success',
    'REJECTED': 'danger',
    'IMPLEMENTING': 'primary',
    'COMPLETED': '',
    'CANCELLED': 'info'
  }
  return types[status] || 'info'
}

const getPriorityTagType = (priority) => {
  const types = {
    'URGENT': 'danger',
    'HIGH': 'warning',
    'MEDIUM': '',
    'LOW': 'info'
  }
  return types[priority] || 'info'
}

const getChangeTypeTagType = (type) => {
  const types = {
    'DESIGN': 'primary',
    'PROCESS': 'success',
    'MATERIAL': 'warning',
    'SPEC': 'info',
    'DRAWING': '',
    'OTHER': 'info'
  }
  return types[type] || 'info'
}

const getItemChangeTypeTagType = (type) => {
  const types = {
    'ADD': 'success',
    'DELETE': 'danger',
    'MODIFY': 'warning',
    'REPLACE': 'primary'
  }
  return types[type] || 'info'
}

// handleDelete 已被 useBatchDelete 的 deleteRow 替代

// 初始化
onMounted(() => {
  loadECNList()
  loadProjects()
})
</script>

<style scoped>
.ecn-list {
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
</style>

