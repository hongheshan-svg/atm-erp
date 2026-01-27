<template>
  <div class="equipment-lifecycle-report">
    <el-card>
      <template #header><span>设备生命周期报表</span></template>
      
      <el-form :inline="true" class="filter-form">
        <el-form-item label="设备类型">
          <el-select v-model="filters.equipment_type" clearable @change="loadData">
            <el-option label="组装线" value="ASSEMBLY_LINE" />
            <el-option label="检测设备" value="TESTING_EQUIPMENT" />
            <el-option label="加工设备" value="PROCESSING_EQUIPMENT" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
        </el-form-item>
      </el-form>
      
      <el-row :gutter="20" class="stats-row">
        <el-col :span="6"><el-statistic title="设备总数" :value="stats.total_equipment" /></el-col>
        <el-col :span="6"><el-statistic title="运行中" :value="stats.running" /></el-col>
        <el-col :span="6"><el-statistic title="维护中" :value="stats.in_maintenance" /></el-col>
        <el-col :span="6"><el-statistic title="已退役" :value="stats.retired" /></el-col>
      </el-row>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="equipment_no" label="设备编号" width="140" />
        <el-table-column prop="name" label="设备名称" />
        <el-table-column prop="customer_name" label="客户" width="150" />
        <el-table-column prop="delivery_date" label="交付日期" width="120" />
        <el-table-column prop="warranty_end_date" label="保修到期" width="120" />
        <el-table-column prop="total_maintenance_cost" label="维护成本" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.total_maintenance_cost) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }"><el-tag>{{ row.status_display }}</el-tag></template>
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
const filters = ref({ equipment_type: null })
const stats = ref({ total_equipment: 0, running: 0, in_maintenance: 0, retired: 0 })

const formatMoney = (v) => v ? parseFloat(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get('/reports/industry/equipment-lifecycle/', { params: filters.value })
    tableData.value = res.data?.equipment || res.equipment || []
    stats.value = res.data?.stats || res.stats || stats.value
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.filter-form { margin-bottom: 20px; }
.stats-row { margin-bottom: 20px; }
</style>
