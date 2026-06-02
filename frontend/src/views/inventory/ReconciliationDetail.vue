<template>
  <div class="reconciliation-detail">
    <el-page-header @back="goBack" :content="pageTitle" />
    
    <el-card class="detail-card" v-loading="loading">
      <template #header><span>对账信息</span></template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="对账编号">{{ session.session_no }}</el-descriptions-item>
        <el-descriptions-item label="对账类型">{{ session.reconciliation_type_display }}</el-descriptions-item>
        <el-descriptions-item label="仓库">{{ session.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="开始日期">{{ session.start_date }}</el-descriptions-item>
        <el-descriptions-item label="结束日期">{{ session.end_date }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag>{{ session.status_display }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="总项目数">{{ session.total_items }}</el-descriptions-item>
        <el-descriptions-item label="差异项目数">{{ session.variance_items }}</el-descriptions-item>
        <el-descriptions-item label="差异金额">¥ {{ formatMoney(session.variance_amount) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
    
    <el-card class="items-card">
      <template #header><span>对账明细</span></template>
      <el-table :data="session.items || []" stripe>
        <el-table-column prop="item_name" label="物料" />
        <el-table-column prop="opening_qty" label="期初数量" align="right" />
        <el-table-column prop="in_qty" label="入库数量" align="right" />
        <el-table-column prop="out_qty" label="出库数量" align="right" />
        <el-table-column prop="calculated_closing_qty" label="计算期末" align="right" />
        <el-table-column prop="actual_closing_qty" label="实际期末" align="right" />
        <el-table-column prop="variance_qty" label="差异数量" align="right">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.variance_qty !== 0 }">{{ row.variance_qty }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getReconciliationSession } from '@/api/inventory'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const session = ref<Record<string, any>>({})

const pageTitle = computed(() => session.value.session_no ? `对账详情 - ${session.value.session_no}` : '对账详情')
const formatMoney = (v) => v ? parseFloat(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'

const loadData = async () => {
  loading.value = true
  try {
    const res = await getReconciliationSession(route.params.id)
    session.value = res
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const goBack = () => router.push({ name: 'DataAccuracy' })

onMounted(() => loadData())
</script>

<style scoped>
.reconciliation-detail { padding: 20px; }
.el-page-header { margin-bottom: 20px; }
.detail-card, .items-card { margin-bottom: 20px; }
.text-danger { color: #f56c6c; }
</style>
