<template>
  <div class="diagnostic-session-list">
    <el-card>
      <template #header><span>远程诊断会话</span></template>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="session_no" label="会话编号" width="150" />
        <el-table-column prop="equipment_name" label="设备" width="150" />
        <el-table-column prop="reason_display" label="诊断原因" width="120" />
        <el-table-column prop="technician_name" label="技术员" width="120" />
        <el-table-column prop="started_at" label="开始时间" width="180" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="findings" label="诊断结果" show-overflow-tooltip />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
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

const getStatusType = (s) => ({ 'IN_PROGRESS': 'primary', 'COMPLETED': 'success', 'PENDING': 'warning' }[s] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get('/projects/diagnostic-sessions/', { params: { page: page.value, page_size: pageSize.value } })
    tableData.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleView = () => ElMessage.info('功能开发中')

onMounted(() => loadData())
</script>

<style scoped>
.el-pagination { margin-top: 20px; }
</style>
