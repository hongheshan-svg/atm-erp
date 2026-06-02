<template>
  <div class="customer-followup-container">
    <div class="page-header">
      <h2>客户跟进记录</h2>
      <div class="header-actions">
        <el-button type="primary" v-permission="'masterdata:customer:create'" @click="handleAdd">
          <el-icon><Plus /></el-icon> 新增跟进
        </el-button>
      </div>
    </div>
    
    <!-- 搜索和过滤 -->
    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" :model="queryParams">
        <el-form-item label="客户">
          <el-select v-model="queryParams.customer" placeholder="选择客户" clearable filterable>
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="跟进方式">
          <el-select v-model="queryParams.follow_type" placeholder="全部" clearable>
            <el-option v-for="t in followTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="跟进结果">
          <el-select v-model="queryParams.result" placeholder="全部" clearable>
            <el-option label="积极反馈" value="POSITIVE" />
            <el-option label="一般" value="NEUTRAL" />
            <el-option label="消极反馈" value="NEGATIVE" />
            <el-option label="待跟进" value="PENDING" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.total || 0 }}</div>
          <div class="stat-label">总跟进数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-primary">
          <div class="stat-value">{{ stats.this_week || 0 }}</div>
          <div class="stat-label">本周跟进</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-success">
          <div class="stat-value">{{ stats.this_month || 0 }}</div>
          <div class="stat-label">本月跟进</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card stat-warning">
          <div class="stat-value">{{ stats.pending || 0 }}</div>
          <div class="stat-label">待跟进</div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 数据表格 -->
    <el-card shadow="never">
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" border stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="follow_date" label="跟进日期" width="110" />
        <el-table-column prop="customer_name" label="客户" min-width="150" />
        <el-table-column prop="subject" label="跟进主题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="follow_type_display" label="跟进方式" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="getFollowTypeTag(row.follow_type)">
              {{ row.follow_type_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="follower_name" label="跟进人" width="100" />
        <el-table-column prop="result_display" label="结果" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="getResultTag(row.result)">
              {{ row.result_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="next_follow_date" label="下次跟进" width="110">
          <template #default="{ row }">
            <span :class="{ 'text-danger': isOverdue(row.next_follow_date) }">
              {{ row.next_follow_date || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">查看</el-button>
            <el-button type="primary" link size="small" v-permission="'masterdata:customer:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" v-permission="'masterdata:customer:delete'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        class="pagination"
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>
    
    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户" prop="customer">
              <el-select v-model="form.customer" placeholder="选择客户" filterable style="width: 100%">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="跟进方式" prop="follow_type">
              <el-select v-model="form.follow_type" placeholder="选择方式" style="width: 100%">
                <el-option v-for="t in followTypes" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="跟进日期" prop="follow_date">
              <el-date-picker v-model="form.follow_date" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="跟进结果" prop="result">
              <el-select v-model="form.result" placeholder="选择结果" style="width: 100%">
                <el-option label="积极反馈" value="POSITIVE" />
                <el-option label="一般" value="NEUTRAL" />
                <el-option label="消极反馈" value="NEGATIVE" />
                <el-option label="待跟进" value="PENDING" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="跟进主题" prop="subject">
          <el-input v-model="form.subject" placeholder="请输入跟进主题" />
        </el-form-item>
        <el-form-item label="跟进内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="4" placeholder="请输入跟进内容" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="下次跟进日期">
              <el-date-picker v-model="form.next_follow_date" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级">
              <el-select v-model="form.priority" placeholder="选择优先级" style="width: 100%">
                <el-option label="低" value="LOW" />
                <el-option label="中" value="MEDIUM" />
                <el-option label="高" value="HIGH" />
                <el-option label="紧急" value="URGENT" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="下次跟进计划">
          <el-input v-model="form.next_follow_plan" type="textarea" :rows="2" placeholder="请输入下次跟进计划" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>
    
    <!-- 查看详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="跟进详情" width="600px">
      <el-descriptions :column="2" border v-if="currentRecord">
        <el-descriptions-item label="客户">{{ currentRecord.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="跟进方式">{{ currentRecord.follow_type_display }}</el-descriptions-item>
        <el-descriptions-item label="跟进日期">{{ currentRecord.follow_date }}</el-descriptions-item>
        <el-descriptions-item label="跟进人">{{ currentRecord.follower_name }}</el-descriptions-item>
        <el-descriptions-item label="跟进主题" :span="2">{{ currentRecord.subject }}</el-descriptions-item>
        <el-descriptions-item label="跟进内容" :span="2">{{ currentRecord.content }}</el-descriptions-item>
        <el-descriptions-item label="跟进结果">
          <el-tag :type="getResultTag(currentRecord.result)">{{ currentRecord.result_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="优先级">{{ currentRecord.priority_display }}</el-descriptions-item>
        <el-descriptions-item label="下次跟进日期">{{ currentRecord.next_follow_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="下次跟进计划">{{ currentRecord.next_follow_plan || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getCustomerList, getCustomerFollowUpList, createCustomerFollowUp, updateCustomerFollowUp, deleteCustomerFollowUp, getFollowTypes, getFollowUpStatistics } from '@/api/masterdata'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/masterdata/')


const loading = ref(false)
const submitLoading = ref(false)
const tableData = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const dialogTitle = ref('新增跟进')
const isEdit = ref(false)
const currentRecord = ref(null)
const formRef = ref(null)
const customers = ref<any[]>([])
const followTypes = ref<any[]>([])
const stats = ref<Record<string, any>>({})

const queryParams = reactive({
  page: 1,
  page_size: 10,
  customer: null,
  follow_type: null,
  result: null
})

const form = reactive({
  customer: null,
  follow_type: 'PHONE',
  follow_date: null,
  subject: '',
  content: '',
  result: 'NEUTRAL',
  next_follow_date: null,
  next_follow_plan: '',
  priority: 'MEDIUM'
})

const rules = {
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  follow_type: [{ required: true, message: '请选择跟进方式', trigger: 'change' }],
  follow_date: [{ required: true, message: '请选择跟进日期', trigger: 'change' }],
  subject: [{ required: true, message: '请输入跟进主题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入跟进内容', trigger: 'blur' }],
  result: [{ required: true, message: '请选择跟进结果', trigger: 'change' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await getCustomerFollowUpList(queryParams)
    tableData.value = data.results || data
    total.value = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchCustomers = async () => {
  try {
    const data = await getCustomerList({ page_size: 1000 })
    customers.value = data.results || data
  } catch (e) {
    console.error(e)
  }
}

const fetchFollowTypes = async () => {
  try {
    const data = await getFollowTypes()
    followTypes.value = data
  } catch (e) {
    followTypes.value = [
      { value: 'VISIT', label: '客户拜访' },
      { value: 'PHONE', label: '电话沟通' },
      { value: 'EMAIL', label: '邮件往来' },
      { value: 'MEETING', label: '会议洽谈' },
      { value: 'VIDEO', label: '视频会议' },
      { value: 'WECHAT', label: '微信沟通' }
    ]
  }
}

const fetchStats = async () => {
  try {
    const data = await getFollowUpStatistics()
    stats.value = data
  } catch (e) {
    console.error(e)
  }
}

const resetQuery = () => {
  queryParams.customer = null
  queryParams.follow_type = null
  queryParams.result = null
  queryParams.page = 1
  fetchData()
}

const handleAdd = () => {
  isEdit.value = false
  dialogTitle.value = '新增跟进'
  Object.assign(form, {
    customer: null,
    follow_type: 'PHONE',
    follow_date: new Date().toISOString().split('T')[0],
    subject: '',
    content: '',
    result: 'NEUTRAL',
    next_follow_date: null,
    next_follow_plan: '',
    priority: 'MEDIUM'
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  dialogTitle.value = '编辑跟进'
  Object.assign(form, row)
  form.id = row.id
  dialogVisible.value = true
}

const handleView = (row) => {
  currentRecord.value = row
  viewDialogVisible.value = true
}

const handleSubmit = async () => {
  const valid = await formRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateCustomerFollowUp(form.id, form)
      ElMessage.success('修改成功')
    } else {
      await createCustomerFollowUp(form)
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    fetchData()
    fetchStats()
  } catch (e) {
    console.error(e)
    ElMessage.error('操作失败')
  } finally {
    submitLoading.value = false
  }
}

const handleDelete = (row) => {
  ElMessageBox.confirm('确定要删除此跟进记录吗？', '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await deleteCustomerFollowUp(row.id)
      ElMessage.success('删除成功')
      fetchData()
      fetchStats()
    } catch (e) {
      ElMessage.error('删除失败')
    }
  })
}

const getFollowTypeTag = (type) => {
  const tags = {
    VISIT: 'success',
    PHONE: '',
    EMAIL: 'info',
    MEETING: 'warning',
    VIDEO: 'primary'
  }
  return tags[type] || ''
}

const getResultTag = (result) => {
  const tags = {
    POSITIVE: 'success',
    NEUTRAL: 'info',
    NEGATIVE: 'danger',
    PENDING: 'warning'
  }
  return tags[result] || ''
}

const isOverdue = (date) => {
  if (!date) return false
  return new Date(date) < new Date(new Date().toISOString().split('T')[0])
}

onMounted(() => {
  fetchData()
  fetchCustomers()
  fetchFollowTypes()
  fetchStats()
})
</script>

<style scoped>
.customer-followup-container {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.filter-card {
  margin-bottom: 16px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 10px 0;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.stat-primary .stat-value {
  color: #409eff;
}

.stat-success .stat-value {
  color: #67c23a;
}

.stat-warning .stat-value {
  color: #e6a23c;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

.text-danger {
  color: #f56c6c;
  font-weight: bold;
}
</style>
