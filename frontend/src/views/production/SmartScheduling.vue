<template>
  <div class="smart-scheduling">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>智能排产</span>
          <el-button type="primary" @click="handleNewScenario">新建排产方案</el-button>
        </div>
      </template>
      
      <el-row :gutter="20" class="stats-row">
        <el-col :span="6">
          <el-statistic title="待排产订单" :value="stats.pending_orders" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="产能利用率" :value="stats.capacity_utilization + '%'" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="本周计划产量" :value="stats.weekly_planned" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="延期风险订单" :value="stats.at_risk_orders" />
        </el-col>
      </el-row>
      
      <el-divider />
      
      <h4>排产方案列表</h4>
      <el-table :data="scenarios" v-loading="loading" stripe>
        <el-table-column prop="scenario_code" label="方案编号" width="150" />
        <el-table-column prop="name" label="方案名称" />
        <el-table-column prop="objective_display" label="优化目标" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
            <el-button v-if="row.status === 'DRAFT'" link type="success" @click="handleRun(row)">执行排产</el-button>
            <el-button v-if="row.status === 'COMPLETED'" link type="warning" @click="handleApply(row)">应用方案</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const router = useRouter()
const loading = ref(false)
const scenarios = ref([])
const stats = ref({ pending_orders: 0, capacity_utilization: 0, weekly_planned: 0, at_risk_orders: 0 })

const getStatusType = (s) => ({ 'DRAFT': 'info', 'RUNNING': 'warning', 'COMPLETED': 'success', 'APPLIED': 'primary' }[s] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get('/production/scheduling-scenarios/')
    scenarios.value = res.data?.results || res.results || []
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleNewScenario = () => ElMessage.info('功能开发中')
const handleView = (row) => router.push({ name: 'SchedulingScenarioDetail', params: { id: row.id } })
const handleRun = () => ElMessage.info('功能开发中')
const handleApply = () => ElMessage.info('功能开发中')

onMounted(() => loadData())
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.stats-row { margin-bottom: 20px; }
</style>
