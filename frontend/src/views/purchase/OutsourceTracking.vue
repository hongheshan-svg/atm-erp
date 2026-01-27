<template>
  <div class="outsource-tracking">
    <el-card>
      <template #header><span>外协加工跟踪</span></template>
      
      <el-row :gutter="20" class="stats-row">
        <el-col :span="6">
          <el-statistic title="进行中" :value="stats.in_progress" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="待检验" :value="stats.pending_inspection" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="本月完成" :value="stats.completed_this_month" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="延期订单" :value="stats.delayed" />
        </el-col>
      </el-row>
      
      <el-divider />
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="order_no" label="外协单号" width="150" />
        <el-table-column prop="supplier_name" label="供应商" width="150" />
        <el-table-column prop="process_name" label="加工工序" />
        <el-table-column prop="quantity" label="数量" width="80" align="right" />
        <el-table-column prop="delivery_date" label="交期" width="120" />
        <el-table-column prop="progress" label="进度" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.progress || 0" :status="row.progress >= 100 ? 'success' : ''" />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleProgress(row)">更新进度</el-button>
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
const stats = ref({ in_progress: 0, pending_inspection: 0, completed_this_month: 0, delayed: 0 })

const getStatusType = (s) => ({ 'PENDING': 'info', 'IN_PROGRESS': 'primary', 'COMPLETED': 'success', 'DELAYED': 'danger' }[s] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get('/purchase/outsource-progress/', { params: { page: page.value, page_size: pageSize.value } })
    tableData.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleProgress = () => ElMessage.info('功能开发中')

onMounted(() => loadData())
</script>

<style scoped>
.stats-row { margin-bottom: 20px; }
.el-pagination { margin-top: 20px; }
</style>
