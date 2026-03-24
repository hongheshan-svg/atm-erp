<template>
  <el-dialog
    v-model="visible"
    title="审批进度"
    width="720px"
    :close-on-click-modal="true"
    @close="handleClose"
  >
    <div v-loading="loading">
      <!-- Header info -->
      <el-descriptions v-if="progressData" :column="3" border size="small" class="workflow-info">
        <el-descriptions-item label="审批流程">{{ progressData.workflow_name }}</el-descriptions-item>
        <el-descriptions-item label="单据编号">{{ progressData.business_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(progressData.status)" size="small">
            {{ progressData.status_display }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="提交人">{{ progressData.submitter_name }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ formatDate(progressData.submit_time) }}</el-descriptions-item>
        <el-descriptions-item label="进度">
          <span>{{ progressData.current_step }} / {{ progressData.total_steps }} 步</span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- Steps visualization -->
      <div v-if="progressData && progressData.nodes" class="workflow-steps">
        <div class="steps-header">审批节点</div>
        <el-steps
          :active="activeStep"
          :process-status="processStatus"
          :finish-status="finishStatus"
          align-center
          class="workflow-el-steps"
        >
          <el-step
            v-for="node in progressData.nodes"
            :key="node.step_order"
            :title="node.step_name"
            :description="getStepDescription(node)"
            :status="getElStepStatus(node)"
          />
        </el-steps>

        <!-- Detailed timeline -->
        <el-divider>审批记录</el-divider>
        <el-timeline class="workflow-timeline">
          <el-timeline-item
            v-for="node in progressData.nodes"
            :key="'tl-' + node.step_order"
            :type="timelineType(node.status)"
            :hollow="node.status === 'WAITING'"
            :timestamp="node.action_time ? formatDate(node.action_time) : (node.created_at ? formatDate(node.created_at) : '')"
            placement="top"
          >
            <div class="timeline-content">
              <div class="timeline-header">
                <span class="step-name">{{ node.step_name }}</span>
                <el-tag :type="statusType(node.status)" size="small">{{ node.status_display }}</el-tag>
              </div>
              <div class="timeline-detail">
                <span class="assignee">
                  <el-icon><User /></el-icon>
                  {{ node.assignee_name || '待分配' }}
                </span>
                <span v-if="node.approver_type_display" class="approver-type">
                  ({{ node.approver_type_display }})
                </span>
              </div>
              <div v-if="node.comment" class="timeline-comment">
                <el-icon><ChatDotRound /></el-icon>
                {{ node.comment }}
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>

      <el-empty v-if="!loading && !progressData" description="暂无审批记录" />
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { User, ChatDotRound } from '@element-plus/icons-vue'
import { getWorkflowProgress, getWorkflowByBusiness } from '@/api/workflow'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  instanceId: { type: [Number, String], default: null },
  businessType: { type: String, default: '' },
  businessId: { type: [Number, String], default: null },
})

const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const loading = ref(false)
const progressData = ref(null)

const activeStep = computed(() => {
  if (!progressData.value) return 0
  const { status, current_step, total_steps } = progressData.value
  if (status === 'APPROVED') return total_steps
  if (status === 'REJECTED' || status === 'WITHDRAWN') return current_step - 1
  return current_step - 1
})

const processStatus = computed(() => {
  if (!progressData.value) return 'process'
  if (progressData.value.status === 'REJECTED') return 'error'
  return 'process'
})

const finishStatus = computed(() => {
  return 'success'
})

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const statusType = (status) => {
  const map = {
    PENDING: 'warning',
    APPROVED: 'success',
    REJECTED: 'danger',
    CANCELLED: 'info',
    WITHDRAWN: 'info',
    WAITING: 'info',
    SKIPPED: 'info',
    TIMEOUT: 'danger',
  }
  return map[status] || 'info'
}

const timelineType = (status) => {
  const map = {
    PENDING: 'warning',
    APPROVED: 'success',
    REJECTED: 'danger',
    WAITING: 'info',
    SKIPPED: 'info',
    TIMEOUT: 'danger',
  }
  return map[status] || 'info'
}

const getElStepStatus = (node) => {
  const map = {
    APPROVED: 'success',
    REJECTED: 'error',
    PENDING: 'process',
    WAITING: 'wait',
    SKIPPED: 'success',
    TIMEOUT: 'error',
  }
  return map[node.status] || 'wait'
}

const getStepDescription = (node) => {
  let desc = node.assignee_name || '待分配'
  if (node.status === 'APPROVED') desc += ' · 已通过'
  else if (node.status === 'REJECTED') desc += ' · 已拒绝'
  else if (node.status === 'PENDING') desc += ' · 审批中'
  else if (node.status === 'WAITING') desc += ' · 等待中'
  return desc
}

const loadProgress = async () => {
  loading.value = true
  progressData.value = null
  try {
    if (props.instanceId) {
      progressData.value = await getWorkflowProgress(props.instanceId)
    } else if (props.businessType && props.businessId) {
      const res = await getWorkflowByBusiness(props.businessType, props.businessId)
      const inst = res.instance
      if (inst) {
        progressData.value = await getWorkflowProgress(inst.id)
      }
    }
  } catch (error) {
    console.error('获取审批进度失败:', error)
    ElMessage.error('获取审批进度失败')
  } finally {
    loading.value = false
  }
}

const handleClose = () => {
  visible.value = false
}

watch(() => props.modelValue, (val) => {
  if (val) loadProgress()
})
</script>

<style scoped>
.workflow-info {
  margin-bottom: 20px;
}
.workflow-steps {
  margin-top: 16px;
}
.steps-header {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 16px;
}
.workflow-el-steps {
  margin-bottom: 8px;
}
.workflow-timeline {
  margin-top: 12px;
  padding-left: 4px;
}
.timeline-content {
  padding: 4px 0;
}
.timeline-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.step-name {
  font-weight: 600;
  font-size: 14px;
}
.timeline-detail {
  color: #909399;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.assignee {
  display: flex;
  align-items: center;
  gap: 2px;
}
.approver-type {
  color: #b0b0b0;
  font-size: 12px;
}
.timeline-comment {
  margin-top: 4px;
  padding: 6px 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
