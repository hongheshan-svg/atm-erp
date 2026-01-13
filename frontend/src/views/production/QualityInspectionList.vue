<template>
  <div class="quality-inspection-list">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2>质量检验管理</h2>
        <span class="subtitle">生产过程中的质量检验记录</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="handleAdd">
          <el-icon><Plus /></el-icon>
          新建检验单
        </el-button>
      </div>
    </div>

    <!-- 搜索筛选 -->
    <el-card class="filter-card" shadow="never">
      <el-form :model="filters" inline>
        <el-form-item label="项目">
          <el-select
            v-model="filters.project"
            placeholder="选择项目"
            clearable
            filterable
            style="width: 220px"
          >
            <el-option
              v-for="item in projects"
              :key="item.id"
              :label="`${item.code} - ${item.name}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="检验类型">
          <el-select v-model="filters.inspection_type" placeholder="全部类型" clearable style="width: 130px">
            <el-option label="来料检验" value="INCOMING" />
            <el-option label="首件检验" value="FIRST_PIECE" />
            <el-option label="过程检验" value="PROCESS" />
            <el-option label="成品检验" value="FINAL" />
            <el-option label="出货检验" value="OUTGOING" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 110px">
            <el-option label="待检验" value="PENDING" />
            <el-option label="检验中" value="IN_PROGRESS" />
            <el-option label="已完成" value="COMPLETED" />
          </el-select>
        </el-form-item>
        <el-form-item label="结果">
          <el-select v-model="filters.result" placeholder="全部结果" clearable style="width: 110px">
            <el-option label="合格" value="PASS" />
            <el-option label="不合格" value="FAIL" />
            <el-option label="让步接收" value="CONDITIONAL" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-icon pending">
              <el-icon><Clock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.pending }}</div>
              <div class="stat-label">待检验</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-icon progress">
              <el-icon><Loading /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.in_progress }}</div>
              <div class="stat-label">检验中</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-icon pass">
              <el-icon><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.pass }}</div>
              <div class="stat-label">已合格</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="never">
          <div class="stat-content">
            <div class="stat-icon fail">
              <el-icon><CircleClose /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.fail }}</div>
              <div class="stat-label">不合格</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 检验单列表 -->
    <el-card class="table-card" shadow="never">
      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="inspectionList"
        stripe
        border
        style="width: 100%"
        @row-click="handleRowClick"
        @selection-change="handleSelectionChange"
      >
        <el-table-column v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="inspection_no" label="检验单号" width="160" />
        <el-table-column prop="title" label="检验名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="project_code" label="项目编号" width="130" />
        <el-table-column prop="inspection_type_display" label="检验类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getInspectionTypeTag(row.inspection_type)" size="small">
              {{ row.inspection_type_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="result_display" label="结果" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.result" :type="getResultType(row.result)" size="small">
              {{ row.result_display }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="合格率" width="100" align="center">
          <template #default="{ row }">
            <span :class="['pass-rate', { good: row.pass_rate >= 95, warning: row.pass_rate >= 80 && row.pass_rate < 95, bad: row.pass_rate < 80 }]">
              {{ row.pass_rate }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="抽检数量" width="120" align="center">
          <template #default="{ row }">
            <span>{{ row.pass_qty }}/{{ row.fail_qty }}/{{ row.sample_qty }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="inspection_date" label="检验日期" width="110" />
        <el-table-column prop="inspector_name" label="检验员" width="90" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click.stop="handleEdit(row)">
              编辑
            </el-button>
            <el-button
              v-if="row.status === 'PENDING'"
              type="success"
              size="small"
              link
              @click.stop="handleStartInspection(row)"
            >
              开始检验
            </el-button>
            <el-button
              v-if="row.status === 'IN_PROGRESS'"
              type="warning"
              size="small"
              link
              @click.stop="handleCompleteInspection(row)"
            >
              完成
            </el-button>
            <el-button
              v-if="canDelete"
              type="danger"
              size="small"
              link
              @click.stop="deleteRow(row)"
              :loading="deleteLoading"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 检验详情对话框 -->
    <el-drawer
      v-model="detailVisible"
      :title="currentInspection?.inspection_no + ' - ' + currentInspection?.title"
      size="65%"
      direction="rtl"
    >
      <template v-if="currentInspection">
        <div class="detail-section">
          <h4>基本信息</h4>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="检验单号">{{ currentInspection.inspection_no }}</el-descriptions-item>
            <el-descriptions-item label="检验名称">{{ currentInspection.title }}</el-descriptions-item>
            <el-descriptions-item label="项目编号">{{ currentInspection.project_code }}</el-descriptions-item>
            <el-descriptions-item label="项目名称">{{ currentInspection.project_name }}</el-descriptions-item>
            <el-descriptions-item label="检验类型">
              <el-tag :type="getInspectionTypeTag(currentInspection.inspection_type)">
                {{ currentInspection.inspection_type_display }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(currentInspection.status)">
                {{ currentInspection.status_display }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="检验结果">
              <el-tag v-if="currentInspection.result" :type="getResultType(currentInspection.result)">
                {{ currentInspection.result_display }}
              </el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="合格率">
              <span :class="['pass-rate', { good: currentInspection.pass_rate >= 95 }]">
                {{ currentInspection.pass_rate }}%
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="计划日期">{{ currentInspection.planned_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="检验日期">{{ currentInspection.inspection_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="检验员">{{ currentInspection.inspector_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="审核人">{{ currentInspection.reviewer_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="抽样方法">{{ currentInspection.sampling_method || '-' }}</el-descriptions-item>
            <el-descriptions-item label="抽检数量">
              合格: {{ currentInspection.pass_qty }} / 不合格: {{ currentInspection.fail_qty }} / 总数: {{ currentInspection.sample_qty }}
            </el-descriptions-item>
            <el-descriptions-item label="检验依据" :span="2">{{ currentInspection.inspection_standard || '-' }}</el-descriptions-item>
            <el-descriptions-item label="检验结论" :span="2">{{ currentInspection.conclusion || '-' }}</el-descriptions-item>
            <el-descriptions-item label="处理意见" :span="2">{{ currentInspection.treatment || '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="detail-section">
          <div class="section-header">
            <h4>检验项目</h4>
            <el-button type="primary" size="small" @click="handleAddItems">
              <el-icon><Plus /></el-icon>
              添加检验项
            </el-button>
          </div>
          <el-table :data="currentInspection.items" border stripe size="small">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="item_name" label="检验项目" min-width="150" />
            <el-table-column prop="standard" label="标准要求" width="150" show-overflow-tooltip />
            <el-table-column prop="method" label="检验方法" width="100" />
            <el-table-column prop="nominal_value" label="标准值" width="90" />
            <el-table-column label="公差" width="100">
              <template #default="{ row }">
                <span v-if="row.tolerance_upper || row.tolerance_lower">
                  +{{ row.tolerance_upper || '0' }} / -{{ row.tolerance_lower || '0' }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="actual_value" label="实测值" width="90" />
            <el-table-column prop="result_display" label="结果" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="getItemResultType(row.result)" size="small">
                  {{ row.result_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="notes" label="备注" width="100" show-overflow-tooltip />
          </el-table>
        </div>
      </template>
    </el-drawer>

    <!-- 新增/编辑检验单对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="800px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="100px"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目" prop="project">
              <el-select
                v-model="formData.project"
                placeholder="选择项目"
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="item in projects"
                  :key="item.id"
                  :label="`${item.code} - ${item.name}`"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="检验名称" prop="title">
              <el-input v-model="formData.title" placeholder="如：来料检验-电机" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="检验类型" prop="inspection_type">
              <el-select v-model="formData.inspection_type" placeholder="选择类型" style="width: 100%">
                <el-option label="来料检验" value="INCOMING" />
                <el-option label="首件检验" value="FIRST_PIECE" />
                <el-option label="过程检验" value="PROCESS" />
                <el-option label="成品检验" value="FINAL" />
                <el-option label="出货检验" value="OUTGOING" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划日期">
              <el-date-picker
                v-model="formData.planned_date"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="检验员">
              <el-select
                v-model="formData.inspector"
                placeholder="选择检验员"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="user in users"
                  :key="user.id"
                  :label="user.full_name || user.username"
                  :value="user.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="审核人">
              <el-select
                v-model="formData.reviewer"
                placeholder="选择审核人"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="user in users"
                  :key="user.id"
                  :label="user.full_name || user.username"
                  :value="user.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="抽样方法">
              <el-input v-model="formData.sampling_method" placeholder="如：GB/T 2828.1" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="检验数量">
              <el-input-number v-model="formData.sample_qty" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="检验依据">
          <el-input
            v-model="formData.inspection_standard"
            type="textarea"
            :rows="2"
            placeholder="检验标准或依据"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 完成检验对话框 -->
    <el-dialog
      v-model="completeDialogVisible"
      title="完成检验"
      width="600px"
    >
      <el-form :model="completeFormData" label-width="100px">
        <el-form-item label="检验结果" required>
          <el-radio-group v-model="completeFormData.result">
            <el-radio-button label="PASS">合格</el-radio-button>
            <el-radio-button label="FAIL">不合格</el-radio-button>
            <el-radio-button label="CONDITIONAL">让步接收</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="检验结论">
          <el-input
            v-model="completeFormData.conclusion"
            type="textarea"
            :rows="3"
            placeholder="检验结论"
          />
        </el-form-item>
        <el-form-item label="处理意见">
          <el-input
            v-model="completeFormData.treatment"
            type="textarea"
            :rows="2"
            placeholder="对不合格品的处理意见"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleCompleteConfirm">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 添加检验项对话框 -->
    <el-dialog
      v-model="itemDialogVisible"
      title="添加检验项"
      width="900px"
    >
      <el-form :model="itemFormData" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="检验项目" required>
              <el-input v-model="itemFormData.item_name" placeholder="检验项目名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="检验方法">
              <el-input v-model="itemFormData.method" placeholder="检验方法" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="标准值">
              <el-input v-model="itemFormData.nominal_value" placeholder="标准值" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="上公差">
              <el-input v-model="itemFormData.tolerance_upper" placeholder="上公差" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="下公差">
              <el-input v-model="itemFormData.tolerance_lower" placeholder="下公差" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="标准要求">
          <el-input v-model="itemFormData.standard" placeholder="标准要求" />
        </el-form-item>
        <el-divider>已添加的检验项</el-divider>
        <el-table :data="newItems" border stripe size="small" max-height="250">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="item_name" label="检验项目" min-width="120" />
          <el-table-column prop="standard" label="标准要求" width="150" />
          <el-table-column prop="nominal_value" label="标准值" width="80" />
          <el-table-column label="公差" width="100">
            <template #default="{ row }">
              +{{ row.tolerance_upper || '0' }} / -{{ row.tolerance_lower || '0' }}
            </template>
          </el-table-column>
          <el-table-column prop="method" label="检验方法" width="100" />
          <el-table-column label="操作" width="80">
            <template #default="{ $index }">
              <el-button type="danger" size="small" link @click="newItems.splice($index, 1)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="margin-top: 12px; text-align: center">
          <el-button type="primary" @click="addItemToList">
            <el-icon><Plus /></el-icon>
            添加到列表
          </el-button>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="itemDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleItemsConfirm">
          保存全部
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh, Clock, Loading, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/production/inspections/',
  { onSuccess: loadData, confirmTitle: '删除检验单', confirmMessage: '确定要删除该检验单吗？' }
)

// 状态
const loading = ref(false)
const saving = ref(false)
const inspectionList = ref([])
const projects = ref([])
const users = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新建检验单')
const detailVisible = ref(false)
const currentInspection = ref(null)
const completeDialogVisible = ref(false)
const itemDialogVisible = ref(false)
const newItems = ref([])
const formRef = ref(null)

// 筛选条件
const filters = reactive({
  project: null,
  inspection_type: '',
  status: '',
  result: ''
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 统计数据
const stats = computed(() => {
  const pending = inspectionList.value.filter(i => i.status === 'PENDING').length
  const in_progress = inspectionList.value.filter(i => i.status === 'IN_PROGRESS').length
  const pass = inspectionList.value.filter(i => i.result === 'PASS').length
  const fail = inspectionList.value.filter(i => i.result === 'FAIL').length
  return { pending, in_progress, pass, fail }
})

// 表单数据
const formData = reactive({
  id: null,
  project: null,
  title: '',
  inspection_type: 'PROCESS',
  planned_date: '',
  inspector: null,
  reviewer: null,
  sampling_method: '',
  sample_qty: 1,
  inspection_standard: ''
})

// 完成检验表单
const completeFormData = reactive({
  result: 'PASS',
  conclusion: '',
  treatment: ''
})

// 检验项表单
const itemFormData = reactive({
  item_name: '',
  standard: '',
  method: '',
  nominal_value: '',
  tolerance_upper: '',
  tolerance_lower: ''
})

// 表单验证
const formRules = {
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  title: [{ required: true, message: '请输入检验名称', trigger: 'blur' }],
  inspection_type: [{ required: true, message: '请选择检验类型', trigger: 'change' }]
}

// 获取样式
const getInspectionTypeTag = (type) => {
  const map = {
    'INCOMING': 'primary',
    'FIRST_PIECE': 'warning',
    'PROCESS': '',
    'FINAL': 'success',
    'OUTGOING': 'danger'
  }
  return map[type] || ''
}

const getStatusType = (status) => {
  const map = {
    'PENDING': 'info',
    'IN_PROGRESS': 'warning',
    'COMPLETED': 'success'
  }
  return map[status] || ''
}

const getResultType = (result) => {
  const map = {
    'PASS': 'success',
    'FAIL': 'danger',
    'CONDITIONAL': 'warning'
  }
  return map[result] || ''
}

const getItemResultType = (result) => {
  const map = {
    'PASS': 'success',
    'FAIL': 'danger',
    'NA': 'info',
    'PENDING': ''
  }
  return map[result] || ''
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters
    }
    const res = await request.get('/production/inspections/', { params })
    inspectionList.value = res.results || res || []
    pagination.total = res.count || (Array.isArray(inspectionList.value) ? inspectionList.value.length : 0)
  } catch (error) {
    console.error('加载检验单失败:', error)
  } finally {
    loading.value = false
  }
}

// 加载项目列表
const loadProjects = async () => {
  try {
    const res = await request.get('/projects/', { params: { page_size: 1000 } })
    projects.value = res.results || res || []
  } catch (error) {
    console.error('加载项目列表失败:', error)
  }
}

// 加载用户列表
const loadUsers = async () => {
  try {
    const res = await request.get('/auth/users/', { params: { page_size: 1000 } })
    users.value = res.results || res || []
  } catch (error) {
    console.error('加载用户列表失败:', error)
  }
}

// 搜索
const handleSearch = () => {
  pagination.page = 1
  loadData()
}

// 重置
const handleReset = () => {
  filters.project = null
  filters.inspection_type = ''
  filters.status = ''
  filters.result = ''
  pagination.page = 1
  loadData()
}

// 分页
const handleSizeChange = (size) => {
  pagination.pageSize = size
  pagination.page = 1
  loadData()
}

const handlePageChange = (page) => {
  pagination.page = page
  loadData()
}

// 点击行查看详情
const handleRowClick = async (row) => {
  try {
    const res = await request.get(`/production/inspections/${row.id}/`)
    currentInspection.value = res.data
    detailVisible.value = true
  } catch (error) {
    console.error('加载详情失败:', error)
  }
}

// 新增
const handleAdd = () => {
  dialogTitle.value = '新建检验单'
  Object.assign(formData, {
    id: null,
    project: null,
    title: '',
    inspection_type: 'PROCESS',
    planned_date: '',
    inspector: null,
    reviewer: null,
    sampling_method: '',
    sample_qty: 1,
    inspection_standard: ''
  })
  dialogVisible.value = true
}

// 编辑
const handleEdit = (row) => {
  dialogTitle.value = '编辑检验单'
  Object.assign(formData, {
    id: row.id,
    project: row.project,
    title: row.title,
    inspection_type: row.inspection_type,
    planned_date: row.planned_date,
    inspector: row.inspector,
    reviewer: row.reviewer,
    sampling_method: row.sampling_method,
    sample_qty: row.sample_qty,
    inspection_standard: row.inspection_standard
  })
  dialogVisible.value = true
}

// 删除
// handleDelete 已被 useBatchDelete 的 deleteRow 替代

// 开始检验
const handleStartInspection = async (row) => {
  try {
    await request.post(`/production/inspections/${row.id}/start_inspection/`)
    ElMessage.success('检验已开始')
    loadData()
  } catch (error) {
    console.error('开始检验失败:', error)
  }
}

// 完成检验
const handleCompleteInspection = (row) => {
  currentInspection.value = row
  Object.assign(completeFormData, {
    result: 'PASS',
    conclusion: '',
    treatment: ''
  })
  completeDialogVisible.value = true
}

// 确认完成检验
const handleCompleteConfirm = async () => {
  if (!completeFormData.result) {
    ElMessage.warning('请选择检验结果')
    return
  }
  
  try {
    saving.value = true
    await request.post(`/production/inspections/${currentInspection.value.id}/complete_inspection/`, completeFormData)
    ElMessage.success('检验已完成')
    completeDialogVisible.value = false
    loadData()
  } catch (error) {
    console.error('完成检验失败:', error)
  } finally {
    saving.value = false
  }
}

// 保存
const handleSave = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
    saving.value = true
    
    const data = { ...formData }
    if (data.id) {
      await request.put(`/production/inspections/${data.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/production/inspections/', data)
      ElMessage.success('创建成功')
    }
    
    dialogVisible.value = false
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('保存失败:', error)
    }
  } finally {
    saving.value = false
  }
}

// 添加检验项
const handleAddItems = () => {
  Object.assign(itemFormData, {
    item_name: '',
    standard: '',
    method: '',
    nominal_value: '',
    tolerance_upper: '',
    tolerance_lower: ''
  })
  newItems.value = []
  itemDialogVisible.value = true
}

// 添加检验项到列表
const addItemToList = () => {
  if (!itemFormData.item_name) {
    ElMessage.warning('请输入检验项目名称')
    return
  }
  newItems.value.push({ ...itemFormData })
  Object.assign(itemFormData, {
    item_name: '',
    standard: '',
    method: '',
    nominal_value: '',
    tolerance_upper: '',
    tolerance_lower: ''
  })
}

// 确认保存检验项
const handleItemsConfirm = async () => {
  if (newItems.value.length === 0) {
    ElMessage.warning('请至少添加一个检验项')
    return
  }
  
  try {
    saving.value = true
    await request.post(`/production/inspections/${currentInspection.value.id}/add_items/`, {
      items: newItems.value
    })
    ElMessage.success('检验项已添加')
    itemDialogVisible.value = false
    
    // 刷新详情
    const res = await request.get(`/production/inspections/${currentInspection.value.id}/`)
    currentInspection.value = res.data
  } catch (error) {
    console.error('添加检验项失败:', error)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadData()
  loadProjects()
  loadUsers()
})
</script>

<style scoped>
.quality-inspection-list {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.header-left .subtitle {
  font-size: 14px;
  color: #909399;
  margin-left: 12px;
}

.filter-card {
  margin-bottom: 20px;
}

.filter-card :deep(.el-card__body) {
  padding: 16px 20px 0;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  height: 80px;
}

.stat-card :deep(.el-card__body) {
  padding: 16px;
  height: 100%;
}

.stat-content {
  display: flex;
  align-items: center;
  height: 100%;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
}

.stat-icon :deep(.el-icon) {
  font-size: 24px;
  color: #fff;
}

.stat-icon.pending {
  background: linear-gradient(135deg, #909399 0%, #606266 100%);
}

.stat-icon.progress {
  background: linear-gradient(135deg, #e6a23c 0%, #f56c6c 100%);
}

.stat-icon.pass {
  background: linear-gradient(135deg, #67c23a 0%, #529b2e 100%);
}

.stat-icon.fail {
  background: linear-gradient(135deg, #f56c6c 0%, #c45656 100%);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.stat-label {
  font-size: 13px;
  color: #909399;
}

.table-card :deep(.el-card__body) {
  padding: 0;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  padding: 16px 20px;
  background: #fff;
}

.pass-rate {
  font-weight: 600;
}

.pass-rate.good {
  color: #67c23a;
}

.pass-rate.warning {
  color: #e6a23c;
}

.pass-rate.bad {
  color: #f56c6c;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section h4 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h4 {
  margin: 0;
}
</style>
