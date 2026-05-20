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
        <el-descriptions-item label="增值税率">{{ order.tax_rate ?? 13 }}%</el-descriptions-item>
        <el-descriptions-item label="不含税金额">
            ¥{{ formatMoney(order.total_amount) }}
        </el-descriptions-item>
        <el-descriptions-item label="税额">
          ¥{{ formatMoney(order.tax_amount) }}
        </el-descriptions-item>
        <el-descriptions-item label="含税总额" :span="3">
          <span style="font-size: 18px; font-weight: 600; color: #f56c6c;">
            ¥{{ formatMoney(order.total_with_tax || order.total_amount) }}
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
        <el-table-column label="产品名称" min-width="200">
          <template #default="{ row }">
            {{ row.item_name || row.custom_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="规格型号" width="150">
          <template #default="{ row }">
            {{ row.item_spec || row.custom_spec || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="单位" width="80">
          <template #default="{ row }">
            {{ row.item_unit || row.custom_unit || '件' }}
          </template>
        </el-table-column>
        <el-table-column prop="qty" label="订单数量" width="100" align="right" />
        <el-table-column prop="delivered_qty" label="已发货" width="90" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.delivered_qty >= row.qty ? '#67C23A' : '#E6A23C' }">
              {{ row.delivered_qty || 0 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="100">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.min(100, ((row.delivered_qty || 0) / (row.qty || 1) * 100))"
              :stroke-width="6"
              :status="(row.delivered_qty || 0) >= row.qty ? 'success' : null"
            />
          </template>
        </el-table-column>
        <el-table-column prop="unit_price" label="单价" width="110" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.unit_price || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="金额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ (parseFloat(row.qty || 0) * parseFloat(row.unit_price || 0)).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="120" show-overflow-tooltip />
      </el-table>

      <div style="margin-top: 20px; display: flex; justify-content: space-between; align-items: center;">
        <div>
          <el-button type="primary" @click="handleCreateDelivery" v-if="order.status === 'CONFIRMED' && (order.lines?.length > 0)">
            <el-icon><Van /></el-icon>
            创建发货单
          </el-button>
          <el-button @click="handleEdit" v-if="order.status === 'DRAFT'">
            <el-icon><Edit /></el-icon>
            编辑订单
          </el-button>
          <el-button type="warning" @click="handleReturnToDraft" v-if="order.status === 'CONFIRMED' && (!order.lines || order.lines.length === 0)">
            <el-icon><RefreshLeft /></el-icon>
            退回草稿(补充明细)
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
        <el-statistic title="订单总金额" :value="parseFloat(order.total_amount || 0)" prefix="¥" :precision="2" />
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
      width="85%"
      top="3vh"
    >
      <el-form :model="deliveryForm" label-width="100px">
        <el-tabs v-model="deliveryActiveTab">
          <!-- 基本信息 -->
          <el-tab-pane label="基本信息" name="basic">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="发货仓库" required>
                  <el-select v-model="deliveryForm.warehouse" placeholder="请选择发货仓库" style="width: 100%">
                    <el-option v-for="warehouse in warehouses" :key="warehouse.id" :label="warehouse.name" :value="warehouse.id" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="计划发货日期" required>
                  <el-date-picker v-model="deliveryForm.delivery_date" type="date" placeholder="选择发货日期" 
                                  value-format="YYYY-MM-DD" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-tab-pane>

          <!-- 收货信息 -->
          <el-tab-pane label="收货信息" name="receiver">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="收货人">
                  <el-input v-model="deliveryForm.receiver_name" placeholder="请输入收货人姓名" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="收货电话">
                  <el-input v-model="deliveryForm.receiver_phone" placeholder="请输入收货电话" />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="收货地址">
                  <el-input v-model="deliveryForm.receiver_address" type="textarea" :rows="2" placeholder="请输入收货地址" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-tab-pane>

          <!-- 包装/保险/物流 -->
          <el-tab-pane label="物流要求" name="logistics">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="包装方式">
                  <el-select v-model="deliveryForm.packaging_type" style="width: 100%">
                    <el-option label="标准包装" value="STANDARD" />
                    <el-option label="木箱包装" value="WOODEN_CASE" />
                    <el-option label="纸箱包装" value="CARTON" />
                    <el-option label="托盘包装" value="PALLET" />
                    <el-option label="特殊包装" value="CUSTOM" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="需要保险">
                  <el-switch v-model="deliveryForm.needs_insurance" />
                  <el-input-number v-if="deliveryForm.needs_insurance" v-model="deliveryForm.insurance_amount" 
                                   :precision="2" :min="0" placeholder="保险金额" style="margin-left: 10px; width: 150px" />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="包装要求">
                  <el-input v-model="deliveryForm.packaging_notes" type="textarea" :rows="2" placeholder="请输入特殊包装要求" />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="物流要求">
                  <el-input v-model="deliveryForm.logistics_notes" type="textarea" :rows="2" placeholder="请输入物流要求说明" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-tab-pane>

          <!-- 产品信息 -->
          <el-tab-pane label="产品明细" name="products">
            <el-table :data="deliveryForm.lines" border>
              <el-table-column prop="item_name" label="物料" />
              <el-table-column prop="qty" label="订单数量" width="100" align="right" />
              <el-table-column prop="delivered_qty" label="已发货" width="100" align="right" />
              <el-table-column label="本次发货" width="150">
                <template #default="{ row }">
                  <el-input-number v-model="row.delivery_qty" :min="0" :max="row.qty - (row.delivered_qty || 0)" 
                                   :step="1" size="small" style="width: 100%" />
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <!-- 备注 -->
          <el-tab-pane label="备注" name="notes">
            <el-form-item label="备注">
              <el-input v-model="deliveryForm.notes" type="textarea" :rows="4" placeholder="请输入备注信息" />
            </el-form-item>
          </el-tab-pane>
        </el-tabs>
      </el-form>
      
      <template #footer>
        <el-button @click="deliveryDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitDelivery">创建发货单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Van, Edit, Check, Close, RefreshLeft } from '@element-plus/icons-vue'
import { getOrder, getDeliveryOrders, confirmOrder, returnOrderToDraft, cancelOrder, createDeliveryOrder, submitDeliveryOrder } from '@/api/sales'
import { getWarehouseList } from '@/api/masterdata'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const order = ref({})
const deliveryOrders = ref([])
const warehouses = ref([])
const deliveryDialogVisible = ref(false)
const deliveryActiveTab = ref('basic')
const deliveryForm = ref({
  warehouse: null,
  delivery_date: new Date().toISOString().split('T')[0],
  notes: '',
  lines: [],
  // 收货信息
  receiver_name: '',
  receiver_phone: '',
  receiver_address: '',
  // 物流要求
  packaging_type: 'STANDARD',
  packaging_notes: '',
  needs_insurance: false,
  insurance_amount: null,
  logistics_notes: ''
})

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'PENDING_APPROVAL': 'warning',
    'PENDING': 'warning',
    'APPROVED': 'success',
    'REJECTED': 'danger',
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
    'PENDING_APPROVAL': '待审批',
    'PENDING': '审批中',
    'APPROVED': '已审批',
    'REJECTED': '已拒绝',
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

const formatMoney = (val) => parseFloat(val || 0).toFixed(2)

const loadOrderDetail = async () => {
  loading.value = true
  try {
    const response = await getOrder(route.params.id)
    order.value = response.data || response
    
    // 加载关联的发货单
    const deliveryRes = await getDeliveryOrders({ so: route.params.id })
    deliveryOrders.value = deliveryRes.data?.results || deliveryRes.results || deliveryRes.data || []
  } catch (error) {
    console.error('加载订单详情失败:', error)
    ElMessage.error('加载订单详情失败')
  } finally {
    loading.value = false
  }
}

const loadWarehouses = async () => {
  try {
    const response = await getWarehouseList({
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

    await confirmOrder(route.params.id)
    ElMessage.success('订单确认成功')
    loadOrderDetail()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('确认订单失败:', error)
      ElMessage.error('确认订单失败')
    }
  }
}

const handleReturnToDraft = async () => {
  try {
    await ElMessageBox.confirm(
      '将订单退回草稿状态后，您可以编辑订单并补充产品明细。确定要退回吗？', 
      '退回草稿', 
      {
        confirmButtonText: '确定退回',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await returnOrderToDraft(route.params.id)
    ElMessage.success('订单已退回草稿状态，请点击"编辑订单"补充明细')
    loadOrderDetail()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('退回草稿失败:', error)
      ElMessage.error('退回草稿失败: ' + (error.response?.data?.error || error.message))
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

    await cancelOrder(route.params.id)
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
  // 重置表单
  deliveryActiveTab.value = 'basic'
  deliveryForm.value = {
    warehouse: null,
    delivery_date: new Date().toISOString().split('T')[0],
    notes: '',
    lines: [],
    // 从客户信息预填收货信息
    receiver_name: order.value.customer_contact || '',
    receiver_phone: order.value.customer_phone || '',
    receiver_address: order.value.customer_address || order.value.shipping_address || '',
    // 物流要求
    packaging_type: 'STANDARD',
    packaging_notes: '',
    needs_insurance: false,
    insurance_amount: null,
    logistics_notes: ''
  }
  
  // 准备发货明细
  deliveryForm.value.lines = order.value.lines.map(line => ({
    order_line: line.id,
    item_id: line.item,
    item_name: line.item_name || line.custom_name,
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
    // 获取订单明细以获取 item_id
    const orderLines = order.value.lines || []
    
    const payload = {
      so: route.params.id,
      warehouse: deliveryForm.value.warehouse,
      delivery_date: deliveryForm.value.delivery_date,
      notes: deliveryForm.value.notes,
      // 收货信息
      receiver_name: deliveryForm.value.receiver_name,
      receiver_phone: deliveryForm.value.receiver_phone,
      receiver_address: deliveryForm.value.receiver_address,
      // 物流要求
      packaging_type: deliveryForm.value.packaging_type,
      packaging_notes: deliveryForm.value.packaging_notes,
      needs_insurance: deliveryForm.value.needs_insurance,
      insurance_amount: deliveryForm.value.needs_insurance ? deliveryForm.value.insurance_amount : null,
      logistics_notes: deliveryForm.value.logistics_notes,
      // 产品明细
      lines: deliveryForm.value.lines
        .filter(line => line.delivery_qty > 0)
        .map(line => {
          const orderLine = orderLines.find(ol => ol.id === line.order_line)
          return {
            so_line: line.order_line,
            item: line.item_id || orderLine?.item || orderLine?.item_id,
            qty: line.delivery_qty
          }
        })
    }

    if (payload.lines.length === 0) {
      ElMessage.warning('请至少选择一项要发货的明细')
      return
    }

    const response = await createDeliveryOrder(payload)
    const newDelivery = response.data || response
    
    deliveryDialogVisible.value = false
    
    // 询问是否立即提交审批
    try {
      await ElMessageBox.confirm(
        '发货单创建成功！是否立即提交审批？',
        '提交审批',
        {
          confirmButtonText: '立即提交',
          cancelButtonText: '稍后提交',
          type: 'success'
        }
      )
      
      // 用户选择立即提交
      try {
        await submitDeliveryOrder(newDelivery.id)
        ElMessage.success('发货单已提交审批')
      } catch (submitError) {
        console.error('提交审批失败:', submitError)
        ElMessage.warning('发货单已创建，但提交审批失败，请稍后在发货单列表中重新提交')
      }
    } catch (error) {
    console.error(error)
      // 用户选择稍后提交
      ElMessage.success('发货单已创建，可在发货单列表中提交审批')
    }
    
    loadOrderDetail()
  } catch (error) {
    console.error('创建发货单失败:', error)
    ElMessage.error(error.response?.data?.detail || error.response?.data?.error || '创建发货单失败')
  }
}

const viewDelivery = (row) => {
  router.push(`/sales/delivery-orders/${row.id}`)
}

onMounted(async () => {
  await loadOrderDetail()
  await loadWarehouses()
  
  // 如果带有action=create_delivery参数，自动打开创建发货单对话框
  if (route.query.action === 'create_delivery') {
    if (order.value.status === 'CONFIRMED' || order.value.status === 'PARTIAL') {
      handleCreateDelivery()
    } else {
      ElMessage.warning('只有已确认或部分发货状态的订单才能创建发货单')
    }
  }
})
</script>

<style scoped>
.sales-order-detail {
  padding: 20px;
}
</style>

