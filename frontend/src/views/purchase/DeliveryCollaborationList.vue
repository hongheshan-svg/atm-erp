<template>
  <div class="delivery-collaboration-list">
    <el-card>
      <template #header><span>送货协作</span></template>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="collaboration_no" label="协作编号" width="150" />
        <el-table-column prop="purchase_order_no" label="采购订单" width="150" />
        <el-table-column prop="supplier_name" label="供应商" width="150" />
        <el-table-column prop="planned_delivery_date" label="计划送货日" width="120" />
        <el-table-column prop="actual_delivery_date" label="实际送货日" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
            <el-button v-if="row.status === 'PENDING'" link type="success" @click="handleConfirm(row)">确认</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>

    <!-- 查看详情 -->
    <el-dialog v-model="viewDialogVisible" title="送货详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="协作编号">{{ viewDetail.collaboration_no }}</el-descriptions-item>
        <el-descriptions-item label="采购订单">{{ viewDetail.purchase_order_no }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ viewDetail.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(viewDetail.status)">{{ viewDetail.status_display || viewDetail.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="计划送货日">{{ viewDetail.planned_delivery_date }}</el-descriptions-item>
        <el-descriptions-item label="实际送货日">{{ viewDetail.actual_delivery_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ viewDetail.remarks || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template v-if="viewDetail.items && viewDetail.items.length">
        <h4 style="margin: 16px 0 8px">送货明细</h4>
        <el-table :data="viewDetail.items" stripe size="small">
          <el-table-column prop="material_name" label="物料" />
          <el-table-column prop="quantity" label="计划数量" width="100" align="right" />
          <el-table-column prop="actual_quantity" label="实收数量" width="100" align="right" />
        </el-table>
      </template>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 确认收货 -->
    <el-dialog v-model="confirmDialogVisible" title="确认收货" width="500px">
      <el-form :model="confirmForm" label-width="100px">
        <el-form-item label="实际送货日">
          <el-date-picker v-model="confirmForm.actual_delivery_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="confirmForm.remarks" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="confirmDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveConfirm">确认收货</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getDeliveryCollaborations, getDeliveryCollaboration, confirmDeliveryCollaboration } from '@/api/purchase'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/purchase/')


const loading = ref(false)
const saving = ref(false)
const tableData = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const viewDialogVisible = ref(false)
const confirmDialogVisible = ref(false)
const viewDetail = ref({})
const currentRow = ref(null)
const confirmForm = reactive({ actual_delivery_date: '', remarks: '' })

const getStatusType = (s) => ({ 'PENDING': 'warning', 'CONFIRMED': 'primary', 'DELIVERED': 'success', 'REJECTED': 'danger' }[s] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await getDeliveryCollaborations({ page: page.value, page_size: pageSize.value })
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
    const res = await getDeliveryCollaboration(row.id)
    viewDetail.value = res.data || res
    viewDialogVisible.value = true
  } catch (error) {
    console.error(error)
    viewDetail.value = row
    viewDialogVisible.value = true
  }
}

const handleConfirm = (row) => {
  currentRow.value = row
  confirmForm.actual_delivery_date = new Date().toISOString().split('T')[0]
  confirmForm.remarks = ''
  confirmDialogVisible.value = true
}

const saveConfirm = async () => {
  try {
    saving.value = true
    await confirmDeliveryCollaboration(currentRow.value.id, confirmForm)
    ElMessage.success('确认收货成功')
    confirmDialogVisible.value = false
    loadData()
  } catch (error) {
    ElMessage.error('确认失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.el-pagination { margin-top: 20px; }
</style>
