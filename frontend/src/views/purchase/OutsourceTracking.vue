<template>
  <div class="outsource-tracking">
    <el-card>
      <template #header><span>外协加工跟踪</span></template>
      
      <el-row :gutter="20" class="stats-row">
        <el-col :span="6">
          <el-statistic title="进行中" :value="stats.in_progress" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="待检验" :value="stats.pending_inspection" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="本月完成" :value="stats.completed_this_month" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="延期订单" :value="stats.delayed" />
        </el-col>
      </el-row>
      
      <el-divider />
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="order_no" label="外协单号" width="150" />
        <el-table-column prop="progress_date" label="进度日期" width="120" />
        <el-table-column prop="progress_type_display" label="进度类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.progress_type)">{{ row.progress_type_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="completed_qty" label="完成数量" width="100" align="right" />
        <el-table-column prop="completion_rate" label="完成率" width="160">
          <template #default="{ row }">
            <el-progress :percentage="Number(row.completion_rate) || 0" :status="Number(row.completion_rate) >= 100 ? 'success' : ''" />
          </template>
        </el-table-column>
        <el-table-column prop="description" label="进度说明" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleProgress(row)">更新进度</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>

    <el-dialog v-model="progressDialogVisible" title="更新进度" width="500px">
      <el-form :model="progressForm" label-width="100px">
        <el-form-item label="外协单号">
          <el-input :model-value="currentRow?.order_no" disabled />
        </el-form-item>
        <el-form-item label="完成率(%)">
          <el-slider v-model="progressForm.completion_rate" :min="0" :max="100" show-input />
        </el-form-item>
        <el-form-item label="进度类型">
          <el-select v-model="progressForm.progress_type" style="width: 100%">
            <el-option label="已发料" value="MATERIAL_SENT" />
            <el-option label="生产进度" value="PRODUCTION" />
            <el-option label="质检" value="QUALITY" />
            <el-option label="发货" value="SHIPPING" />
            <el-option label="已收货" value="RECEIVED" />
          </el-select>
        </el-form-item>
        <el-form-item label="进度说明">
          <el-input v-model="progressForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="progressDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveProgress">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getOutsourceProgress, getOutsourceProgressStatistics, updateOutsourceProgress } from '@/api/purchase'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/purchase/outsource-progress/', { onSuccess: () => loadData() })


const loading = ref(false)
const saving = ref(false)
const tableData = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const stats = ref({ in_progress: 0, pending_inspection: 0, completed_this_month: 0, delayed: 0 })
const progressDialogVisible = ref(false)
const currentRow = ref(null)
const progressForm = reactive({ completion_rate: 0, progress_type: '', description: '' })

const getStatusType = (s) => ({ 'MATERIAL_SENT': 'info', 'PRODUCTION': 'primary', 'QUALITY': 'warning', 'SHIPPING': 'primary', 'RECEIVED': 'success' }[s] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await getOutsourceProgress({ page: page.value, page_size: pageSize.value })
    tableData.value = res.results || res.results || []
    total.value = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const res = await getOutsourceProgressStatistics()
    stats.value = res || stats.value
  } catch (error) {
    console.error('OutsourceTracking getOutsourceProgressStatistics error:', error)
  }
}

const handleProgress = (row) => {
  currentRow.value = row
  progressForm.completion_rate = Number(row.completion_rate) || 0
  progressForm.progress_type = row.progress_type || 'PRODUCTION'
  progressForm.description = row.description || ''
  progressDialogVisible.value = true
}

const saveProgress = async () => {
  try {
    saving.value = true
    await updateOutsourceProgress(currentRow.value.id, progressForm)
    ElMessage.success('进度更新成功')
    progressDialogVisible.value = false
    loadData()
    loadStats()
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => { loadData(); loadStats() })
</script>

<style scoped>
.stats-row { margin-bottom: 20px; }
.el-pagination { margin-top: 20px; }
</style>
