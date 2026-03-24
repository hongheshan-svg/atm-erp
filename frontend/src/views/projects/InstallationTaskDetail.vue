<template>
  <div class="installation-task-detail" v-loading="loading">
    <!-- 任务基本信息 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>安装调试任务 - {{ task.task_number }}</span>
          <div>
            <el-tag :type="statusType(task.status)" size="large">{{ statusLabel(task.status) }}</el-tag>
            <el-button type="primary" style="margin-left: 12px;" @click="showStatusDialog = true">更新状态</el-button>
            <el-button @click="$router.back()">返回</el-button>
          </div>
        </div>
      </template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="项目">{{ task.project_name }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ task.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="负责人">{{ task.leader_name }}</el-descriptions-item>
        <el-descriptions-item label="现场地址" :span="2">{{ task.site_address }}</el-descriptions-item>
        <el-descriptions-item label="联系人">{{ task.site_contact }} {{ task.site_phone }}</el-descriptions-item>
        <el-descriptions-item label="计划开始">{{ task.planned_start }}</el-descriptions-item>
        <el-descriptions-item label="计划完成">{{ task.planned_end }}</el-descriptions-item>
        <el-descriptions-item label="进度">
          <el-progress :percentage="task.progress || 0" />
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-tabs v-model="activeTab" style="margin-top: 16px;">
      <!-- 施工日志 -->
      <el-tab-pane label="施工日志" name="logs">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>施工日志</span>
              <el-button type="primary" size="small" @click="showLogDialog = true"><el-icon><Plus /></el-icon>新增日志</el-button>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item v-for="log in siteLogs" :key="log.id" :timestamp="log.log_date" placement="top"
              :type="log.log_type === 'issue' ? 'danger' : (log.log_type === 'milestone' ? 'success' : '')">
              <el-card shadow="hover">
                <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                  <el-tag size="small" :type="logTypeTag(log.log_type)">{{ logTypeLabel(log.log_type) }}</el-tag>
                  <span style="color:#909399;font-size:12px;">{{ log.created_by_name }}</span>
                </div>
                <p>{{ log.content }}</p>
                <p v-if="log.work_hours" style="color:#909399;font-size:12px;">工时: {{ log.work_hours }}h | 人数: {{ log.workers_count }}</p>
              </el-card>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-tab-pane>

      <!-- 调试记录 -->
      <el-tab-pane label="调试记录" name="commissioning">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>调试记录</span>
              <el-button type="primary" size="small" @click="showCommDialog = true"><el-icon><Plus /></el-icon>新增调试</el-button>
            </div>
          </template>
          <el-table :data="commRecords" stripe size="small">
            <el-table-column prop="test_item" label="测试项目" min-width="150" />
            <el-table-column prop="test_date" label="测试日期" width="110" />
            <el-table-column label="结果" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.result === 'pass' ? 'success' : (row.result === 'fail' ? 'danger' : 'warning')" size="small">
                  {{ { pass: '通过', fail: '不合格', conditional: '有条件' }[row.result] || row.result }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="tester_name" label="测试人" width="100" />
            <el-table-column prop="notes" label="备注" min-width="200" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 现场问题 -->
      <el-tab-pane label="现场问题" name="issues">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>现场问题</span>
              <el-button type="primary" size="small" @click="showIssueDialog = true"><el-icon><Plus /></el-icon>记录问题</el-button>
            </div>
          </template>
          <el-table :data="siteIssues" stripe size="small">
            <el-table-column prop="title" label="问题标题" min-width="200" />
            <el-table-column label="严重程度" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="severityType(row.severity)" size="small">{{ severityLabel(row.severity) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'resolved' ? 'success' : (row.status === 'open' ? 'danger' : 'warning')" size="small">
                  {{ { open: '待处理', processing: '处理中', resolved: '已解决', closed: '关闭' }[row.status] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reported_by_name" label="报告人" width="100" />
            <el-table-column prop="created_at" label="时间" width="160" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button size="small" link type="success" @click="resolveIssue(row)" v-if="row.status !== 'resolved'">解决</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 客户验收 -->
      <el-tab-pane label="客户验收" name="acceptance">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>客户验收记录</span>
              <el-button type="primary" size="small" @click="showAccDialog = true"><el-icon><Plus /></el-icon>新建验收</el-button>
            </div>
          </template>
          <el-table :data="acceptances" stripe size="small">
            <el-table-column prop="acceptance_date" label="验收日期" width="110" />
            <el-table-column label="结果" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.result === 'accepted' ? 'success' : (row.result === 'rejected' ? 'danger' : 'warning')" size="small">
                  {{ { accepted: '通过', conditional: '有条件', rejected: '拒绝' }[row.result] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="customer_representative" label="客户代表" width="120" />
            <el-table-column prop="notes" label="备注" min-width="200" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 状态更新对话框 -->
    <el-dialog v-model="showStatusDialog" title="更新任务状态" width="400px">
      <el-form label-width="80px">
        <el-form-item label="新状态">
          <el-select v-model="newStatus" style="width: 100%">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showStatusDialog = false">取消</el-button>
        <el-button type="primary" @click="doUpdateStatus">确定</el-button>
      </template>
    </el-dialog>

    <!-- 日志对话框 -->
    <el-dialog v-model="showLogDialog" title="新增施工日志" width="600px">
      <el-form :model="logForm" label-width="80px">
        <el-form-item label="类型">
          <el-select v-model="logForm.log_type" style="width: 100%">
            <el-option label="日常记录" value="daily" />
            <el-option label="进度更新" value="progress" />
            <el-option label="问题记录" value="issue" />
            <el-option label="里程碑" value="milestone" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="logForm.log_date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input type="textarea" v-model="logForm.content" :rows="4" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="工时"><el-input-number v-model="logForm.work_hours" :min="0" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="人数"><el-input-number v-model="logForm.workers_count" :min="1" style="width:100%" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showLogDialog = false">取消</el-button>
        <el-button type="primary" @click="submitLog">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getInstallationTask, updateInstallationTaskStatus,
  getSiteLogs, createSiteLog,
  getCommissioningRecords, getSiteIssues, resolveSiteIssue,
  getCustomerAcceptances
} from '@/api/projects/enhancement'

const route = useRoute()
const loading = ref(false)
const task = ref({})
const siteLogs = ref([])
const commRecords = ref([])
const siteIssues = ref([])
const acceptances = ref([])
const activeTab = ref('logs')
const showStatusDialog = ref(false)
const showLogDialog = ref(false)
const showCommDialog = ref(false)
const showIssueDialog = ref(false)
const showAccDialog = ref(false)
const newStatus = ref('')

const logForm = reactive({ log_type: 'daily', log_date: '', content: '', work_hours: 8, workers_count: 1 })

const statusOptions = [
  { value: 'pending', label: '待安排' }, { value: 'dispatched', label: '已派工' },
  { value: 'in_transit', label: '在途中' }, { value: 'on_site', label: '现场施工' },
  { value: 'installing', label: '安装中' }, { value: 'commissioning', label: '调试中' },
  { value: 'acceptance', label: '验收中' }, { value: 'completed', label: '已完成' }
]

const statusType = (s) => ({ pending: 'info', dispatched: '', in_transit: 'warning', on_site: 'warning', installing: '', commissioning: '', acceptance: 'warning', completed: 'success' }[s] || 'info')
const statusLabel = (s) => statusOptions.find(o => o.value === s)?.label || s
const logTypeTag = (t) => ({ daily: 'info', progress: '', issue: 'danger', milestone: 'success' }[t] || 'info')
const logTypeLabel = (t) => ({ daily: '日常', progress: '进度', issue: '问题', milestone: '里程碑' }[t] || t)
const severityType = (s) => ({ low: 'info', medium: 'warning', high: 'danger', critical: 'danger' }[s] || 'info')
const severityLabel = (s) => ({ low: '低', medium: '中', high: '高', critical: '严重' }[s] || s)

const taskId = route.params.id

const loadTask = async () => {
  loading.value = true
  try {
    const res = await getInstallationTask(taskId)
    task.value = res.data || res
  } finally { loading.value = false }
}

const loadLogs = async () => {
  const res = await getSiteLogs({ task: taskId })
  siteLogs.value = res.data?.results || res.results || []
}

const loadComm = async () => {
  const res = await getCommissioningRecords({ task: taskId })
  commRecords.value = res.data?.results || res.results || []
}

const loadIssues = async () => {
  const res = await getSiteIssues({ task: taskId })
  siteIssues.value = res.data?.results || res.results || []
}

const loadAcceptances = async () => {
  const res = await getCustomerAcceptances({ task: taskId })
  acceptances.value = res.data?.results || res.results || []
}

const doUpdateStatus = async () => {
  await updateInstallationTaskStatus(taskId, { status: newStatus.value })
  ElMessage.success('状态更新成功')
  showStatusDialog.value = false
  loadTask()
}

const submitLog = async () => {
  await createSiteLog({ ...logForm, task: taskId })
  ElMessage.success('日志已保存')
  showLogDialog.value = false
  loadLogs()
}

const resolveIssue = async (row) => {
  const { value } = await ElMessageBox.prompt('请输入解决方案', '解决问题', { inputType: 'textarea' })
  await resolveSiteIssue(row.id, { resolution: value })
  ElMessage.success('已解决')
  loadIssues()
}

onMounted(() => {
  loadTask()
  loadLogs()
  loadComm()
  loadIssues()
  loadAcceptances()
})
</script>

<style scoped>
.installation-task-detail { padding: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
