<template>
  <div class="service-order-detail">
    <el-page-header @back="goBack" :content="pageTitle" />
    
    <el-card class="detail-card" v-loading="loading">
      <template #header><span>工单信息</span></template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="工单编号">{{ order.order_no }}</el-descriptions-item>
        <el-descriptions-item label="服务类型">{{ order.service_type_display }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag>{{ order.status_display }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="客户">{{ order.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="联系人">{{ order.contact_name }}</el-descriptions-item>
        <el-descriptions-item label="联系电话">{{ order.contact_phone }}</el-descriptions-item>
        <el-descriptions-item label="服务地址" :span="3">{{ order.service_address }}</el-descriptions-item>
        <el-descriptions-item label="问题描述" :span="3">{{ order.description }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
    
    <el-card class="dispatch-card">
      <template #header><span>派工记录</span></template>
      <el-table :data="order.dispatches || []" stripe>
        <el-table-column prop="technician_name" label="技术员" />
        <el-table-column prop="planned_start" label="计划开始" />
        <el-table-column prop="planned_end" label="计划结束" />
        <el-table-column prop="status_display" label="状态" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getServiceOrder } from '@/api/projects/service-order'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const order = ref<Record<string, any>>({})

const pageTitle = computed(() => order.value.order_no ? `服务工单 - ${order.value.order_no}` : '服务工单详情')

const loadData = async () => {
  loading.value = true
  try {
    const res = await getServiceOrder(route.params.id)
    order.value = res
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const goBack = () => router.push({ name: 'ServiceOrderList' })

onMounted(() => loadData())
</script>

<style scoped>
.service-order-detail { padding: 20px; }
.el-page-header { margin-bottom: 20px; }
.detail-card, .dispatch-card { margin-bottom: 20px; }
</style>
