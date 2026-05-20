<template>
  <div class="stock-transfer">
    <el-card>
      <template #header><span>库存调拨</span></template>

      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="源仓库" prop="from_warehouse">
              <el-select v-model="form.from_warehouse" placeholder="请选择源仓库" @change="loadFromStock" filterable style="width: 100%">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="目标仓库" prop="to_warehouse">
              <el-select v-model="form.to_warehouse" placeholder="请选择目标仓库" filterable style="width: 100%">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" :disabled="w.id === form.from_warehouse" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="调拨日期" prop="transfer_date">
          <el-date-picker v-model="form.transfer_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>

        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" />
        </el-form-item>

        <el-divider content-position="left">调拨明细</el-divider>

        <el-button type="primary" @click="addLine" :disabled="!form.from_warehouse" style="margin-bottom: 10px">
          <el-icon><Plus /></el-icon>
          添加物料
        </el-button>

        <el-table :data="form.lines" border>
          <el-table-column label="物料" width="300">
            <template #default="{ row, $index }">
              <el-select v-model="row.item" placeholder="选择物料" filterable @change="handleItemChange($index)" style="width: 100%">
                <el-option v-for="s in fromStock" :key="s.item" :label="`${s.item_sku} - ${s.item_name}`" :value="s.item" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="可用库存" width="100" align="right">
            <template #default="{ row }">{{ row.available_qty || 0 }}</template>
          </el-table-column>
          <el-table-column label="调拨数量" width="150">
            <template #default="{ row }">
              <el-input-number v-model="row.qty" :min="0" :max="row.available_qty || 0" :precision="2" size="small" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="单位" width="80">
            <template #default="{ row }">{{ row.unit }}</template>
          </el-table-column>
          <el-table-column label="备注">
            <template #default="{ row }">
              <el-input v-model="row.notes" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80">
            <template #default="{ $index }">
              <el-button size="small" type="danger" @click="removeLine($index)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div style="margin-top: 20px; text-align: center;">
          <el-button @click="resetForm">重置</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">提交调拨</el-button>
        </div>
      </el-form>
    </el-card>

    <!-- 调拨历史 -->
    <el-card style="margin-top: 20px;">
      <template #header><span>调拨历史</span></template>
      <el-table :data="history" v-loading="loadingHistory" border>
        <el-table-column prop="move_no" label="调拨单号" width="150" />
        <el-table-column prop="warehouse_from_name" label="源仓库" width="150" />
        <el-table-column prop="warehouse_to_name" label="目标仓库" width="150" />
        <el-table-column prop="item_name" label="物料" />
        <el-table-column prop="qty" label="数量" width="100" align="right" />
        <el-table-column prop="move_date" label="调拨日期" width="120" />
        <el-table-column prop="created_by_name" label="操作人" width="100" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getStocks, getMoves, createTransfer } from '@/api/inventory'
import { getWarehouseList } from '@/api/masterdata'

const formRef = ref(null)
const submitting = ref(false)
const warehouses = ref([])
const fromStock = ref([])
const history = ref([])
const loadingHistory = ref(false)

const form = reactive({
  from_warehouse: null,
  to_warehouse: null,
  transfer_date: new Date().toISOString().split('T')[0],
  notes: '',
  lines: []
})

const rules = {
  from_warehouse: [{ required: true, message: '请选择源仓库', trigger: 'change' }],
  to_warehouse: [{ required: true, message: '请选择目标仓库', trigger: 'change' }],
  transfer_date: [{ required: true, message: '请选择调拨日期', trigger: 'change' }]
}

const loadWarehouses = async () => {
  try {
    const response = await getWarehouseList({ page_size: 100 })
    warehouses.value = response.results || response || []
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const loadFromStock = async () => {
  if (!form.from_warehouse) return
  try {
    const response = await getStocks({ warehouse: form.from_warehouse, page_size: 500 })
    fromStock.value = (response.results || response || []).filter(s => (s.qty_available || 0) > 0)
  } catch (error) {
    ElMessage.error('加载库存失败')
  }
}

const loadHistory = async () => {
  loadingHistory.value = true
  try {
    const response = await getMoves({ move_type: 'TRANSFER', page_size: 50 })
    history.value = response.results || []
  } catch (error) {
    console.error('加载调拨历史失败:', error)
  } finally {
    loadingHistory.value = false
  }
}

const addLine = () => {
  form.lines.push({ item: null, qty: 0, available_qty: 0, unit: '', notes: '' })
}

const removeLine = (index) => {
  form.lines.splice(index, 1)
}

const handleItemChange = (index) => {
  const line = form.lines[index]
  const stock = fromStock.value.find(s => s.item === line.item)
  if (stock) {
    line.available_qty = stock.qty_available || 0
    line.unit = stock.unit
    line.qty = Math.min(1, line.available_qty)
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    if (form.lines.length === 0) return ElMessage.warning('请至少添加一项调拨明细')
    if (form.lines.some(l => !l.item || l.qty <= 0)) return ElMessage.warning('请完善调拨明细')
    
    submitting.value = true
    try {
      await createTransfer(form)
      ElMessage.success('调拨成功')
      resetForm()
      loadHistory()
    } catch (error) {
      ElMessage.error('调拨失败')
    } finally {
      submitting.value = false
    }
  })
}

const resetForm = () => {
  form.from_warehouse = null
  form.to_warehouse = null
  form.transfer_date = new Date().toISOString().split('T')[0]
  form.notes = ''
  form.lines = []
  fromStock.value = []
  if (formRef.value) formRef.value.clearValidate()
}

onMounted(() => {
  loadWarehouses()
  loadHistory()
})
</script>

<style scoped>
.stock-transfer { padding: 20px; }
</style>

