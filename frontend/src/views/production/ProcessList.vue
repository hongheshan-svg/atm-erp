<template>
  <div class="process-list">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2>生产工序管理</h2>
        <span class="subtitle">定义项目的生产工序流程</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="handleAdd">
          <el-icon><Plus /></el-icon>
          新增工序
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
        <el-form-item label="工序类型">
          <el-select v-model="filters.process_type" placeholder="全部类型" clearable style="width: 140px">
            <el-option label="机加工" value="MACHINING" />
            <el-option label="焊接" value="WELDING" />
            <el-option label="装配" value="ASSEMBLY" />
            <el-option label="布线" value="WIRING" />
            <el-option label="编程调试" value="PROGRAMMING" />
            <el-option label="测试" value="TESTING" />
            <el-option label="喷涂" value="PAINTING" />
            <el-option label="包装" value="PACKAGING" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="filters.search"
            placeholder="工序编号/名称"
            clearable
            style="width: 180px"
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

    <!-- 工序列表 -->
    <el-card class="table-card" shadow="never">
      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="processList"
        stripe
        border
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="project_code" label="项目编号" width="130" />
        <el-table-column prop="process_no" label="工序编号" width="120" />
        <el-table-column prop="name" label="工序名称" min-width="150" />
        <el-table-column prop="process_type_display" label="工序类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getProcessTypeTag(row.process_type)" size="small">
              {{ row.process_type_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sequence" label="顺序" width="70" align="center" />
        <el-table-column label="工时(计划/实际)" width="130" align="center">
          <template #default="{ row }">
            <span>{{ row.planned_hours }}h / {{ row.actual_hours }}h</span>
          </template>
        </el-table-column>
        <el-table-column prop="work_center" label="工作中心" width="120" />
        <el-table-column prop="assignee_name" label="负责人" width="100" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="handleEdit(row)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button v-if="canDelete" type="danger" size="small" link @click="deleteRow(row)" :loading="deleteLoading">
              <el-icon><Delete /></el-icon>
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

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="700px"
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
            <el-form-item label="工序编号" prop="process_no">
              <el-input v-model="formData.process_no" placeholder="如：OP10" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="工序名称" prop="name">
              <el-input v-model="formData.name" placeholder="请输入工序名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工序类型" prop="process_type">
              <el-select v-model="formData.process_type" placeholder="选择类型" style="width: 100%">
                <el-option label="机加工" value="MACHINING" />
                <el-option label="焊接" value="WELDING" />
                <el-option label="装配" value="ASSEMBLY" />
                <el-option label="布线" value="WIRING" />
                <el-option label="编程调试" value="PROGRAMMING" />
                <el-option label="测试" value="TESTING" />
                <el-option label="喷涂" value="PAINTING" />
                <el-option label="包装" value="PACKAGING" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="工序顺序" prop="sequence">
              <el-input-number v-model="formData.sequence" :min="1" :max="999" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="计划工时" prop="planned_hours">
              <el-input-number
                v-model="formData.planned_hours"
                :min="0"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="工作中心">
              <el-input v-model="formData.work_center" placeholder="工位/设备" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="负责人">
              <el-select
                v-model="formData.assignee"
                placeholder="选择负责人"
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
        <el-form-item label="工序说明">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="2"
            placeholder="工序描述"
          />
        </el-form-item>
        <el-form-item label="作业指导书">
          <el-input
            v-model="formData.work_instruction"
            type="textarea"
            :rows="3"
            placeholder="作业步骤和要点"
          />
        </el-form-item>
        <el-form-item label="质量要求">
          <el-input
            v-model="formData.quality_requirements"
            type="textarea"
            :rows="2"
            placeholder="质量标准和检验要点"
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh, Edit, Delete } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/production/processes/',
  { onSuccess: () => loadData(), confirmTitle: '删除工序', confirmMessage: '确定要删除该工序吗？' }
)

// 状态
const loading = ref(false)
const saving = ref(false)
const processList = ref([])
const projects = ref([])
const users = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增工序')
const formRef = ref(null)

// 筛选条件
const filters = reactive({
  project: null,
  process_type: '',
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
  process_no: '',
  name: '',
  process_type: 'ASSEMBLY',
  sequence: 1,
  planned_hours: 0,
  work_center: '',
  assignee: null,
  description: '',
  work_instruction: '',
  quality_requirements: ''
})

// 表单验证
const formRules = {
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  process_no: [{ required: true, message: '请输入工序编号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入工序名称', trigger: 'blur' }],
  process_type: [{ required: true, message: '请选择工序类型', trigger: 'change' }],
  sequence: [{ required: true, message: '请输入工序顺序', trigger: 'blur' }]
}

// 获取工序类型标签样式
const getProcessTypeTag = (type) => {
  const map = {
    'MACHINING': 'primary',
    'WELDING': 'danger',
    'ASSEMBLY': 'success',
    'WIRING': 'warning',
    'PROGRAMMING': 'info',
    'TESTING': '',
    'PAINTING': 'primary',
    'PACKAGING': 'info',
    'OTHER': ''
  }
  return map[type] || ''
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
    const res = await request.get('/production/processes/', { params })
    processList.value = res.results || res || []
    pagination.total = res.count || (Array.isArray(processList.value) ? processList.value.length : 0)
  } catch (error) {
    console.error('加载工序列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 加载项目列表
const loadProjects = async () => {
  try {
    const res = await request.get('/projects/projects/', { params: { page_size: 1000 } })
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
  filters.process_type = ''
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

// 新增
const handleAdd = () => {
  dialogTitle.value = '新增工序'
  Object.assign(formData, {
    id: null,
    project: null,
    process_no: '',
    name: '',
    process_type: 'ASSEMBLY',
    sequence: 1,
    planned_hours: 0,
    work_center: '',
    assignee: null,
    description: '',
    work_instruction: '',
    quality_requirements: ''
  })
  dialogVisible.value = true
}

// 编辑
const handleEdit = (row) => {
  dialogTitle.value = '编辑工序'
  Object.assign(formData, {
    id: row.id,
    project: row.project,
    process_no: row.process_no,
    name: row.name,
    process_type: row.process_type,
    sequence: row.sequence,
    planned_hours: row.planned_hours,
    work_center: row.work_center,
    assignee: row.assignee,
    description: row.description,
    work_instruction: row.work_instruction,
    quality_requirements: row.quality_requirements
  })
  dialogVisible.value = true
}

// 删除 - handleDelete 已被 useBatchDelete 的 deleteRow 替代

// 保存
const handleSave = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
    saving.value = true
    
    const data = { ...formData }
    if (data.id) {
      await request.put(`/production/processes/${data.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/production/processes/', data)
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

onMounted(() => {
  loadData()
  loadProjects()
  loadUsers()
})
</script>

<style scoped>
.process-list {
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

.table-card :deep(.el-table) {
  border-radius: 4px;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  padding: 16px 20px;
  background: #fff;
}
</style>
