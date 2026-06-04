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

      <!-- 批量操作 -->

      <div v-if="selectedRows.length > 0" class="batch-toolbar">

        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>

        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>

        <el-button size="small" @click="batchExport">导出选中</el-button>

      </div>

      <el-table :data="issues" v-loading="loading" stripe style="width: 100%; margin-top: 16px" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
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
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
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

    <!-- 查看详情 -->
    <el-dialog v-model="viewDialogVisible" title="问题详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="标题" :span="2">{{ viewDetail.title }}</el-descriptions-item>
        <el-descriptions-item label="关联项目">{{ viewDetail.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="分类">{{ viewDetail.category_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="严重程度">
          <el-tag :type="getSeverityType(viewDetail.severity)">{{ viewDetail.severity_display || viewDetail.severity }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(viewDetail.status)">{{ viewDetail.status_display || viewDetail.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="问题描述" :span="2">{{ viewDetail.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="解决方案" :span="2">{{ viewDetail.solution || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(viewDetail.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="创建人">{{ viewDetail.created_by_name || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 新建问题 -->
    <el-dialog v-model="createDialogVisible" title="新建技术问题" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="问题标题" prop="title">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="关联项目">
          <el-select v-model="form.project" placeholder="选择项目" filterable clearable style="width: 100%">
            <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="严重程度" prop="severity">
          <el-select v-model="form.severity" style="width: 100%">
            <el-option label="低" value="LOW" />
            <el-option label="中" value="MEDIUM" />
            <el-option label="高" value="HIGH" />
            <el-option label="严重" value="CRITICAL" />
          </el-select>
        </el-form-item>
        <el-form-item label="问题描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { getTechnicalIssueList, getTechnicalIssue, createTechnicalIssue, convertIssueToKnowledge } from '@/api/projects/knowledge'
import { getProjectList } from '@/api/projects/project'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects/technical-issues/', { onSuccess: () => fetchData() })


const loading = ref(false)
const saving = ref(false)
const issues = ref<any[]>([])
const total = ref(0)
const viewDialogVisible = ref(false)
const createDialogVisible = ref(false)
const viewDetail = ref<Record<string, any>>({})
const projectList = ref<any[]>([])
const formRef = ref(null)

const queryParams = reactive({ search: '', severity: '', status: '', page: 1, page_size: 20 })
const form = reactive({ title: '', project: null, severity: 'MEDIUM', description: '' })
const rules = {
  title: [{ required: true, message: '请输入问题标题', trigger: 'blur' }],
  severity: [{ required: true, message: '请选择严重程度', trigger: 'change' }]
}

const getSeverityType = (severity) => ({ LOW: 'info', MEDIUM: '', HIGH: 'warning', CRITICAL: 'danger' }[severity] || '')
const getStatusType = (status) => ({ OPEN: 'info', IN_PROGRESS: 'warning', RESOLVED: 'success', CLOSED: '' }[status] || '')
const formatDate = (dateStr) => dateStr ? new Date(dateStr).toLocaleString('zh-CN') : ''

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getTechnicalIssueList(queryParams)
    issues.value = res.results || res || []
    total.value = res.count || issues.value.length
  } catch (error) {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjectList({ page_size: 1000 })
    projectList.value = res.results || res.results || []
  } catch (error) {
    console.error('TechnicalIssueList getProjectList error:', error)
  }
}

const handleCreate = () => {
  Object.assign(form, { title: '', project: null, severity: 'MEDIUM', description: '' })
  formRef.value?.resetFields()
  createDialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const res = await getTechnicalIssue(row.id)
    viewDetail.value = res
    viewDialogVisible.value = true
  } catch (error) {
    console.error(error)
    viewDetail.value = row
    viewDialogVisible.value = true
  }
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    await createTechnicalIssue(form)
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    fetchData()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
  } finally {
    saving.value = false
  }
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

onMounted(() => { loadProjects(); fetchData() })
</script>

<style scoped>
.issue-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filter-area { display: flex; gap: 12px; flex-wrap: wrap; }
</style>
