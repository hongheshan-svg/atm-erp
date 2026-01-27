<template>
  <div class="scheduling-scenario-detail">
    <el-page-header @back="goBack" :content="pageTitle" />
    
    <el-card class="detail-card" v-loading="loading">
      <template #header><span>方案信息</span></template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="方案编号">{{ scenario.scenario_code }}</el-descriptions-item>
        <el-descriptions-item label="方案名称">{{ scenario.name }}</el-descriptions-item>
        <el-descriptions-item label="优化目标">{{ scenario.objective_display }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag>{{ scenario.status_display }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ scenario.created_at }}</el-descriptions-item>
        <el-descriptions-item label="创建人">{{ scenario.created_by_name }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
    
    <el-card class="result-card" v-if="scenario.result">
      <template #header><span>排产结果</span></template>
      <el-table :data="scenario.result?.tasks || []" stripe>
        <el-table-column prop="order_no" label="生产订单" width="150" />
        <el-table-column prop="product_name" label="产品" />
        <el-table-column prop="work_center_name" label="工作中心" width="150" />
        <el-table-column prop="planned_start" label="计划开始" width="180" />
        <el-table-column prop="planned_end" label="计划结束" width="180" />
        <el-table-column prop="quantity" label="数量" width="80" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const scenario = ref({})

const pageTitle = computed(() => scenario.value.name ? `排产方案 - ${scenario.value.name}` : '排产方案详情')

const loadData = async () => {
  loading.value = true
  try {
    const res = await request.get(`/production/scheduling-scenarios/${route.params.id}/`)
    scenario.value = res.data || res
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const goBack = () => router.push({ name: 'SmartScheduling' })

onMounted(() => loadData())
</script>

<style scoped>
.scheduling-scenario-detail { padding: 20px; }
.el-page-header { margin-bottom: 20px; }
.detail-card, .result-card { margin-bottom: 20px; }
</style>
