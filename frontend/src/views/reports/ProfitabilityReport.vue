<template>
  <div class="profitability-report">
    <el-card>
      <template #header>
        <span>项目利润分析</span>
      </template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="项目">
          <el-select v-model="searchForm.project" placeholder="选择项目" clearable filterable>
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable>
            <el-option label="规划中" value="PLANNING" />
            <el-option label="进行中" value="ACTIVE" />
            <el-option label="暂停" value="PAUSED" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已取消" value="CANCELLED" />
            <el-option label="全部" value="" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadReport">搜索</el-button>
          <el-button @click="exportExcel">导出</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="reportData" v-loading="loading" stripe border show-summary>
        <el-table-column prop="code" label="项目编号" width="120" />
        <el-table-column prop="name" label="项目名称" min-width="150" />
        <el-table-column prop="manager" label="项目经理" width="100" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="revenue" label="收入" width="120" align="right">
          <template #default="{ row }">
            {{ formatCurrency(row.revenue) }}
          </template>
        </el-table-column>
        <el-table-column prop="material_cost" label="材料成本" width="130" align="right">
          <template #default="{ row }">
            {{ formatCurrency(row.material_cost) }}
          </template>
        </el-table-column>
        <el-table-column prop="labor_cost" label="人工成本" width="120" align="right">
          <template #default="{ row }">
            {{ formatCurrency(row.labor_cost) }}
          </template>
        </el-table-column>
        <el-table-column prop="expense_cost" label="费用" width="120" align="right">
          <template #default="{ row }">
            {{ formatCurrency(row.expense_cost) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_cost" label="总成本" width="120" align="right">
          <template #default="{ row }">
            {{ formatCurrency(row.total_cost) }}
          </template>
        </el-table-column>
        <el-table-column prop="profit" label="利润" width="120" align="right">
          <template #default="{ row }">
            <span :class="row.profit < 0 ? 'text-danger' : 'text-success'">
              {{ formatCurrency(row.profit) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="margin_percent" label="利润率%" width="100" align="right">
          <template #default="{ row }">
            <span :class="(row.margin_percent || 0) < 0 ? 'text-danger' : 'text-success'">
              {{ (row.margin_percent || 0).toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const reportData = ref([])
const projects = ref([])

const searchForm = reactive({
  project: null,
  status: ''
})

const formatCurrency = (value) => {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY'
  }).format(value || 0)
}

const getStatusLabel = (status) => {
  const labels = {
    'PLANNING': '规划中',
    'ACTIVE': '进行中',
    'PAUSED': '暂停',
    'COMPLETED': '已完成',
    'CANCELLED': '已取消'
  }
  return labels[status] || status
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'ACTIVE': 'success',
    'PAUSED': 'warning',
    'COMPLETED': 'primary',
    'ARCHIVED': 'info'
  }
  return types[status] || 'info'
}

const loadReport = async () => {
  loading.value = true
  try {
    const params = { ...searchForm }
    // 移除空值参数
    Object.keys(params).forEach(key => {
      if (params[key] === null || params[key] === '') {
        delete params[key]
      }
    })
    const res = await request.get('/reports/profitability/', { params })
    // 后端可能返回数组或 {results: [...]}
    reportData.value = res.results || res || []
  } catch (error) {
    console.error('加载利润报表失败:', error)
    ElMessage.error('加载利润报表失败')
    reportData.value = []
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    const response = await request.get('/projects/projects/')
    projects.value = response.results || response || []
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const exportExcel = () => {
  if (!reportData.value.length) {
    ElMessage.warning('没有数据可导出')
    return
  }
  
  import('@/utils/export').then(({ exportToExcel: doExport, formatMoney }) => {
    const columns = [
      { field: 'code', title: '项目编号' },
      { field: 'name', title: '项目名称' },
      { field: 'status', title: '状态', formatter: v => getStatusLabel(v) },
      { field: 'revenue', title: '收入', formatter: formatMoney },
      { field: 'material_cost', title: '材料成本', formatter: formatMoney },
      { field: 'labor_cost', title: '人工成本', formatter: formatMoney },
      { field: 'expense_cost', title: '费用', formatter: formatMoney },
      { field: 'total_cost', title: '总成本', formatter: formatMoney },
      { field: 'profit', title: '利润', formatter: formatMoney },
      { field: 'margin_percent', title: '利润率(%)', formatter: v => (v || 0).toFixed(2) }
    ]
    doExport(reportData.value, columns, '项目利润分析')
    ElMessage.success('导出成功')
  })
}

onMounted(() => {
  loadReport()
  loadProjects()
})
</script>

<style scoped>
.search-form {
  margin-bottom: 20px;
}

.text-danger {
  color: #f56c6c;
}

.text-success {
  color: #67c23a;
}
</style>
