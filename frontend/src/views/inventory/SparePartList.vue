<template>
  <div class="spare-part-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>备件管理</span>
          <el-button type="primary" @click="handleCreate">新增备件</el-button>
        </div>
      </template>
      
      <el-form :inline="true" class="filter-form">
        <el-form-item label="分类">
          <el-select v-model="filters.category" clearable @change="loadData">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键字">
          <el-input v-model="filters.search" placeholder="搜索备件" clearable @clear="loadData" @keyup.enter="loadData" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
        </el-form-item>
      </el-form>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="spare_part_no" label="备件编号" width="140" />
        <el-table-column prop="name" label="备件名称" />
        <el-table-column prop="category_name" label="分类" width="120" />
        <el-table-column prop="specification" label="规格" width="120" />
        <el-table-column prop="current_stock" label="当前库存" width="100" align="right" />
        <el-table-column prop="safety_stock" label="安全库存" width="100" align="right" />
        <el-table-column prop="unit_price" label="单价" width="100" align="right">
          <template #default="{ row }">¥ {{ row.unit_price }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="handleConsume(row)">消耗</el-button>
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
const categories = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filters = ref({ category: null, search: '' })

const loadData = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value, ...filters.value }
    const res = await request.get('/inventory/spare-parts/', { params })
    tableData.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadCategories = async () => {
  try {
    const res = await request.get('/inventory/spare-part-categories/')
    categories.value = res.data?.results || res.results || []
  } catch (error) { console.error(error) }
}

const handleCreate = () => ElMessage.info('功能开发中')
const handleEdit = () => ElMessage.info('功能开发中')
const handleConsume = () => ElMessage.info('功能开发中')

onMounted(() => { loadCategories(); loadData() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filter-form { margin-bottom: 20px; }
.el-pagination { margin-top: 20px; }
</style>
