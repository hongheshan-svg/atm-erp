<template>
  <div class="project-cost-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>项目成本核算</span>
          <el-button type="primary" @click="handleRecalculate">
            <el-icon><Refresh /></el-icon>
            重新计算
          </el-button>
        </div>
      </template>
      
      <!-- 搜索区域 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="项目名称">
          <el-input v-model="searchForm.name" placeholder="输入项目名称" clearable />
        </el-form-item>
        <el-form-item label="项目状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable>
            <el-option label="草稿" value="DRAFT" />
            <el-option label="规划中" value="PLANNING" />
            <el-option label="进行中" value="ACTIVE" />
            <el-option label="暂停" value="PAUSED" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目经理">
          <el-select v-model="searchForm.manager" placeholder="选择经理" clearable filterable>
            <el-option
              v-for="user in managers"
              :key="user.id"
              :label="user.username"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="handleReset">重置</el-button>
          <el-button type="success" @click="handleExport">
            <el-icon><Download /></el-icon>
            导出
          </el-button>
        </el-form-item>
      </el-form>
      
      <!-- 汇总统计 -->
      <el-row :gutter="20" class="summary-row">
        <el-col :span="4">
          <el-statistic title="项目总数" :value="summary.totalProjects" />
        </el-col>
        <el-col :span="5">
          <el-statistic title="总预算" :value="summary.totalBudget" :precision="2" prefix="¥" />
        </el-col>
        <el-col :span="5">
          <el-statistic title="总收入" :value="summary.totalRevenue" :precision="2" prefix="¥" />
        </el-col>
        <el-col :span="5">
          <el-statistic title="总成本" :value="summary.totalCost" :precision="2" prefix="¥" />
        </el-col>
        <el-col :span="5">
          <el-statistic 
            title="总利润" 
            :value="summary.totalProfit" 
            :precision="2" 
            prefix="¥"
            :value-style="{ color: summary.totalProfit >= 0 ? '#67c23a' : '#f56c6c' }"
          />
        </el-col>
      </el-row>
      
      <!-- 数据表格 -->
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="tableData" border stripe v-loading="loading" @row-click="handleRowClick" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="code" label="项目编号" width="120" />
        <el-table-column prop="name" label="项目名称" min-width="180" />
        <el-table-column prop="manager_name" label="项目经理" width="100" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预算" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatNumber(row.budget_total) }}
          </template>
        </el-table-column>
        <el-table-column label="收入" width="120" align="right">
          <template #default="{ row }">
            <span class="text-success">¥{{ formatNumber(row.revenue) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="材料成本" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatNumber(row.material_cost) }}
          </template>
        </el-table-column>
        <el-table-column label="人工成本" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatNumber(row.labor_cost) }}
          </template>
        </el-table-column>
        <el-table-column label="费用成本" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatNumber(row.expense_cost) }}
          </template>
        </el-table-column>
        <el-table-column label="总成本" width="120" align="right">
          <template #default="{ row }">
            <span class="text-danger">¥{{ formatNumber(row.total_cost) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="利润" width="120" align="right">
          <template #default="{ row }">
            <span :class="row.profit >= 0 ? 'text-success' : 'text-danger'">
              ¥{{ formatNumber(row.profit) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="利润率" width="90" align="right">
          <template #default="{ row }">
            <span :class="row.profit_margin >= 0 ? 'text-success' : 'text-danger'">
              {{ toFixedSafe(row.profit_margin, 1, '0.0') }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="预算使用" width="120">
          <template #default="{ row }">
            <el-progress 
              :percentage="Math.min(row.budget_usage || 0, 100)" 
              :status="getBudgetStatus(row.budget_usage)"
              :stroke-width="10"
            />
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>
    
    <!-- 项目成本详情对话框 -->
    <el-dialog v-model="detailVisible" :title="'项目成本详情 - ' + currentProject.name" width="900px">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="项目编号">{{ currentProject.code }}</el-descriptions-item>
        <el-descriptions-item label="项目名称">{{ currentProject.name }}</el-descriptions-item>
        <el-descriptions-item label="项目经理">{{ currentProject.manager_name }}</el-descriptions-item>
        <el-descriptions-item label="开始日期">{{ currentProject.start_date }}</el-descriptions-item>
        <el-descriptions-item label="结束日期">{{ currentProject.end_date }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentProject.status)">
            {{ getStatusLabel(currentProject.status) }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
      
      <el-divider>成本明细</el-divider>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>预算 vs 实际</template>
            <el-table :data="budgetComparison" size="small">
              <el-table-column prop="category" label="类别" />
              <el-table-column prop="budget" label="预算" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.budget) }}</template>
              </el-table-column>
              <el-table-column prop="actual" label="实际" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.actual) }}</template>
              </el-table-column>
              <el-table-column prop="variance" label="差异" align="right">
                <template #default="{ row }">
                  <span :class="row.variance >= 0 ? 'text-success' : 'text-danger'">
                    ¥{{ formatNumber(row.variance) }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>成本构成</template>
            <div ref="costChartRef" style="height: 250px;"></div>
          </el-card>
        </el-col>
      </el-row>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, Download } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getProjectCosts, recalculateCosts } from '@/api/analytics'
import { getUsers } from '@/api/auth'
import { toFixedSafe } from '@/utils/number'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchExport } = useBatchOperation('/api/analytics/')


const loading = ref(false)
const tableData = ref<any[]>([])
const managers = ref<any[]>([])
const detailVisible = ref(false)
const currentProject = ref<Record<string, any>>({})
const costChartRef = ref(null)
let costChart = null

const searchForm = reactive({
  name: '',
  status: '',
  manager: ''
})

const summary = reactive({
  totalProjects: 0,
  totalBudget: 0,
  totalRevenue: 0,
  totalCost: 0,
  totalProfit: 0
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const budgetComparison = ref<any[]>([])

const getStatusLabel = (status) => {
  const labels = {
    'DRAFT': '草稿',
    'PLANNING': '规划中',
    'ACTIVE': '进行中',
    'PAUSED': '暂停',
    'COMPLETED': '已完成',
    'CANCELLED': '已取消',
    'ARCHIVED': '已归档'
  }
  return labels[status] || status
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'PLANNING': 'info',
    'ACTIVE': 'success',
    'PAUSED': 'warning',
    'COMPLETED': 'primary',
    'CANCELLED': 'danger',
    'ARCHIVED': ''
  }
  return types[status] || ''
}

const getBudgetStatus = (usage) => {
  if (usage >= 100) return 'exception'
  if (usage >= 80) return 'warning'
  return 'success'
}

const formatNumber = (num) => {
  if (!num) return '0.00'
  return Number(num).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.name) params.name = searchForm.name
    if (searchForm.status) params.status = searchForm.status
    if (searchForm.manager) params.manager = searchForm.manager
    
    const res = await getProjectCosts(params)
    const data = res.results || res.results || res || []
    tableData.value = data
    pagination.total = res.count || res.count || data.length
    
    // 计算汇总
    calculateSummary(data)
  } catch (error) {
    console.error('获取项目成本失败:', error)
    tableData.value = []
    ElMessage.error('获取项目成本数据失败')
  } finally {
    loading.value = false
  }
}

const calculateSummary = (data) => {
  summary.totalProjects = data.length
  summary.totalBudget = data.reduce((sum, item) => sum + (item.budget_total || 0), 0)
  summary.totalRevenue = data.reduce((sum, item) => sum + (item.revenue || 0), 0)
  summary.totalCost = data.reduce((sum, item) => sum + (item.total_cost || 0), 0)
  summary.totalProfit = summary.totalRevenue - summary.totalCost
}

const fetchManagers = async () => {
  try {
    const res = await getUsers()
    managers.value = res.results || res.results || res || []
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.name = ''
  searchForm.status = ''
  searchForm.manager = ''
  handleSearch()
}

const handleRecalculate = async () => {
  try {
    const res = await recalculateCosts()
    ElMessage.success(res.message || '成本重新计算已触发')
    // 延迟刷新数据，给后端计算时间
    setTimeout(() => {
      fetchData()
    }, 1000)
  } catch (error) {
    console.error('成本计算失败:', error)
    ElMessage.error('成本计算失败，请稍后重试')
  }
}

const handleExport = () => {
  if (!tableData.value.length) {
    ElMessage.warning('没有数据可导出')
    return
  }
  
  import('@/utils/export').then(({ exportToExcel, formatMoney }) => {
    const columns = [
      { field: 'code', title: '项目编号' },
      { field: 'name', title: '项目名称' },
      { field: 'manager_name', title: '项目经理' },
      { field: 'status_display', title: '状态' },
      { field: 'budget_total', title: '总预算', formatter: formatMoney },
      { field: 'revenue', title: '收入', formatter: formatMoney },
      { field: 'material_cost', title: '材料成本', formatter: formatMoney },
      { field: 'labor_cost', title: '人工成本', formatter: formatMoney },
      { field: 'expense_cost', title: '费用成本', formatter: formatMoney },
      { field: 'total_cost', title: '总成本', formatter: formatMoney },
      { field: 'profit', title: '利润', formatter: formatMoney },
      { field: 'profit_margin', title: '利润率(%)', formatter: (val) => (val * 100).toFixed(2) + '%' }
    ]
    exportToExcel(tableData.value, columns, '项目成本核算表')
    ElMessage.success('导出成功')
  }).catch(error => {
    console.error('导出失败:', error)
    ElMessage.error('导出失败')
  })
}

const handleRowClick = (row) => {
  currentProject.value = row
  budgetComparison.value = [
    { category: '材料成本', budget: row.budget_material || 0, actual: row.material_cost || 0, variance: (row.budget_material || 0) - (row.material_cost || 0) },
    { category: '人工成本', budget: row.budget_labor || 0, actual: row.labor_cost || 0, variance: (row.budget_labor || 0) - (row.labor_cost || 0) },
    { category: '费用成本', budget: row.budget_expense || 0, actual: row.expense_cost || 0, variance: (row.budget_expense || 0) - (row.expense_cost || 0) },
    { category: '合计', budget: row.budget_total || 0, actual: row.total_cost || 0, variance: (row.budget_total || 0) - (row.total_cost || 0) }
  ]
  detailVisible.value = true
  
  nextTick(() => {
    initCostChart(row)
  })
}

const initCostChart = (data) => {
  if (!costChartRef.value) return
  
  if (costChart) {
    costChart.dispose()
  }
  
  costChart = echarts.init(costChartRef.value)
  
  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [
      {
        name: '成本构成',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false,
          position: 'center'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold'
          }
        },
        labelLine: {
          show: false
        },
        data: [
          { value: data.material_cost || 0, name: '材料成本' },
          { value: data.labor_cost || 0, name: '人工成本' },
          { value: data.expense_cost || 0, name: '费用成本' }
        ]
      }
    ]
  }
  
  costChart.setOption(option)
}

onMounted(() => {
  fetchData()
  fetchManagers()
})
</script>

<style scoped>
.project-cost-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
}

.search-form {
  margin-bottom: 20px;
}

.summary-row {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
