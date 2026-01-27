<template>
  <div class="rfq-collaboration-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>询价协作</span>
          <el-button type="primary" @click="handleCreate">发起询价</el-button>
        </div>
      </template>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="rfq_no" label="询价单号" width="150" />
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="items_count" label="物料数" width="80" align="right" />
        <el-table-column prop="suppliers_count" label="供应商数" width="100" align="right" />
        <el-table-column prop="response_count" label="已响应" width="80" align="right" />
        <el-table-column prop="deadline" label="截止日期" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
            <el-button v-if="row.status === 'OPEN'" link type="success" @click="handleCompare(row)">比价</el-button>
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

const getStatusType = (s) => ({ 'DRAFT': 'info', 'OPEN': 'primary', 'CLOSED': 'success', 'CANCELLED': 'danger' }[s] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get('/purchase/rfq-collaborations/', { params: { page: page.value, page_size: pageSize.value } })
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
const handleCompare = () => ElMessage.info('功能开发中')

onMounted(() => loadData())
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.el-pagination { margin-top: 20px; }
</style>
