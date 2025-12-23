<template>
  <div class="delivery-order-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>发货单管理</span>
        </div>
      </template>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="发货单号">
          <el-input v-model="searchForm.delivery_no" placeholder="请输入发货单号" clearable />
        </el-form-item>
        <el-form-item label="销售订单">
          <el-input v-model="searchForm.sales_order_no" placeholder="请输入销售订单号" clearable />
        </el-form-item>
        <el-form-item label="仓库">
          <el-select v-model="searchForm.warehouse" placeholder="请选择仓库" clearable style="width: 180px;">
            <el-option
              v-for="warehouse in warehouses"
              :key="warehouse.id"
              :label="warehouse.name"
              :value="warehouse.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择状态" clearable style="width: 140px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已确认" value="CONFIRMED" />
            <el-option label="已完成" value="COMPLETED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadDeliveryOrders">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 发货单列表 -->
      <el-table :data="deliveryOrders" v-loading="loading" border stripe>
        <el-table-column prop="delivery_no" label="发货单号" width="150" />
        <el-table-column prop="sales_order_no" label="销售订单号" width="150" />
        <el-table-column prop="customer_name" label="客户" width="200" />
        <el-table-column prop="warehouse_name" label="发货仓库" width="150" />
        <el-table-column prop="delivery_date" label="发货日期" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="创建人" width="100" />
        <el-table-column prop="notes" label="备注" show-overflow-tooltip />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" type="success" @click="handleConfirm(row)" v-if="row.status === 'DRAFT'">
              确认发货
            </el-button>
            <el-button size="small" type="primary" @click="handlePrint(row)">打印</el-button>
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
        @size-change="loadDeliveryOrders"
        @current-change="loadDeliveryOrders"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 发货单详情对话框 -->
    <el-dialog
      v-model="detailVisible"
      title="发货单详情"
      width="80%"
      top="5vh"
    >
      <el-descriptions :column="3" border>
        <el-descriptions-item label="发货单号">{{ currentDelivery.delivery_no }}</el-descriptions-item>
        <el-descriptions-item label="销售订单">{{ currentDelivery.sales_order_no }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ currentDelivery.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="发货仓库">{{ currentDelivery.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="发货日期">{{ currentDelivery.delivery_date }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentDelivery.status)">
            {{ getStatusLabel(currentDelivery.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建人">{{ currentDelivery.created_by_name }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ currentDelivery.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ currentDelivery.updated_at }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">{{ currentDelivery.notes || '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">发货明细</el-divider>

      <el-table :data="currentDelivery.lines || []" border>
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="item_sku" label="物料编码" width="150" />
        <el-table-column prop="item_name" label="物料名称" />
        <el-table-column prop="specification" label="规格" />
        <el-table-column prop="qty" label="发货数量" width="100" align="right" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="notes" label="备注" show-overflow-tooltip />
      </el-table>

      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="handlePrint(currentDelivery)">打印发货单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import request from '@/utils/request'

const router = useRouter()

const loading = ref(false)
const deliveryOrders = ref([])
const warehouses = ref([])
const detailVisible = ref(false)
const currentDelivery = ref({})

const searchForm = reactive({
  delivery_no: '',
  sales_order_no: '',
  warehouse: null,
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
    'CONFIRMED': 'warning',
    'COMPLETED': 'success'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    'DRAFT': '草稿',
    'CONFIRMED': '已确认',
    'COMPLETED': '已完成'
  }
  return labels[status] || status
}

const loadDeliveryOrders = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    
    Object.keys(params).forEach(key => {
      if (params[key] === '' || params[key] === null) {
        delete params[key]
      }
    })

    const response = await request.get('/sales/deliveries/', { params })
    deliveryOrders.value = response.results || []
    pagination.total = response.count || 0
  } catch (error) {
    console.error('加载发货单失败:', error)
    ElMessage.error('加载发货单失败')
  } finally {
    loading.value = false
  }
}

const loadWarehouses = async () => {
  try {
    const response = await request.get('/masterdata/warehouses/', {
      params: { page_size: 100 }
    })
    warehouses.value = response.results || response || []
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const resetSearch = () => {
  searchForm.delivery_no = ''
  searchForm.sales_order_no = ''
  searchForm.warehouse = null
  searchForm.status = null
  pagination.page = 1
  loadDeliveryOrders()
}

const handleView = async (row) => {
  try {
    const response = await request.get(`/sales/deliveries/${row.id}/`)
    currentDelivery.value = response.data || response
    detailVisible.value = true
  } catch (error) {
    console.error('加载发货单详情失败:', error)
    ElMessage.error('加载发货单详情失败')
  }
}

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm('确定要确认此发货单吗？确认后将生成出库记录。', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await request.post(`/sales/deliveries/${row.id}/confirm/`)
    ElMessage.success('发货单确认成功')
    loadDeliveryOrders()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('确认发货单失败:', error)
      ElMessage.error('确认发货单失败')
    }
  }
}

const handlePrint = (row) => {
  ElMessage.info('打印功能待实现')
  // 这里可以集成打印或PDF生成功能
}

onMounted(() => {
  loadDeliveryOrders()
  loadWarehouses()
})
</script>

<style scoped>
.delivery-order-list {
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
