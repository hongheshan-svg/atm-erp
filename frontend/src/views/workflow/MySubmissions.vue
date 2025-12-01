<template>
  <div class="my-submissions">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>我的提交</span>
          <el-button type="primary" @click="loadData" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-table :data="workflows" v-loading="loading" stripe>
        <el-table-column prop="business_no" label="单据编号" width="150" />
        <el-table-column prop="business_type_display" label="业务类型" width="120" />
        <el-table-column prop="workflow_name" label="审批流程" width="150" />
        <el-table-column prop="amount" label="金额" width="120">
          <template #default="{ row }">
            <span v-if="row.amount">¥{{ Number(row.amount).toLocaleString() }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="150">
          <template #default="{ row }">
            <el-progress 
              :percentage="getProgress(row)" 
              :status="getProgressStatus(row.status)"
              :stroke-width="10"
            />
          </template>
        </el-table-column>
        <el-table-column prop="submit_time" label="提交时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.submit_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="completed_at" label="完成时间" width="160">
          <template #default="{ row }">
            {{ row.completed_at ? formatDate(row.completed_at) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="info" size="small" @click="viewDetail(row)">
              详情
            </el-button>
            <el-button 
              v-if="row.status === 'PENDING'"
              type="warning" 
              size="small" 
              @click="handleWithdraw(row)"
            >
              撤回
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && workflows.length === 0" description="暂无提交记录" />
    </el-card>

    <!-- Detail Dialog -->
    <el-dialog v-model="detailDialogVisible" title="审批详情" width="700px">
      <div v-if="currentWorkflow">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="单据编号">{{ currentWorkflow.business_no }}</el-descriptions-item>
          <el-descriptions-item label="业务类型">{{ currentWorkflow.business_type_display }}</el-descriptions-item>
          <el-descriptions-item label="审批流程">{{ currentWorkflow.workflow_name }}</el-descriptions-item>
          <el-descriptions-item label="金额">
            {{ currentWorkflow.amount ? `¥${Number(currentWorkflow.amount).toLocaleString()}` : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentWorkflow.status)">
              {{ currentWorkflow.status_display }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="提交时间">{{ formatDate(currentWorkflow.submit_time) }}</el-descriptions-item>
        </el-descriptions>

        <el-divider>审批记录</el-divider>

        <el-timeline>
          <el-timeline-item
            v-for="task in currentWorkflow.tasks"
            :key="task.id"
            :type="getTaskTimelineType(task.status)"
            :timestamp="formatDate(task.action_time || task.created_at)"
            placement="top"
          >
            <el-card>
              <h4>{{ task.step_name }} - {{ task.assignee_name }}</h4>
              <p>
                <el-tag :type="getStatusType(task.status)" size="small">
                  {{ task.status_display }}
                </el-tag>
              </p>
              <p v-if="task.comment" class="comment">
                审批意见: {{ task.comment }}
              </p>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getMySubmittedWorkflows, withdrawWorkflow } from '@/api/workflow'

const loading = ref(false)
const workflows = ref([])
const detailDialogVisible = ref(false)
const currentWorkflow = ref(null)

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getStatusType = (status) => {
  const types = {
    'PENDING': 'warning',
    'APPROVED': 'success',
    'REJECTED': 'danger',
    'CANCELLED': 'info',
    'WITHDRAWN': 'info',
    'SKIPPED': 'info',
  }
  return types[status] || 'info'
}

const getProgress = (row) => {
  if (row.status === 'APPROVED') return 100
  if (row.status === 'REJECTED' || row.status === 'WITHDRAWN') return 100
  if (!row.total_steps) return 0
  return Math.round((row.current_step - 1) / row.total_steps * 100)
}

const getProgressStatus = (status) => {
  if (status === 'APPROVED') return 'success'
  if (status === 'REJECTED') return 'exception'
  return null
}

const getTaskTimelineType = (status) => {
  const types = {
    'PENDING': 'warning',
    'APPROVED': 'success',
    'REJECTED': 'danger',
    'SKIPPED': 'info',
  }
  return types[status] || 'info'
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getMySubmittedWorkflows()
    workflows.value = res.results || res.data || res || []
  } catch (error) {
    console.error('Failed to load workflows:', error)
    workflows.value = []
  } finally {
    loading.value = false
  }
}

const viewDetail = (row) => {
  currentWorkflow.value = row
  detailDialogVisible.value = true
}

const handleWithdraw = async (row) => {
  try {
    await ElMessageBox.confirm('确定要撤回此审批吗？', '确认撤回', {
      type: 'warning'
    })
    await withdrawWorkflow(row.id)
    ElMessage.success('已撤回')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '操作失败')
    }
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.comment {
  color: #909399;
  font-size: 13px;
  margin-top: 5px;
}
</style>
