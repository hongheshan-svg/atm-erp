<template>
  <div class="training-plan-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>培训计划管理</span>
          <el-button type="primary" v-permission="'sales:order:create'" @click="handleCreate">新建培训计划</el-button>
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
        <el-table-column prop="plan_no" label="计划编号" width="150" />
        <el-table-column prop="name" label="计划名称" />
        <el-table-column prop="customer_name" label="客户" width="150" />
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
            <el-button link type="primary" v-permission="'sales:order:edit'" @click="handleEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>

    <!-- 查看详情 -->
    <el-dialog v-model="viewDialogVisible" title="培训计划详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="计划编号">{{ viewDetail.plan_no }}</el-descriptions-item>
        <el-descriptions-item label="计划名称">{{ viewDetail.name }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ viewDetail.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(viewDetail.status)">{{ viewDetail.status_display || viewDetail.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="开始日期">{{ viewDetail.start_date }}</el-descriptions-item>
        <el-descriptions-item label="结束日期">{{ viewDetail.end_date }}</el-descriptions-item>
        <el-descriptions-item label="培训地点" :span="2">{{ viewDetail.location || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ viewDetail.remarks || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template v-if="viewDetail.courses && viewDetail.courses.length">
        <h4 style="margin: 16px 0 8px">课程安排</h4>
        <el-table :data="viewDetail.courses" stripe size="small">
          <el-table-column prop="course_name" label="课程" />
          <el-table-column prop="trainer" label="讲师" width="120" />
          <el-table-column prop="date" label="日期" width="120" />
        </el-table>
      </template>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑培训计划' : '新建培训计划'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="计划名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入计划名称" />
        </el-form-item>
        <el-form-item label="客户">
          <el-select v-model="form.customer" placeholder="选择客户" filterable clearable style="width: 100%">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期" prop="start_date">
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束日期" prop="end_date">
          <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="培训地点">
          <el-input v-model="form.location" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remarks" type="textarea" :rows="3" />
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
import { getTrainingPlans, getTrainingPlan, createTrainingPlan, updateTrainingPlan } from '@/api/sales'
import { getCustomerList } from '@/api/masterdata'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/sales/')


const loading = ref(false)
const saving = ref(false)
const tableData = ref<any[]>([])
const customers = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const viewDetail = ref<Record<string, any>>({})

const form = reactive({ id: null, name: '', customer: null, start_date: '', end_date: '', location: '', remarks: '' })
const rules = { name: [{ required: true, message: '请输入计划名称', trigger: 'blur' }] }
const getStatusType = (status) => ({ 'DRAFT': 'info', 'PLANNED': 'warning', 'IN_PROGRESS': 'primary', 'COMPLETED': 'success' }[status] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await getTrainingPlans({ page: page.value, page_size: pageSize.value })
    tableData.value = res.results || res.results || []
    total.value = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const res = await getCustomerList({ page_size: 1000 })
    customers.value = res.results || res.results || []
  } catch (error) {
    console.error('TrainingPlanList getCustomerList error:', error)
  }
}

const handleView = async (row) => {
  try {
    const res = await getTrainingPlan(row.id)
    viewDetail.value = res
    viewDialogVisible.value = true
  } catch (error) {
    console.error(error)
    viewDetail.value = row
    viewDialogVisible.value = true
  }
}

const handleCreate = () => {
  isEdit.value = false
  Object.assign(form, { id: null, name: '', customer: null, start_date: '', end_date: '', location: '', remarks: '' })
  formRef.value?.resetFields()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, { id: row.id, name: row.name, customer: row.customer, start_date: row.start_date, end_date: row.end_date, location: row.location, remarks: row.remarks })
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    if (isEdit.value) {
      await updateTrainingPlan(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createTrainingPlan(form)
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

onMounted(() => { loadCustomers(); loadData() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.el-pagination { margin-top: 20px; }
</style>
