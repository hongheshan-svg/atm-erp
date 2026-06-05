<template>
  <div class="stock-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>库存概览</span>
          <el-button type="primary" @click="handleAdjustment">库存调整</el-button>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="仓库">
          <el-select v-model="searchForm.warehouse" placeholder="选择仓库" clearable style="width: 180px;">
            <el-option v-for="wh in warehouses" :key="wh.id" :label="wh.name" :value="wh.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="物料">
          <el-input v-model="searchForm.item_name" placeholder="搜索物料" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadStock">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作 -->

      <div v-if="selectedRows.length > 0" class="batch-toolbar">

        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>


        <el-button v-if="isAdmin" type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>

      </div>

      <el-table :data="stocks" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="warehouse_name" label="仓库" />
        <el-table-column prop="item_name" label="物料" />
        <el-table-column prop="item_sku" label="物料编码" width="150" />
        <el-table-column prop="qty_on_hand" label="在库" width="100" align="right" />
        <el-table-column prop="qty_reserved" label="预留" width="100" align="right" />
        <el-table-column prop="qty_available" label="可用" width="100" align="right">
          <template #default="{ row }">
            <span :class="row.qty_available < 0 ? 'text-danger' : ''">
              {{ row.qty_available }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="weighted_avg_cost" label="单位成本" width="120" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.weighted_avg_cost || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewHistory(row)">历史</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 库存历史 -->
    <el-dialog v-model="historyVisible" :title="'库存历史 - ' + (historyItem?.item_name || '')" width="800px">
      <el-table :data="historyList" v-loading="historyLoading" max-height="400">
        <el-table-column prop="movement_no" label="单号" width="160" />
        <el-table-column prop="movement_type_display" label="类型" width="100" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="from_warehouse_name" label="来源仓库" />
        <el-table-column prop="to_warehouse_name" label="目标仓库" />
        <el-table-column prop="created_at" label="时间" width="160" />
        <el-table-column prop="remarks" label="备注" />
      </el-table>
      <template #footer>
        <el-button @click="historyVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getStocks, getStockMoves } from '@/api/inventory'
import { getWarehouseList } from '@/api/masterdata'
import { useBatchOperation } from '@/composables/useBatchOperation'
import { usePermission } from '@/composables/usePermission'

const { isAdmin } = usePermission()
const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/inventory/stocks/', { onSuccess: () => loadStock() })


const router = useRouter()
const loading = ref(false)
const historyVisible = ref(false)
const historyLoading = ref(false)
const historyList = ref<any[]>([])
const historyItem = ref(null)
const stocks = ref<any[]>([])
const warehouses = ref<any[]>([])

const searchForm = reactive({
  warehouse: null,
  item_name: ''
})

const loadStock = async () => {
  loading.value = true
  try {
    const params = { ...searchForm }
    const response = await getStocks(params)
    stocks.value = response.results || response || []
  } catch (error) {
    ElMessage.error('加载库存失败')
  } finally {
    loading.value = false
  }
}

const loadWarehouses = async () => {
  try {
    const response = await getWarehouseList()
    warehouses.value = response.results || response || []
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const handleAdjustment = () => {
  router.push('/inventory/adjustment')
}

const viewHistory = async (row) => {
  historyItem.value = row
  historyVisible.value = true
  historyLoading.value = true
  try {
    const res = await getStockMoves({ item: row.item, warehouse: row.warehouse, page_size: 50 })
    historyList.value = res.results || res.results || []
  } catch (error) {
    console.error(error)
    historyList.value = []
  } finally {
    historyLoading.value = false
  }
}

const resetSearch = () => {
  Object.assign(searchForm, { warehouse: null, item_name: '' })
  loadStock()
}

onMounted(() => {
  loadStock()
  loadWarehouses()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.text-danger {
  color: #f56c6c;
}
</style>
