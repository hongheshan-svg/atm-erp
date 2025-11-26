<template>
  <div class="quotation-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>销售报价管理</span>
          <el-button type="primary" @click="handleCreate">
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

      <!-- 报价列表 -->
      <el-table :data="quotations" v-loading="loading" border stripe>
        <el-table-column prop="quote_no" label="报价编号" width="150" />
        <el-table-column prop="customer_name" label="客户" width="200" />
        <el-table-column prop="project_name" label="关联项目" width="150" show-overflow-tooltip />
        <el-table-column prop="quote_date" label="报价日期" width="120" />
        <el-table-column prop="valid_until" label="有效期至" width="120" />
        <el-table-column prop="total_amount" label="报价金额" width="130" align="right">
          <template #default="{ row }">
            ¥{{ (row.total_amount || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="80" align="center" />
        <el-table-column prop="created_by_name" label="创建人" width="100" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="success" @click="handleCreateVersion(row)">
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
        <el-table-column prop="specification" label="规格" />
        <el-table-column prop="qty" label="数量" width="100" align="right" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="unit_price" label="单价" width="120" align="right">
          <template #default="{ row }">
            ¥{{ (row.unit_price || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="130" align="right">
          <template #default="{ row }">
            ¥{{ ((row.qty || 0) * (row.unit_price || 0)).toFixed(2) }}
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
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'

const router = useRouter()

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
    'SENT': '已发送',
    'ACCEPTED': '已接受',
    'REJECTED': '已拒绝',
    'EXPIRED': '已过期'
  }
  return labels[status] || status
}

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

    const { data } = await request.get('/sales/quotations/', { params })
    quotations.value = data.results || []
    pagination.total = data.count || 0
  } catch (error) {
    console.error('加载报价失败:', error)
    ElMessage.error('加载报价失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const { data } = await request.get('/masterdata/customers/', {
      params: { page_size: 100 }
    })
    customers.value = data.results || data
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
    const { data } = await request.get(`/sales/quotations/${row.id}/`)
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

const handleCreateVersion = async (row) => {
  try {
    await ElMessageBox.confirm('确定要创建新版本吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    })

    await request.post(`/sales/quotations/${row.id}/create_new_version/`)
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

    const { data } = await request.post(`/sales/quotations/${row.id}/convert_to_order/`)
    ElMessage.success('转换成功')
    router.push(`/sales/orders/${data.id}`)
  } catch (error) {
    if (error !== 'cancel') {
      console.error('转换为订单失败:', error)
      ElMessage.error('转换为订单失败')
    }
  }
}

const handlePrint = () => {
  ElMessage.info('打印功能待实现')
  // 这里可以集成打印或PDF生成功能
}

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
</style>

