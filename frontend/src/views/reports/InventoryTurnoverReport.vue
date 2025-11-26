<template>
  <div class="inventory-turnover-report">
    <el-card>
      <template #header><span>库存周转率分析</span></template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="searchForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="仓库">
          <el-select v-model="searchForm.warehouse" placeholder="请选择仓库" clearable>
            <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="物料分类">
          <el-select v-model="searchForm.category" placeholder="请选择分类" clearable>
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadReport">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="success" @click="exportToExcel">导出Excel</el-button>
        </el-form-item>
      </el-form>

      <!-- 周转率概览 -->
      <el-row :gutter="20" style="margin-bottom: 20px;">
        <el-col :span="6">
          <el-statistic title="平均周转天数" :value="summary.avg_turnover_days || 0" suffix="天">
            <template #prefix><el-icon><Clock /></el-icon></template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="平均周转率" :value="summary.avg_turnover_rate || 0" suffix="次/年" :precision="2">
            <template #prefix><el-icon><TrendCharts /></el-icon></template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="总库存价值" :value="summary.total_inventory_value || 0" prefix="¥" :precision="2">
            <template #prefix><el-icon><Money /></el-icon></template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="呆滞物料数" :value="summary.slow_moving_count || 0" suffix="种">
            <template #prefix><el-icon style="color: #F56C6C;"><Warning /></el-icon></template>
          </el-statistic>
        </el-col>
      </el-row>

      <!-- 周转率表格 -->
      <el-table :data="reportData" v-loading="loading" border stripe>
        <el-table-column prop="item_sku" label="物料编码" width="150" />
        <el-table-column prop="item_name" label="物料名称" min-width="200" />
        <el-table-column prop="category_name" label="分类" width="120" />
        <el-table-column prop="warehouse_name" label="仓库" width="150" />
        <el-table-column prop="avg_inventory" label="平均库存" width="100" align="right">
          <template #default="{ row }">{{ (row.avg_inventory || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="total_out_qty" label="出库总量" width="100" align="right">
          <template #default="{ row }">{{ (row.total_out_qty || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="turnover_days" label="周转天数" width="100" align="right">
          <template #default="{ row }">
            <span :style="{ color: getTurnoverColor(row.turnover_days) }">
              {{ (row.turnover_days || 0).toFixed(1) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="turnover_rate" label="周转率(次/年)" width="130" align="right">
          <template #default="{ row }">{{ (row.turnover_rate || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="评级" width="100">
          <template #default="{ row }">
            <el-tag :type="getTurnoverLevel(row.turnover_days)">
              {{ getTurnoverLabel(row.turnover_days) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="inventory_value" label="库存价值" width="130" align="right">
          <template #default="{ row }">¥{{ (row.inventory_value || 0).toFixed(2) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 周转率趋势图 -->
    <el-card style="margin-top: 20px;">
      <template #header><span>周转率趋势</span></template>
      <div ref="chartRef" style="height: 400px;"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Clock, TrendCharts, Money, Warning } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import request from '@/utils/request'

const loading = ref(false)
const reportData = ref([])
const warehouses = ref([])
const categories = ref([])
const chartRef = ref(null)
const searchForm = reactive({
  dateRange: [new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], new Date().toISOString().split('T')[0]],
  warehouse: null,
  category: null
})
const summary = reactive({ avg_turnover_days: 0, avg_turnover_rate: 0, total_inventory_value: 0, slow_moving_count: 0 })

const getTurnoverColor = (days) => {
  if (days <= 30) return '#67C23A'
  if (days <= 60) return '#E6A23C'
  return '#F56C6C'
}

const getTurnoverLevel = (days) => {
  if (days <= 30) return 'success'
  if (days <= 60) return 'warning'
  return 'danger'
}

const getTurnoverLabel = (days) => {
  if (days <= 30) return '优秀'
  if (days <= 60) return '良好'
  if (days <= 90) return '一般'
  return '呆滞'
}

const loadReport = async () => {
  loading.value = true
  try {
    const params = { ...searchForm }
    if (params.dateRange) {
      params.start_date = params.dateRange[0]
      params.end_date = params.dateRange[1]
      delete params.dateRange
    }
    Object.keys(params).forEach(k => { if (params[k] === null) delete params[k] })
    
    const response = await request.get('/reports/inventory-turnover/', { params })
    reportData.value = response.results || response.items || response || []
    Object.assign(summary, response.summary || {})
    
    await nextTick()
    renderChart()
  } catch (error) {
    ElMessage.error('加载报表失败')
  } finally {
    loading.value = false
  }
}

const loadWarehouses = async () => {
  try {
    const response = await request.get('/masterdata/warehouses/', { params: { page_size: 100 } })
    warehouses.value = response.results || response || []
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const loadCategories = async () => {
  try {
    const response = await request.get('/masterdata/categories/', { params: { page_size: 100 } })
    categories.value = response.results || response || []
  } catch (error) {
    console.error('加载分类失败:', error)
  }
}

const resetSearch = () => {
  searchForm.dateRange = [new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], new Date().toISOString().split('T')[0]]
  searchForm.warehouse = null
  searchForm.category = null
  loadReport()
}

const exportToExcel = () => {
  if (!reportData.value.length) {
    ElMessage.warning('没有数据可导出')
    return
  }
  
  import('@/utils/export').then(({ exportToExcel: doExport, formatMoney }) => {
    const columns = [
      { field: 'item_sku', title: '物料编码' },
      { field: 'item_name', title: '物料名称' },
      { field: 'category_name', title: '分类' },
      { field: 'warehouse_name', title: '仓库' },
      { field: 'avg_inventory', title: '平均库存' },
      { field: 'total_out_qty', title: '出库总量' },
      { field: 'turnover_rate', title: '周转率', formatter: v => v?.toFixed(2) },
      { field: 'turnover_days', title: '周转天数', formatter: v => v?.toFixed(1) },
      { field: 'inventory_value', title: '库存价值', formatter: formatMoney }
    ]
    doExport(reportData.value, columns, '库存周转率报表')
    ElMessage.success('导出成功')
  })
}

const renderChart = () => {
  if (!chartRef.value) return
  const chart = echarts.init(chartRef.value)
  
  const topItems = reportData.value.slice(0, 10)
  
  chart.setOption({
    title: { text: '库存周转率 TOP 10' },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: topItems.map(i => i.item_sku), axisLabel: { rotate: 45 } },
    yAxis: { type: 'value', name: '周转率(次/年)' },
    series: [{
      name: '周转率',
      type: 'bar',
      data: topItems.map(i => i.turnover_rate || 0),
      itemStyle: { color: (params) => {
        const days = topItems[params.dataIndex].turnover_days
        return getTurnoverColor(days)
      }}
    }]
  })
}

onMounted(() => {
  loadWarehouses()
  loadCategories()
  loadReport()
})
</script>

<style scoped>
.inventory-turnover-report { padding: 20px; }
.search-form { margin-bottom: 20px; }
</style>

