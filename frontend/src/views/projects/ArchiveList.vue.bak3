<template>
  <div class="archive-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>项目归档管理</span>
          <el-button type="primary" @click="handleCreate"><el-icon><Plus /></el-icon> 新建归档</el-button>
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

      <el-table :data="archives" v-loading="loading" stripe style="width: 100%; margin-top: 16px">
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
        <el-table-column label="操作" width="150" fixed="right">
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { getProjectArchiveList, generateKnowledgeFromArchive } from '@/api/projects/knowledge'

const loading = ref(false)
const archives = ref([])
const total = ref(0)

const queryParams = reactive({
  search: '',
  status: '',
  page: 1,
  page_size: 20
})

const getStatusType = (status) => {
  const map = { DRAFT: 'info', REVIEW: 'warning', APPROVED: 'success', REJECTED: 'danger' }
  return map[status] || ''
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getProjectArchiveList(queryParams)
    archives.value = res.results || res || []
    total.value = res.count || archives.value.length
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

const handleGenerate = async (row) => {
  try {
    await generateKnowledgeFromArchive(row.id)
    ElMessage.success('知识文章已生成')
  } catch (error) {
    ElMessage.error('生成失败')
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.archive-container {
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
