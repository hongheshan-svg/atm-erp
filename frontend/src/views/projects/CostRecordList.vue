<template>
  <div class="cost-record-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>成本记录</span>
          <el-button type="primary" @click="handleCreate">新增记录</el-button>
        </div>
      </template>
      
      <el-form :inline="true" class="filter-form">
        <el-form-item label="项目">
          <el-select v-model="filters.project" placeholder="选择项目" clearable @change="loadData">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="成本类型">
          <el-select v-model="filters.cost_type" placeholder="全部" clearable @change="loadData">
            <el-option label="材料" value="MATERIAL" />
            <el-option label="人工" value="LABOR" />
            <el-option label="外协" value="OUTSOURCE" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
      </el-form>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="project_name" label="项目" width="150" />
        <el-table-column prop="cost_type_display" label="成本类型" width="100" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="amount" label="金额" width="120" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="cost_date" label="日期" width="120" />
        <el-table-column prop="is_verified" label="已核实" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_verified ? 'success' : 'warning'">{{ row.is_verified ? '是' : '否' }}</el-tag>
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
const projects = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filters = ref({ project: null, cost_type: null })

const formatMoney = (v) => v ? parseFloat(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'

const loadData = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value, ...filters.value }
    const res = await request.get('/projects/cost-records/', { params })
    tableData.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    const res = await request.get('/projects/projects/', { params: { page_size: 1000 } })
    projects.value = res.data?.results || res.results || []
  } catch (error) { console.error(error) }
}

const handleCreate = () => ElMessage.info('功能开发中')

onMounted(() => { loadProjects(); loadData() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filter-form { margin-bottom: 20px; }
.el-pagination { margin-top: 20px; }
</style>
