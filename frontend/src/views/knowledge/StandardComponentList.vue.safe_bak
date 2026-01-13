<template>
  <div class="component-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>标准部件库</span>
          <el-button type="primary" @click="handleCreate"><el-icon><Plus /></el-icon> 新建部件</el-button>
        </div>
      </template>
      
      <div class="filter-area">
        <el-input v-model="queryParams.search" placeholder="搜索部件编码/名称" style="width: 240px" clearable @keyup.enter="fetchData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="queryParams.status" placeholder="状态" clearable @change="fetchData">
          <el-option label="草稿" value="DRAFT" />
          <el-option label="可用" value="ACTIVE" />
          <el-option label="已废弃" value="DEPRECATED" />
        </el-select>
      </div>

      <el-table :data="components" v-loading="loading" stripe style="width: 100%; margin-top: 16px">
        <el-table-column prop="code" label="编码" width="150" />
        <el-table-column prop="name" label="部件名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="category_name" label="分类" width="120" />
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="估算成本" width="120" align="right">
          <template #default="{ row }">
            ¥{{ row.estimated_cost?.toLocaleString() || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="usage_count" label="使用次数" width="100" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
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
import { getStandardComponentList } from '@/api/projects/knowledge'

const loading = ref(false)
const components = ref([])
const total = ref(0)

const queryParams = reactive({
  search: '',
  status: '',
  page: 1,
  page_size: 20
})

const getStatusType = (status) => {
  const map = { DRAFT: 'info', ACTIVE: 'success', DEPRECATED: 'danger' }
  return map[status] || ''
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getStandardComponentList(queryParams)
    components.value = res.results || res || []
    total.value = res.count || components.value.length
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

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.component-container {
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
