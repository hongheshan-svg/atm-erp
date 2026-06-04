<template>
  <div class="rfq-collaboration-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>询价协作</span>
          <el-button type="primary" @click="handleCreate">发起询价</el-button>
        </div>
      </template>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="rfq_no" label="询价单号" width="150" />
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="items_count" label="物料数" width="80" align="right" />
        <el-table-column prop="suppliers_count" label="供应商数" width="100" align="right" />
        <el-table-column prop="response_count" label="已响应" width="80" align="right" />
        <el-table-column prop="deadline" label="截止日期" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">查看</el-button>
            <el-button v-if="row.response_count > 0" link type="success" @click="handleCompare(row)">比价</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>

    <!-- 查看详情 -->
    <el-dialog v-model="viewDialogVisible" title="询价详情" width="800px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="询价单号">{{ viewDetail.rfq_no }}</el-descriptions-item>
        <el-descriptions-item label="标题">{{ viewDetail.title }}</el-descriptions-item>
        <el-descriptions-item label="截止日期">{{ viewDetail.deadline }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(viewDetail.status)">{{ viewDetail.status_display || viewDetail.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ viewDetail.remarks || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template v-if="viewDetail.items && viewDetail.items.length">
        <h4 style="margin: 16px 0 8px">询价物料</h4>
        <el-table :data="viewDetail.items" stripe size="small">
          <el-table-column prop="material_name" label="物料名称" />
          <el-table-column prop="quantity" label="数量" width="100" align="right" />
          <el-table-column prop="unit" label="单位" width="80" />
          <el-table-column prop="required_date" label="需求日期" width="120" />
        </el-table>
      </template>
      <template v-if="viewDetail.responses && viewDetail.responses.length">
        <h4 style="margin: 16px 0 8px">供应商响应</h4>
        <el-table :data="viewDetail.responses" stripe size="small">
          <el-table-column prop="supplier_name" label="供应商" />
          <el-table-column prop="total_price" label="报价总额" width="120" align="right">
            <template #default="{ row }">¥ {{ row.total_price?.toLocaleString() }}</template>
          </el-table-column>
          <el-table-column prop="delivery_days" label="交期(天)" width="100" />
          <el-table-column prop="responded_at" label="响应时间" width="160" />
        </el-table>
      </template>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 发起询价 -->
    <el-dialog v-model="dialogVisible" title="发起询价" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="截止日期" prop="deadline">
          <el-date-picker v-model="form.deadline" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remarks" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 比价对话框 -->
    <el-dialog v-model="compareDialogVisible" title="供应商比价" width="900px">
      <el-table :data="compareData" stripe>
        <el-table-column prop="supplier_name" label="供应商" />
        <el-table-column prop="total_price" label="报价总额" align="right">
          <template #default="{ row }">¥ {{ row.total_price?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column prop="delivery_days" label="交期(天)" width="100" align="center" />
        <el-table-column prop="quality_rating" label="质量评级" width="100" align="center" />
        <el-table-column prop="remarks" label="备注" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="selectSupplier(row)">选定</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="compareDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
getRFQCollaborations, getRFQCollaboration, createRFQCollaboration,
  compareRFQCollaboration, selectRFQCollaborationSupplier
} from '@/api/purchase'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/purchase/rfq-collaborations/', { onSuccess: () => loadData() })


const loading = ref(false)
const saving = ref(false)
const tableData = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const compareDialogVisible = ref(false)
const formRef = ref(null)
const viewDetail = ref<Record<string, any>>({})
const compareData = ref<any[]>([])
const currentRFQId = ref(null)

const form = reactive({ title: '', deadline: '', remarks: '' })
const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  deadline: [{ required: true, message: '请选择截止日期', trigger: 'change' }]
}
const getStatusType = (s) => ({ 'DRAFT': 'info', 'OPEN': 'primary', 'CLOSED': 'success', 'CANCELLED': 'danger' }[s] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await getRFQCollaborations({ page: page.value, page_size: pageSize.value })
    tableData.value = res.results || res.results || []
    total.value = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  Object.assign(form, { title: '', deadline: '', remarks: '' })
  formRef.value?.resetFields()
  dialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const res = await getRFQCollaboration(row.id)
    viewDetail.value = res
    viewDialogVisible.value = true
  } catch (error) {
    console.error(error)
    viewDetail.value = row
    viewDialogVisible.value = true
  }
}

const handleCompare = async (row) => {
  try {
    const res = await compareRFQCollaboration(row.id)
    compareData.value = res.results || res.results || res || res || []
    currentRFQId.value = row.id
    compareDialogVisible.value = true
  } catch (error) {
    console.error(error)
    ElMessage.error('加载比价数据失败')
  }
}

const selectSupplier = async (row) => {
  try {
    await ElMessageBox.confirm(`确定选定 ${row.supplier_name} 吗？`, '确认')
    await selectRFQCollaborationSupplier(currentRFQId.value, { supplier_id: row.supplier_id || row.id })
    ElMessage.success('选定成功')
    compareDialogVisible.value = false
    loadData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('操作失败')
  }
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    await createRFQCollaboration(form)
    ElMessage.success('创建成功')
    dialogVisible.value = false
    loadData()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
  } finally {
    saving.value = false
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.el-pagination { margin-top: 20px; }
</style>
