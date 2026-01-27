<template>
  <div class="spare-part-alert-list">
    <el-card>
      <template #header><span>备件库存预警</span></template>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="spare_part_name" label="备件名称" />
        <el-table-column prop="alert_type" label="预警类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getAlertType(row.alert_type)">{{ row.alert_type_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_stock" label="当前库存" width="100" align="right" />
        <el-table-column prop="threshold" label="阈值" width="100" align="right" />
        <el-table-column prop="triggered_at" label="触发时间" width="180" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_resolved ? 'success' : 'danger'">{{ row.is_resolved ? '已解决' : '未解决' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.is_resolved" link type="primary" @click="handleResolve(row)">处理</el-button>
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

const getAlertType = (t) => ({ 'LOW_STOCK': 'warning', 'OUT_OF_STOCK': 'danger', 'EXPIRING': 'info' }[t] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get('/inventory/spare-part-alerts/', { params: { page: page.value, page_size: pageSize.value } })
    tableData.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleResolve = async (row) => {
  try {
    await request.post(`/inventory/spare-part-alerts/${row.id}/resolve/`)
    ElMessage.success('已处理')
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.el-pagination { margin-top: 20px; }
</style>
