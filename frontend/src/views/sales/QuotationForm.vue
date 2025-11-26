<template>
  <div class="quotation-form">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ isEdit ? '编辑报价单' : '新增报价单' }}</span>
          <el-button @click="goBack">
            <el-icon><Back /></el-icon>
            返回
          </el-button>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        v-loading="loading"
      >
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="客户" prop="customer">
              <el-select
                v-model="form.customer"
                placeholder="请选择客户"
                filterable
                style="width: 100%;"
              >
                <el-option
                  v-for="customer in customers"
                  :key="customer.id"
                  :label="customer.name"
                  :value="customer.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="关联项目" prop="project">
              <el-select
                v-model="form.project"
                placeholder="请选择项目（可选）"
                filterable
                clearable
                style="width: 100%;"
              >
                <el-option
                  v-for="project in projects"
                  :key="project.id"
                  :label="project.name"
                  :value="project.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="有效期至" prop="valid_until">
              <el-date-picker
                v-model="form.valid_until"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择有效期"
                style="width: 100%;"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input
                v-model="form.notes"
                type="textarea"
                :rows="2"
                placeholder="请输入备注信息"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 报价明细 -->
        <el-divider content-position="left">报价明细</el-divider>
        
        <div class="lines-toolbar">
          <el-button type="primary" @click="addLine">
            <el-icon><Plus /></el-icon>
            添加产品
          </el-button>
          <el-button @click="addLineFromStock" type="success">
            <el-icon><Box /></el-icon>
            从库存选择
          </el-button>
        </div>

        <el-table :data="form.lines" border stripe style="margin-top: 15px;">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column label="产品/物料" min-width="220">
            <template #default="{ row, $index }">
              <el-select
                v-model="row.item"
                placeholder="选择产品"
                filterable
                style="width: 100%;"
                @change="onItemChange($index)"
              >
                <el-option
                  v-for="item in items"
                  :key="item.id"
                  :label="`${item.sku} - ${item.name}`"
                  :value="item.id"
                >
                  <span style="float: left">{{ item.sku }}</span>
                  <span style="float: right; color: #8492a6; font-size: 13px; margin-left: 15px;">
                    {{ item.name }}
                  </span>
                </el-option>
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="规格" width="150">
            <template #default="{ row }">
              {{ getItemSpec(row.item) }}
            </template>
          </el-table-column>
          <el-table-column label="库存" width="100" align="right">
            <template #default="{ row }">
              <span :class="getStockClass(row.item)">
                {{ getStockQty(row.item) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="数量" width="130">
            <template #default="{ row }">
              <el-input-number
                v-model="row.qty"
                :min="0.01"
                :precision="2"
                size="small"
                style="width: 100%;"
                @change="calculateLineAmount(row)"
              />
            </template>
          </el-table-column>
          <el-table-column label="单位" width="80">
            <template #default="{ row }">
              {{ getItemUnit(row.item) }}
            </template>
          </el-table-column>
          <el-table-column label="单价" width="140">
            <template #default="{ row }">
              <el-input-number
                v-model="row.unit_price"
                :min="0"
                :precision="2"
                size="small"
                style="width: 100%;"
                @change="calculateLineAmount(row)"
              />
            </template>
          </el-table-column>
          <el-table-column label="金额" width="130" align="right">
            <template #default="{ row }">
              <span class="line-amount">¥{{ calculateLineTotal(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="备注" width="150">
            <template #default="{ row }">
              <el-input v-model="row.notes" size="small" placeholder="备注" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ $index }">
              <el-button
                type="danger"
                size="small"
                link
                @click="removeLine($index)"
                :disabled="form.lines.length <= 1"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 汇总 -->
        <div class="summary-section">
          <div class="summary-row">
            <span class="label">合计金额:</span>
            <span class="total-amount">¥{{ totalAmount }}</span>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="form-actions">
          <el-button @click="goBack">取消</el-button>
          <el-button type="primary" @click="handleSave" :loading="saving">
            {{ isEdit ? '保存修改' : '保存报价单' }}
          </el-button>
          <el-button type="success" @click="handleSaveAndSend" :loading="saving" v-if="!isEdit">
            保存并发送
          </el-button>
        </div>
      </el-form>
    </el-card>

    <!-- 从库存选择对话框 -->
    <el-dialog v-model="stockDialogVisible" title="从库存选择产品" width="900px">
      <el-table
        :data="stockItems"
        v-loading="loadingStock"
        @selection-change="handleStockSelection"
        max-height="400"
        border
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="item_sku" label="产品编码" width="120" />
        <el-table-column prop="item_name" label="产品名称" />
        <el-table-column prop="warehouse_name" label="仓库" width="120" />
        <el-table-column prop="qty_on_hand" label="可用库存" width="100" align="right" />
        <el-table-column prop="weighted_avg_cost" label="成本" width="100" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.weighted_avg_cost || 0).toFixed(2) }}
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="stockDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmStockSelection">确定添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, Plus, Delete, Box } from '@element-plus/icons-vue'
import request from '@/utils/request'

const router = useRouter()
const route = useRoute()

const formRef = ref(null)
const loading = ref(false)
const saving = ref(false)
const isEdit = computed(() => !!route.params.id)

const customers = ref([])
const projects = ref([])
const items = ref([])
const stocks = ref([])

// 库存选择对话框
const stockDialogVisible = ref(false)
const stockItems = ref([])
const loadingStock = ref(false)
const selectedStockItems = ref([])

const form = reactive({
  customer: null,
  project: null,
  valid_until: '',
  notes: '',
  lines: [
    { item: null, qty: 1, unit_price: 0, notes: '' }
  ]
})

const rules = {
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  valid_until: [{ required: true, message: '请选择有效期', trigger: 'change' }]
}

// 计算总金额
const totalAmount = computed(() => {
  return form.lines.reduce((sum, line) => {
    return sum + (line.qty || 0) * (line.unit_price || 0)
  }, 0).toFixed(2)
})

// 获取物料规格
const getItemSpec = (itemId) => {
  const item = items.value.find(i => i.id === itemId)
  return item?.specification || '-'
}

// 获取物料单位
const getItemUnit = (itemId) => {
  const item = items.value.find(i => i.id === itemId)
  return item?.unit || ''
}

// 获取库存数量
const getStockQty = (itemId) => {
  const stock = stocks.value.find(s => s.item === itemId)
  return stock ? parseFloat(stock.qty_on_hand).toFixed(0) : '0'
}

// 库存数量样式
const getStockClass = (itemId) => {
  const stock = stocks.value.find(s => s.item === itemId)
  if (!stock || parseFloat(stock.qty_on_hand) <= 0) {
    return 'stock-zero'
  }
  return 'stock-normal'
}

// 计算行金额
const calculateLineAmount = (row) => {
  row.line_amount = (row.qty || 0) * (row.unit_price || 0)
}

const calculateLineTotal = (row) => {
  return ((row.qty || 0) * (row.unit_price || 0)).toFixed(2)
}

// 物料选择变化
const onItemChange = (index) => {
  const line = form.lines[index]
  const item = items.value.find(i => i.id === line.item)
  if (item) {
    // 默认使用标准成本的1.3倍作为报价
    line.unit_price = parseFloat(item.standard_cost || 0) * 1.3
    calculateLineAmount(line)
  }
}

// 添加明细行
const addLine = () => {
  form.lines.push({ item: null, qty: 1, unit_price: 0, notes: '' })
}

// 删除明细行
const removeLine = (index) => {
  if (form.lines.length > 1) {
    form.lines.splice(index, 1)
  }
}

// 从库存选择
const addLineFromStock = async () => {
  loadingStock.value = true
  stockDialogVisible.value = true
  try {
    const res = await request.get('/inventory/stocks/', {
      params: { page_size: 200 }
    })
    stockItems.value = (res.data?.results || res.results || res.data || [])
      .filter(s => parseFloat(s.qty_on_hand) > 0)
  } catch (error) {
    console.error('加载库存失败:', error)
  } finally {
    loadingStock.value = false
  }
}

const handleStockSelection = (selection) => {
  selectedStockItems.value = selection
}

const confirmStockSelection = () => {
  if (selectedStockItems.value.length === 0) {
    ElMessage.warning('请选择至少一个产品')
    return
  }

  selectedStockItems.value.forEach(stock => {
    // 检查是否已存在
    const exists = form.lines.some(line => line.item === stock.item)
    if (!exists) {
      const item = items.value.find(i => i.id === stock.item)
      form.lines.push({
        item: stock.item,
        qty: 1,
        unit_price: parseFloat(stock.weighted_avg_cost || 0) * 1.3,
        notes: ''
      })
    }
  })

  // 移除空行
  form.lines = form.lines.filter(line => line.item !== null)
  if (form.lines.length === 0) {
    form.lines.push({ item: null, qty: 1, unit_price: 0, notes: '' })
  }

  stockDialogVisible.value = false
  ElMessage.success('已添加所选产品')
}

// 加载数据
const loadCustomers = async () => {
  try {
    const res = await request.get('/masterdata/customers/', { params: { page_size: 200 } })
    customers.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载客户失败:', error)
  }
}

const loadProjects = async () => {
  try {
    const res = await request.get('/projects/projects/', { params: { page_size: 200 } })
    projects.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const loadItems = async () => {
  try {
    const res = await request.get('/masterdata/items/', { params: { page_size: 500 } })
    items.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载物料失败:', error)
  }
}

const loadStocks = async () => {
  try {
    const res = await request.get('/inventory/stocks/', { params: { page_size: 500 } })
    stocks.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载库存失败:', error)
  }
}

const loadQuotation = async () => {
  if (!route.params.id) return
  
  loading.value = true
  try {
    const res = await request.get(`/sales/quotations/${route.params.id}/`)
    const data = res.data || res
    
    form.customer = data.customer
    form.project = data.project
    form.valid_until = data.valid_until
    form.notes = data.notes || ''
    form.lines = (data.lines || []).map(line => ({
      id: line.id,
      item: line.item,
      qty: parseFloat(line.qty),
      unit_price: parseFloat(line.unit_price),
      notes: line.notes || ''
    }))
    
    if (form.lines.length === 0) {
      form.lines = [{ item: null, qty: 1, unit_price: 0, notes: '' }]
    }
  } catch (error) {
    console.error('加载报价单失败:', error)
    ElMessage.error('加载报价单失败')
  } finally {
    loading.value = false
  }
}

// 保存
const handleSave = async () => {
  try {
    await formRef.value?.validate()
    
    const validLines = form.lines.filter(line => line.item && line.qty > 0)
    if (validLines.length === 0) {
      ElMessage.warning('请至少添加一个有效的产品明细')
      return
    }
    
    saving.value = true
    
    const payload = {
      customer: form.customer,
      project: form.project,
      valid_until: form.valid_until,
      notes: form.notes,
      lines: validLines.map(line => ({
        item: line.item,
        qty: line.qty,
        unit_price: line.unit_price,
        notes: line.notes
      }))
    }
    
    if (isEdit.value) {
      await request.put(`/sales/quotations/${route.params.id}/`, payload)
      ElMessage.success('报价单更新成功')
    } else {
      await request.post('/sales/quotations/', payload)
      ElMessage.success('报价单创建成功')
    }
    
    router.push('/sales/quotations')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('保存报价单失败:', error)
      ElMessage.error('保存报价单失败')
    }
  } finally {
    saving.value = false
  }
}

// 保存并发送
const handleSaveAndSend = async () => {
  try {
    await formRef.value?.validate()
    
    const validLines = form.lines.filter(line => line.item && line.qty > 0)
    if (validLines.length === 0) {
      ElMessage.warning('请至少添加一个有效的产品明细')
      return
    }
    
    await ElMessageBox.confirm('确定要保存并发送给客户吗？', '确认发送', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    })
    
    saving.value = true
    
    const payload = {
      customer: form.customer,
      project: form.project,
      valid_until: form.valid_until,
      notes: form.notes,
      status: 'SENT', // 直接设置为已发送
      lines: validLines.map(line => ({
        item: line.item,
        qty: line.qty,
        unit_price: line.unit_price,
        notes: line.notes
      }))
    }
    
    await request.post('/sales/quotations/', payload)
    ElMessage.success('报价单已创建并发送')
    router.push('/sales/quotations')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('操作失败:', error)
      ElMessage.error('操作失败')
    }
  } finally {
    saving.value = false
  }
}

const goBack = () => {
  router.push('/sales/quotations')
}

onMounted(async () => {
  await Promise.all([
    loadCustomers(),
    loadProjects(),
    loadItems(),
    loadStocks()
  ])
  
  if (isEdit.value) {
    await loadQuotation()
  } else {
    // 设置默认有效期为30天后
    const date = new Date()
    date.setDate(date.getDate() + 30)
    form.valid_until = date.toISOString().split('T')[0]
  }
})
</script>

<style scoped>
.quotation-form {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.lines-toolbar {
  display: flex;
  gap: 10px;
}

.line-amount {
  font-weight: 600;
  color: #f56c6c;
}

.summary-section {
  margin-top: 20px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  text-align: right;
}

.summary-row {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 20px;
}

.summary-row .label {
  font-size: 16px;
  color: #606266;
}

.total-amount {
  font-size: 24px;
  font-weight: bold;
  color: #f56c6c;
}

.form-actions {
  margin-top: 30px;
  text-align: center;
}

.form-actions .el-button {
  min-width: 120px;
}

.stock-zero {
  color: #f56c6c;
}

.stock-normal {
  color: #67c23a;
}
</style>

