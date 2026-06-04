<template>
  <div class="training-course-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>培训课程管理</span>
          <el-button type="primary" v-permission="'sales:order:create'" @click="handleCreate">新建课程</el-button>
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
        <el-table-column prop="code" label="课程编号" width="150" />
        <el-table-column prop="name" label="课程名称" />
        <el-table-column prop="course_type_display" label="课程类型" width="120" />
        <el-table-column prop="duration_hours" label="时长(小时)" width="100" />
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" v-permission="'sales:order:edit'" @click="handleEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑课程' : '新建课程'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="课程名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="课程类型" prop="course_type">
          <el-select v-model="form.course_type" style="width: 100%">
            <el-option label="操作培训" value="OPERATION" />
            <el-option label="维护培训" value="MAINTENANCE" />
            <el-option label="安全培训" value="SAFETY" />
            <el-option label="编程培训" value="PROGRAMMING" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="时长(小时)" prop="duration_hours">
          <el-input-number v-model="form.duration_hours" :min="0.5" :step="0.5" style="width: 100%" />
        </el-form-item>
        <el-form-item label="课程描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getTrainingCourses, createTrainingCourse, updateTrainingCourse } from '@/api/sales'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/sales/training-courses/', { onSuccess: () => loadData() })


const loading = ref(false)
const saving = ref(false)
const tableData = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({ id: null, name: '', course_type: '', duration_hours: 1, description: '', is_active: true })
const rules = {
  name: [{ required: true, message: '请输入课程名称', trigger: 'blur' }],
  course_type: [{ required: true, message: '请选择课程类型', trigger: 'change' }]
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getTrainingCourses({ page: page.value, page_size: pageSize.value })
    tableData.value = res.results || res.results || []
    total.value = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  isEdit.value = false
  Object.assign(form, { id: null, name: '', course_type: '', duration_hours: 1, description: '', is_active: true })
  formRef.value?.resetFields()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, { id: row.id, name: row.name, course_type: row.course_type, duration_hours: row.duration_hours, description: row.description, is_active: row.is_active })
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    if (isEdit.value) {
      await updateTrainingCourse(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createTrainingCourse(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
  } finally {
    saving.value = false
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.el-pagination { margin-top: 20px; }
</style>
