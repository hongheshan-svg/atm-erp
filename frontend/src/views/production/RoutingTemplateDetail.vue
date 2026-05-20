<template>
  <div class="routing-template-detail">
    <el-page-header @back="goBack" :content="pageTitle" />
    
    <el-card class="detail-card" v-loading="loading">
      <template #header><span>模板信息</span></template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="模板编号">{{ template.template_code }}</el-descriptions-item>
        <el-descriptions-item label="模板名称">{{ template.name }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ template.version }}</el-descriptions-item>
        <el-descriptions-item label="产品类别">{{ template.product_category_name }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag>{{ template.status_display }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="标准工时">{{ template.total_standard_hours }} 小时</el-descriptions-item>
        <el-descriptions-item label="描述" :span="3">{{ template.description }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
    
    <el-card class="operations-card">
      <template #header><span>工序列表</span></template>
      <el-table :data="template.operations || []" stripe>
        <el-table-column prop="sequence" label="序号" width="80" />
        <el-table-column prop="operation_code" label="工序编号" width="120" />
        <el-table-column prop="name" label="工序名称" />
        <el-table-column prop="work_center_name" label="工作中心" width="150" />
        <el-table-column prop="standard_hours" label="标准工时" width="100" />
        <el-table-column prop="setup_hours" label="准备工时" width="100" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getRoutingTemplate } from '@/api/production'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const template = ref({})

const pageTitle = computed(() => template.value.name ? `工艺模板 - ${template.value.name}` : '工艺模板详情')

const loadData = async () => {
  loading.value = true
  try {
    const res = await getRoutingTemplate(route.params.id)
    template.value = res.data || res
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const goBack = () => router.push({ name: 'RoutingTemplateList' })

onMounted(() => loadData())
</script>

<style scoped>
.routing-template-detail { padding: 20px; }
.el-page-header { margin-bottom: 20px; }
.detail-card, .operations-card { margin-bottom: 20px; }
</style>
