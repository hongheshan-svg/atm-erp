<template>
  <div class="cost-accounting-container">
    <div class="page-header">
      <h2>库存成本核算</h2>
      <el-button type="primary" @click="handleGenerateSummary">生成期间汇总</el-button>
    </div>
    
    <el-tabs v-model="activeTab">
      <el-tab-pane label="库存估值" name="valuation">
        <!-- 筛选条件 -->
        <el-card shadow="never" class="filter-card">
          <el-form :inline="true" :model="queryParams">
            <el-form-item label="年份">
              <el-select v-model="queryParams.year" style="width: 100px">
                <el-option v-for="y in yearOptions" :key="y" :label="y + '年'" :value="y" />
              </el-select>
            </el-form-item>
            <el-form-item label="月份">
              <el-select v-model="queryParams.month" style="width: 100px">
                <el-option v-for="m in 12" :key="m" :label="m + '月'" :value="m" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="fetchValuation">查询</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        
        <!-- 汇总卡片 -->
        <el-row :gutter="16" class="stats-row">
          <el-col :span="6">
            <el-card shadow="never" class="stat-card">
              <div class="stat-value">￥{{ formatAmount(valuation.total_opening_cost) }}</div>
              <div class="stat-label">期初金额</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never" class="stat-card stat-success">
              <div class="stat-value">￥{{ formatAmount(valuation.total_in_cost) }}</div>
              <div class="stat-label">本期入库</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never" class="stat-card stat-danger">
              <div class="stat-value">￥{{ formatAmount(valuation.total_out_cost) }}</div>
              <div class="stat-label">本期出库</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never" class="stat-card stat-primary">
              <div class="stat-value">￥{{ formatAmount(valuation.total_closing_cost) }}</div>
              <div class="stat-label">期末金额</div>
            </el-card>
          </el-col>
        </el-row>
        
        <!-- 分仓库统计 -->
        <el-row :gutter="16">
          <el-col :span="12">
            <el-card shadow="never" header="按仓库分布">
              <div ref="warehouseChart" style="height: 300px"></div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never" header="按类别分布">
              <div ref="categoryChart" style="height: 300px"></div>
            </el-card>
          </el-col>
        </el-row>
        
        <!-- 明细表格 -->
        <el-card shadow="never" style="margin-top: 16px">
          <template #header>
            <span>库存估值明细</span>
          </template>
          <el-table :data="valuation.details" border stripe max-height="400">
            <el-table-column prop="item_code" label="物料编码" width="120" />
            <el-table-column prop="item_name" label="物料名称" min-width="150" show-overflow-tooltip />
            <el-table-column prop="warehouse_name" label="仓库" width="100" />
            <el-table-column label="期初" align="right" width="120">
              <template #default="{ row }">
                {{ row.opening_qty }} / ￥{{ formatAmount(row.opening_cost) }}
              </template>
            </el-table-column>
            <el-table-column label="入库" align="right" width="120">
              <template #default="{ row }">
                {{ row.in_qty }} / ￥{{ formatAmount(row.in_cost) }}
              </template>
            </el-table-column>
            <el-table-column label="出库" align="right" width="120">
              <template #default="{ row }">
                {{ row.out_qty }} / ￥{{ formatAmount(row.out_cost) }}
              </template>
            </el-table-column>
            <el-table-column label="期末数量" prop="closing_qty" align="right" width="100" />
            <el-table-column label="期末单价" align="right" width="100">
              <template #default="{ row }">
                ￥{{ formatAmount(row.closing_unit_cost) }}
              </template>
            </el-table-column>
            <el-table-column label="期末金额" align="right" width="120">
              <template #default="{ row }">
                <span class="amount">￥{{ formatAmount(row.closing_cost) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="成本记录" name="records">
        <el-card shadow="never">
          <template #header>
            <el-form :inline="true" :model="recordQuery">
              <el-form-item label="物料">
                <el-input v-model="recordQuery.search" placeholder="编码或名称" clearable style="width: 200px" />
              </el-form-item>
              <el-form-item label="交易类型">
                <el-select v-model="recordQuery.transaction_type" clearable placeholder="全部">
                  <el-option label="采购入库" value="PURCHASE_IN" />
                  <el-option label="销售出库" value="SALES_OUT" />
                  <el-option label="生产领料" value="PRODUCTION_OUT" />
                  <el-option label="盘点调整" value="ADJUST_IN" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="fetchRecords">查询</el-button>
              </el-form-item>
            </el-form>
          </template>
          <el-table :data="records" v-loading="recordLoading" border stripe>
            <el-table-column prop="transaction_date" label="日期" width="100" />
            <el-table-column prop="item_code" label="物料编码" width="120" />
            <el-table-column prop="item_name" label="物料名称" min-width="150" show-overflow-tooltip />
            <el-table-column prop="transaction_type_display" label="类型" width="100" />
            <el-table-column prop="reference_no" label="参考单号" width="140" />
            <el-table-column label="数量" prop="quantity" align="right" width="100">
              <template #default="{ row }">
                <span :class="row.quantity > 0 ? 'text-success' : 'text-danger'">
                  {{ row.quantity > 0 ? '+' : '' }}{{ row.quantity }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="单价" prop="unit_cost" align="right" width="100">
              <template #default="{ row }">
                ￥{{ formatAmount(row.unit_cost) }}
              </template>
            </el-table-column>
            <el-table-column label="金额" prop="total_cost" align="right" width="120">
              <template #default="{ row }">
                <span :class="row.total_cost > 0 ? 'text-success' : 'text-danger'">
                  ￥{{ formatAmount(row.total_cost) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="结存数量" prop="balance_qty" align="right" width="100" />
            <el-table-column label="结存金额" align="right" width="120">
              <template #default="{ row }">
                ￥{{ formatAmount(row.balance_cost) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
      
      <el-tab-pane label="成本配置" name="config">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>计价方法配置</span>
              <el-button type="primary" size="small" v-permission="'inventory:stock:create'" @click="handleAddConfig">新增配置</el-button>
            </div>
          </template>
          <el-table :data="configs" border stripe>
            <el-table-column prop="name" label="配置名称" width="150" />
            <el-table-column prop="costing_method_display" label="计价方法" width="150" />
            <el-table-column prop="period_type_display" label="结算周期" width="100" />
            <el-table-column label="成本要素">
              <template #default="{ row }">
                <el-tag v-if="row.include_purchase_price" size="small" type="success">采购价</el-tag>
                <el-tag v-if="row.include_freight" size="small" type="info">运费</el-tag>
                <el-tag v-if="row.include_tax" size="small" type="warning">税费</el-tag>
                <el-tag v-if="row.include_handling" size="small">装卸费</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="默认" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.is_default" type="success" size="small">是</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleSetDefault(row)" v-if="!row.is_default">设为默认</el-button>
                <el-button type="primary" link size="small" v-permission="'inventory:stock:edit'" @click="handleEditConfig(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
    
    <!-- 生成汇总对话框 -->
    <el-dialog v-model="generateDialogVisible" title="生成期间汇总" width="400px">
      <el-form :model="generateForm" label-width="80px">
        <el-form-item label="年份">
          <el-select v-model="generateForm.year" style="width: 100%">
            <el-option v-for="y in yearOptions" :key="y" :label="y + '年'" :value="y" />
          </el-select>
        </el-form-item>
        <el-form-item label="月份">
          <el-select v-model="generateForm.month" style="width: 100%">
            <el-option v-for="m in 12" :key="m" :label="m + '月'" :value="m" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmGenerate" :loading="generating">生成</el-button>
      </template>
    </el-dialog>

    <!-- 成本配置 -->
    <el-dialog v-model="configDialogVisible" :title="configIsEdit ? '编辑配置' : '添加配置'" width="500px">
      <el-form label-width="100px">
        <el-form-item label="配置名称">
          <el-input v-model="configForm.name" />
        </el-form-item>
        <el-form-item label="计算方法">
          <el-select v-model="configForm.method" style="width: 100%">
            <el-option label="加权平均" value="WEIGHTED_AVERAGE" />
            <el-option label="先进先出" value="FIFO" />
            <el-option label="标准成本" value="STANDARD" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="configForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="configDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="configSaving" @click="handleConfigSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { getInventoryValuation, getCostRecords, getCostConfigs, generatePeriodSummary, setCostConfigDefault, updateCostConfig, createCostConfig } from '@/api/inventory'
import * as echarts from 'echarts'

const activeTab = ref('valuation')
const warehouseChart = ref(null)
const categoryChart = ref(null)
let warehouseChartInstance = null
let categoryChartInstance = null

const currentYear = new Date().getFullYear()
const currentMonth = new Date().getMonth() + 1

const yearOptions = Array.from({ length: 3 }, (_, i) => currentYear - i)

const queryParams = reactive({
  year: currentYear,
  month: currentMonth
})

const recordQuery = reactive({
  search: '',
  transaction_type: ''
})

const generateForm = reactive({
  year: currentYear,
  month: currentMonth
})

const valuation = ref({})
const records = ref([])
const configs = ref([])
const recordLoading = ref(false)
const generateDialogVisible = ref(false)
const generating = ref(false)
const configDialogVisible = ref(false)
const configIsEdit = ref(false)
const configSaving = ref(false)
const configForm = reactive({ id: null, name: '', method: 'WEIGHTED_AVERAGE', description: '' })

const fetchValuation = async () => {
  try {
    const data = await getInventoryValuation(
    queryParams
    )
    valuation.value = data
    
    nextTick(() => {
      renderCharts()
    })
  } catch (e) {
    console.error(e)
  }
}

const fetchRecords = async () => {
  recordLoading.value = true
  try {
    const data = await getCostRecords(
      { ...recordQuery, page_size: 100 }
    )
    records.value = data.results || data
  } catch (e) {
    console.error(e)
  } finally {
    recordLoading.value = false
  }
}

const fetchConfigs = async () => {
  try {
    const data = await getCostConfigs()
    configs.value = data.results || data
  } catch (e) {
    console.error(e)
  }
}

const handleGenerateSummary = () => {
  generateDialogVisible.value = true
}

const confirmGenerate = async () => {
  generating.value = true
  try {
    const data = await generatePeriodSummary(generateForm)
    ElMessage.success(data.message)
    generateDialogVisible.value = false
    fetchValuation()
  } catch (e) {
    ElMessage.error('生成失败')
  } finally {
    generating.value = false
  }
}

const handleSetDefault = async (row) => {
  try {
    await setCostConfigDefault(row.id)
    ElMessage.success('设置成功')
    fetchConfigs()
  } catch (e) {
    ElMessage.error('设置失败')
  }
}

const handleAddConfig = () => {
  configIsEdit.value = false
  Object.assign(configForm, { id: null, name: '', method: 'WEIGHTED_AVERAGE', description: '' })
  configDialogVisible.value = true
}

const handleEditConfig = (row) => {
  configIsEdit.value = true
  Object.assign(configForm, { id: row.id, name: row.name, method: row.method, description: row.description })
  configDialogVisible.value = true
}

const handleConfigSave = async () => {
  configSaving.value = true
  try {
    if (configIsEdit.value) {
      await updateCostConfig(configForm.id, configForm)
      ElMessage.success('更新成功')
    } else {
      await createCostConfig(configForm)
      ElMessage.success('创建成功')
    }
    configDialogVisible.value = false
    fetchConfigs()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
    else ElMessage.error('操作失败')
  } finally {
    configSaving.value = false
  }
}

const renderCharts = () => {
  // 仓库分布图
  if (warehouseChart.value) {
    if (!warehouseChartInstance) {
      warehouseChartInstance = echarts.init(warehouseChart.value)
    }
    
    const warehouseData = (valuation.value.by_warehouse || []).map(item => ({
      name: item.warehouse__name || '未分配',
      value: Number(item.total_cost || 0)
    }))
    
    warehouseChartInstance.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: ￥{c} ({d}%)' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: warehouseData,
        emphasis: { itemStyle: { shadowBlur: 10 } }
      }]
    })
  }
  
  // 类别分布图
  if (categoryChart.value) {
    if (!categoryChartInstance) {
      categoryChartInstance = echarts.init(categoryChart.value)
    }
    
    const categoryData = (valuation.value.by_category || []).map(item => ({
      name: item.item__category__name || '未分类',
      value: Number(item.total_cost || 0)
    }))
    
    categoryChartInstance.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: ￥{c} ({d}%)' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: categoryData,
        emphasis: { itemStyle: { shadowBlur: 10 } }
      }]
    })
  }
}

const formatAmount = (val) => {
  if (!val) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

onMounted(() => {
  fetchValuation()
  fetchRecords()
  fetchConfigs()
})
</script>

<style scoped>
.cost-accounting-container {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.filter-card {
  margin-bottom: 16px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 16px 0;
}

.stat-value {
  font-size: 22px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.stat-primary .stat-value { color: #409eff; }
.stat-success .stat-value { color: #67c23a; }
.stat-danger .stat-value { color: #f56c6c; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.amount {
  font-weight: 500;
}

.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }
</style>
