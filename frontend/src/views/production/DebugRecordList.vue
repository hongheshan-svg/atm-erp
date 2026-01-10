<template>
  <div class="debug-record-list">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2>调试记录管理</h2>
        <span class="subtitle">非标自动化设备的调试过程记录</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="handleAdd">
          <el-icon><Plus /></el-icon>
          新建调试记录
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
        <el-form-item label="调试类型">
          <el-select v-model="filters.debug_type" placeholder="全部类型" clearable style="width: 140px">
            <el-option label="机械调试" value="MECHANICAL" />
            <el-option label="电气调试" value="ELECTRICAL" />
            <el-option label="气动调试" value="PNEUMATIC" />
            <el-option label="PLC程序" value="PLC" />
            <el-option label="人机界面" value="HMI" />
            <el-option label="视觉系统" value="VISION" />
            <el-option label="机器人" value="ROBOT" />
            <el-option label="运动控制" value="MOTION" />
            <el-option label="整机联调" value="INTEGRATION" />
            <el-option label="出厂验收" value="FAT" />
            <el-option label="现场验收" value="SAT" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="待调试" value="PENDING" />
            <el-option label="调试中" value="IN_PROGRESS" />
            <el-option label="问题处理中" value="DEBUGGING" />
            <el-option label="调试完成" value="COMPLETED" />
            <el-option label="调试失败" value="FAILED" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="filters.search"
            placeholder="单号/标题"
            clearable
            style="width: 150px"
            @keyup.enter="handleSearch"
          />
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

    <!-- 调试记录列表 -->
    <el-card class="table-card" shadow="never">
      <el-table
        v-loading="loading"
        :data="recordList"
        stripe
        border
        style="width: 100%"
        @row-click="handleRowClick"
      >
        <el-table-column prop="record_no" label="调试单号" width="160" />
        <el-table-column prop="title" label="调试项目" min-width="180" show-overflow-tooltip />
        <el-table-column prop="project_code" label="项目编号" width="130" />
        <el-table-column prop="debug_type_display" label="调试类型" width="110">
          <template #default="{ row }">
            <el-tag :type="getDebugTypeTag(row.debug_type)" size="small">
              {{ row.debug_type_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="100" align="center">
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
        <el-table-column label="检查项" width="100" align="center">
          <template #default="{ row }">
            <span class="check-stats">
              <span class="pass">{{ row.pass_items }}</span>/<span class="fail">{{ row.fail_items }}</span>/{{ row.total_items }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="debug_date" label="调试日期" width="110" />
        <el-table-column prop="debugger_name" label="调试人员" width="100" />
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
              @click.stop="handleStartDebug(row)"
            >
              开始调试
            </el-button>
            <el-button
              v-if="row.status === 'IN_PROGRESS'"
              type="warning"
              size="small"
              link
              @click.stop="handleCompleteDebug(row)"
            >
              完成
            </el-button>
            <el-button
              v-if="row.status === 'PENDING'"
              type="danger"
              size="small"
              link
              @click.stop="handleDelete(row)"
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

    <!-- 调试记录详情对话框 -->
    <el-drawer
      v-model="detailVisible"
      :title="currentRecord?.record_no + ' - ' + currentRecord?.title"
      size="65%"
      direction="rtl"
    >
      <template v-if="currentRecord">
        <div class="detail-section">
          <h4>基本信息</h4>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="调试单号">{{ currentRecord.record_no }}</el-descriptions-item>
            <el-descriptions-item label="调试项目">{{ currentRecord.title }}</el-descriptions-item>
            <el-descriptions-item label="项目编号">{{ currentRecord.project_code }}</el-descriptions-item>
            <el-descriptions-item label="项目名称">{{ currentRecord.project_name }}</el-descriptions-item>
            <el-descriptions-item label="调试类型">
              <el-tag :type="getDebugTypeTag(currentRecord.debug_type)">
                {{ currentRecord.debug_type_display }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(currentRecord.status)">
                {{ currentRecord.status_display }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="调试结果">
              <el-tag v-if="currentRecord.result" :type="getResultType(currentRecord.result)">
                {{ currentRecord.result_display }}
              </el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="计划日期">{{ currentRecord.planned_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="调试日期">{{ currentRecord.debug_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="调试人员">{{ currentRecord.debugger_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="审核人">{{ currentRecord.reviewer_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="完成时间">{{ currentRecord.completed_at || '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="detail-section">
          <h4>调试内容</h4>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="调试内容">{{ currentRecord.debug_content || '-' }}</el-descriptions-item>
            <el-descriptions-item label="测试条件">{{ currentRecord.test_conditions || '-' }}</el-descriptions-item>
            <el-descriptions-item label="预期结果">{{ currentRecord.expected_result || '-' }}</el-descriptions-item>
            <el-descriptions-item label="实际结果">{{ currentRecord.actual_result || '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="detail-section" v-if="currentRecord.issues_found || currentRecord.solutions || currentRecord.remaining_issues">
          <h4>问题与解决</h4>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="发现问题">{{ currentRecord.issues_found || '-' }}</el-descriptions-item>
            <el-descriptions-item label="解决措施">{{ currentRecord.solutions || '-' }}</el-descriptions-item>
            <el-descriptions-item label="遗留问题">{{ currentRecord.remaining_issues || '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="detail-section">
          <div class="section-header">
            <h4>检查项 ({{ currentRecord.pass_items }}/{{ currentRecord.fail_items }}/{{ currentRecord.total_items }})</h4>
            <el-button type="primary" size="small" @click="handleAddCheckItems">
              <el-icon><Plus /></el-icon>
              添加检查项
            </el-button>
          </div>
          <el-table :data="currentRecord.check_items" border stripe size="small">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="item_name" label="检查项" min-width="150" />
            <el-table-column prop="standard" label="标准/要求" width="150" show-overflow-tooltip />
            <el-table-column prop="method" label="检查方法" width="120" show-overflow-tooltip />
            <el-table-column prop="actual_value" label="实测值" width="100" />
            <el-table-column prop="result_display" label="结果" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="getCheckResultType(row.result)" size="small">
                  {{ row.result_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="notes" label="备注" width="120" show-overflow-tooltip />
          </el-table>
        </div>
      </template>
    </el-drawer>

    <!-- 新增/编辑对话框 -->
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
            <el-form-item label="调试项目" prop="title">
              <el-input v-model="formData.title" placeholder="如：整机电气调试" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="调试类型" prop="debug_type">
              <el-select v-model="formData.debug_type" placeholder="选择类型" style="width: 100%">
                <el-option label="机械调试" value="MECHANICAL" />
                <el-option label="电气调试" value="ELECTRICAL" />
                <el-option label="气动调试" value="PNEUMATIC" />
                <el-option label="PLC程序调试" value="PLC" />
                <el-option label="人机界面调试" value="HMI" />
                <el-option label="视觉系统调试" value="VISION" />
                <el-option label="机器人调试" value="ROBOT" />
                <el-option label="运动控制调试" value="MOTION" />
                <el-option label="整机联调" value="INTEGRATION" />
                <el-option label="出厂验收" value="FAT" />
                <el-option label="现场验收" value="SAT" />
                <el-option label="其他" value="OTHER" />
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
            <el-form-item label="调试人员">
              <el-select
                v-model="formData.debugger"
                placeholder="选择调试人员"
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
        <el-form-item label="调试内容" prop="debug_content">
          <el-input
            v-model="formData.debug_content"
            type="textarea"
            :rows="3"
            placeholder="详细描述调试内容"
          />
        </el-form-item>
        <el-form-item label="测试条件">
          <el-input
            v-model="formData.test_conditions"
            type="textarea"
            :rows="2"
            placeholder="测试前提条件"
          />
        </el-form-item>
        <el-form-item label="预期结果">
          <el-input
            v-model="formData.expected_result"
            type="textarea"
            :rows="2"
            placeholder="期望的调试结果"
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

    <!-- 完成调试对话框 -->
    <el-dialog
      v-model="completeDialogVisible"
      title="完成调试"
      width="600px"
    >
      <el-form :model="completeFormData" label-width="100px">
        <el-form-item label="调试结果" required>
          <el-radio-group v-model="completeFormData.result">
            <el-radio-button label="PASS">通过</el-radio-button>
            <el-radio-button label="FAIL">不通过</el-radio-button>
            <el-radio-button label="CONDITIONAL">有条件通过</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="实际结果">
          <el-input
            v-model="completeFormData.actual_result"
            type="textarea"
            :rows="3"
            placeholder="描述实际调试结果"
          />
        </el-form-item>
        <el-form-item label="发现问题">
          <el-input
            v-model="completeFormData.issues_found"
            type="textarea"
            :rows="2"
            placeholder="调试中发现的问题"
          />
        </el-form-item>
        <el-form-item label="解决措施">
          <el-input
            v-model="completeFormData.solutions"
            type="textarea"
            :rows="2"
            placeholder="问题解决措施"
          />
        </el-form-item>
        <el-form-item label="遗留问题">
          <el-input
            v-model="completeFormData.remaining_issues"
            type="textarea"
            :rows="2"
            placeholder="尚未解决的问题"
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

    <!-- 添加检查项对话框 -->
    <el-dialog
      v-model="checkItemDialogVisible"
      title="添加检查项"
      width="800px"
    >
      <el-form :model="checkItemFormData" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="检查项名称" required>
              <el-input v-model="checkItemFormData.item_name" placeholder="检查项名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="检查方法">
              <el-input v-model="checkItemFormData.method" placeholder="检查方法" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="标准/要求">
          <el-input v-model="checkItemFormData.standard" placeholder="检查标准或要求" />
        </el-form-item>
        <el-divider>已添加的检查项</el-divider>
        <el-table :data="newCheckItems" border stripe size="small" max-height="300">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="item_name" label="检查项" min-width="150" />
          <el-table-column prop="standard" label="标准/要求" width="200" />
          <el-table-column prop="method" label="检查方法" width="150" />
          <el-table-column label="操作" width="80">
            <template #default="{ $index }">
              <el-button type="danger" size="small" link @click="newCheckItems.splice($index, 1)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="margin-top: 12px; text-align: center">
          <el-button type="primary" @click="addCheckItemToList">
            <el-icon><Plus /></el-icon>
            添加到列表
          </el-button>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="checkItemDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleCheckItemsConfirm">
          保存全部
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh } from '@element-plus/icons-vue'
import request from '@/utils/request'

// 状态
const loading = ref(false)
const saving = ref(false)
const recordList = ref([])
const projects = ref([])
const users = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新建调试记录')
const detailVisible = ref(false)
const currentRecord = ref(null)
const completeDialogVisible = ref(false)
const checkItemDialogVisible = ref(false)
const newCheckItems = ref([])
const formRef = ref(null)

// 筛选条件
const filters = reactive({
  project: null,
  debug_type: '',
  status: '',
  search: ''
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 表单数据
const formData = reactive({
  id: null,
  project: null,
  title: '',
  debug_type: 'INTEGRATION',
  planned_date: '',
  debugger: null,
  reviewer: null,
  debug_content: '',
  test_conditions: '',
  expected_result: ''
})

// 完成调试表单
const completeFormData = reactive({
  result: 'PASS',
  actual_result: '',
  issues_found: '',
  solutions: '',
  remaining_issues: ''
})

// 检查项表单
const checkItemFormData = reactive({
  item_name: '',
  standard: '',
  method: ''
})

// 表单验证
const formRules = {
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  title: [{ required: true, message: '请输入调试项目名称', trigger: 'blur' }],
  debug_type: [{ required: true, message: '请选择调试类型', trigger: 'change' }],
  debug_content: [{ required: true, message: '请输入调试内容', trigger: 'blur' }]
}

// 获取样式
const getDebugTypeTag = (type) => {
  const map = {
    'MECHANICAL': 'primary',
    'ELECTRICAL': 'warning',
    'PNEUMATIC': 'info',
    'PLC': 'success',
    'HMI': '',
    'VISION': 'danger',
    'ROBOT': 'warning',
    'MOTION': 'primary',
    'INTEGRATION': 'success',
    'FAT': 'warning',
    'SAT': 'danger',
    'OTHER': 'info'
  }
  return map[type] || ''
}

const getStatusType = (status) => {
  const map = {
    'PENDING': 'info',
    'IN_PROGRESS': 'warning',
    'DEBUGGING': 'warning',
    'COMPLETED': 'success',
    'FAILED': 'danger'
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

const getCheckResultType = (result) => {
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
    const res = await request.get('/production/debug-records/', { params })
    recordList.value = res.data.results || res.data
    pagination.total = res.data.count || res.data.length
  } catch (error) {
    console.error('加载调试记录失败:', error)
  } finally {
    loading.value = false
  }
}

// 加载项目列表
const loadProjects = async () => {
  try {
    const res = await request.get('/projects/', { params: { page_size: 1000 } })
    projects.value = res.data.results || res.data
  } catch (error) {
    console.error('加载项目列表失败:', error)
  }
}

// 加载用户列表
const loadUsers = async () => {
  try {
    const res = await request.get('/auth/users/', { params: { page_size: 1000 } })
    users.value = res.data.results || res.data
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
  filters.debug_type = ''
  filters.status = ''
  filters.search = ''
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
    const res = await request.get(`/production/debug-records/${row.id}/`)
    currentRecord.value = res.data
    detailVisible.value = true
  } catch (error) {
    console.error('加载详情失败:', error)
  }
}

// 新增
const handleAdd = () => {
  dialogTitle.value = '新建调试记录'
  Object.assign(formData, {
    id: null,
    project: null,
    title: '',
    debug_type: 'INTEGRATION',
    planned_date: '',
    debugger: null,
    reviewer: null,
    debug_content: '',
    test_conditions: '',
    expected_result: ''
  })
  dialogVisible.value = true
}

// 编辑
const handleEdit = (row) => {
  dialogTitle.value = '编辑调试记录'
  Object.assign(formData, {
    id: row.id,
    project: row.project,
    title: row.title,
    debug_type: row.debug_type,
    planned_date: row.planned_date,
    debugger: row.debugger,
    reviewer: row.reviewer,
    debug_content: row.debug_content,
    test_conditions: row.test_conditions,
    expected_result: row.expected_result
  })
  dialogVisible.value = true
}

// 删除
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该调试记录吗？', '确认删除', { type: 'warning' })
    await request.delete(`/production/debug-records/${row.id}/`)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
    }
  }
}

// 开始调试
const handleStartDebug = async (row) => {
  try {
    await request.post(`/production/debug-records/${row.id}/start_debug/`)
    ElMessage.success('调试已开始')
    loadData()
  } catch (error) {
    console.error('开始调试失败:', error)
  }
}

// 完成调试
const handleCompleteDebug = (row) => {
  currentRecord.value = row
  Object.assign(completeFormData, {
    result: 'PASS',
    actual_result: '',
    issues_found: '',
    solutions: '',
    remaining_issues: ''
  })
  completeDialogVisible.value = true
}

// 确认完成调试
const handleCompleteConfirm = async () => {
  if (!completeFormData.result) {
    ElMessage.warning('请选择调试结果')
    return
  }
  
  try {
    saving.value = true
    await request.post(`/production/debug-records/${currentRecord.value.id}/complete_debug/`, completeFormData)
    ElMessage.success('调试已完成')
    completeDialogVisible.value = false
    loadData()
  } catch (error) {
    console.error('完成调试失败:', error)
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
      await request.put(`/production/debug-records/${data.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/production/debug-records/', data)
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

// 添加检查项
const handleAddCheckItems = () => {
  Object.assign(checkItemFormData, {
    item_name: '',
    standard: '',
    method: ''
  })
  newCheckItems.value = []
  checkItemDialogVisible.value = true
}

// 添加检查项到列表
const addCheckItemToList = () => {
  if (!checkItemFormData.item_name) {
    ElMessage.warning('请输入检查项名称')
    return
  }
  newCheckItems.value.push({ ...checkItemFormData })
  Object.assign(checkItemFormData, {
    item_name: '',
    standard: '',
    method: ''
  })
}

// 确认保存检查项
const handleCheckItemsConfirm = async () => {
  if (newCheckItems.value.length === 0) {
    ElMessage.warning('请至少添加一个检查项')
    return
  }
  
  try {
    saving.value = true
    await request.post(`/production/debug-records/${currentRecord.value.id}/add_check_items/`, {
      items: newCheckItems.value
    })
    ElMessage.success('检查项已添加')
    checkItemDialogVisible.value = false
    
    // 刷新详情
    const res = await request.get(`/production/debug-records/${currentRecord.value.id}/`)
    currentRecord.value = res.data
  } catch (error) {
    console.error('添加检查项失败:', error)
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
.debug-record-list {
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

.table-card :deep(.el-card__body) {
  padding: 0;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  padding: 16px 20px;
  background: #fff;
}

.check-stats .pass {
  color: #67c23a;
  font-weight: 600;
}

.check-stats .fail {
  color: #f56c6c;
  font-weight: 600;
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
