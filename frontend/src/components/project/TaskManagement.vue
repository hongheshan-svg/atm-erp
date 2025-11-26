<template>
  <div class="task-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>任务管理</span>
          <el-button type="primary" @click="handleAddTask">
            <el-icon><Plus /></el-icon>
            新增任务
          </el-button>
        </div>
      </template>

      <el-table
        :data="tasks"
        row-key="id"
        :tree-props="{ children: 'children', hasChildren: 'hasChildren' }"
        v-loading="loading"
        border
      >
        <el-table-column prop="name" label="任务名称" width="300">
          <template #default="{ row }">
            <el-icon v-if="row.children && row.children.length > 0" style="margin-right: 5px;">
              <FolderOpened />
            </el-icon>
            {{ row.name }}
          </template>
        </el-table-column>
        <el-table-column prop="assignee_name" label="负责人" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="planned_hours" label="计划工时" width="100" align="right" />
        <el-table-column prop="actual_hours" label="实际工时" width="100" align="right" />
        <el-table-column prop="progress" label="进度" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.progress || 0" :stroke-width="6" />
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleAddSubTask(row)">添加子任务</el-button>
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 任务编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
      @close="resetForm"
    >
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="上级任务" prop="parent">
          <el-tree-select
            v-model="formData.parent"
            :data="taskTreeOptions"
            :props="{ label: 'name', value: 'id' }"
            placeholder="请选择上级任务（不选则为顶级任务）"
            clearable
            check-strictly
          />
        </el-form-item>
        <el-form-item label="负责人" prop="assignee">
          <el-select v-model="formData.assignee" placeholder="请选择负责人" clearable filterable>
            <el-option
              v-for="member in projectMembers"
              :key="member.user_id"
              :label="member.user_name"
              :value="member.user_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="formData.status" placeholder="请选择状态">
            <el-option label="待开始" value="PENDING" />
            <el-option label="进行中" value="IN_PROGRESS" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划工时" prop="planned_hours">
          <el-input-number v-model="formData.planned_hours" :min="0" :step="0.5" />
        </el-form-item>
        <el-form-item label="实际工时" prop="actual_hours">
          <el-input-number v-model="formData.actual_hours" :min="0" :step="0.5" />
        </el-form-item>
        <el-form-item label="进度" prop="progress">
          <el-slider v-model="formData.progress" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="开始日期" prop="start_date">
          <el-date-picker
            v-model="formData.start_date"
            type="date"
            placeholder="选择开始日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="结束日期" prop="end_date">
          <el-date-picker
            v-model="formData.end_date"
            type="date"
            placeholder="选择结束日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入任务描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, FolderOpened } from '@element-plus/icons-vue'
import request from '@/utils/request'

const props = defineProps({
  projectId: {
    type: [Number, String],
    required: true
  }
})

const emit = defineEmits(['refresh'])

const loading = ref(false)
const tasks = ref([])
const projectMembers = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const formRef = ref(null)
const submitting = ref(false)
const isEdit = ref(false)
const currentTaskId = ref(null)

const formData = ref({
  name: '',
  parent: null,
  assignee: null,
  status: 'PENDING',
  planned_hours: 0,
  actual_hours: 0,
  progress: 0,
  start_date: '',
  end_date: '',
  description: ''
})

const rules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

// 构建任务树选项（排除当前任务及其子任务）
const taskTreeOptions = computed(() => {
  const buildTree = (items, excludeId = null) => {
    return items
      .filter(item => item.id !== excludeId)
      .map(item => ({
        id: item.id,
        name: item.name,
        children: item.children ? buildTree(item.children, excludeId) : []
      }))
  }
  return buildTree(tasks.value, currentTaskId.value)
})

const getStatusType = (status) => {
  const types = {
    'PENDING': 'info',
    'IN_PROGRESS': 'warning',
    'COMPLETED': 'success',
    'CANCELLED': 'danger'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    'PENDING': '待开始',
    'IN_PROGRESS': '进行中',
    'COMPLETED': '已完成',
    'CANCELLED': '已取消'
  }
  return labels[status] || status
}

const loadTasks = async () => {
  loading.value = true
  try {
    const { data } = await request.get(`/projects/tasks/`, {
      params: { project: props.projectId }
    })
    // 构建树形结构
    tasks.value = buildTaskTree(data.results || data)
  } catch (error) {
    console.error('加载任务失败:', error)
    ElMessage.error('加载任务失败')
  } finally {
    loading.value = false
  }
}

const loadProjectMembers = async () => {
  try {
    const { data } = await request.get(`/projects/members/`, {
      params: { project: props.projectId }
    })
    projectMembers.value = data.results || data
  } catch (error) {
    console.error('加载项目成员失败:', error)
  }
}

// 构建任务树
const buildTaskTree = (flatTasks) => {
  const taskMap = new Map()
  const rootTasks = []

  // 先创建所有任务的映射
  flatTasks.forEach(task => {
    taskMap.set(task.id, { ...task, children: [] })
  })

  // 构建树形结构
  flatTasks.forEach(task => {
    const taskNode = taskMap.get(task.id)
    if (task.parent) {
      const parentNode = taskMap.get(task.parent)
      if (parentNode) {
        parentNode.children.push(taskNode)
      } else {
        rootTasks.push(taskNode)
      }
    } else {
      rootTasks.push(taskNode)
    }
  })

  return rootTasks
}

const handleAddTask = () => {
  isEdit.value = false
  dialogTitle.value = '新增任务'
  resetForm()
  dialogVisible.value = true
}

const handleAddSubTask = (row) => {
  isEdit.value = false
  dialogTitle.value = '新增子任务'
  resetForm()
  formData.value.parent = row.id
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  currentTaskId.value = row.id
  dialogTitle.value = '编辑任务'
  formData.value = {
    name: row.name,
    parent: row.parent,
    assignee: row.assignee,
    status: row.status,
    planned_hours: row.planned_hours || 0,
    actual_hours: row.actual_hours || 0,
    progress: row.progress || 0,
    start_date: row.start_date || '',
    end_date: row.end_date || '',
    description: row.description || ''
  }
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await request.delete(`/projects/tasks/${row.id}/`)
    ElMessage.success('删除成功')
    loadTasks()
    emit('refresh')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除任务失败:', error)
      ElMessage.error('删除任务失败')
    }
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      const payload = {
        ...formData.value,
        project: props.projectId
      }

      if (isEdit.value) {
        await request.put(`/projects/tasks/${currentTaskId.value}/`, payload)
        ElMessage.success('更新成功')
      } else {
        await request.post('/projects/tasks/', payload)
        ElMessage.success('创建成功')
      }

      dialogVisible.value = false
      loadTasks()
      emit('refresh')
    } catch (error) {
      console.error('保存任务失败:', error)
      ElMessage.error(isEdit.value ? '更新任务失败' : '创建任务失败')
    } finally {
      submitting.value = false
    }
  })
}

const resetForm = () => {
  formData.value = {
    name: '',
    parent: null,
    assignee: null,
    status: 'PENDING',
    planned_hours: 0,
    actual_hours: 0,
    progress: 0,
    start_date: '',
    end_date: '',
    description: ''
  }
  currentTaskId.value = null
  if (formRef.value) {
    formRef.value.clearValidate()
  }
}

onMounted(() => {
  loadTasks()
  loadProjectMembers()
})

defineExpose({
  loadTasks
})
</script>

<style scoped>
.task-management {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>

