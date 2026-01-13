<template>
  <div class="issue-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>技术问题记录</span>
          <el-button type="primary" @click="handleCreate"><el-icon><Plus /></el-icon> 新建问题</el-button>
        </div>
      </template>
      
      <div class="filter-area">
        <el-input v-model="queryParams.search" placeholder="搜索问题" style="width: 240px" clearable @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="queryParams.severity" placeholder="严重程度" clearable @change="fetchData">
          <el-option label="低" value="LOW" />
          <el-option label="中" value="MEDIUM" />
          <el-option label="高" value="HIGH" />
          <el-option label="严重" value="CRITICAL" />
        </el-select>
        <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchData">
          <el-option label="待解决" value="OPEN" />
          <el-option label="处理中" value="IN_PROGRESS" />
          <el-option label="已解决" value="RESOLVED" />
          <el-option label="已关闭" value="CLOSED" />
        </el-select>
      </div>

      <el-table :data="issues" v-loading="loading" stripe style="width: 100%; margin-top: 16px">
        <el-table-column prop="title" label="问题标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="project_name" label="关联项目" width="150" />
        <el-table-column prop="category_name" label="分类" width="120" />
        <el-table-column label="严重程度" width="100">
          <template #default="{ row }">
            <el-tag :type="getSeverityType(row.severity)">{{ row.severity_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button v-if="row.status === 'RESOLVED'" size="small" type="success" @click="handleConvert(row)">转知识</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :total="total"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { getTechnicalIssueList, convertIssueToKnowledge } from '@/api/projects/knowledge'

const loading = ref(false)
const issues = ref([])
const total = ref(0)

const queryParams = reactive({
  search: '',
  severity: '',
  status: '',
  page: 1,
  page_size: 20
})

const getSeverityType = (severity) => {
  const map = { LOW: 'info', MEDIUM: '', HIGH: 'warning', CRITICAL: 'danger' }
  return map[severity] || ''
}

const getStatusType = (status) => {
  const map = { OPEN: 'info', IN_PROGRESS: 'warning', RESOLVED: 'success', CLOSED: '' }
  return map[status] || ''
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getTechnicalIssueList(queryParams)
    issues.value = res.results || res || []
    total.value = res.count || issues.value.length
  } catch (error) {
    console.error('获取数据失败', error)
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  ElMessage.info('新建功能开发中')
}

const handleView = (row) => {
  ElMessage.info('查看功能开发中')
}

const handleConvert = async (row) => {
  try {
    await convertIssueToKnowledge(row.id)
    ElMessage.success('已转换为知识文章')
    fetchData()
  } catch (error) {
    ElMessage.error('转换失败')
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.issue-container {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-area {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
