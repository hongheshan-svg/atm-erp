<template>
  <div class="purchase-order-detail">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span style="font-size: 18px; font-weight: 600;">采购订单详情</span>
      </template>
    </el-page-header>

    <el-card style="margin-top: 20px;" v-loading="loading">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="订单编号">{{ order.order_no }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ order.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ order.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="订单日期">{{ order.order_date }}</el-descriptions-item>
        <el-descriptions-item label="预计到货日期">{{ order.expected_date }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(order.status)">{{ getStatusLabel(order.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="订单金额" :span="3">
          <span style="font-size: 18px; font-weight: 600; color: #67C23A;">¥{{ formatMoney(order.total_amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="付款条款" :span="3">{{ order.payment_terms || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">{{ order.notes || '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">订单明细</el-divider>

      <el-table :data="order.lines || []" border stripe>
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="item_sku" label="物料编码" width="150" />
        <el-table-column prop="item_name" label="物料名称" min-width="200" />
        <el-table-column prop="specification" label="规格" width="150" />
        <el-table-column prop="qty" label="订单数量" width="100" align="right" />
        <el-table-column prop="received_qty" label="已收货数量" width="110" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.received_qty >= row.qty ? '#67C23A' : '#E6A23C' }">
              {{ row.received_qty || 0 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="收货进度" width="120">
          <template #default="{ row }">
            <el-progress
              :percentage="((row.received_qty || 0) / (row.qty || 1) * 100)"
              :stroke-width="6"
              :status="(row.received_qty || 0) >= row.qty ? 'success' : null"
            />
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="unit_price" label="单价" width="120" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.unit_price) }}</template>
        </el-table-column>
        <el-table-column label="金额" width="130" align="right">
          <template #default="{ row }">¥{{ formatMoney(parseFloat(row.qty || 0) * parseFloat(row.unit_price || 0)) }}</template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 20px; display: flex; justify-content: space-between;">
        <div>
          <el-button type="primary" @click="handleCreateReceipt" v-if="order.status === 'CONFIRMED'">
            <el-icon><Box /></el-icon>
            创建收货单
          </el-button>
          <el-button type="success" @click="handleConfirm" v-if="order.status === 'DRAFT'">确认订单</el-button>
          <el-button type="danger" @click="handleCancel" v-if="['DRAFT', 'CONFIRMED'].includes(order.status)">取消订单</el-button>
        </div>
        <el-statistic title="订单总金额" :value="parseFloat(order.total_amount || 0)" prefix="¥" :precision="2" />
      </div>
    </el-card>

    <!-- 收货记录 -->
    <el-card style="margin-top: 20px;" v-if="receipts.length > 0">
      <template #header><span>收货记录</span></template>
      <el-table :data="receipts" border>
        <el-table-column prop="receipt_no" label="收货单号" width="150" />
        <el-table-column prop="receipt_date" label="收货日期" width="120" />
        <el-table-column prop="warehouse_name" label="收货仓库" width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'COMPLETED' ? 'success' : 'warning'">
              {{ row.status === 'COMPLETED' ? '已完成' : '进行中' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" @click="viewReceipt(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建收货单对话框 -->
    <el-dialog v-model="receiptDialogVisible" title="创建收货单" width="70%">
      <el-form :model="receiptForm" label-width="120px">
        <el-form-item label="收货仓库" required>
          <el-select v-model="receiptForm.warehouse" placeholder="请选择收货仓库" style="width: 100%">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="收货日期" required>
          <el-date-picker v-model="receiptForm.receipt_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-divider>收货明细</el-divider>
        <el-table :data="receiptForm.lines" border>
          <el-table-column prop="item_name" label="物料" />
          <el-table-column prop="qty" label="订单数量" width="100" align="right" />
          <el-table-column prop="received_qty" label="已收货" width="100" align="right" />
          <el-table-column label="本次收货" width="150">
            <template #default="{ row }">
              <el-input-number v-model="row.receipt_qty" :min="0" :max="row.qty - (row.received_qty || 0)" size="small" style="width: 100%" />
            </template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="receiptDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitReceipt">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Box } from '@element-plus/icons-vue'
import { getWarehouseList } from '@/api/masterdata'
import {
  getPurchaseOrder, confirmPurchaseOrder, cancelPurchaseOrder,
  getGoodsReceipts, createGoodsReceipt
} from '@/api/purchase'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const order = ref<Record<string, any>>({})
const receipts = ref<any[]>([])
const warehouses = ref<any[]>([])
const receiptDialogVisible = ref(false)
const receiptForm = ref({ warehouse: null, receipt_date: new Date().toISOString().split('T')[0], lines: [] })

const getStatusType = (s) => ({ 'DRAFT': 'info', 'CONFIRMED': 'warning', 'PARTIAL': 'primary', 'RECEIVED': 'success', 'CANCELLED': 'danger' }[s] || 'info')
const getStatusLabel = (s) => ({ 'DRAFT': '草稿', 'CONFIRMED': '已确认', 'PARTIAL': '部分收货', 'RECEIVED': '已完成', 'CANCELLED': '已取消' }[s] || s)
const formatMoney = (val) => parseFloat(val || 0).toFixed(2)

const loadOrderDetail = async () => {
  loading.value = true
  try {
    const response = await getPurchaseOrder(route.params.id)
    order.value = response.data || response
    const receiptRes = await getGoodsReceipts({ purchase_order: route.params.id })
    receipts.value = receiptRes.results || receiptRes.results || receiptRes || []
  } catch (error) {
    console.error('加载订单详情失败:', error)
    ElMessage.error('加载订单详情失败')
  } finally {
    loading.value = false
  }
}

const loadWarehouses = async () => {
  try {
    const response = await getWarehouseList({ page_size: 100 })
    warehouses.value = response.results || response || []
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const goBack = () => router.back()

const handleConfirm = async () => {
  try {
    await ElMessageBox.confirm('确定要确认此订单吗？', '提示', { type: 'warning' })
    await confirmPurchaseOrder(route.params.id)
    ElMessage.success('订单确认成功')
    loadOrderDetail()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('确认订单失败')
  }
}

const handleCancel = async () => {
  try {
    await ElMessageBox.confirm('确定要取消此订单吗？', '提示', { type: 'warning' })
    await cancelPurchaseOrder(route.params.id)
    ElMessage.success('订单取消成功')
    loadOrderDetail()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('取消订单失败')
  }
}

const handleCreateReceipt = () => {
  receiptForm.value.lines = order.value.lines.map(line => ({
    order_line: line.id,
    item_name: line.item_name,
    qty: line.qty,
    received_qty: line.received_qty || 0,
    receipt_qty: Math.max(0, line.qty - (line.received_qty || 0))
  }))
  receiptDialogVisible.value = true
}

const submitReceipt = async () => {
  if (!receiptForm.value.warehouse) return ElMessage.warning('请选择收货仓库')
  try {
    const payload = {
      purchase_order: route.params.id,
      warehouse: receiptForm.value.warehouse,
      receipt_date: receiptForm.value.receipt_date,
      lines: receiptForm.value.lines.filter(l => l.receipt_qty > 0).map(l => ({ order_line: l.order_line, qty: l.receipt_qty }))
    }
    if (payload.lines.length === 0) return ElMessage.warning('请至少选择一项要收货的明细')
    await createGoodsReceipt(payload)
    ElMessage.success('收货单创建成功')
    receiptDialogVisible.value = false
    loadOrderDetail()
  } catch (error) {
    ElMessage.error('创建收货单失败')
  }
}

const viewReceipt = (row) => router.push(`/purchase/goods-receipts/${row.id}`)

onMounted(() => {
  loadOrderDetail()
  loadWarehouses()
})
</script>

<style scoped>
.purchase-order-detail { padding: 20px; }
</style>

