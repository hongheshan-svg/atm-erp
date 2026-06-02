<template>
  <div class="technician-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>技术员管理</span>
          <el-button type="primary" v-permission="'projects:project:create'" @click="handleCreate">添加技术员</el-button>
        </div>
      </template>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="employee_no" label="工号" width="120" />
        <el-table-column prop="user_name" label="姓名" width="120" />
        <el-table-column prop="skill_level_display" label="技能等级" width="100" />
        <el-table-column prop="phone" label="联系电话" width="140" />
        <el-table-column prop="is_available" label="可用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_available ? 'success' : 'danger'">{{ row.is_available ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="skills_display" label="技能" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" v-permission="'projects:project:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="handleSchedule(row)">排班</el-button>
            <el-button link type="danger" v-permission="'projects:project:delete'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑技术员' : '添加技术员'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="用户" prop="user">
          <el-select v-model="form.user" placeholder="选择用户" filterable style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.username || u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="工号" prop="employee_no">
          <el-input v-model="form.employee_no" />
        </el-form-item>
        <el-form-item label="技能等级" prop="skill_level">
          <el-select v-model="form.skill_level" style="width: 100%">
            <el-option label="初级" value="JUNIOR" />
            <el-option label="中级" value="INTERMEDIATE" />
            <el-option label="高级" value="SENIOR" />
            <el-option label="专家" value="EXPERT" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="技能描述">
          <el-input v-model="form.skills" type="textarea" :rows="3" placeholder="如: PLC编程, 电气调试, 机械装配" />
        </el-form-item>
        <el-form-item label="是否可用">
          <el-switch v-model="form.is_available" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 排班对话框 -->
    <el-dialog v-model="scheduleDialogVisible" title="技术员排班" width="500px">
      <el-form :model="scheduleForm" label-width="100px">
        <el-form-item label="技术员">
          <el-input :model-value="currentRow?.user_name" disabled />
        </el-form-item>
        <el-form-item label="排班日期">
          <el-date-picker v-model="scheduleForm.date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="班次">
          <el-select v-model="scheduleForm.shift" style="width: 100%">
            <el-option label="早班" value="MORNING" />
            <el-option label="中班" value="AFTERNOON" />
            <el-option label="晚班" value="NIGHT" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目">
          <el-select v-model="scheduleForm.project" placeholder="选择项目" filterable clearable style="width: 100%">
            <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scheduleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveSchedule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTechnicianProfileList, createTechnicianProfile, updateTechnicianProfile, deleteTechnicianProfile, scheduleTechnician } from '@/api/projects/technician'
import { getProjectList } from '@/api/projects/project'
import { getUsers } from '@/api/auth'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects_technician/')


const loading = ref(false)
const saving = ref(false)
const tableData = ref<any[]>([])
const users = ref<any[]>([])
const projectList = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const dialogVisible = ref(false)
const scheduleDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const currentRow = ref(null)

const form = reactive({ id: null, user: null, employee_no: '', skill_level: '', phone: '', skills: '', is_available: true })
const scheduleForm = reactive({ date: '', shift: 'MORNING', project: null })

const rules = {
  user: [{ required: true, message: '请选择用户', trigger: 'change' }],
  skill_level: [{ required: true, message: '请选择技能等级', trigger: 'change' }]
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getTechnicianProfileList({ page: page.value, page_size: pageSize.value })
    tableData.value = res.results || res.results || []
    total.value = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadUsers = async () => {
  try {
    const res = await getUsers({ page_size: 1000 })
    users.value = res.results || res.results || []
  } catch (error) {
    console.error('TechnicianList getUsers error:', error)
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjectList({ page_size: 1000 })
    projectList.value = res.results || res.results || []
  } catch (error) {
    console.error('TechnicianList getProjectList error:', error)
  }
}

const handleCreate = () => {
  isEdit.value = false
  Object.assign(form, { id: null, user: null, employee_no: '', skill_level: '', phone: '', skills: '', is_available: true })
  formRef.value?.resetFields()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, { id: row.id, user: row.user, employee_no: row.employee_no, skill_level: row.skill_level, phone: row.phone, skills: row.skills, is_available: row.is_available })
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    if (isEdit.value) {
      await updateTechnicianProfile(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createTechnicianProfile(form)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
  } finally {
    saving.value = false
  }
}

const handleSchedule = (row) => {
  currentRow.value = row
  scheduleForm.date = new Date().toISOString().split('T')[0]
  scheduleForm.shift = 'MORNING'
  scheduleForm.project = null
  scheduleDialogVisible.value = true
}

const saveSchedule = async () => {
  try {
    saving.value = true
    await scheduleTechnician(currentRow.value.id, scheduleForm)
    ElMessage.success('排班成功')
    scheduleDialogVisible.value = false
  } catch (error) {
    ElMessage.error('排班失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除此技术员吗？', '提示', { type: 'warning' })
    await deleteTechnicianProfile(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => { loadUsers(); loadProjects(); loadData() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.el-pagination { margin-top: 20px; }
</style>
