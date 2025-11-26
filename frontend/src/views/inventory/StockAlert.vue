<template>
  <div class="stock-alert">
    <el-card>
      <template #header><span>库存预警</span></template>

      <el-alert
        title="库存预警说明"
        type="warning"
        description="以下物料的库存已低于最小库存水平，请及时补货"
        :closable="false"
        style="margin-bottom: 20px;"
      />

      <el-tabs v-model="activeTab">
        <el-tab-pane label="低库存预警" name="low">
          <el-table :data="filteredAlerts" v-loading="loading" border stripe>
            <el-table-column prop="item_sku" label="物料编码" width="150" />
            <el-table-column prop="item_name" label="物料名称" />
            <el-table-column prop="warehouse_name" label="仓库" width="150" />
            <el-table-column prop="qty_on_hand" label="当前库存" width="100" align="right">
              <template #default="{ row }">
                <span style="color: #F56C6C; font-weight: 600;">{{ row.qty_on_hand || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="安全库存" width="100" align="right">
              <template #default="{ row }">
                {{ row.min_stock || 10 }}
              </template>
            </el-table-column>
            <el-table-column label="缺口" width="100" align="right">
              <template #default="{ row }">
                <span style="color: #F56C6C;">
                  {{ (row.min_stock || 10) - (row.qty_on_hand || 0) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="预警级别" width="100">
              <template #default="{ row }">
                <el-tag :type="getAlertLevel(row)">
                  {{ getAlertLabel(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="handleCreatePR(row)">创建采购申请</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="超库存预警" name="high">
          <el-table :data="filteredAlerts" v-loading="loading" border stripe>
            <el-table-column prop="item_sku" label="物料编码" width="150" />
            <el-table-column prop="item_name" label="物料名称" />
            <el-table-column prop="warehouse_name" label="仓库" width="150" />
            <el-table-column prop="qty_on_hand" label="当前库存" width="100" align="right">
              <template #default="{ row }">
                <span style="color: #E6A23C; font-weight: 600;">{{ row.qty_on_hand || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="最大库存" width="100" align="right">
              <template #default="{ row }">
                {{ row.max_stock || 1000 }}
              </template>
            </el-table-column>
            <el-table-column label="超出" width="100" align="right">
              <template #default="{ row }">
                <span style="color: #E6A23C;">
                  {{ (row.qty_on_hand || 0) - (row.max_stock || 1000) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="建议" width="150">
              <template #default="{ row }">
                <el-tag type="info">建议促销</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-card style="margin-top: 20px;">
      <template #header><span>库存统计</span></template>
      <el-row :gutter="20">
        <el-col :span="8">
          <el-statistic title="低库存物料数" :value="stats.low_stock_count" suffix="种">
            <template #prefix><el-icon style="color: #F56C6C;"><Warning /></el-icon></template>
          </el-statistic>
        </el-col>
        <el-col :span="8">
          <el-statistic title="超库存物料数" :value="stats.high_stock_count" suffix="种">
            <template #prefix><el-icon style="color: #E6A23C;"><InfoFilled /></el-icon></template>
          </el-statistic>
        </el-col>
        <el-col :span="8">
          <el-statistic title="正常库存物料数" :value="stats.normal_stock_count" suffix="种">
            <template #prefix><el-icon style="color: #67C23A;"><SuccessFilled /></el-icon></template>
          </el-statistic>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Warning, InfoFilled, SuccessFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'

const router = useRouter()
const loading = ref(false)
const allStocks = ref([])
const activeTab = ref('low')
const stats = reactive({ low_stock_count: 0, high_stock_count: 0, normal_stock_count: 0 })

// 低库存阈值 (默认10)
const LOW_STOCK_THRESHOLD = 10
// 高库存阈值 (默认1000)
const HIGH_STOCK_THRESHOLD = 1000

const filteredAlerts = computed(() => {
  if (activeTab.value === 'low') {
    return allStocks.value.filter(s => (s.qty_on_hand || 0) < LOW_STOCK_THRESHOLD)
  } else {
    return allStocks.value.filter(s => (s.qty_on_hand || 0) > HIGH_STOCK_THRESHOLD)
  }
})

const getAlertLevel = (row) => {
  const qty = row.qty_on_hand || 0
  const minStock = row.min_stock || LOW_STOCK_THRESHOLD
  const ratio = qty / minStock
  if (ratio < 0.3) return 'danger'
  if (ratio < 0.6) return 'warning'
  return 'info'
}

const getAlertLabel = (row) => {
  const qty = row.qty_on_hand || 0
  const minStock = row.min_stock || LOW_STOCK_THRESHOLD
  const ratio = qty / minStock
  if (ratio < 0.3) return '严重'
  if (ratio < 0.6) return '警告'
  return '注意'
}

const loadStocks = async () => {
  loading.value = true
  try {
    const response = await request.get('/inventory/stocks/', { params: { page_size: 1000 } })
    allStocks.value = response.results || response || [] || []
    calculateStats()
  } catch (error) {
    console.error('加载库存失败:', error)
    allStocks.value = []
    // 不显示错误消息，因为可能只是没有库存数据
  } finally {
    loading.value = false
  }
}

const calculateStats = () => {
  const stocks = allStocks.value
  stats.low_stock_count = stocks.filter(s => (s.qty_on_hand || 0) < LOW_STOCK_THRESHOLD).length
  stats.high_stock_count = stocks.filter(s => (s.qty_on_hand || 0) > HIGH_STOCK_THRESHOLD).length
  stats.normal_stock_count = stocks.filter(s => {
    const qty = s.qty_on_hand || 0
    return qty >= LOW_STOCK_THRESHOLD && qty <= HIGH_STOCK_THRESHOLD
  }).length
}

const handleCreatePR = (row) => {
  const deficit = (row.min_stock || LOW_STOCK_THRESHOLD) - (row.qty_on_hand || 0)
  router.push(`/purchase/requests?item=${row.item}&qty=${deficit}`)
}

onMounted(() => {
  loadStocks()
})
</script>

<style scoped>
.stock-alert { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
