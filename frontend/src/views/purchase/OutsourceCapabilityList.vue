<template>
  <div class="outsource-capability-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>外协加工能力</span>
          <el-button type="primary" @click="handleCreate">新增能力</el-button>
        </div>
      </template>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="supplier_name" label="供应商" width="150" />
        <el-table-column prop="process_type_display" label="加工类型" width="120" />
        <el-table-column prop="capability_description" label="能力描述" />
        <el-table-column prop="max_capacity" label="最大产能" width="100" />
        <el-table-column prop="lead_time_days" label="交期(天)" width="100" />
        <el-table-column prop="quality_rating" label="质量评级" width="100">
          <template #default="{ row }">
            <el-rate v-model="row.quality_rating" disabled />
          </template>
        </el-table-column>
        <el-table-column prop="is_preferred" label="首选" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_preferred" type="success">是</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
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

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get('/purchase/outsource-capabilities/', { params: { page: page.value, page_size: pageSize.value } })
    tableData.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => ElMessage.info('功能开发中')
const handleEdit = () => ElMessage.info('功能开发中')

onMounted(() => loadData())
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.el-pagination { margin-top: 20px; }
</style>
