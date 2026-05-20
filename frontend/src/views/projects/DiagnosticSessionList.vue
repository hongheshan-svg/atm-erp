<template>
  <div class="diagnostic-session-list">
    <el-card>
      <template #header><span>远程诊断会话</span></template>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="session_no" label="会话编号" width="150" />
        <el-table-column prop="equipment_name" label="设备" width="150" />
        <el-table-column prop="reason_display" label="诊断原因" width="120" />
        <el-table-column prop="technician_name" label="技术员" width="120" />
        <el-table-column prop="started_at" label="开始时间" width="180" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="findings" label="诊断结果" show-overflow-tooltip />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>

    <el-dialog v-model="viewDialogVisible" title="诊断会话详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="会话编号">{{ viewDetail.session_no }}</el-descriptions-item>
        <el-descriptions-item label="设备">{{ viewDetail.equipment_name }}</el-descriptions-item>
        <el-descriptions-item label="诊断原因">{{ viewDetail.reason_display || viewDetail.reason }}</el-descriptions-item>
        <el-descriptions-item label="技术员">{{ viewDetail.technician_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(viewDetail.status)">{{ viewDetail.status_display || viewDetail.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ viewDetail.started_at }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ viewDetail.ended_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="持续时间">{{ viewDetail.duration || '-' }}</el-descriptions-item>
        <el-descriptions-item label="诊断结果" :span="2">{{ viewDetail.findings || '-' }}</el-descriptions-item>
        <el-descriptions-item label="建议措施" :span="2">{{ viewDetail.recommendations || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getDiagnosticSessionList, getDiagnosticSession } from '@/api/projects/diagnostic'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects_diagnostic/')


const loading = ref(false)
const tableData = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const viewDialogVisible = ref(false)
const viewDetail = ref({})

const getStatusType = (s) => ({ 'IN_PROGRESS': 'primary', 'COMPLETED': 'success', 'PENDING': 'warning' }[s] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await getDiagnosticSessionList({ page: page.value, page_size: pageSize.value })
    tableData.value = res.data?.results || res.results || []
    total.value = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleView = async (row) => {
  try {
    const res = await getDiagnosticSession(row.id)
    viewDetail.value = res.data || res
    viewDialogVisible.value = true
  } catch (error) {
    console.error(error)
    viewDetail.value = row
    viewDialogVisible.value = true
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.el-pagination { margin-top: 20px; }
</style>
