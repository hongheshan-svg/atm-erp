<template>
  <div class="delivery-collaboration-list">
    <el-card>
      <template #header><span>送货协作</span></template>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="collaboration_no" label="协作编号" width="150" />
        <el-table-column prop="purchase_order_no" label="采购订单" width="150" />
        <el-table-column prop="supplier_name" label="供应商" width="150" />
        <el-table-column prop="planned_delivery_date" label="计划送货日" width="120" />
        <el-table-column prop="actual_delivery_date" label="实际送货日" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
            <el-button v-if="row.status === 'PENDING'" link type="success" @click="handleConfirm(row)">确认</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const tableData = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const getStatusType = (s) => ({ 'PENDING': 'warning', 'CONFIRMED': 'primary', 'DELIVERED': 'success', 'REJECTED': 'danger' }[s] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get('/purchase/delivery-collaborations/', { params: { page: page.value, page_size: pageSize.value } })
    tableData.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleView = () => ElMessage.info('功能开发中')
const handleConfirm = () => ElMessage.info('功能开发中')

onMounted(() => loadData())
</script>

<style scoped>
.el-pagination { margin-top: 20px; }
</style>
