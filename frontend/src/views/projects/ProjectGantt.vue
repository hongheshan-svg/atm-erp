<template>
  <div class="project-gantt">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">项目甘特图</span>
          <div>
            <el-select v-model="selectedProject" placeholder="选择项目" @change="loadProjectTasks" style="width: 300px; margin-right: 10px;">
              <el-option
                v-for="project in projects"
                :key="project.id"
                :label="project.name"
                :value="project.id"
              />
            </el-select>
            <el-button type="primary" @click="refreshData">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <div v-loading="loading" style="min-height: 400px;">
        <div v-if="!selectedProject" class="empty-state">
          <el-empty description="请选择一个项目查看甘特图" />
        </div>
        
        <div v-else>
          <!-- Project Info -->
          <div class="project-info" v-if="currentProject">
            <el-descriptions :column="4" border>
              <el-descriptions-item label="项目名称">{{ currentProject.name }}</el-descriptions-item>
              <el-descriptions-item label="项目经理">{{ currentProject.manager_name }}</el-descriptions-item>
              <el-descriptions-item label="开始日期">{{ currentProject.start_date }}</el-descriptions-item>
              <el-descriptions-item label="结束日期">{{ currentProject.end_date }}</el-descriptions-item>
            </el-descriptions>
          </div>

          <!-- Gantt Chart -->
          <div class="gantt-container" ref="ganttContainer">
            <g-gantt-chart
              v-if="tasks.length > 0"
              :chart-start="chartStart"
              :chart-end="chartEnd"
              precision="day"
              bar-start="start"
              bar-end="end"
              grid
              :width="'100%'"
              :row-height="40"
            >
              <g-gantt-row
                v-for="task in tasks"
                :key="task.id"
                :label="task.label"
                :bars="task.bars"
                highlight-on-hover
              >
                <template #bar-label="{ bar }">
                  <div class="bar-label">{{ bar.label }}</div>
                </template>
              </g-gantt-row>
            </g-gantt-chart>
            
            <el-empty v-else description="该项目暂无任务" />
          </div>

          <!-- Task List -->
          <div class="task-list" style="margin-top: 30px;">
            <h3>任务列表</h3>
            <el-table :data="taskList" border stripe>
              <el-table-column type="index" label="#" width="50" />
              <el-table-column prop="name" label="任务名称" />
              <el-table-column prop="assignee_name" label="负责人" width="120" />
              <el-table-column prop="start_date" label="开始日期" width="120" />
              <el-table-column prop="end_date" label="结束日期" width="120" />
              <el-table-column prop="planned_hours" label="计划工时" width="100" />
              <el-table-column prop="actual_hours" label="实际工时" width="100" />
              <el-table-column prop="progress_percent" label="进度" width="100">
                <template #default="{ row }">
                  <el-progress :percentage="row.progress_percent" :status="getProgress状态(row.progress_percent)" />
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="get状态Type(row.status)">
                    {{ get状态Label(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { GGanttChart, GGanttRow } from 'vue-ganttastic'
import { getProjectList, getProject, getTaskList } from '@/api/projects/project'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const projects = ref([])
const selectedProject = ref(null)
const currentProject = ref(null)
const taskList = ref([])
const ganttContainer = ref(null)

const chartStart = computed(() => {
  if (currentProject.value && currentProject.value.start_date) {
    return currentProject.value.start_date
  }
  return new Date().toISOString().split('T')[0]
})

const chartEnd = computed(() => {
  if (currentProject.value && currentProject.value.end_date) {
    return currentProject.value.end_date
  }
  const end = new Date()
  end.setMonth(end.getMonth() + 3)
  return end.toISOString().split('T')[0]
})

const tasks = computed(() => {
  return taskList.value.map(task => ({
    id: task.id,
    label: task.name,
    bars: [
      {
        id: `bar-${task.id}`,
        label: `${task.progress_percent}%`,
        start: task.start_date || chartStart.value,
        end: task.end_date || chartEnd.value,
        ganttBarConfig: {
          id: `bar-${task.id}`,
          label: task.name,
          style: {
            background: getTaskColor(task.status),
            borderRadius: '4px'
          }
        }
      }
    ]
  }))
})

const getTaskColor = (status) => {
  const colors = {
    'PENDING': '#909399',
    'IN_PROGRESS': '#409EFF',
    'COMPLETED': '#67C23A',
    'ON_HOLD': '#E6A23C',
    'CANCELLED': '#F56C6C'
  }
  return colors[status] || '#909399'
}

const get状态Label = (status) => {
  const labels = {
    'PENDING': '待开始',
    'IN_PROGRESS': '进行中',
    'COMPLETED': '已完成',
    'ON_HOLD': '暂停',
    'CANCELLED': '已取消'
  }
  return labels[status] || status
}

const get状态Type = (status) => {
  const types = {
    'PENDING': 'info',
    'IN_PROGRESS': 'primary',
    'COMPLETED': 'success',
    'ON_HOLD': 'warning',
    'CANCELLED': 'danger'
  }
  return types[status] || 'info'
}

const getProgress状态 = (percent) => {
  if (percent >= 100) return 'success'
  if (percent >= 70) return 'primary'
  if (percent >= 30) return 'warning'
  return 'exception'
}

const loadProjects = async () => {
  try {
    const response = await getProjectList({ status: 'ACTIVE' })
    projects.value = response.results || response || []
  } catch (error) {
    ElMessage.error('加载项目列表失败')
    console.error(error)
  }
}

const loadProjectTasks = async () => {
  if (!selectedProject.value) return
  
  loading.value = true
  try {
    // Load project details
    const projectRes = await getProject(selectedProject.value)
    currentProject.value = projectRes.data || projectRes
    
    // Load tasks
    const tasksRes = await getTaskList({ project: selectedProject.value })
    taskList.value = tasksRes.results || tasksRes.data || tasksRes || []
    
    // Ensure tasks have dates
    taskList.value = taskList.value.map(task => ({
      ...task,
      start_date: task.start_date || currentProject.value.start_date,
      end_date: task.end_date || currentProject.value.end_date
    }))
  } catch (error) {
    ElMessage.error('加载项目任务失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const refreshData = () => {
  if (selectedProject.value) {
    loadProjectTasks()
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.project-gantt {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 18px;
  font-weight: bold;
}

.project-info {
  margin-bottom: 30px;
}

.gantt-container {
  margin-top: 20px;
  overflow-x: auto;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.bar-label {
  color: white;
  font-size: 12px;
  font-weight: bold;
  padding: 0 5px;
}

.task-list h3 {
  margin-bottom: 15px;
  color: #303133;
}

/* Gantt chart styling */
:deep(.g-gantt-chart) {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
}

:deep(.g-gantt-row-label) {
  background: #f5f7fa;
  border-right: 1px solid #dcdfe6;
  padding: 10px;
  font-weight: 500;
}

:deep(.g-gantt-bar) {
  cursor: pointer;
  transition: all 0.3s;
}

:deep(.g-gantt-bar:hover) {
  opacity: 0.8;
  transform: translateY(-2px);
}
</style>

