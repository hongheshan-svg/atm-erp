<template>
  <div class="training-plan-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>培训计划管理</span>
          <el-button type="primary" @click="handleCreate">新建培训计划</el-button>
        </div>
      </template>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="plan_no" label="计划编号" width="150" />
        <el-table-column prop="name" label="计划名称" />
        <el-table-column prop="customer_name" label="客户" width="150" />
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
            <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadData"
      />
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

const getStatusType = (status) => {
  const types = { 'DRAFT': 'info', 'PLANNED': 'warning', 'IN_PROGRESS': 'primary', 'COMPLETED': 'success' }
  return types[status] || 'info'
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get('/sales/training-plans/', { params: { page: page.value, page_size: pageSize.value } })
    tableData.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => ElMessage.info('功能开发中')
const handleView = () => ElMessage.info('功能开发中')
const handleEdit = () => ElMessage.info('功能开发中')

onMounted(() => loadData())
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.el-pagination { margin-top: 20px; }
</style>
