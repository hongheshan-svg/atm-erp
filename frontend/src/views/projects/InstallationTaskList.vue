<template>
  <div class="installation-task-list">
    <!-- 统计概览 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="4" v-for="item in statusStats" :key="item.label">
        <el-card class="stat-card" :class="item.class">
          <el-statistic :title="item.label" :value="item.value" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 任务列表 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>安装调试任务</span>
          <div>
            <el-input v-model="queryParams.search" placeholder="搜索项目/客户" clearable style="width: 200px; margin-right: 12px" @keyup.enter="loadList" />
            <el-select v-model="queryParams.status" placeholder="全部状态" clearable style="width: 130px; margin-right: 12px" @change="loadList">
              <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <el-button type="primary" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon>新建任务
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="taskList" v-loading="loading" stripe>
        <el-table-column prop="task_number" label="任务编号" width="140" />
        <el-table-column prop="project_name" label="项目" min-width="180" />
        <el-table-column prop="customer_name" label="客户" min-width="150" />
        <el-table-column prop="site_address" label="现场地址" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="130">
          <template #default="{ row }">
            <el-progress :percentage="row.progress || 0" :stroke-width="8" />
          </template>
        </el-table-column>
        <el-table-column prop="leader_name" label="负责人" width="100" />
        <el-table-column prop="planned_start" label="计划开始" width="110" />
        <el-table-column prop="planned_end" label="计划完成" width="110" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="goDetail(row)">详情</el-button>
            <el-button size="small" link type="warning" @click="dispatchTask(row)" v-if="row.status === 'pending'">派工</el-button>
            <el-button size="small" link type="success" @click="updateStatus(row, 'in_transit')" v-if="row.status === 'dispatched'">出发</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size"
          :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @change="loadList" />
      </div>
    </el-card>

    <!-- 新建对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建安装调试任务" width="650px">
      <el-form :model="form" ref="formRef" label-width="100px" :rules="formRules">
        <el-form-item label="项目" prop="project">
          <el-input v-model="form.project" placeholder="项目ID" />
        </el-form-item>
        <el-form-item label="现场地址" prop="site_address">
          <el-input v-model="form.site_address" placeholder="安装现场地址" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.site_contact" placeholder="现场联系人" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.site_phone" placeholder="联系电话" />
        </el-form-item>
        <el-form-item label="计划周期">
          <el-date-picker v-model="form.dateRange" type="daterange" range-separator="至"
            start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="设备清单">
          <el-input type="textarea" v-model="form.equipment_list_text" :rows="3" placeholder="每行一个设备名称" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input type="textarea" v-model="form.notes" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="submitLoading">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getInstallationTasks, createInstallationTask, dispatchInstallationTask,
  updateInstallationTaskStatus, getInstallationTaskSummary
} from '@/api/projects/enhancement'

const router = useRouter()
const loading = ref(false)
const submitLoading = ref(false)
const taskList = ref([])
const total = ref(0)
const showCreateDialog = ref(false)
const formRef = ref(null)

const queryParams = reactive({ page: 1, page_size: 20, search: '', status: '' })
const form = reactive({ project: '', site_address: '', site_contact: '', site_phone: '', dateRange: [], equipment_list_text: '', notes: '' })
const formRules = {
  project: [{ required: true, message: '必填' }],
  site_address: [{ required: true, message: '必填' }]
}

const statusOptions = [
  { value: 'pending', label: '待安排' }, { value: 'dispatched', label: '已派工' },
  { value: 'in_transit', label: '在途中' }, { value: 'on_site', label: '现场施工' },
  { value: 'installing', label: '安装中' }, { value: 'commissioning', label: '调试中' },
  { value: 'acceptance', label: '验收中' }, { value: 'completed', label: '已完成' }
]

const statusType = (s) => ({ pending: 'info', dispatched: '', in_transit: 'warning', on_site: 'warning', installing: '', commissioning: '', acceptance: 'warning', completed: 'success' }[s] || 'info')
const statusLabel = (s) => statusOptions.find(o => o.value === s)?.label || s

const summary = ref({})
const statusStats = computed(() => [
  { label: '待安排', value: summary.value.pending || 0, class: '' },
  { label: '已派工', value: summary.value.dispatched || 0, class: '' },
  { label: '施工中', value: (summary.value.on_site || 0) + (summary.value.installing || 0), class: 'warning' },
  { label: '调试中', value: summary.value.commissioning || 0, class: 'warning' },
  { label: '验收中', value: summary.value.acceptance || 0, class: '' },
  { label: '已完成', value: summary.value.completed || 0, class: 'success' }
])

const loadList = async () => {
  loading.value = true
  try {
    const params = { ...queryParams }
    if (!params.search) delete params.search
    if (!params.status) delete params.status
    const res = await getInstallationTasks(params)
    taskList.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
  } finally { loading.value = false }
}

const loadSummary = async () => {
  try {
    const res = await getInstallationTaskSummary()
    summary.value = res.data || res || {}
  } catch {}
}

const goDetail = (row) => {
  router.push({ name: 'InstallationTaskDetail', params: { id: row.id } })
}

const dispatchTask = async (row) => {
  await ElMessageBox.confirm('确认派工？', '提示')
  await dispatchInstallationTask(row.id)
  ElMessage.success('派工成功')
  loadList()
  loadSummary()
}

const updateStatus = async (row, status) => {
  await updateInstallationTaskStatus(row.id, { status })
  ElMessage.success('状态更新成功')
  loadList()
  loadSummary()
}

const handleCreate = async () => {
  await formRef.value.validate()
  submitLoading.value = true
  try {
    const data = {
      ...form,
      planned_start: form.dateRange?.[0],
      planned_end: form.dateRange?.[1],
      equipment_list: form.equipment_list_text ? form.equipment_list_text.split('\n').filter(Boolean) : []
    }
    delete data.dateRange
    delete data.equipment_list_text
    await createInstallationTask(data)
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    loadList()
    loadSummary()
  } finally { submitLoading.value = false }
}

onMounted(() => { loadList(); loadSummary() })
</script>

<style scoped>
.installation-task-list { padding: 0; }
.stat-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
