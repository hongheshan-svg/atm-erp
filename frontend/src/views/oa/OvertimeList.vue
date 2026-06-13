<template>
  <div class="overtime-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>加班申请</span>
          <el-button type="primary" v-permission="'oa:overtime:create'" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新建加班
          </el-button>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 130px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="待审批" value="PENDING" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已拒绝" value="REJECTED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
        </el-form-item>
      </el-form>

      <el-empty v-if="!loading && list.length === 0" description="暂无加班记录" />

      <el-table v-else :data="list" v-loading="loading" stripe border>
        <el-table-column prop="overtime_date" label="加班日期" width="120" />
        <el-table-column prop="start_time" label="开始时间" width="100" />
        <el-table-column prop="end_time" label="结束时间" width="100" />
        <el-table-column prop="hours" label="时长(h)" width="90" align="right" />
        <el-table-column prop="project_name" label="关联项目" width="140" show-overflow-tooltip />
        <el-table-column prop="reason" label="加班原因" min-width="180" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="approver_name" label="审批人" width="100" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'DRAFT'" size="small" type="primary" @click="handleSubmit(row)">提交</el-button>
            <el-button v-if="row.status === 'DRAFT'" size="small" type="danger" v-permission="'oa:overtime:delete'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新建对话框 -->
    <el-dialog v-model="dialogVisible" title="新建加班申请" width="600px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="加班日期" prop="overtime_date">
          <el-date-picker v-model="form.overtime_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始时间" prop="start_time">
              <el-time-picker v-model="form.start_time" value-format="HH:mm:ss" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束时间" prop="end_time">
              <el-time-picker v-model="form.end_time" value-format="HH:mm:ss" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="加班原因" prop="reason">
          <el-input v-model="form.reason" type="textarea" :rows="3" placeholder="请输入加班原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存并提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getOvertimeRequests, createOvertimeRequest, submitOvertimeRequest, deleteOvertimeRequest } from '@/api/oa'

const loading = ref(false)
const saving = ref(false)
const list = ref<any[]>([])
const dialogVisible = ref(false)
const formRef = ref()

const searchForm = reactive({ status: '' })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const form = reactive({
  overtime_date: '',
  start_time: '',
  end_time: '',
  reason: ''
})

const rules = {
  overtime_date: [{ required: true, message: '请选择加班日期', trigger: 'change' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  end_time: [{ required: true, message: '请选择结束时间', trigger: 'change' }],
  reason: [{ required: true, message: '请输入加班原因', trigger: 'blur' }]
}

const getStatusType = (status: string) => {
  const types: Record<string, string> = {
    DRAFT: 'info',
    PENDING: 'warning',
    APPROVED: 'success',
    REJECTED: 'danger',
    CANCELLED: 'info'
  }
  return types[status] || 'info'
}

const loadData = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize, ...searchForm }
    const res = await getOvertimeRequests(params)
    if (Array.isArray(res)) {
      list.value = res
      pagination.total = res.length
    } else if (res && res.results) {
      list.value = res.results
      pagination.total = res.count || 0
    } else {
      list.value = []
      pagination.total = 0
    }
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  Object.assign(form, { overtime_date: '', start_time: '', end_time: '', reason: '' })
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    const res = await createOvertimeRequest({ ...form })
    const id = res?.id
    if (id) {
      try {
        await submitOvertimeRequest(id)
      } catch (e) {
        console.error('submit overtime error:', e)
      }
    }
    ElMessage.success('已创建并提交')
    dialogVisible.value = false
    loadData()
  } catch (error: any) {
    if (error?.response?.data) ElMessage.error(JSON.stringify(error.response.data))
  } finally {
    saving.value = false
  }
}

const handleSubmit = async (row: any) => {
  try {
    await submitOvertimeRequest(row.id)
    ElMessage.success('提交成功')
    loadData()
  } catch (error) {
    ElMessage.error('提交失败')
  }
}

const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm('确定要删除该加班申请吗？', '提示', { type: 'warning' })
    await deleteOvertimeRequest(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.overtime-list {
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
