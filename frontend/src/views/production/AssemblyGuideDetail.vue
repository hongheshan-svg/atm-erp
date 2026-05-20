<template>
  <div class="assembly-guide-detail">
    <el-page-header @back="goBack" :content="pageTitle" />
    
    <el-card class="detail-card" v-loading="loading">
      <template #header><span>指导信息</span></template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="编号">{{ guide.guide_code }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ guide.name }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ guide.version }}</el-descriptions-item>
        <el-descriptions-item label="产品">{{ guide.product_name }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag>{{ guide.status_display }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="创建人">{{ guide.created_by_name }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
    
    <el-card class="steps-card">
      <template #header><span>装配步骤</span></template>
      <el-timeline>
        <el-timeline-item v-for="step in guide.steps || []" :key="step.id" :timestamp="`步骤 ${step.sequence}`" placement="top">
          <el-card>
            <h4>{{ step.name }}</h4>
            <p>{{ step.instructions }}</p>
            <div v-if="step.model_url" class="model-viewer">
              <el-button type="primary" @click="viewModel(step)">查看3D模型</el-button>
            </div>
          </el-card>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- 3D模型查看 -->
    <el-dialog v-model="modelDialogVisible" title="3D模型查看" width="80%" top="5vh">
      <div style="height: 70vh; display: flex; align-items: center; justify-content: center; background: #f5f5f5; border-radius: 8px;">
        <iframe v-if="guide?.model_url" :src="guide.model_url" style="width: 100%; height: 100%; border: none;" />
        <el-empty v-else description="暂无3D模型" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAssemblyGuide } from '@/api/production'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const guide = ref({})

const pageTitle = computed(() => guide.value.name ? `装配指导 - ${guide.value.name}` : '装配指导详情')

const loadData = async () => {
  loading.value = true
  try {
    const res = await getAssemblyGuide(route.params.id)
    guide.value = res.data || res
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const goBack = () => router.push({ name: 'AssemblyGuideList' })
const modelDialogVisible = ref(false)
const viewModel = () => {
  if (guide.value?.model_url) {
    modelDialogVisible.value = true
  } else {
    ElMessage.warning('该指导未关联3D模型文件')
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.assembly-guide-detail { padding: 20px; }
.el-page-header { margin-bottom: 20px; }
.detail-card, .steps-card { margin-bottom: 20px; }
.model-viewer { margin-top: 10px; }
</style>
