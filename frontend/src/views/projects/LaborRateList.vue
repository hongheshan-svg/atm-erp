<template>
  <div class="labor-rate-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>工时费率标准</span>
          <el-button type="primary" @click="handleCreate">新增费率</el-button>
        </div>
      </template>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="work_type_display" label="工种" width="150" />
        <el-table-column prop="standard_rate" label="标准费率" align="right">
          <template #default="{ row }">¥ {{ row.standard_rate }}/小时</template>
        </el-table-column>
        <el-table-column prop="overtime_rate" label="加班费率" align="right">
          <template #default="{ row }">¥ {{ row.overtime_rate }}/小时</template>
        </el-table-column>
        <el-table-column prop="weekend_rate" label="周末费率" align="right">
          <template #default="{ row }">¥ {{ row.weekend_rate }}/小时</template>
        </el-table-column>
        <el-table-column prop="holiday_rate" label="节假日费率" align="right">
          <template #default="{ row }">¥ {{ row.holiday_rate }}/小时</template>
        </el-table-column>
        <el-table-column prop="effective_from" label="生效日期" width="120" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const tableData = ref([])

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get('/projects/labor-rates/')
    tableData.value = res.data?.results || res.results || res.data || []
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
</style>
