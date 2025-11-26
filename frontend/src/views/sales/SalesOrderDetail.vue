<template>
  <div class="sales-order-detail">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span style="font-size: 18px; font-weight: 600;">销售订单详情</span>
      </template>
    </el-page-header>

    <el-card style="margin-top: 20px;" v-loading="loading">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="订单编号">{{ order.order_no }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ order.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ order.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="订单日期">{{ order.order_date }}</el-descriptions-item>
        <el-descriptions-item label="要求交付日期">{{ order.delivery_date }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(order.status)">
            {{ getStatusLabel(order.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="订单金额" :span="3">
          <span style="font-size: 18px; font-weight: 600; color: #409EFF;">
            ¥{{ (order.total_amount || 0).toFixed(2) }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="创建人">{{ order.created_by_name }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ order.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ order.updated_at }}</el-descriptions-item>
        <el-descriptions-item label="客户地址" :span="3">{{ order.customer_address || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">{{ order.notes || '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">订单明细</el-divider>

      <el-table :data="order.lines || []" border stripe>
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="item_sku" label="物料编码" width="150" />
        <el-table-column prop="item_name" label="物料名称" min-width="200" />
        <el-table-column prop="specification" label="规格" width="150" />
        <el-table-column prop="qty" label="订单数量" width="100" align="right" />
        <el-table-column prop="delivered_qty" label="已发货数量" width="110" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.delivered_qty >= row.qty ? '#67C23A' : '#E6A23C' }">
              {{ row.delivered_qty || 0 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="发货进度" width="120">
          <template #default="{ row }">
            <el-progress
              :percentage="((row.delivered_qty || 0) / (row.qty || 1) * 100)"
              :stroke-width="6"
              :status="(row.delivered_qty || 0) >= row.qty ? 'success' : null"
            />
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="unit_price" label="单价" width="120" align="right">
          <template #default="{ row }">
            ¥{{ (row.unit_price || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="金额" width="130" align="right">
          <template #default="{ row }">
            ¥{{ ((row.qty || 0) * (row.unit_price || 0)).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="150" show-overflow-tooltip />
      </el-table>

      <div style="margin-top: 20px; display: flex; justify-content: space-between; align-items: center;">
        <div>
          <el-button type="primary" @click="handleCreateDelivery" v-if="order.status === 'CONFIRMED'">
            <el-icon><Van /></el-icon>
            创建发货单
          </el-button>
          <el-button @click="handleEdit" v-if="order.status === 'DRAFT'">
            <el-icon><Edit /></el-icon>
            编辑订单
          </el-button>
          <el-button type="success" @click="handleConfirm" v-if="order.status === 'DRAFT'">
            <el-icon><Check /></el-icon>
            确认订单
          </el-button>
          <el-button type="danger" @click="handleCancel" v-if="['DRAFT', 'CONFIRMED'].includes(order.status)">
            <el-icon><Close /></el-icon>
            取消订单
          </el-button>
        </div>
        <el-statistic title="订单总金额" :value="order.total_amount || 0" prefix="¥" :precision="2" />
      </div>
    </el-card>

    <!-- 发货单列表 -->
    <el-card style="margin-top: 20px;" v-if="deliveryOrders.length > 0">
      <template #header>
        <span>发货记录</span>
      </template>

      <el-table :data="deliveryOrders" border>
        <el-table-column prop="delivery_no" label="发货单号" width="150" />
        <el-table-column prop="delivery_date" label="发货日期" width="120" />
        <el-table-column prop="warehouse_name" label="发货仓库" width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getDeliveryStatusType(row.status)">
              {{ getDeliveryStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" show-overflow-tooltip />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" @click="viewDelivery(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建发货单对话框 -->
    <el-dialog
      v-model="deliveryDialogVisible"
      title="创建发货单"
      width="70%"
    >
      <el-form :model="deliveryForm" label-width="120px">
        <el-form-item label="发货仓库" required>
          <el-select v-model="deliveryForm.warehouse" placeholder="请选择发货仓库" style="width: 100%">
            <el-option
              v-for="warehouse in warehouses"
              :key="warehouse.id"
              :label="warehouse.name"
              :value="warehouse.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="发货日期" required>
          <el-date-picker
            v-model="deliveryForm.delivery_date"
            type="date"
            placeholder="选择发货日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="deliveryForm.notes" type="textarea" :rows="3" />
        </el-form-item>
        
        <el-divider content-position="left">发货明细</el-divider>
        
        <el-table :data="deliveryForm.lines" border>
          <el-table-column prop="item_name" label="物料" />
          <el-table-column prop="qty" label="订单数量" width="100" align="right" />
          <el-table-column prop="delivered_qty" label="已发货" width="100" align="right" />
          <el-table-column label="本次发货" width="150">
            <template #default="{ row, $index }">
              <el-input-number
                v-model="row.delivery_qty"
                :min="0"
                :max="row.qty - (row.delivered_qty || 0)"
                :step="1"
                size="small"
                style="width: 100%"
              />
            </template>
          </el-table-column>
        </el-table>
      </el-form>
      
      <template #footer>
        <el-button @click="deliveryDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitDelivery">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Van, Edit, Check, Close } from '@element-plus/icons-vue'
import request from '@/utils/request'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const order = ref({})
const deliveryOrders = ref([])
const warehouses = ref([])
const deliveryDialogVisible = ref(false)
const deliveryForm = ref({
  warehouse: null,
  delivery_date: new Date().toISOString().split('T')[0],
  notes: '',
  lines: []
})

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'CONFIRMED': 'warning',
    'PARTIAL': 'primary',
    'DELIVERED': 'success',
    'CANCELLED': 'danger'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    'DRAFT': '草稿',
    'CONFIRMED': '已确认',
    'PARTIAL': '部分发货',
    'DELIVERED': '已完成',
    'CANCELLED': '已取消'
  }
  return labels[status] || status
}

const getDeliveryStatusType = (status) => {
  return status === 'COMPLETED' ? 'success' : 'warning'
}

const getDeliveryStatusLabel = (status) => {
  return status === 'COMPLETED' ? '已完成' : '进行中'
}

const loadOrderDetail = async () => {
  loading.value = true
  try {
    const response = await request.get(`/sales/orders/${route.params.id}/`)
    order.value = data
    
    // 加载关联的发货单
    const { data: deliveries } = await request.get(`/sales/deliveries/`, {
      params: { sales_order: route.params.id }
    })
    deliveryOrders.value = deliveries.results || deliveries
  } catch (error) {
    console.error('加载订单详情失败:', error)
    ElMessage.error('加载订单详情失败')
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

const goBack = () => {
  router.back()
}

const handleEdit = () => {
  router.push(`/sales/orders/${route.params.id}/edit`)
}

const handleConfirm = async () => {
  try {
    await ElMessageBox.confirm('确定要确认此订单吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await request.post(`/sales/orders/${route.params.id}/confirm/`)
    ElMessage.success('订单确认成功')
    loadOrderDetail()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('确认订单失败:', error)
      ElMessage.error('确认订单失败')
    }
  }
}

const handleCancel = async () => {
  try {
    await ElMessageBox.confirm('确定要取消此订单吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await request.post(`/sales/orders/${route.params.id}/cancel/`)
    ElMessage.success('订单取消成功')
    loadOrderDetail()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('取消订单失败:', error)
      ElMessage.error('取消订单失败')
    }
  }
}

const handleCreateDelivery = () => {
  // 准备发货明细
  deliveryForm.value.lines = order.value.lines.map(line => ({
    order_line: line.id,
    item_name: line.item_name,
    qty: line.qty,
    delivered_qty: line.delivered_qty || 0,
    delivery_qty: Math.max(0, line.qty - (line.delivered_qty || 0))
  }))
  
  deliveryDialogVisible.value = true
}

const submitDelivery = async () => {
  if (!deliveryForm.value.warehouse) {
    ElMessage.warning('请选择发货仓库')
    return
  }

  try {
    const payload = {
      sales_order: route.params.id,
      warehouse: deliveryForm.value.warehouse,
      delivery_date: deliveryForm.value.delivery_date,
      notes: deliveryForm.value.notes,
      lines: deliveryForm.value.lines
        .filter(line => line.delivery_qty > 0)
        .map(line => ({
          order_line: line.order_line,
          qty: line.delivery_qty
        }))
    }

    if (payload.lines.length === 0) {
      ElMessage.warning('请至少选择一项要发货的明细')
      return
    }

    await request.post('/sales/deliveries/', payload)
    ElMessage.success('发货单创建成功')
    deliveryDialogVisible.value = false
    loadOrderDetail()
  } catch (error) {
    console.error('创建发货单失败:', error)
    ElMessage.error('创建发货单失败')
  }
}

const viewDelivery = (row) => {
  router.push(`/sales/delivery-orders/${row.id}`)
}

onMounted(() => {
  loadOrderDetail()
  loadWarehouses()
})
</script>

<style scoped>
.sales-order-detail {
  padding: 20px;
}
</style>

