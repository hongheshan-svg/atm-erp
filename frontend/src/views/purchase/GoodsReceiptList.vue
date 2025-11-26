<template>
  <div class="goods-receipt-list">
    <el-card>
      <template #header>
        <div class="card-header"><span>到货质检管理</span></div>
      </template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="收货单号">
          <el-input v-model="searchForm.receipt_no" placeholder="请输入收货单号" clearable />
        </el-form-item>
        <el-form-item label="采购订单">
          <el-input v-model="searchForm.po_no" placeholder="请输入采购订单号" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择状态" clearable>
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已确认" value="CONFIRMED" />
            <el-option label="已完成" value="COMPLETED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadReceipts">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="receipts" v-loading="loading" border stripe>
        <el-table-column prop="receipt_no" label="收货单号" width="150" />
        <el-table-column prop="purchase_order_no" label="采购订单号" width="150" />
        <el-table-column prop="supplier_name" label="供应商" width="200" />
        <el-table-column prop="warehouse_name" label="收货仓库" width="150" />
        <el-table-column prop="receipt_date" label="收货日期" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="创建人" width="100" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" type="success" @click="handleConfirm(row)" v-if="row.status === 'DRAFT'">确认收货</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadReceipts"
        @current-change="loadReceipts"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 收货单详情 -->
    <el-dialog v-model="detailVisible" title="收货单详情" width="80%">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="收货单号">{{ current.receipt_no }}</el-descriptions-item>
        <el-descriptions-item label="采购订单">{{ current.purchase_order_no }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ current.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="收货仓库">{{ current.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="收货日期">{{ current.receipt_date }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(current.status)">{{ getStatusLabel(current.status) }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <el-divider>收货明细</el-divider>
      <el-table :data="current.lines || []" border>
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="item_sku" label="物料编码" width="150" />
        <el-table-column prop="item_name" label="物料名称" />
        <el-table-column prop="qty" label="收货数量" width="100" align="right" />
        <el-table-column prop="quality_status" label="质检状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.quality_status === 'PASS' ? 'success' : row.quality_status === 'FAIL' ? 'danger' : 'info'">
              {{ row.quality_status === 'PASS' ? '合格' : row.quality_status === 'FAIL' ? '不合格' : '待检' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const receipts = ref([])
const detailVisible = ref(false)
const current = ref({})
const searchForm = reactive({ receipt_no: '', po_no: '', status: null })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const getStatusType = (s) => ({ 'DRAFT': 'info', 'CONFIRMED': 'warning', 'COMPLETED': 'success' }[s] || 'info')
const getStatusLabel = (s) => ({ 'DRAFT': '草稿', 'CONFIRMED': '已确认', 'COMPLETED': '已完成' }[s] || s)

const loadReceipts = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize, ...searchForm }
    Object.keys(params).forEach(k => { if (params[k] === '' || params[k] === null) delete params[k] })
    const { data } = await request.get('/purchase/receipts/', { params })
    receipts.value = data.results || []
    pagination.total = data.count || 0
  } catch (error) {
    ElMessage.error('加载收货单失败')
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.receipt_no = ''
  searchForm.po_no = ''
  searchForm.status = null
  pagination.page = 1
  loadReceipts()
}

const handleView = async (row) => {
  try {
    const { data } = await request.get(`/purchase/receipts/${row.id}/`)
    current.value = data
    detailVisible.value = true
  } catch (error) {
    ElMessage.error('加载详情失败')
  }
}

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm('确定要确认收货吗？确认后将生成入库记录。', '提示', { type: 'warning' })
    await request.post(`/purchase/receipts/${row.id}/confirm/`)
    ElMessage.success('收货确认成功')
    loadReceipts()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('确认收货失败')
  }
}

onMounted(() => loadReceipts())
</script>

<style scoped>
.goods-receipt-list { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.search-form { margin-bottom: 20px; }
</style>

