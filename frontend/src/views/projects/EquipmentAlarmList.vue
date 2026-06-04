<template>
  <div class="equipment-alarm-list">
    <el-card>
      <template #header><span>设备告警记录</span></template>
      
      <el-form :inline="true" class="filter-form">
        <el-form-item label="告警级别">
          <el-select v-model="filters.severity" clearable @change="loadData">
            <el-option label="紧急" value="CRITICAL" />
            <el-option label="警告" value="WARNING" />
            <el-option label="信息" value="INFO" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable @change="loadData">
            <el-option label="活动" value="ACTIVE" />
            <el-option label="已确认" value="ACKNOWLEDGED" />
            <el-option label="已解决" value="RESOLVED" />
          </el-select>
        </el-form-item>
      </el-form>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="equipment_name" label="设备" width="150" />
        <el-table-column prop="alarm_code" label="告警代码" width="120" />
        <el-table-column prop="message" label="告警信息" />
        <el-table-column prop="severity" label="级别" width="80">
          <template #default="{ row }">
            <el-tag :type="getSeverityType(row.severity)">{{ row.severity_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="triggered_at" label="触发时间" width="180" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'ACTIVE'" link type="primary" @click="handleAck(row)">确认</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getEquipmentAlarmList, acknowledgeEquipmentAlarm } from '@/api/projects/equipment-monitoring'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects/equipment-alarms/', { onSuccess: () => loadData() })


const loading = ref(false)
const tableData = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filters = ref({ severity: null, status: null })

const getSeverityType = (s) => ({ 'CRITICAL': 'danger', 'WARNING': 'warning', 'INFO': 'info' }[s] || 'info')
const getStatusType = (s) => ({ 'ACTIVE': 'danger', 'ACKNOWLEDGED': 'warning', 'RESOLVED': 'success' }[s] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value, ...filters.value }
    const res = await getEquipmentAlarmList(params)
    tableData.value = res.results || res.results || []
    total.value = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleAck = async (row) => {
  try {
    await acknowledgeEquipmentAlarm(row.id)
    ElMessage.success('已确认')
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.filter-form { margin-bottom: 20px; }
.el-pagination { margin-top: 20px; }
</style>
