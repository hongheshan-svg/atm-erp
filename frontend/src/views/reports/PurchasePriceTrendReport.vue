<template>
  <div class="price-trend-report">
    <el-card>
      <template #header><span>采购价格波动趋势</span></template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="物料">
          <el-select
            v-model="searchForm.item"
            placeholder="请选择物料"
            filterable
            remote
            :remote-method="searchItems"
            clearable
            style="width: 300px;"
          >
            <el-option
              v-for="item in itemOptions"
              :key="item.id"
              :label="`${item.sku} - ${item.name}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="供应商">
          <el-select v-model="searchForm.supplier" placeholder="请选择供应商" clearable filterable>
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
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
        <el-form-item>
          <el-button type="primary" @click="loadReport">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="success" @click="exportToExcel">导出Excel</el-button>
        </el-form-item>
      </el-form>

      <!-- 价格统计 -->
      <el-row :gutter="20" style="margin-bottom: 20px;">
        <el-col :span="6">
          <el-statistic title="平均采购价" :value="stats.avg_price || 0" prefix="¥" :precision="2">
            <template #prefix><el-icon><Money /></el-icon></template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="最低采购价" :value="stats.min_price || 0" prefix="¥" :precision="2">
            <template #prefix><el-icon style="color: #67C23A;"><Bottom /></el-icon></template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="最高采购价" :value="stats.max_price || 0" prefix="¥" :precision="2">
            <template #prefix><el-icon style="color: #F56C6C;"><Top /></el-icon></template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="价格波动率" :value="stats.volatility || 0" suffix="%" :precision="2">
            <template #prefix><el-icon><TrendCharts /></el-icon></template>
          </el-statistic>
        </el-col>
      </el-row>

      <!-- 价格趋势表格 -->
      <el-table :data="reportData" v-loading="loading" border stripe>
        <el-table-column prop="purchase_date" label="采购日期" width="120" />
        <el-table-column prop="purchase_order_no" label="采购订单" width="150" />
        <el-table-column prop="supplier_name" label="供应商" width="200" />
        <el-table-column prop="item_sku" label="物料编码" width="150" />
        <el-table-column prop="item_name" label="物料名称" min-width="200" />
        <el-table-column prop="qty" label="采购数量" width="100" align="right" />
        <el-table-column prop="unit_price" label="单价" width="120" align="right">
          <template #default="{ row }">
            <span :style="{ color: getPriceColor(row.unit_price) }">
              ¥{{ (row.unit_price || 0).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="价格趋势" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.price_change > 0" type="danger">
              <el-icon><Top /></el-icon> {{ row.price_change.toFixed(1) }}%
            </el-tag>
            <el-tag v-else-if="row.price_change < 0" type="success">
              <el-icon><Bottom /></el-icon> {{ Math.abs(row.price_change).toFixed(1) }}%
            </el-tag>
            <el-tag v-else type="info">持平</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_amount" label="总金额" width="130" align="right">
          <template #default="{ row }">¥{{ (row.total_amount || 0).toFixed(2) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 价格趋势图 -->
    <el-card style="margin-top: 20px;">
      <template #header><span>价格趋势图</span></template>
      <div ref="chartRef" style="height: 400px;"></div>
    </el-card>

    <!-- 供应商价格对比 -->
    <el-card style="margin-top: 20px;">
      <template #header><span>供应商价格对比</span></template>
      <div ref="supplierChartRef" style="height: 400px;"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Money, Top, Bottom, TrendCharts } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import request from '@/utils/request'

const loading = ref(false)
const reportData = ref([])
const itemOptions = ref([])
const suppliers = ref([])
const chartRef = ref(null)
const supplierChartRef = ref(null)

const searchForm = reactive({
  item: null,
  supplier: null,
  dateRange: [
    new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    new Date().toISOString().split('T')[0]
  ]
})

const stats = reactive({
  avg_price: 0,
  min_price: 0,
  max_price: 0,
  volatility: 0
})

const getPriceColor = (price) => {
  if (price >= stats.avg_price * 1.1) return '#F56C6C'
  if (price <= stats.avg_price * 0.9) return '#67C23A'
  return '#606266'
}

const searchItems = async (query) => {
  if (!query) return
  try {
    const response = await request.get('/masterdata/items/', {
      params: { search: query, page_size: 20 }
    })
    itemOptions.value = response.results || response || []
  } catch (error) {
    console.error('搜索物料失败:', error)
  }
}

const loadSuppliers = async () => {
  try {
    const response = await request.get('/masterdata/suppliers/', { params: { page_size: 100 } })
    suppliers.value = response.results || response || []
  } catch (error) {
    console.error('加载供应商失败:', error)
  }
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
    
    const response = await request.get('/reports/purchase-price-trend/', { params })
    
    // 后端返回的是 results 数组，每个元素包含物料的价格趋势数据
    const results = response.results || response || []
    
    // 将后端返回的数据格式转换为前端需要的格式
    const items = []
    results.forEach(item => {
      // 每个物料的 trend_data 包含了该物料的所有采购记录
      if (item.trend_data && item.trend_data.length > 0) {
        item.trend_data.forEach((trend) => {
          items.push({
            purchase_date: trend.date,
            purchase_order_no: trend.order_no || '-',
            supplier_name: trend.supplier,
            item_sku: item.item_sku,
            item_name: item.item_name,
            qty: trend.qty,
            unit_price: trend.price,
            price_change: item.price_change_pct || 0,
            total_amount: trend.price * trend.qty
          })
        })
      }
    })
    
    reportData.value = items
    
    // 计算统计数据
    if (results.length > 0) {
      const allPrices = items.map(i => i.unit_price)
      const avgPrice = allPrices.length > 0 ? allPrices.reduce((a, b) => a + b, 0) / allPrices.length : 0
      const minPrice = allPrices.length > 0 ? Math.min(...allPrices) : 0
      const maxPrice = allPrices.length > 0 ? Math.max(...allPrices) : 0
      const volatility = avgPrice > 0 ? ((maxPrice - minPrice) / avgPrice * 100) : 0
      
      Object.assign(stats, {
        avg_price: avgPrice,
        min_price: minPrice,
        max_price: maxPrice,
        volatility: volatility
      })
    } else {
      Object.assign(stats, { avg_price: 0, min_price: 0, max_price: 0, volatility: 0 })
    }
    
    await nextTick()
    renderChart()
    renderSupplierChart()
  } catch (error) {
    ElMessage.error('加载报表失败')
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.item = null
  searchForm.supplier = null
  searchForm.dateRange = [
    new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    new Date().toISOString().split('T')[0]
  ]
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
      { field: 'supplier_name', title: '供应商' },
      { field: 'purchase_date', title: '采购日期' },
      { field: 'qty', title: '数量' },
      { field: 'unit_price', title: '单价', formatter: formatMoney },
      { field: 'price_change', title: '价格变化(%)', formatter: v => v?.toFixed(2) },
      { field: 'total_amount', title: '总金额', formatter: formatMoney }
    ]
    doExport(reportData.value, columns, '采购价格趋势')
    ElMessage.success('导出成功')
  })
}

const renderChart = () => {
  if (!chartRef.value) return
  const chart = echarts.init(chartRef.value)
  
  chart.setOption({
    title: { text: '采购价格趋势' },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: reportData.value.map(i => i.purchase_date)
    },
    yAxis: { type: 'value', name: '单价（元）' },
    series: [{
      name: '采购单价',
      type: 'line',
      data: reportData.value.map(i => i.unit_price),
      itemStyle: { color: '#409EFF' },
      markLine: {
        data: [
          { type: 'average', name: '平均价格' },
          { type: 'max', name: '最高价格' },
          { type: 'min', name: '最低价格' }
        ]
      }
    }]
  })
}

const renderSupplierChart = () => {
  if (!supplierChartRef.value) return
  const chart = echarts.init(supplierChartRef.value)
  
  // 按供应商分组计算平均价格
  const supplierPrices = {}
  reportData.value.forEach(item => {
    if (!supplierPrices[item.supplier_name]) {
      supplierPrices[item.supplier_name] = []
    }
    supplierPrices[item.supplier_name].push(item.unit_price)
  })
  
  const supplierAvg = Object.keys(supplierPrices).map(supplier => ({
    name: supplier,
    value: (supplierPrices[supplier].reduce((a, b) => a + b, 0) / supplierPrices[supplier].length).toFixed(2)
  }))
  
  chart.setOption({
    title: { text: '供应商价格对比', left: 'center' },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: supplierAvg.map(s => s.name) },
    yAxis: { type: 'value', name: '平均单价（元）' },
    series: [{
      name: '平均价格',
      type: 'bar',
      data: supplierAvg.map(s => parseFloat(s.value)),
      itemStyle: {
        color: (params) => {
          const colors = ['#5470C6', '#91CC75', '#FAC858', '#EE6666', '#73C0DE']
          return colors[params.dataIndex % colors.length]
        }
      }
    }]
  })
}

onMounted(() => {
  loadSuppliers()
  loadReport()
})
</script>

<style scoped>
.price-trend-report { padding: 20px; }
.search-form { margin-bottom: 20px; }
</style>

