<template>
  <div class="project-detail">
    <el-page-header @back="goBack" title="项目">
      <template #content>
        <span class="text-large font-600 mr-3">{{ project.name }}</span>
      </template>
    </el-page-header>

    <el-card style="margin-top: 20px;">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="info">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="项目编号">{{ project.code }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(project.status)">{{ getStatusLabel(project.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="客户">{{ project.customer_name }}</el-descriptions-item>
            <el-descriptions-item label="负责人">{{ project.manager_name }}</el-descriptions-item>
            <el-descriptions-item label="开始日期">{{ project.start_date }}</el-descriptions-item>
            <el-descriptions-item label="结束日期">{{ project.end_date }}</el-descriptions-item>
            <el-descriptions-item label="总预算">{{ project.budget_total }}</el-descriptions-item>
            <el-descriptions-item label="实际成本">{{ project.actual_cost || 0 }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <el-tab-pane label="任务" name="tasks">
          <TaskManagement :project-id="projectId" ref="taskManagementRef" @refresh="loadProject" />
        </el-tab-pane>

        <el-tab-pane label="物料清单" name="bom">
          <BOMManagement :project-id="projectId" ref="bomManagementRef" @refresh="loadProject" />
        </el-tab-pane>

        <el-tab-pane label="成员" name="members">
          <MemberManagement :project-id="projectId" ref="memberManagementRef" @refresh="loadProject" />
        </el-tab-pane>

        <el-tab-pane label="成本分析" name="cost">
          <el-row :gutter="20" style="margin-bottom: 20px;">
            <el-col :span="6">
              <el-statistic title="收入" :value="project.revenue || 0" prefix="¥" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="材料成本" :value="project.material_cost || 0" prefix="¥" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="人工成本" :value="project.labor_cost || 0" prefix="¥" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="利润" :value="project.profit || 0" prefix="¥" />
            </el-col>
          </el-row>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getProject } from '@/api/projects/project'
import TaskManagement from '@/components/project/TaskManagement.vue'
import BOMManagement from '@/components/project/BOMManagement.vue'
import MemberManagement from '@/components/project/MemberManagement.vue'

const route = useRoute()
const router = useRouter()
const activeTab = ref('info')
const project = ref<Record<string, any>>({})
const taskManagementRef = ref(null)
const bomManagementRef = ref(null)
const memberManagementRef = ref(null)

const projectId = computed(() => route.params.id)
const isValidProjectId = computed(() => /^\d+$/.test(String(route.params.id || '')))

const statusMap = {
  'DRAFT': '草稿',
  'PLANNING': '规划中',
  'ACTIVE': '进行中',
  'PAUSED': '暂停',
  'COMPLETED': '已完成',
  'CANCELLED': '已取消',
  'ARCHIVED': '已归档'
}

const getStatusLabel = (status) => {
  return statusMap[status] || status
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'PLANNING': 'primary',
    'ACTIVE': 'success',
    'PAUSED': 'warning',
    'COMPLETED': '',
    'CANCELLED': 'danger',
    'ARCHIVED': 'info'
  }
  return types[status] || ''
}

const loadProject = async () => {
  if (!isValidProjectId.value) {
    router.replace('/projects')
    return
  }

  try {
    const response = await getProject(route.params.id)
    project.value = response.data || response
  } catch (error) {
    console.error('加载项目失败:', error)
    ElMessage.error('加载项目失败')
  }
}

const goBack = () => {
  router.back()
}

onMounted(() => {
  loadProject()
})
</script>

<style scoped>
.text-large {
  font-size: 18px;
}

.font-600 {
  font-weight: 600;
}

.mr-3 {
  margin-right: 12px;
}
</style>

