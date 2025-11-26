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
          <el-select v-model="searchForm.warehouse" placeholder="选择仓库" clearable>
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

      <el-table :data="stocks" v-loading="loading" stripe border>
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
        <el-table-column prop="unit_cost" label="单位成本" width="120" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.weighted_avg_cost || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewHistory(row)">历史</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const router = useRouter()
const loading = ref(false)
const stocks = ref([])
const warehouses = ref([])

const searchForm = reactive({
  warehouse: null,
  item_name: ''
})

const loadStock = async () => {
  loading.value = true
  try {
    const params = { ...searchForm }
    const response = await request.get('/inventory/stocks/', { params })
    stocks.value = response.results || response || []
  } catch (error) {
    ElMessage.error('加载库存失败')
  } finally {
    loading.value = false
  }
}

const loadWarehouses = async () => {
  try {
    const response = await request.get('/masterdata/warehouses/')
    warehouses.value = response.results || response || []
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const handleAdjustment = () => {
  router.push('/inventory/adjustment')
}

const viewHistory = (row) => {
  ElMessage.info(`查看 ${row.item_name} 的库存历史`)
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
