<template>
  <div class="stock-adjustment-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>库存盘点</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新增盘点
          </el-button>
        </div>
      </template>

      <el-table :data="adjustments" v-loading="loading" border stripe>
        <el-table-column prop="adjustment_no" label="盘点单号" width="150" />
        <el-table-column prop="warehouse_name" label="仓库" width="150" />
        <el-table-column prop="adjustment_date" label="盘点日期" width="120" />
        <el-table-column prop="reason" label="原因" show-overflow-tooltip />
        <el-table-column prop="cost_impact" label="成本影响" width="130" align="right">
          <template #default="{ row }">
            <span :style="{ color: (row.cost_impact || 0) < 0 ? '#F56C6C' : '#67C23A' }">
              ¥{{ (row.cost_impact || 0).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'COMPLETED' ? 'success' : 'warning'">
              {{ row.status === 'COMPLETED' ? '已完成' : '草稿' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="创建人" width="100" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" type="success" @click="handleConfirm(row)" v-if="row.status === 'DRAFT'">确认盘点</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadAdjustments"
        @current-change="loadAdjustments"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新增/编辑盘点 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="80%">
      <el-form :model="adjustmentForm" label-width="100px">
        <el-form-item label="仓库" required>
          <el-select v-model="adjustmentForm.warehouse" placeholder="请选择仓库" @change="loadStockForAdjustment" style="width: 100%">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="盘点日期" required>
          <el-date-picker v-model="adjustmentForm.adjustment_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="原因" required>
          <el-input v-model="adjustmentForm.reason" placeholder="例如：定期盘点、异常盘点" />
        </el-form-item>
        
        <el-divider>盘点明细</el-divider>
        
        <el-table :data="adjustmentForm.lines" border max-height="400">
          <el-table-column prop="item_sku" label="物料编码" width="150" />
          <el-table-column prop="item_name" label="物料名称" />
          <el-table-column prop="qty_system" label="系统数量" width="100" align="right" />
          <el-table-column label="实际数量" width="150">
            <template #default="{ row }">
              <el-input-number v-model="row.qty_actual" :min="0" :precision="2" size="small" style="width: 100%" @change="calculateDiff(row)" />
            </template>
          </el-table-column>
          <el-table-column label="盘点差异" width="100" align="right">
            <template #default="{ row }">
              <span :style="{ color: (row.qty_diff || 0) < 0 ? '#F56C6C' : (row.qty_diff || 0) > 0 ? '#67C23A' : '#909399' }">
                {{ row.qty_diff || 0 }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAdjustment">提交盘点</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const adjustments = ref([])
const warehouses = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const formRef = ref(null)
const adjustmentForm = reactive({
  warehouse: null,
  adjustment_date: new Date().toISOString().split('T')[0],
  reason: '',
  lines: []
})

const rules = {
  warehouse: [{ required: true, message: '请选择仓库', trigger: 'change' }],
  adjustment_date: [{ required: true, message: '请选择盘点日期', trigger: 'change' }],
  reason: [{ required: true, message: '请输入盘点原因', trigger: 'blur' }]
}

const loadAdjustments = async () => {
  loading.value = true
  try {
    const { data } = await request.get('/inventory/adjustments/', {
      params: { page: pagination.page, page_size: pagination.pageSize }
    })
    adjustments.value = data.results || []
    pagination.total = data.count || 0
  } catch (error) {
    ElMessage.error('加载盘点记录失败')
  } finally {
    loading.value = false
  }
}

const loadWarehouses = async () => {
  try {
    const { data } = await request.get('/masterdata/warehouses/', { params: { page_size: 100 } })
    warehouses.value = data.results || data
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const loadStockForAdjustment = async () => {
  if (!adjustmentForm.warehouse) return
  try {
    const { data } = await request.get('/inventory/stocks/', {
      params: { warehouse: adjustmentForm.warehouse, page_size: 500 }
    })
    adjustmentForm.lines = (data.results || data).map(s => ({
      item: s.item,
      item_sku: s.item_sku,
      item_name: s.item_name,
      qty_system: s.qty_on_hand || 0,
      qty_actual: s.qty_on_hand || 0,
      qty_diff: 0
    }))
  } catch (error) {
    ElMessage.error('加载库存失败')
  }
}

const calculateDiff = (row) => {
  row.qty_diff = (row.qty_actual || 0) - (row.qty_system || 0)
}

const handleCreate = () => {
  dialogTitle.value = '新增盘点'
  adjustmentForm.warehouse = null
  adjustmentForm.adjustment_date = new Date().toISOString().split('T')[0]
  adjustmentForm.reason = ''
  adjustmentForm.lines = []
  dialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const { data } = await request.get(`/inventory/adjustments/${row.id}/`)
    ElMessage.info('查看盘点详情功能待完善')
    console.log(data)
  } catch (error) {
    ElMessage.error('加载详情失败')
  }
}

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm('确定要确认此盘点吗？确认后将调整库存。', '提示', { type: 'warning' })
    await request.post(`/inventory/adjustments/${row.id}/confirm/`)
    ElMessage.success('盘点确认成功')
    loadAdjustments()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('确认盘点失败')
  }
}

const submitAdjustment = async () => {
  if (!adjustmentForm.warehouse) return ElMessage.warning('请选择仓库')
  if (!adjustmentForm.reason) return ElMessage.warning('请输入盘点原因')
  if (adjustmentForm.lines.length === 0) return ElMessage.warning('请先加载库存数据')
  
  try {
    await request.post('/inventory/adjustments/', adjustmentForm)
    ElMessage.success('盘点单创建成功')
    dialogVisible.value = false
    loadAdjustments()
  } catch (error) {
    ElMessage.error('创建盘点单失败')
  }
}

const addLine = () => {
  adjustmentForm.lines.push({ item: null, qty_system: 0, qty_actual: 0, qty_diff: 0 })
}

const removeLine = (index) => {
  adjustmentForm.lines.splice(index, 1)
}

const resetForm = () => {
  adjustmentForm.warehouse = null
  adjustmentForm.adjustment_date = new Date().toISOString().split('T')[0]
  adjustmentForm.reason = ''
  adjustmentForm.lines = []
}

onMounted(() => {
  loadAdjustments()
  loadWarehouses()
})
</script>

<style scoped>
.stock-adjustment-list { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>

