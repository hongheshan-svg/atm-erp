<template>
  <div class="cost-record-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>成本记录</span>
          <el-button type="primary" v-permission="'projects:project:create'" @click="handleCreate">新增记录</el-button>
        </div>
      </template>
      
      <el-form :inline="true" class="filter-form">
        <el-form-item label="项目">
          <el-select v-model="filters.project" placeholder="选择项目" clearable @change="loadData">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="成本类型">
          <el-select v-model="filters.cost_type" placeholder="全部" clearable @change="loadData">
            <el-option label="材料" value="MATERIAL" />
            <el-option label="人工" value="LABOR" />
            <el-option label="外协" value="OUTSOURCE" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
      </el-form>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="project_name" label="项目" width="150" />
        <el-table-column prop="cost_type_display" label="成本类型" width="100" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="amount" label="金额" width="120" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="cost_date" label="日期" width="120" />
        <el-table-column prop="is_verified" label="已核实" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_verified ? 'success' : 'warning'">{{ row.is_verified ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" v-permission="'projects:project:delete'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>

    <el-dialog v-model="dialogVisible" title="新增成本记录" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="项目" prop="project">
          <el-select v-model="form.project" placeholder="选择项目" filterable style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="成本类型" prop="cost_type">
          <el-select v-model="form.cost_type" placeholder="选择类型" style="width: 100%">
            <el-option label="材料" value="MATERIAL" />
            <el-option label="人工" value="LABOR" />
            <el-option label="外协" value="OUTSOURCE" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="金额" prop="amount">
          <el-input-number v-model="form.amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="日期" prop="cost_date">
          <el-date-picker v-model="form.cost_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProjectList, getCostRecordList, createCostRecord, deleteCostRecord } from '@/api/projects/project'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects/project-cost-records/')


const loading = ref(false)
const saving = ref(false)
const tableData = ref<any[]>([])
const projects = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filters = ref({ project: null, cost_type: null })
const dialogVisible = ref(false)
const formRef = ref(null)

const form = reactive({
  project: null, cost_type: '', description: '', amount: 0, cost_date: ''
})

const rules = {
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  cost_type: [{ required: true, message: '请选择成本类型', trigger: 'change' }],
  amount: [{ required: true, message: '请输入金额', trigger: 'blur' }],
  cost_date: [{ required: true, message: '请选择日期', trigger: 'change' }]
}

const formatMoney = (v) => v ? parseFloat(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'

const loadData = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value, ...filters.value }
    const res = await getCostRecordList(params)
    tableData.value = res.results || res.results || []
    total.value = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjectList({ page_size: 1000 })
    projects.value = res.results || res.results || []
  } catch (error) {
    console.error('CostRecordList getProjectList error:', error)
  }
}

const handleCreate = () => {
  Object.assign(form, { project: null, cost_type: '', description: '', amount: 0, cost_date: new Date().toISOString().split('T')[0] })
  formRef.value?.resetFields()
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    await createCostRecord(form)
    ElMessage.success('创建成功')
    dialogVisible.value = false
    loadData()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除此记录吗？', '提示', { type: 'warning' })
    await deleteCostRecord(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => { loadProjects(); loadData() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filter-form { margin-bottom: 20px; }
.el-pagination { margin-top: 20px; }
</style>
