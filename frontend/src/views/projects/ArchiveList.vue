<template>
  <div class="archive-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>项目归档管理</span>
          <el-button type="primary" v-permission="'projects:project:create'" @click="handleCreate"><el-icon><Plus /></el-icon> 新建归档</el-button>
        </div>
      </template>
      
      <div class="filter-area">
        <el-input v-model="queryParams.search" placeholder="搜索项目名称" style="width: 240px" clearable @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchData">
          <el-option label="草稿" value="DRAFT" />
          <el-option label="审核中" value="REVIEW" />
          <el-option label="已通过" value="APPROVED" />
          <el-option label="已驳回" value="REJECTED" />
        </el-select>
      </div>

      <!-- 批量操作 -->

      <div v-if="selectedRows.length > 0" class="batch-toolbar">

        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>

        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>

        <el-button size="small" @click="batchExport">导出选中</el-button>

      </div>

      <el-table :data="archives" v-loading="loading" stripe style="width: 100%; margin-top: 16px" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="project_no" label="项目编号" width="140" />
        <el-table-column prop="project_name" label="项目名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="archive_date" label="归档日期" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预算/实际成本" width="180">
          <template #default="{ row }">
            <div>预算: ¥{{ row.budget_amount?.toLocaleString() || 0 }}</div>
            <div>实际: ¥{{ row.actual_cost?.toLocaleString() || 0 }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="customer_satisfaction" label="客户满意度" width="100">
          <template #default="{ row }">
            <el-rate v-model="row.customer_satisfaction" :max="10" disabled size="small" />
          </template>
        </el-table-column>
        <el-table-column prop="reviewer_name" label="评审人" width="100" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button v-if="row.status === 'APPROVED'" size="small" type="primary" @click="handleGenerate(row)">生成知识</el-button>
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
    <el-dialog v-model="viewDialogVisible" title="归档详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="项目编号">{{ viewDetail.project_no }}</el-descriptions-item>
        <el-descriptions-item label="项目名称">{{ viewDetail.project_name }}</el-descriptions-item>
        <el-descriptions-item label="归档日期">{{ viewDetail.archive_date }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(viewDetail.status)">{{ viewDetail.status_display || viewDetail.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="预算金额">¥{{ viewDetail.budget_amount?.toLocaleString() || 0 }}</el-descriptions-item>
        <el-descriptions-item label="实际成本">¥{{ viewDetail.actual_cost?.toLocaleString() || 0 }}</el-descriptions-item>
        <el-descriptions-item label="客户满意度">{{ viewDetail.customer_satisfaction || '-' }}</el-descriptions-item>
        <el-descriptions-item label="评审人">{{ viewDetail.reviewer_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="经验总结" :span="2">{{ viewDetail.lessons_learned || '-' }}</el-descriptions-item>
        <el-descriptions-item label="项目成果" :span="2">{{ viewDetail.achievements || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 新建归档 -->
    <el-dialog v-model="createDialogVisible" title="新建项目归档" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="项目" prop="project">
          <el-select v-model="form.project" placeholder="选择项目" filterable style="width: 100%">
            <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="归档日期" prop="archive_date">
          <el-date-picker v-model="form.archive_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="客户满意度">
          <el-rate v-model="form.customer_satisfaction" :max="10" allow-half />
        </el-form-item>
        <el-form-item label="经验总结">
          <el-input v-model="form.lessons_learned" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="项目成果">
          <el-input v-model="form.achievements" type="textarea" :rows="3" />
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
import { getProjectArchiveList, getProjectArchive, createProjectArchive, generateKnowledgeFromArchive } from '@/api/projects/knowledge'
import { getProjectList } from '@/api/projects/project'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects_knowledge/')


const loading = ref(false)
const saving = ref(false)
const archives = ref<any[]>([])
const total = ref(0)
const viewDialogVisible = ref(false)
const createDialogVisible = ref(false)
const viewDetail = ref<Record<string, any>>({})
const projectList = ref<any[]>([])
const formRef = ref(null)

const queryParams = reactive({ search: '', status: '', page: 1, page_size: 20 })
const form = reactive({ project: null, archive_date: '', customer_satisfaction: 0, lessons_learned: '', achievements: '' })
const rules = {
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  archive_date: [{ required: true, message: '请选择归档日期', trigger: 'change' }]
}
const getStatusType = (status) => ({ DRAFT: 'info', REVIEW: 'warning', APPROVED: 'success', REJECTED: 'danger' }[status] || '')

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getProjectArchiveList(queryParams)
    archives.value = res.results || res || []
    total.value = res.count || archives.value.length
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
    console.error('ArchiveList getProjectList error:', error)
  }
}

const handleCreate = () => {
  Object.assign(form, { project: null, archive_date: new Date().toISOString().split('T')[0], customer_satisfaction: 0, lessons_learned: '', achievements: '' })
  formRef.value?.resetFields()
  createDialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const res = await getProjectArchive(row.id)
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
    await createProjectArchive(form)
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    fetchData()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
  } finally {
    saving.value = false
  }
}

const handleGenerate = async (row) => {
  try {
    await generateKnowledgeFromArchive(row.id)
    ElMessage.success('知识文章已生成')
  } catch (error) {
    ElMessage.error('生成失败')
  }
}

onMounted(() => { loadProjects(); fetchData() })
</script>

<style scoped>
.archive-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filter-area { display: flex; gap: 12px; flex-wrap: wrap; }
</style>
