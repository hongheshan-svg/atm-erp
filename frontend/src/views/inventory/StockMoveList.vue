<template>
  <div class="stock-move-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>库存流水</span>
        </div>
      </template>
      
      <!-- 搜索区域 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="物料">
          <el-select v-model="searchForm.item" placeholder="选择物料" clearable filterable>
            <el-option
              v-for="item in items"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="仓库">
          <el-select v-model="searchForm.warehouse" placeholder="选择仓库" clearable>
            <el-option
              v-for="wh in warehouses"
              :key="wh.id"
              :label="wh.name"
              :value="wh.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="移动类型">
          <el-select v-model="searchForm.move_type" placeholder="选择类型" clearable>
            <el-option label="采购入库" value="IN_PURCHASE" />
            <el-option label="销售出库" value="OUT_SALES" />
            <el-option label="项目领料" value="OUT_PROJECT" />
            <el-option label="仓库调拨" value="TRANSFER" />
            <el-option label="库存调整" value="ADJUSTMENT" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目">
          <el-select v-model="searchForm.project" placeholder="选择项目" clearable filterable>
            <el-option
              v-for="proj in projects"
              :key="proj.id"
              :label="proj.name"
              :value="proj.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="searchForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
          <el-button type="success" @click="handleExport">
            <el-icon><Download /></el-icon>
            导出
          </el-button>
        </el-form-item>
      </el-form>
      
      <!-- 统计卡片 -->
      <el-row :gutter="20" class="stats-row">
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-value in">{{ stats.totalIn }}</div>
            <div class="stat-label">入库数量</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-value out">{{ stats.totalOut }}</div>
            <div class="stat-label">出库数量</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-value">¥{{ formatNumber(stats.totalInValue) }}</div>
            <div class="stat-label">入库金额</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-value">¥{{ formatNumber(stats.totalOutValue) }}</div>
            <div class="stat-label">出库金额</div>
          </el-card>
        </el-col>
      </el-row>
      
      <!-- 数据表格 -->
      <el-table :data="tableData" border stripe v-loading="loading">
        <el-table-column prop="move_no" label="流水号" width="150" />
        <el-table-column prop="move_date" label="日期" width="110" />
        <el-table-column label="物料" min-width="150">
          <template #default="{ row }">
            <div>{{ row.item_name }}</div>
            <div class="text-muted">{{ row.item_code }}</div>
          </template>
        </el-table-column>
        <el-table-column label="移动类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getMoveTypeTag(row.move_type)">
              {{ getMoveTypeLabel(row.move_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="仓库" width="120">
          <template #default="{ row }">
            <div v-if="row.warehouse_from_name">从: {{ row.warehouse_from_name }}</div>
            <div v-if="row.warehouse_to_name">到: {{ row.warehouse_to_name }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="qty" label="数量" width="100" align="right">
          <template #default="{ row }">
            <span :class="row.qty > 0 ? 'text-success' : 'text-danger'">
              {{ row.qty > 0 ? '+' : '' }}{{ row.qty }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="unit_cost" label="单价" width="100" align="right">
          <template #default="{ row }">
            ¥{{ formatNumber(row.unit_cost) }}
          </template>
        </el-table-column>
        <el-table-column label="金额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatNumber(row.qty * row.unit_cost) }}
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="关联项目" width="150">
          <template #default="{ row }">
            {{ row.project_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="reference_no" label="来源单据" width="150" />
        <el-table-column prop="created_by_name" label="操作人" width="100" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'CONFIRMED' ? 'success' : 'warning'" size="small">
              {{ row.status === 'CONFIRMED' ? '已确认' : '待确认' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next, jumper"
        class="pagination"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, Download } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const tableData = ref([])
const items = ref([])
const warehouses = ref([])
const projects = ref([])

const searchForm = reactive({
  item: '',
  warehouse: '',
  move_type: '',
  project: '',
  dateRange: []
})

const stats = reactive({
  totalIn: 0,
  totalOut: 0,
  totalInValue: 0,
  totalOutValue: 0
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const getMoveTypeLabel = (type) => {
  const labels = {
    'IN_PURCHASE': '采购入库',
    'OUT_SALES': '销售出库',
    'OUT_PROJECT': '项目领料',
    'TRANSFER': '仓库调拨',
    'ADJUSTMENT': '库存调整'
  }
  return labels[type] || type
}

const getMoveTypeTag = (type) => {
  const tags = {
    'IN_PURCHASE': 'success',
    'OUT_SALES': 'danger',
    'OUT_PROJECT': 'warning',
    'TRANSFER': 'info',
    'ADJUSTMENT': ''
  }
  return tags[type] || ''
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
    if (searchForm.item) params.item = searchForm.item
    if (searchForm.warehouse) params.warehouse = searchForm.warehouse
    if (searchForm.move_type) params.move_type = searchForm.move_type
    if (searchForm.project) params.project = searchForm.project
    if (searchForm.dateRange && searchForm.dateRange.length === 2) {
      params.start_date = searchForm.dateRange[0]
      params.end_date = searchForm.dateRange[1]
    }
    
    const res = await request.get('/inventory/moves/', { params })
    tableData.value = res.data?.results || res.results || res.data || []
    pagination.total = res.data?.count || res.count || 0
    
    // 计算统计数据
    calculateStats()
  } catch (error) {
    console.error('获取库存流水失败:', error)
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

const calculateStats = () => {
  let totalIn = 0, totalOut = 0, totalInValue = 0, totalOutValue = 0
  tableData.value.forEach(item => {
    const value = Math.abs(item.qty * item.unit_cost)
    if (item.qty > 0) {
      totalIn += item.qty
      totalInValue += value
    } else {
      totalOut += Math.abs(item.qty)
      totalOutValue += value
    }
  })
  stats.totalIn = totalIn
  stats.totalOut = totalOut
  stats.totalInValue = totalInValue
  stats.totalOutValue = totalOutValue
}

const fetchItems = async () => {
  try {
    const res = await request.get('/masterdata/items/')
    items.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取物料列表失败:', error)
  }
}

const fetchWarehouses = async () => {
  try {
    const res = await request.get('/masterdata/warehouses/')
    warehouses.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取仓库列表失败:', error)
  }
}

const fetchProjects = async () => {
  try {
    const res = await request.get('/projects/projects/')
    projects.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取项目列表失败:', error)
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.item = ''
  searchForm.warehouse = ''
  searchForm.move_type = ''
  searchForm.project = ''
  searchForm.dateRange = []
  handleSearch()
}

const handleExport = () => {
  if (!stockMoves.value.length) {
    ElMessage.warning('没有数据可导出')
    return
  }
  
  import('@/utils/export').then(({ exportToExcel, formatMoney }) => {
    const columns = [
      { field: 'move_no', title: '流水号' },
      { field: 'item_name', title: '物料' },
      { field: 'move_type', title: '类型' },
      { field: 'warehouse_from_name', title: '源仓库' },
      { field: 'warehouse_to_name', title: '目标仓库' },
      { field: 'qty', title: '数量' },
      { field: 'unit_cost', title: '单位成本', formatter: formatMoney },
      { field: 'move_date', title: '移动日期' },
      { field: 'status', title: '状态' }
    ]
    exportToExcel(stockMoves.value, columns, '库存流水')
    ElMessage.success('导出成功')
  })
}

onMounted(() => {
  fetchData()
  fetchItems()
  fetchWarehouses()
  fetchProjects()
})
</script>

<style scoped>
.stock-move-list {
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

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
  padding: 10px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.stat-value.in {
  color: #67c23a;
}

.stat-value.out {
  color: #f56c6c;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.text-muted {
  font-size: 12px;
  color: #909399;
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

