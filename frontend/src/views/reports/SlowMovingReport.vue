<template>
  <div class="slow-moving-report">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>呆滞物料分析</span>
          <div class="header-actions">
            <el-select v-model="daysThreshold" placeholder="呆滞天数" style="width: 150px; margin-right: 10px;">
              <el-option label="超过30天" :value="30" />
              <el-option label="超过60天" :value="60" />
              <el-option label="超过90天" :value="90" />
              <el-option label="超过180天" :value="180" />
              <el-option label="超过365天" :value="365" />
            </el-select>
            <el-button type="primary" @click="handleAnalyze">
              <el-icon><DataAnalysis /></el-icon>
              分析
            </el-button>
            <el-button type="success" @click="handleExport">
              <el-icon><Download /></el-icon>
              导出
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 统计概览 -->
      <el-row :gutter="20" class="overview-row">
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="呆滞物料种类" :value="stats.itemCount" suffix="种" />
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="呆滞库存数量" :value="stats.totalQty" />
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card warning">
            <el-statistic 
              title="呆滞库存金额" 
              :value="stats.totalValue" 
              :precision="2" 
              prefix="¥"
              :value-style="{ color: '#f56c6c' }"
            />
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic 
              title="占库存总额比例" 
              :value="stats.percentage" 
              :precision="1" 
              suffix="%"
            />
          </el-card>
        </el-col>
      </el-row>
      
      <!-- 图表区域 -->
      <el-row :gutter="20" class="chart-row">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>呆滞物料分类分布</template>
            <div ref="categoryChartRef" style="height: 300px;"></div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>呆滞时间分布</template>
            <div ref="ageChartRef" style="height: 300px;"></div>
          </el-card>
        </el-col>
      </el-row>
      
      <!-- 数据表格 -->
      <el-table :data="tableData" border stripe v-loading="loading" class="data-table" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="item_code" label="物料编码" width="120" />
        <el-table-column prop="item_name" label="物料名称" min-width="180" />
        <el-table-column prop="category_name" label="分类" width="120" />
        <el-table-column prop="specification" label="规格" width="120" />
        <el-table-column prop="unit" label="单位" width="60" />
        <el-table-column prop="warehouse_name" label="仓库" width="100" />
        <el-table-column prop="qty" label="库存数量" width="100" align="right" />
        <el-table-column label="单价" width="100" align="right">
          <template #default="{ row }">
            ¥{{ formatNumber(row.unit_cost) }}
          </template>
        </el-table-column>
        <el-table-column label="库存金额" width="120" align="right">
          <template #default="{ row }">
            <span class="text-danger">¥{{ formatNumber(row.total_value) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="last_move_date" label="最后移动日期" width="120" />
        <el-table-column label="呆滞天数" width="100" align="right">
          <template #default="{ row }">
            <el-tag :type="getAgingType(row.aging_days)" size="small">
              {{ row.aging_days }}天
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="建议处理" width="100">
          <template #default="{ row }">
            <el-tag :type="getSuggestionType(row.aging_days)" size="small">
              {{ getSuggestion(row.aging_days) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleViewDetail(row)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="fetchData"
        @current-change="fetchData"
      />
      
      <!-- 批量处理 -->
      <div class="batch-actions" v-if="selectedItems.length > 0">
        <span>已选择 {{ selectedItems.length }} 项</span>
        <el-button type="warning" size="small" @click="handleBatchDisposal">
          批量报废
        </el-button>
        <el-button type="primary" size="small" @click="handleBatchTransfer">
          批量调拨
        </el-button>
        <el-button type="success" size="small" @click="handleBatchPromotion">
          促销清仓
        </el-button>
      </div>
    </el-card>
    
    <!-- 物料详情对话框 -->
    <el-dialog v-model="detailVisible" title="物料呆滞详情" width="700px">
      <el-descriptions :column="2" border v-if="currentItem">
        <el-descriptions-item label="物料编码">{{ currentItem.item_code }}</el-descriptions-item>
        <el-descriptions-item label="物料名称">{{ currentItem.item_name }}</el-descriptions-item>
        <el-descriptions-item label="规格">{{ currentItem.specification }}</el-descriptions-item>
        <el-descriptions-item label="单位">{{ currentItem.unit }}</el-descriptions-item>
        <el-descriptions-item label="仓库">{{ currentItem.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="库存数量">{{ currentItem.qty }}</el-descriptions-item>
        <el-descriptions-item label="单价">¥{{ formatNumber(currentItem.unit_cost) }}</el-descriptions-item>
        <el-descriptions-item label="库存金额">¥{{ formatNumber(currentItem.total_value) }}</el-descriptions-item>
        <el-descriptions-item label="最后移动日期">{{ currentItem.last_move_date }}</el-descriptions-item>
        <el-descriptions-item label="呆滞天数">
          <el-tag :type="getAgingType(currentItem.aging_days)">{{ currentItem.aging_days }}天</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      
      <el-divider>历史移动记录</el-divider>
      
      <el-timeline>
        <el-timeline-item
          v-for="move in moveHistory"
          :key="move.id"
          :timestamp="move.move_date"
          :type="move.qty > 0 ? 'success' : 'danger'"
        >
          {{ move.move_type_label }}: {{ move.qty > 0 ? '+' : '' }}{{ move.qty }} {{ currentItem?.unit }}
          <span class="text-muted">（{{ move.reference_no }}）</span>
        </el-timeline-item>
      </el-timeline>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { getSlowMovingItems } from '@/api/analytics'
import { getStockValuation, getStockMoveList, createStockAdjustment, createStockTransfer } from '@/api/inventory'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DataAnalysis, Download } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const loading = ref(false)
const daysThreshold = ref(90)
const tableData = ref<any[]>([])
const selectedItems = ref<any[]>([])
const handleSelectionChange = (rows) => { selectedItems.value = rows }
const detailVisible = ref(false)
const currentItem = ref(null)
const moveHistory = ref<any[]>([])

const categoryChartRef = ref(null)
const ageChartRef = ref(null)
let categoryChart = null
let ageChart = null

const stats = reactive({
  itemCount: 0,
  totalQty: 0,
  totalValue: 0,
  percentage: 0
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const formatNumber = (num) => {
  if (!num) return '0.00'
  return Number(num).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const getAgingType = (days) => {
  if (days >= 365) return 'danger'
  if (days >= 180) return 'warning'
  if (days >= 90) return ''
  return 'info'
}

const getSuggestionType = (days) => {
  if (days >= 365) return 'danger'
  if (days >= 180) return 'warning'
  return 'info'
}

const getSuggestion = (days) => {
  if (days >= 365) return '建议报废'
  if (days >= 180) return '促销清仓'
  if (days >= 90) return '调拨使用'
  return '继续观察'
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getSlowMovingItems({
        days: daysThreshold.value,
        page: pagination.page,
        page_size: pagination.pageSize
      })
    tableData.value = res.results || res.results || res || []
    pagination.total = res.count || res.count || 0
    
    calculateStats()
    initCharts()
  } catch (error) {
    console.error('获取呆滞物料失败:', error)
    tableData.value = []
    ElMessage.error('获取呆滞物料数据失败')
  } finally {
    loading.value = false
  }
}

const calculateStats = async () => {
  stats.itemCount = tableData.value.length
  stats.totalQty = tableData.value.reduce((sum, item) => sum + item.qty, 0)
  stats.totalValue = tableData.value.reduce((sum, item) => sum + item.total_value, 0)
  
  // 计算呆滞库存占总库存的百分比
  try {
    const res = await getStockValuation()
    const totalInventoryValue = res.total_value || 0
    stats.percentage = totalInventoryValue > 0 
      ? ((stats.totalValue / totalInventoryValue) * 100).toFixed(2)
      : 0
  } catch (error) {
    console.error('获取总库存金额失败:', error)
    stats.percentage = 0
  }
}

const initCharts = () => {
  initCategoryChart()
  initAgeChart()
}

const initCategoryChart = () => {
  if (!categoryChartRef.value) return
  
  if (categoryChart) {
    categoryChart.dispose()
  }
  
  categoryChart = echarts.init(categoryChartRef.value)
  
  // 按分类汇总
  const categoryMap = {}
  tableData.value.forEach(item => {
    const category = item.category_name || '未分类'
    if (!categoryMap[category]) {
      categoryMap[category] = 0
    }
    categoryMap[category] += item.total_value
  })
  
  const data = Object.entries(categoryMap).map(([name, value]) => ({ name, value }))
  
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
        name: '分类分布',
        type: 'pie',
        radius: '60%',
        center: ['60%', '50%'],
        data: data,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }
  
  categoryChart.setOption(option)
}

const initAgeChart = () => {
  if (!ageChartRef.value) return
  
  if (ageChart) {
    ageChart.dispose()
  }
  
  ageChart = echarts.init(ageChartRef.value)
  
  // 按呆滞时间分组
  const ageGroups = {
    '30-60天': 0,
    '60-90天': 0,
    '90-180天': 0,
    '180-365天': 0,
    '超过1年': 0
  }
  
  tableData.value.forEach(item => {
    const days = item.aging_days
    if (days < 60) ageGroups['30-60天'] += item.total_value
    else if (days < 90) ageGroups['60-90天'] += item.total_value
    else if (days < 180) ageGroups['90-180天'] += item.total_value
    else if (days < 365) ageGroups['180-365天'] += item.total_value
    else ageGroups['超过1年'] += item.total_value
  })
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        return `${params[0].name}<br/>金额: ¥${formatNumber(params[0].value)}`
      }
    },
    xAxis: {
      type: 'category',
      data: Object.keys(ageGroups)
    },
    yAxis: {
      type: 'value',
      name: '金额 (元)',
      axisLabel: {
        formatter: (value) => {
          if (value >= 10000) return (value / 10000).toFixed(0) + '万'
          return value
        }
      }
    },
    series: [
      {
        type: 'bar',
        data: Object.values(ageGroups),
        itemStyle: {
          color: (params) => {
            const colors = ['#67c23a', '#e6a23c', '#f56c6c', '#f56c6c', '#909399']
            return colors[params.dataIndex]
          }
        },
        label: {
          show: true,
          position: 'top',
          formatter: (params) => '¥' + formatNumber(params.value)
        }
      }
    ]
  }
  
  ageChart.setOption(option)
}

const handleAnalyze = () => {
  fetchData()
}

const handleExport = () => {
  if (!tableData.value.length) {
    ElMessage.warning('没有数据可导出')
    return
  }
  
  import('@/utils/export').then(({ exportToExcel, formatMoney }) => {
    const columns = [
      { field: 'item_code', title: '物料编码' },
      { field: 'item_name', title: '物料名称' },
      { field: 'category_name', title: '分类' },
      { field: 'warehouse_name', title: '仓库' },
      { field: 'qty_on_hand', title: '库存数量' },
      { field: 'unit_cost', title: '单位成本', formatter: formatMoney },
      { field: 'inventory_value', title: '库存金额', formatter: formatMoney },
      { field: 'days_no_movement', title: '未动天数' },
      { field: 'last_movement_date', title: '最后移动日期' }
    ]
    exportToExcel(tableData.value, columns, '呆滞物料分析')
    ElMessage.success('导出成功')
  })
}

const handleViewDetail = async (row) => {
  currentItem.value = row
  // 加载真实的移动历史
  try {
    const res = await getStockMoveList({
        item: row.item_id,
        warehouse: row.warehouse_id,
        page_size: 20,
        ordering: '-move_date'
      })
    const moves = res.results || res.results || res || []
    moveHistory.value = moves.map(m => ({
      id: m.id,
      move_date: m.move_date,
      move_type_label: m.move_type_display || m.move_type,
      qty: m.move_type.startsWith('IN') ? m.qty : -m.qty,
      reference_no: m.move_no
    }))
  } catch (error) {
    console.error('获取移动历史失败:', error)
    moveHistory.value = []
  }
  detailVisible.value = true
}

const handleBatchDisposal = async () => {
  if (!selectedItems.value.length) {
    ElMessage.warning('请先选择要报废的物料')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要对选中的 ${selectedItems.value.length} 种物料进行报废处理吗？报废后将生成库存调整单。`,
      '批量报废',
      {
        type: 'warning',
        confirmButtonText: '确认报废',
        cancelButtonText: '取消'
      }
    )
    
    // 为每个选中的物料创建库存调整
    let successCount = 0
    let failCount = 0
    
    for (const row of selectedItems.value) {
      try {
        await createStockAdjustment({
          warehouse: row.warehouse_id,
          adjustment_date: new Date().toISOString().split('T')[0],
          reason: '呆滞物料报废处理',
          notes: `呆滞天数：${row.aging_days}天`,
          lines: [{
            item: row.item_id,
            system_qty: row.qty,
            actual_qty: 0,
            variance: -row.qty,
            notes: '呆滞报废'
          }]
        })
        successCount++
      } catch (error) {
        console.error(`报废物料 ${row.item_code} 失败:`, error)
        failCount++
      }
    }
    
    if (successCount > 0) {
      ElMessage.success(`成功报废 ${successCount} 种物料${failCount > 0 ? `，${failCount} 种失败` : ''}`)
      fetchData() // 刷新数据
      selectedItems.value = []
    } else {
      ElMessage.error('报废操作失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('报废操作失败')
    }
  }
}

const handleBatchTransfer = async () => {
  if (!selectedItems.value.length) {
    ElMessage.warning('请先选择要调拨的物料')
    return
  }
  
  try {
    const { value: targetWarehouse } = await ElMessageBox.prompt(
      `选中 ${selectedItems.value.length} 种物料，请输入目标仓库ID`,
      '批量调拨',
      {
        confirmButtonText: '确认调拨',
        cancelButtonText: '取消',
        inputPattern: /^\d+$/,
        inputErrorMessage: '请输入有效的仓库ID'
      }
    )
    
    let successCount = 0
    let failCount = 0
    
    for (const row of selectedItems.value) {
      try {
        await createStockTransfer({
          item: row.item_id,
          warehouse_from: row.warehouse_id,
          warehouse_to: parseInt(targetWarehouse),
          qty: row.qty,
          unit_cost: row.unit_cost,
          move_date: new Date().toISOString().split('T')[0],
          notes: `呆滞物料调拨（呆滞${row.aging_days}天）`
        })
        successCount++
      } catch (error) {
        console.error(`调拨物料 ${row.item_code} 失败:`, error)
        failCount++
      }
    }
    
    if (successCount > 0) {
      ElMessage.success(`成功调拨 ${successCount} 种物料${failCount > 0 ? `，${failCount} 种失败` : ''}`)
      fetchData()
      selectedItems.value = []
    } else {
      ElMessage.error('调拨操作失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('调拨操作失败')
    }
  }
}

const handleBatchPromotion = async () => {
  if (!selectedItems.value.length) {
    ElMessage.warning('请先选择要促销的物料')
    return
  }
  
  try {
    const { value: discountPercent } = await ElMessageBox.prompt(
      `选中 ${selectedItems.value.length} 种物料，请输入折扣比例（例如：30表示3折）`,
      '批量促销',
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        inputPattern: /^\d+$/,
        inputErrorMessage: '请输入1-99之间的数字'
      }
    )
    
    const discount = parseInt(discountPercent) / 100
    if (discount <= 0 || discount >= 1) {
      ElMessage.error('折扣比例必须在1-99之间')
      return
    }
    
    // 为选中的物料应用促销标记（可以在物料主数据中添加促销标记字段）
    // 这里先显示促销信息提示
    const promotionInfo = selectedItems.value.map(row => {
      const originalPrice = row.unit_cost
      const promotionPrice = (originalPrice * discount).toFixed(2)
      return `${row.item_code} - ${row.item_name}: ¥${originalPrice} → ¥${promotionPrice} (${discountPercent}折)`
    }).join('\n')
    
    await ElMessageBox.alert(
      `以下物料已标记为促销（需在销售模块应用促销价格）：\n\n${promotionInfo}`,
      '促销清仓',
      { type: 'success' }
    )
    
    ElMessage.info('促销信息已生成，请在销售模块中应用促销价格')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('促销操作失败')
    }
  }
}

onMounted(() => {
  fetchData()
  window.addEventListener('resize', () => {
    categoryChart?.resize()
    ageChart?.resize()
  })
})

onUnmounted(() => {
  categoryChart?.dispose()
  ageChart?.dispose()
})
</script>

<style scoped>
.slow-moving-report {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
}

.header-actions {
  display: flex;
  align-items: center;
}

.overview-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.chart-row {
  margin-bottom: 20px;
}

.data-table {
  margin-top: 20px;
}

.text-danger {
  color: #f56c6c;
}

.text-muted {
  color: #909399;
  font-size: 12px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.batch-actions {
  margin-top: 15px;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>

