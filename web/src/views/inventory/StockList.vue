<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import { useStocksQuery } from '@/api/inventory'
import type { Stock, StockListQuery } from '@/types'

// ===== 查询条件与分页(库存为只读聚合视图)=====
const warehouseIdFilter = ref<number | undefined>(0)
const itemIdFilter = ref<number | undefined>(0)
const lowStockFilter = ref(false)
const page = ref(1)
const pageSize = ref(20)

const submittedQuery = reactive<StockListQuery>({})

const query = computed<StockListQuery>(() => ({
  warehouse_id: submittedQuery.warehouse_id,
  item_id: submittedQuery.item_id,
  low_stock: submittedQuery.low_stock,
  page: page.value,
  page_size: pageSize.value
}))

const { data, isFetching } = useStocksQuery(query)

const rows = computed<Stock[]>(() => data.value?.results ?? [])
const total = computed(() => data.value?.count ?? 0)

function handleSearch() {
  submittedQuery.warehouse_id = warehouseIdFilter.value || undefined
  submittedQuery.item_id = itemIdFilter.value || undefined
  submittedQuery.low_stock = lowStockFilter.value || undefined
  page.value = 1
}

function handleReset() {
  warehouseIdFilter.value = 0
  itemIdFilter.value = 0
  lowStockFilter.value = false
  handleSearch()
}

function handlePageChange(val: number) {
  page.value = val
}

function handleSizeChange(val: number) {
  pageSize.value = val
  page.value = 1
}
</script>

<template>
  <div>
    <PageHeader title="库存查询" subtitle="inventory / stocks(只读)" />

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="仓库 ID">
        <el-input-number v-model="warehouseIdFilter" :min="0" />
      </el-form-item>
      <el-form-item label="物料 ID">
        <el-input-number v-model="itemIdFilter" :min="0" />
      </el-form-item>
      <el-form-item label="低库存">
        <el-switch v-model="lowStockFilter" />
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="rows" border stripe>
      <el-table-column prop="warehouse_id" label="仓库 ID" width="120" />
      <el-table-column prop="item_id" label="物料 ID" width="120" />
      <el-table-column prop="qty_on_hand" label="账面数量" width="140" align="right" />
      <el-table-column prop="qty_reserved" label="预留数量" width="140" align="right" />
      <el-table-column prop="qty_available" label="可用数量" width="140" align="right" />
      <el-table-column prop="weighted_avg_cost" label="加权平均成本" min-width="140" align="right" />
    </el-table>

    <el-pagination
      class="pager"
      layout="total, prev, pager, next, sizes"
      :total="total"
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      @current-change="handlePageChange"
      @size-change="handleSizeChange"
    />
  </div>
</template>

<style scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
