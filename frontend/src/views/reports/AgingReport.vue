<template>
  <div class="aging-report">
    <el-card>
      <template #header><span>账龄分析</span></template>

      <el-tabs v-model="activeTab" @tab-change="loadReport">
        <el-tab-pane label="应收账款账龄" name="ar">
          <el-form :inline="true" :model="searchForm" class="search-form">
            <el-form-item label="客户">
              <el-select v-model="searchForm.customer" placeholder="请选择客户" clearable filterable>
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadReport">查询</el-button>
              <el-button @click="resetSearch">重置</el-button>
              <el-button type="success" @click="exportToExcel">导出Excel</el-button>
            </el-form-item>
          </el-form>

          <!-- 账龄统计 -->
          <el-row :gutter="20" style="margin-bottom: 20px;">
            <el-col :span="6">
              <el-statistic title="未逾期" :value="agingSummary.current || 0" prefix="¥" :precision="2">
                <template #prefix><el-icon style="color: #67C23A;"><SuccessFilled /></el-icon></template>
              </el-statistic>
            </el-col>
            <el-col :span="6">
              <el-statistic title="逾期1-30天" :value="agingSummary.days_1_30 || 0" prefix="¥" :precision="2">
                <template #prefix><el-icon style="color: #E6A23C;"><Warning /></el-icon></template>
              </el-statistic>
            </el-col>
            <el-col :span="6">
              <el-statistic title="逾期31-60天" :value="agingSummary.days_31_60 || 0" prefix="¥" :precision="2">
                <template #prefix><el-icon style="color: #F56C6C;"><Warning /></el-icon></template>
              </el-statistic>
            </el-col>
            <el-col :span="6">
              <el-statistic title="逾期60天以上" :value="agingSummary.days_60_plus || 0" prefix="¥" :precision="2">
                <template #prefix><el-icon style="color: #F56C6C;"><CircleCloseFilled /></el-icon></template>
              </el-statistic>
            </el-col>
          </el-row>

          <!-- 批量操作 -->

          <div v-if="selectedRows.length > 0" class="batch-toolbar">

            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>

            <el-button size="small" @click="batchExport">导出选中</el-button>

          </div>

          <el-table :data="reportData" v-loading="loading" border stripe @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="ar_no" label="应收单号" width="150" />
            <el-table-column prop="customer_name" label="客户" width="200" />
            <el-table-column prop="invoice_no" label="发票号" width="150" />
            <el-table-column prop="invoice_date" label="发票日期" width="120" />
            <el-table-column prop="due_date" label="到期日期" width="120" />
            <el-table-column prop="amount_due" label="应收金额" width="130" align="right">
              <template #default="{ row }">¥{{ toFixedSafe(row.amount_due) }}</template>
            </el-table-column>
            <el-table-column prop="amount_paid" label="已收金额" width="130" align="right">
              <template #default="{ row }">¥{{ toFixedSafe(row.amount_paid) }}</template>
            </el-table-column>
            <el-table-column label="未收金额" width="130" align="right">
              <template #default="{ row }">
                <span style="font-weight: 600;">¥{{ subtractFixedSafe(row.amount_due, row.amount_paid) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="逾期天数" width="100" align="right">
              <template #default="{ row }">
                <span :style="{ color: getOverdueDaysColor(row.overdue_days) }">
                  {{ row.overdue_days || 0 }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="账龄" width="120">
              <template #default="{ row }">
                <el-tag :type="getAgingType(row.overdue_days)">
                  {{ getAgingLabel(row.overdue_days) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="应付账款账龄" name="ap">
          <el-form :inline="true" :model="searchForm" class="search-form">
            <el-form-item label="供应商">
              <el-select v-model="searchForm.supplier" placeholder="请选择供应商" clearable filterable>
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadReport">查询</el-button>
              <el-button @click="resetSearch">重置</el-button>
              <el-button type="success" @click="exportToExcel">导出Excel</el-button>
            </el-form-item>
          </el-form>

          <!-- 账龄统计 -->
          <el-row :gutter="20" style="margin-bottom: 20px;">
            <el-col :span="6">
              <el-statistic title="未逾期" :value="agingSummary.current || 0" prefix="¥" :precision="2" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="逾期1-30天" :value="agingSummary.days_1_30 || 0" prefix="¥" :precision="2" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="逾期31-60天" :value="agingSummary.days_31_60 || 0" prefix="¥" :precision="2" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="逾期60天以上" :value="agingSummary.days_60_plus || 0" prefix="¥" :precision="2" />
            </el-col>
          </el-row>

          <el-table :data="reportData" v-loading="loading" border stripe>
            <el-table-column prop="ap_no" label="应付单号" width="150" />
            <el-table-column prop="supplier_name" label="供应商" width="200" />
            <el-table-column prop="invoice_no" label="发票号" width="150" />
            <el-table-column prop="invoice_date" label="发票日期" width="120" />
            <el-table-column prop="due_date" label="到期日期" width="120" />
            <el-table-column prop="amount_due" label="应付金额" width="130" align="right">
              <template #default="{ row }">¥{{ toFixedSafe(row.amount_due) }}</template>
            </el-table-column>
            <el-table-column prop="amount_paid" label="已付金额" width="130" align="right">
              <template #default="{ row }">¥{{ toFixedSafe(row.amount_paid) }}</template>
            </el-table-column>
            <el-table-column label="未付金额" width="130" align="right">
              <template #default="{ row }">
                <span style="font-weight: 600;">¥{{ ((row.amount_due || 0) - (row.amount_paid || 0)).toFixed(2) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="逾期天数" width="100" align="right">
              <template #default="{ row }">
                <span :style="{ color: getOverdueDaysColor(row.overdue_days) }">
                  {{ row.overdue_days || 0 }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="账龄" width="120">
              <template #default="{ row }">
                <el-tag :type="getAgingType(row.overdue_days)">
                  {{ getAgingLabel(row.overdue_days) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 账龄分布图 -->
    <el-card style="margin-top: 20px;">
      <template #header><span>账龄分布</span></template>
      <div ref="pieChartRef" style="height: 400px;"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { getAgingReport } from '@/api/reports'
import { getCustomerList } from '@/api/masterdata'
import { getSupplierList } from '@/api/masterdata'
import { ElMessage } from 'element-plus'
import { Clock, TrendCharts, Money, Warning, SuccessFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { subtractFixedSafe, toFixedSafe } from '@/utils/number'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchExport } = useBatchOperation('/api/reports/')


const loading = ref(false)
const reportData = ref<any[]>([])
const customers = ref<any[]>([])
const suppliers = ref<any[]>([])
const activeTab = ref('ar')
const chartRef = ref(null)
const pieChartRef = ref(null)
const searchForm = reactive({ customer: null, supplier: null })
const agingSummary = reactive({ current: 0, days_1_30: 0, days_31_60: 0, days_60_plus: 0 })

const getOverdueDaysColor = (days) => days <= 0 ? '#67C23A' : days <= 30 ? '#E6A23C' : '#F56C6C'
const getAgingType = (days) => days <= 0 ? 'success' : days <= 30 ? 'warning' : 'danger'
const getAgingLabel = (days) => {
  if (days <= 0) return '未逾期'
  if (days <= 30) return '1-30天'
  if (days <= 60) return '31-60天'
  return '60天以上'
}

const loadReport = async () => {
  loading.value = true
  try {
    // 使用统一的 /reports/aging/ 接口，通过 type 参数区分 AR/AP
    const params = { type: activeTab.value }
    if (activeTab.value === 'ar' && searchForm.customer) {
      params.customer = searchForm.customer
    } else if (activeTab.value === 'ap' && searchForm.supplier) {
      params.supplier = searchForm.supplier
    }
    
    const response = await getAgingReport(params)
    
    // 映射后端的 summary 字段到前端期望的格式
    const summary = response.summary || {}
    Object.assign(agingSummary, {
      current: summary.current || 0,
      days_1_30: summary['30_60'] || 0,  // 后端用 30_60 表示 1-30天后的逾期
      days_31_60: summary['60_90'] || 0,
      days_60_plus: summary.over_90 || 0
    })
    
    // 映射后端字段到前端显示字段
    const results = response.results || response || []
    reportData.value = results.map(item => ({
      ...item,
      overdue_days: item.days_overdue || 0
    }))
    
    await nextTick()
    renderPieChart()
  } catch (error) {
    ElMessage.error('加载账龄分析失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const response = await getCustomerList({ page_size: 100 })
    customers.value = response.results || response || []
  } catch (error) {
    console.error('加载客户失败:', error)
  }
}

const loadSuppliers = async () => {
  try {
    const response = await getSupplierList({ page_size: 100 })
    suppliers.value = response.results || response || []
  } catch (error) {
    console.error('加载供应商失败:', error)
  }
}

const resetSearch = () => {
  searchForm.customer = null
  searchForm.supplier = null
  loadReport()
}

const exportToExcel = () => {
  if (!reportData.value.length) {
    ElMessage.warning('没有数据可导出')
    return
  }
  
  import('@/utils/export').then(({ exportToExcel: doExport, formatMoney }) => {
    const columns = [
      { field: activeTab.value === 'ar' ? 'ar_no' : 'ap_no', title: '单据号' },
      { field: activeTab.value === 'ar' ? 'customer_name' : 'supplier_name', title: activeTab.value === 'ar' ? '客户' : '供应商' },
      { field: 'invoice_no', title: '发票号' },
      { field: 'invoice_date', title: '开票日期' },
      { field: 'due_date', title: '到期日期' },
      { field: 'amount_due', title: '应收/付金额', formatter: formatMoney },
      { field: 'amount_paid', title: '已收/付金额', formatter: formatMoney },
      { field: 'balance', title: '余额', formatter: formatMoney },
      { field: 'overdue_days', title: '逾期天数' }
    ]
    doExport(reportData.value, columns, activeTab.value === 'ar' ? '应收账龄分析' : '应付账龄分析')
    ElMessage.success('导出成功')
  })
}

const renderPieChart = () => {
  if (!pieChartRef.value) return
  const chart = echarts.init(pieChartRef.value)
  
  chart.setOption({
    title: { text: '账龄分布', left: 'center' },
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    series: [{
      name: '金额',
      type: 'pie',
      radius: ['40%', '70%'],
      data: [
        { value: agingSummary.current, name: '未逾期', itemStyle: { color: '#67C23A' } },
        { value: agingSummary.days_1_30, name: '1-30天', itemStyle: { color: '#E6A23C' } },
        { value: agingSummary.days_31_60, name: '31-60天', itemStyle: { color: '#F56C6C' } },
        { value: agingSummary.days_60_plus, name: '60天以上', itemStyle: { color: '#C0392B' } }
      ]
    }]
  })
}

onMounted(() => {
  loadCustomers()
  loadSuppliers()
  loadReport()
})
</script>

<style scoped>
.aging-report { padding: 20px; }
.search-form { margin-bottom: 20px; }
</style>
