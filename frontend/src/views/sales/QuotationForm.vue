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
          <el-col :span="8">
            <el-form-item label="增值税率" prop="tax_rate">
              <el-select v-model="form.tax_rate" placeholder="选择税率" style="width: 100%;">
                <el-option :value="0" label="0% (免税)" />
                <el-option :value="1" label="1%" />
                <el-option :value="3" label="3%" />
                <el-option :value="6" label="6%" />
                <el-option :value="9" label="9%" />
                <el-option :value="13" label="13%" />
              </el-select>
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
        <el-divider content-position="left">报价明细（非标定制产品可直接填写）</el-divider>
        
        <div class="lines-toolbar">
          <el-button type="primary" @click="addLine">
            <el-icon><Plus /></el-icon>
            添加产品
          </el-button>
        </div>

        <el-table :data="form.lines" border stripe style="margin-top: 15px;">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column label="产品名称 *" min-width="180">
            <template #default="{ row }">
              <el-input 
                v-model="row.custom_name" 
                placeholder="输入产品名称" 
                size="small"
              />
            </template>
          </el-table-column>
          <el-table-column label="规格型号" min-width="150">
            <template #default="{ row }">
              <el-input 
                v-model="row.custom_spec" 
                placeholder="如：φ20×100mm" 
                size="small"
              />
            </template>
          </el-table-column>
          <el-table-column label="单位" width="80">
            <template #default="{ row }">
              <el-input v-model="row.custom_unit" placeholder="件" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="数量" width="100">
            <template #default="{ row }">
              <el-input-number
                v-model="row.qty"
                :min="0.01"
                :precision="2"
                size="small"
                controls-position="right"
                style="width: 100%;"
              />
            </template>
          </el-table-column>
          <el-table-column label="单价" width="120">
            <template #default="{ row }">
              <el-input-number
                v-model="row.unit_price"
                :min="0"
                :precision="2"
                size="small"
                controls-position="right"
                style="width: 100%;"
              />
            </template>
          </el-table-column>
          <el-table-column label="金额" width="110" align="right">
            <template #default="{ row }">
              <span class="line-amount">¥{{ calculateLineTotal(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="备注" width="120">
            <template #default="{ row }">
              <el-input v-model="row.notes" size="small" placeholder="备注" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60" fixed="right">
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
            <span class="label">不含税金额:</span>
            <span class="amount">¥{{ totalAmount }}</span>
          </div>
          <div class="summary-row">
            <span class="label">税额 ({{ form.tax_rate }}%):</span>
            <span class="amount">¥{{ taxAmount }}</span>
          </div>
          <div class="summary-row total">
            <span class="label">含税总额:</span>
            <span class="total-amount">¥{{ totalWithTax }}</span>
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

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, Plus, Delete } from '@element-plus/icons-vue'
import { getQuotation, createQuotation, updateQuotation } from '@/api/sales'
import { getCustomerList } from '@/api/masterdata'

const router = useRouter()
const route = useRoute()

const formRef = ref(null)
const loading = ref(false)
const saving = ref(false)
const isEdit = computed(() => !!route.params.id)

const customers = ref([])

const form = reactive({
  customer: null,
  valid_until: '',
  tax_rate: 13,
  notes: '',
  lines: [
    { custom_name: '', custom_spec: '', custom_unit: '件', qty: 1, unit_price: 0, notes: '' }
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

// 计算税额
const taxAmount = computed(() => {
  const total = parseFloat(totalAmount.value) || 0
  return (total * form.tax_rate / 100).toFixed(2)
})

// 计算含税总额
const totalWithTax = computed(() => {
  const total = parseFloat(totalAmount.value) || 0
  const tax = parseFloat(taxAmount.value) || 0
  return (total + tax).toFixed(2)
})

const calculateLineTotal = (row) => {
  return ((row.qty || 0) * (row.unit_price || 0)).toFixed(2)
}

// 添加明细行
const addLine = () => {
  form.lines.push({ custom_name: '', custom_spec: '', custom_unit: '件', qty: 1, unit_price: 0, notes: '' })
}

// 删除明细行
const removeLine = (index) => {
  if (form.lines.length > 1) {
    form.lines.splice(index, 1)
  }
}

// 加载数据
const loadCustomers = async () => {
  try {
    const res = await getCustomerList({ page_size: 200 })
    customers.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载客户失败:', error)
  }
}

const loadQuotation = async () => {
  if (!route.params.id) return
  
  loading.value = true
  try {
    const res = await getQuotation(route.params.id)
    const data = res.data || res
    
    form.customer = data.customer
    form.valid_until = data.valid_until
    form.tax_rate = data.tax_rate ?? 13
    form.notes = data.notes || ''
    form.lines = (data.lines || []).map(line => ({
      id: line.id,
      item: line.item,
      custom_name: line.custom_name || line.item_name || '',
      custom_spec: line.custom_spec || line.item_spec || '',
      custom_unit: line.custom_unit || line.item_unit || '件',
      qty: parseFloat(line.qty),
      unit_price: parseFloat(line.unit_price),
      notes: line.notes || ''
    }))
    
    if (form.lines.length === 0) {
      form.lines = [{ custom_name: '', custom_spec: '', custom_unit: '件', qty: 1, unit_price: 0, notes: '' }]
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
    
    // 验证：至少有一行填写了产品名称
    const validLines = form.lines.filter(line => line.custom_name && line.qty > 0)
    if (validLines.length === 0) {
      ElMessage.warning('请至少添加一个产品明细（需填写产品名称）')
      return
    }
    
    saving.value = true
    
    const payload = {
      customer: form.customer,
      valid_until: form.valid_until,
      tax_rate: form.tax_rate,
      notes: form.notes,
      lines: validLines.map(line => ({
        item: line.item || null,
        custom_name: line.custom_name,
        custom_spec: line.custom_spec || '',
        custom_unit: line.custom_unit || '件',
        qty: line.qty,
        unit_price: line.unit_price,
        notes: line.notes
      }))
    }
    
    if (isEdit.value) {
      await updateQuotation(route.params.id, payload)
      ElMessage.success('报价单更新成功')
    } else {
      await createQuotation(payload)
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
    
    // 验证：至少有一行填写了产品名称
    const validLines = form.lines.filter(line => line.custom_name && line.qty > 0)
    if (validLines.length === 0) {
      ElMessage.warning('请至少添加一个产品明细（需填写产品名称）')
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
      valid_until: form.valid_until,
      tax_rate: form.tax_rate,
      notes: form.notes,
      status: 'SENT', // 直接设置为已发送
      lines: validLines.map(line => ({
        item: line.item || null,
        custom_name: line.custom_name,
        custom_spec: line.custom_spec || '',
        custom_unit: line.custom_unit || '件',
        qty: line.qty,
        unit_price: line.unit_price,
        notes: line.notes
      }))
    }
    
    await createQuotation(payload)
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
  await loadCustomers()
  
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
  font-size: 14px;
  color: #606266;
}

.summary-row .amount {
  min-width: 100px;
  text-align: right;
  font-size: 14px;
}

.summary-row.total {
  margin-top: 8px;
  padding-top: 10px;
  border-top: 1px dashed #dcdfe6;
}

.total-amount {
  font-size: 22px;
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
</style>

