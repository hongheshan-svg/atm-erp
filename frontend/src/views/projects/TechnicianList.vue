<template>
  <div class="technician-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>技术员管理</span>
          <el-button type="primary" @click="handleCreate">添加技术员</el-button>
        </div>
      </template>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="employee_no" label="工号" width="120" />
        <el-table-column prop="user_name" label="姓名" width="120" />
        <el-table-column prop="skill_level_display" label="技能等级" width="100" />
        <el-table-column prop="phone" label="联系电话" width="140" />
        <el-table-column prop="is_available" label="可用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_available ? 'success' : 'danger'">{{ row.is_available ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="skills_display" label="技能" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="handleSchedule(row)">排班</el-button>
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
    const res = await request.get('/projects/technicians/', { params: { page: page.value, page_size: pageSize.value } })
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
const handleSchedule = () => ElMessage.info('功能开发中')

onMounted(() => loadData())
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.el-pagination { margin-top: 20px; }
</style>
