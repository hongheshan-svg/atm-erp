<template>
  <div class="quotation-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>销售报价管理</span>
          <el-button type="primary" v-permission="'sales:quotation:create'" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新增报价
          </el-button>
        </div>
      </template>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="报价编号">
          <el-input v-model="searchForm.quote_no" placeholder="请输入报价编号" clearable />
        </el-form-item>
        <el-form-item label="客户">
          <el-select v-model="searchForm.customer" placeholder="请选择客户" clearable filterable>
            <el-option
              v-for="customer in customers"
              :key="customer.id"
              :label="customer.name"
              :value="customer.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择状态" clearable>
            <el-option label="草稿" value="DRAFT" />
            <el-option label="审批中" value="PENDING" />
            <el-option label="已审批" value="APPROVED" />
            <el-option label="已发送" value="SENT" />
            <el-option label="已接受" value="ACCEPTED" />
            <el-option label="已拒绝" value="REJECTED" />
            <el-option label="已过期" value="EXPIRED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadQuotations">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-permission="'sales:quotation:delete'" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button 
          type="danger" 
          size="small" 
          @click="batchDelete"
          :loading="deleteLoading"
        >
          批量删除
        </el-button>
      </div>

      <!-- 报价列表 -->
      <el-table :data="quotations" v-loading="loading" border stripe @selection-change="handleSelectionChange">
        <el-table-column v-permission="'sales:quotation:delete'" v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="quote_no" label="报价编号" width="150" />
        <el-table-column prop="customer_name" label="客户" width="200" />
        <el-table-column prop="project_name" label="关联项目" width="150" show-overflow-tooltip />
        <el-table-column prop="quote_date" label="报价日期" width="120" />
        <el-table-column prop="valid_until" label="有效期至" width="120" />
        <el-table-column prop="tax_rate" label="税率" width="80" align="center">
          <template #default="{ row }">
            {{ row.tax_rate ?? 13 }}%
          </template>
        </el-table-column>
        <el-table-column prop="total_with_tax" label="含税总额" width="130" align="right">
          <template #default="{ row }">
            ¥{{ formatMoney(row.total_with_tax || row.total_amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="80" align="center">
          <template #default="{ row }">
            <el-tag type="info" size="small">V{{ row.version || 1 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="创建人" width="100" />
        <el-table-column label="操作" :width="canDelete ? 460 : 400" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" v-permission="'sales:quotation:edit'" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="warning" @click="handleSubmitApproval(row)" v-if="row.status === 'DRAFT' || row.status === 'REJECTED'">提交审批</el-button>
            <el-button size="small" type="info" @click="showWorkflowProgress(row)" v-if="row.status === 'PENDING'">审批进度</el-button>
            <el-button size="small" type="success" v-permission="'sales:quotation:create'" @click="handleCreateVersion(row)">
              新版本
            </el-button>
            <el-button
              size="small"
              type="primary"
              @click="handleConvertToOrder(row)"
              v-if="row.status === 'ACCEPTED'"
            >
              转销售订单
            </el-button>
            <!-- 仅管理员显示删除按钮 -->
            <el-button 
              v-if="canDelete"
              size="small" 
              type="danger" 
              @click="deleteRow(row)"
              :loading="deleteLoading"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadQuotations"
        @current-change="loadQuotations"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 报价详情对话框 -->
    <el-dialog
      v-model="detailVisible"
      :title="dialogTitle"
      width="80%"
      top="5vh"
    >
      <el-descriptions :column="3" border>
        <el-descriptions-item label="报价编号">{{ currentQuotation.quote_no }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ currentQuotation.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ currentQuotation.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="报价日期">{{ currentQuotation.quote_date }}</el-descriptions-item>
        <el-descriptions-item label="有效期至">{{ currentQuotation.valid_until }}</el-descriptions-item>
        <el-descriptions-item label="版本">V{{ currentQuotation.version }}</el-descriptions-item>
        <el-descriptions-item label="状态" :span="3">
          <el-tag :type="getStatusType(currentQuotation.status)">
            {{ getStatusLabel(currentQuotation.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">
          {{ currentQuotation.notes || '-' }}
        </el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">报价明细</el-divider>

      <el-table :data="currentQuotation.lines || []" border>
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="item_sku" label="物料编码" width="150" />
        <el-table-column prop="item_name" label="物料名称" />
        <el-table-column label="规格">
          <template #default="{ row }">
            {{ row.item_spec || row.custom_spec || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="qty" label="数量" width="100" align="right" />
        <el-table-column label="单位" width="80">
          <template #default="{ row }">
            {{ row.item_unit || row.custom_unit || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="unit_price" label="单价" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatMoney(row.unit_price) }}
          </template>
        </el-table-column>
        <el-table-column prop="line_amount" label="金额" width="130" align="right">
          <template #default="{ row }">
            ¥{{ formatMoney(row.line_amount || parseFloat(row.qty || 0) * parseFloat(row.unit_price || 0)) }}
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" show-overflow-tooltip />
      </el-table>

      <div style="margin-top: 20px; text-align: right;">
        <el-statistic title="报价总金额" :value="currentQuotation.total_amount || 0" prefix="¥" :precision="2" />
      </div>

      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="handlePrint">打印报价单</el-button>
      </template>
    </el-dialog>
  </div>

    <!-- 审批进度弹窗 -->
    <WorkflowProgress
      v-model="workflowDialogVisible"
      :business-type="workflowBusinessType"
      :business-id="workflowBusinessId"
    />
  </template>

<script setup>
import WorkflowProgress from '@/components/WorkflowProgress.vue'

import { ref, reactive, onMounted } from 'vue'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { getQuotations, getQuotation, submitQuotation, createQuotationVersion, convertQuotationToOrder } from '@/api/sales'
import { getCustomerList } from '@/api/masterdata'

const router = useRouter()


// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/sales/quotations/',
  {
    confirmTitle: '确认删除报价单',
    confirmMessage: '此操作将永久删除选中的报价单，是否继续？',
    successMessage: '删除成功',
    errorMessage: '删除失败',
    onSuccess: () => loadQuotations()
  }
)

const workflowDialogVisible = ref(false)
const workflowBusinessId = ref(null)
const workflowBusinessType = 'QUOTATION'

const showWorkflowProgress = (row) => {
  workflowBusinessId.value = row.id
  workflowDialogVisible.value = true
}

const loading = ref(false)
const quotations = ref([])
const customers = ref([])
const detailVisible = ref(false)
const dialogTitle = ref('')
const currentQuotation = ref({})

const searchForm = reactive({
  quote_no: '',
  customer: null,
  status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'PENDING': 'warning',
    'APPROVED': 'success',
    'SENT': 'warning',
    'ACCEPTED': 'success',
    'REJECTED': 'danger',
    'EXPIRED': 'info'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    'DRAFT': '草稿',
    'PENDING': '审批中',
    'APPROVED': '已审批',
    'SENT': '已发送',
    'ACCEPTED': '已接受',
    'REJECTED': '已拒绝',
    'EXPIRED': '已过期'
  }
  return labels[status] || status
}

const formatMoney = (val) => parseFloat(val || 0).toFixed(2)

const loadQuotations = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    
    // 移除空值
    Object.keys(params).forEach(key => {
      if (params[key] === '' || params[key] === null) {
        delete params[key]
      }
    })

    const response = await getQuotations(params)
    quotations.value = response.results || []
    pagination.total = response.count || 0
  } catch (error) {
    console.error('加载报价失败:', error)
    ElMessage.error('加载报价失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const response = await getCustomerList({
      params: { page_size: 100 }
    })
    customers.value = response.results || response || []
  } catch (error) {
    console.error('加载客户失败:', error)
  }
}

const resetSearch = () => {
  searchForm.quote_no = ''
  searchForm.customer = null
  searchForm.status = null
  pagination.page = 1
  loadQuotations()
}

const handleCreate = () => {
  router.push('/sales/quotations/create')
}

const handleView = async (row) => {
  try {
    const response = await getQuotation(row.id)
    const data = response.data || response
    currentQuotation.value = data
    dialogTitle.value = `报价详情 - ${data.quote_no}`
    detailVisible.value = true
  } catch (error) {
    console.error('加载报价详情失败:', error)
    ElMessage.error('加载报价详情失败')
  }
}

const handleEdit = (row) => {
  router.push(`/sales/quotations/${row.id}/edit`)
}

const handleSubmitApproval = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交该报价单进行审批吗？', '提交审批', { type: 'warning' })
    const response = await submitQuotation(row.id)
    const data = response.data || response
    if (data.workflow_started) {
      ElMessage.success(data.message || '已提交审批')
    } else {
      ElMessage.success(data.message || '操作成功')
    }
    loadQuotations()
  } catch (error) {
    if (error !== 'cancel') {
      const msg = error.response?.data?.error || '提交失败'
      ElMessage.error(msg)
    }
  }
}

const handleCreateVersion = async (row) => {
  try {
    await ElMessageBox.confirm('确定要创建新版本吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    })

    await createQuotationVersion(row.id)
    ElMessage.success('新版本创建成功')
    loadQuotations()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('创建新版本失败:', error)
      ElMessage.error('创建新版本失败')
    }
  }
}

const handleConvertToOrder = async (row) => {
  try {
    await ElMessageBox.confirm('确定要将此报价转为销售订单吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    })

    const response = await convertQuotationToOrder(row.id)
    const data = response.data || response
    ElMessage.success('转换成功')
    router.push(`/sales/orders/${data.id}`)
  } catch (error) {
    if (error !== 'cancel') {
      console.error('转换为订单失败:', error)
      ElMessage.error('转换为订单失败')
    }
  }
}

const handlePrint = (row) => {
  if (!row) {
    ElMessage.warning('请选择要打印的报价单')
    return
  }
  
  // 创建打印内容
  const printContent = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>销售报价单 - ${row.quote_no}</title>
      <style>
        body { font-family: 'Microsoft YaHei', Arial, sans-serif; padding: 20px; }
        .header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 20px; }
        .header h1 { margin: 0; font-size: 28px; }
        .info-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        .info-table td { padding: 8px; border: 1px solid #ddd; }
        .info-table td:first-child { width: 20%; background: #f5f5f5; font-weight: bold; }
        .items-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        .items-table th, .items-table td { padding: 8px; border: 1px solid #ddd; text-align: left; }
        .items-table th { background: #f5f5f5; font-weight: bold; }
        .items-table td.number { text-align: right; }
        .total-section { text-align: right; padding: 10px; background: #f9f9f9; font-size: 16px; font-weight: bold; }
        .footer { margin-top: 40px; border-top: 1px solid #ddd; padding-top: 20px; }
        @media print {
          body { padding: 0; }
          .no-print { display: none; }
        }
      
.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 10px;
  border: 1px solid #e4e7ed;
}
.table-toolbar span {
  font-size: 14px;
  color: #606266;
}

</style>
    </head>
    <body>
      <div class="header">
        <h1>销售报价单</h1>
        <p>Quotation</p>
      </div>
      
      <table class="info-table">
        <tr><td>报价编号</td><td>${row.quote_no}</td></tr>
        <tr><td>客户名称</td><td>${row.customer_name || '-'}</td></tr>
        <tr><td>报价日期</td><td>${row.quote_date}</td></tr>
        <tr><td>有效期至</td><td>${row.valid_until}</td></tr>
        <tr><td>关联项目</td><td>${row.project_name || '-'}</td></tr>
        <tr><td>状态</td><td>${row.status_display || row.status}</td></tr>
      </table>
      
      <table class="items-table">
        <thead>
          <tr>
            <th>序号</th>
            <th>物料编码</th>
            <th>物料名称</th>
            <th>规格</th>
            <th>单位</th>
            <th class="number">数量</th>
            <th class="number">单价</th>
            <th class="number">金额</th>
          </tr>
        </thead>
        <tbody>
          ${(row.lines || []).map((line, index) => `
            <tr>
              <td>${index + 1}</td>
              <td>${line.item_code || '-'}</td>
              <td>${line.item_name || '-'}</td>
              <td>${line.specification || '-'}</td>
              <td>${line.unit || '-'}</td>
              <td class="number">${line.qty}</td>
              <td class="number">¥${Number(line.unit_price || 0).toFixed(2)}</td>
              <td class="number">¥${Number(line.line_amount || 0).toFixed(2)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      
      <div class="total-section">
        不含税金额：¥${Number(row.total_amount || 0).toFixed(2)}<br>
        增值税（${row.tax_rate || 0}%）：¥${Number(row.tax_amount || 0).toFixed(2)}<br>
        含税总额：¥${Number(row.total_with_tax || 0).toFixed(2)}
      </div>
      
      ${row.notes ? `<div style="margin: 20px 0;"><strong>备注：</strong>${row.notes}</div>` : ''}
      
      <div class="footer">
        <div style="display: flex; justify-content: space-between;">
          <div>
            <p>制单人：____________</p>
            <p>日期：____________</p>
          </div>
          <div>
            <p>审批人：____________</p>
            <p>日期：____________</p>
          </div>
        </div>
      </div>
      
      <div class="no-print" style="text-align: center; margin-top: 20px;">
        <button onclick="window.print()" style="padding: 10px 30px; font-size: 16px;">打印</button>
        <button onclick="window.close()" style="padding: 10px 30px; font-size: 16px; margin-left: 10px;">关闭</button>
      </div>
    </body>
    </html>
  `
  
  // 打开新窗口打印
  const printWindow = window.open('', '_blank')
  printWindow.document.write(printContent)
  printWindow.document.close()
  printWindow.focus()
}

// 删除功能已迁移到 useBatchDelete composable

onMounted(() => {
  loadQuotations()
  loadCustomers()
})
</script>

<style scoped>
.quotation-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 10px;
  border: 1px solid #e4e7ed;
}
.table-toolbar span {
  font-size: 14px;
  color: #606266;
}

</style>

