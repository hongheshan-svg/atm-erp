<template>
  <div class="finite-capacity-list">
    <!-- 排程概览 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="排程计划" :value="stats.totalPlans" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="已排工单" :value="stats.scheduledTasks" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card warning">
          <el-statistic title="平均利用率" :value="stats.avgUtilization" suffix="%" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="延期风险" :value="stats.delayRisks" value-style="color: #F56C6C" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 排程计划列表 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>有限产能排程计划</span>
          <div>
            <el-select v-model="queryParams.status" placeholder="状态" clearable style="width: 120px; margin-right: 12px" @change="loadList">
              <el-option label="草稿" value="draft" />
              <el-option label="运行中" value="running" />
              <el-option label="已完成" value="completed" />
              <el-option label="已发布" value="published" />
            </el-select>
            <el-button type="primary" @click="handleCreate">
              <el-icon><Plus /></el-icon>新建排程
            </el-button>
          </div>
        </div>
      </template>

      <!-- 批量操作 -->

      <div v-if="selectedRows.length > 0" class="batch-toolbar">

        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>

        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>

        <el-button size="small" @click="batchExport">导出选中</el-button>

      </div>

      <el-table :data="planList" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="name" label="计划名称" min-width="180" />
        <el-table-column prop="plan_start" label="计划开始" width="120" />
        <el-table-column prop="plan_end" label="计划结束" width="120" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="scheduling_strategy" label="策略" width="120">
          <template #default="{ row }">
            {{ strategyLabel(row.scheduling_strategy) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_tasks" label="任务数" width="80" align="center" />
        <el-table-column prop="avg_utilization" label="设备利用率" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.avg_utilization || 0" :status="row.avg_utilization > 90 ? 'exception' : ''" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="handleView(row)">查看</el-button>
            <el-button size="small" link type="warning" @click="runSchedule(row)" :disabled="row.status === 'published'">运行排程</el-button>
            <el-button size="small" link type="success" @click="publishSchedule(row)" :disabled="row.status !== 'completed'">发布</el-button>
            <el-button size="small" link type="danger" @click="handleDelete(row)" :disabled="row.status === 'published'">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size"
          :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @change="loadList" />
      </div>
    </el-card>

    <!-- 甘特图 -->
    <el-card style="margin-top: 16px" v-if="selectedPlan">
      <template #header>
        <div class="card-header">
          <span>排程甘特图 - {{ selectedPlan.name }}</span>
        </div>
      </template>
      <div ref="ganttRef" style="height: 400px"></div>
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑排程' : '新建排程'" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="计划名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入计划名称" />
        </el-form-item>
        <el-form-item label="计划周期" prop="dateRange">
          <el-date-picker v-model="form.dateRange" type="daterange" range-separator="至"
            start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="排程策略" prop="scheduling_strategy">
          <el-select v-model="form.scheduling_strategy" style="width: 100%">
            <el-option label="最早开始" value="earliest_start" />
            <el-option label="最晚开始" value="latest_start" />
            <el-option label="瓶颈优先" value="bottleneck_first" />
            <el-option label="订单优先级" value="priority_based" />
          </el-select>
        </el-form-item>
        <el-form-item label="考虑换型" prop="consider_setup_time">
          <el-switch v-model="form.consider_setup_time" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, WarningFilled } from '@element-plus/icons-vue'
import {
getFiniteCapacityPlans, createFiniteCapacityPlan, updateFiniteCapacityPlan,
  deleteFiniteCapacityPlan, runFiniteCapacitySchedule, publishFiniteCapacitySchedule,
  getGanttData
} from '@/api/production'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/production/finite-capacity-plans/', { onSuccess: () => loadList() })


const loading = ref(false)
const submitLoading = ref(false)
const planList = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const isEdit = ref(false)
const selectedPlan = ref(null)
const formRef = ref(null)
const ganttRef = ref(null)

const stats = reactive({ totalPlans: 0, scheduledTasks: 0, avgUtilization: 0, delayRisks: 0 })
const queryParams = reactive({ page: 1, page_size: 20, status: '' })
const form = reactive({
  id: null, name: '', dateRange: [], scheduling_strategy: 'earliest_start', consider_setup_time: true
})
const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  dateRange: [{ required: true, message: '请选择周期', trigger: 'change' }],
  scheduling_strategy: [{ required: true, message: '请选择策略', trigger: 'change' }]
}

const statusType = (s) => ({ draft: 'info', running: 'warning', completed: 'success', published: '', failed: 'danger' }[s] || 'info')
const statusLabel = (s) => ({ draft: '草稿', running: '运行中', completed: '已完成', published: '已发布', failed: '失败' }[s] || s)
const strategyLabel = (s) => ({ earliest_start: '最早开始', latest_start: '最晚开始', bottleneck_first: '瓶颈优先', priority_based: '订单优先级' }[s] || s)

const loadList = async () => {
  loading.value = true
  try {
    const params = { ...queryParams }
    if (params.status === '') delete params.status
    const res = await getFiniteCapacityPlans(params)
    planList.value = res.results || res.results || []
    total.value = res.count || res.count || 0
    stats.totalPlans = total.value
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  isEdit.value = false
  Object.assign(form, { id: null, name: '', dateRange: [], scheduling_strategy: 'earliest_start', consider_setup_time: true })
  dialogVisible.value = true
}

const handleView = (row) => {
  selectedPlan.value = row
}

const handleSubmit = async () => {
  await formRef.value.validate()
  submitLoading.value = true
  try {
    const data = {
      name: form.name,
      plan_start: form.dateRange[0],
      plan_end: form.dateRange[1],
      scheduling_strategy: form.scheduling_strategy,
      consider_setup_time: form.consider_setup_time
    }
    if (isEdit.value) {
      await updateFiniteCapacityPlan(form.id, data)
    } else {
      await createFiniteCapacityPlan(data)
    }
    ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
    dialogVisible.value = false
    loadList()
  } finally {
    submitLoading.value = false
  }
}

const runSchedule = async (row) => {
  await ElMessageBox.confirm('确认运行排程计算？', '提示')
  try {
    await runFiniteCapacitySchedule(row.id)
    ElMessage.success('排程已开始运行')
    loadList()
  } catch (error) {
    console.error('FiniteCapacityList loadList error:', error)
  }
}

const publishSchedule = async (row) => {
  await ElMessageBox.confirm('确认发布排程？', '提示')
  try {
    await publishFiniteCapacitySchedule(row.id)
    ElMessage.success('排程已发布')
    loadList()
  } catch (error) {
    console.error('FiniteCapacityList loadList error:', error)
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm('确认删除？', '提示')
  try {
    await deleteFiniteCapacityPlan(row.id)
    ElMessage.success('删除成功')
    loadList()
  } catch (error) {
    console.error('FiniteCapacityList loadList error:', error)
  }
}

onMounted(() => { loadList() })
</script>

<style scoped>
.finite-capacity-list { padding: 0; }
.stat-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
