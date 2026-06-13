<template>
  <div class="outsource-capability-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>外协加工能力</span>
          <el-button type="primary" @click="handleCreate">新增能力</el-button>
        </div>
      </template>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="supplier_name" label="供应商" width="150" />
        <el-table-column prop="process_type_display" label="加工类型" width="120" />
        <el-table-column prop="process_detail" label="工艺明细" />
        <el-table-column prop="daily_capacity" label="日产能" width="100" />
        <el-table-column prop="capacity_unit" label="单位" width="80" />
        <el-table-column prop="quality_rating" label="质量评级" width="100">
          <template #default="{ row }">
            <el-rate v-model="row.quality_rating" disabled />
          </template>
        </el-table-column>
        <el-table-column prop="is_verified" label="已验证" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_verified" type="success">是</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑加工能力' : '新增加工能力'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="供应商" prop="supplier">
          <el-select v-model="form.supplier" placeholder="选择供应商" filterable style="width: 100%">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="加工类型" prop="process_type">
          <el-select v-model="form.process_type" placeholder="选择类型" style="width: 100%">
            <el-option label="机加工" value="MACHINING" />
            <el-option label="焊接" value="WELDING" />
            <el-option label="喷涂/烤漆" value="PAINTING" />
            <el-option label="电镀" value="PLATING" />
            <el-option label="热处理" value="HEAT_TREAT" />
            <el-option label="表面处理" value="SURFACE" />
            <el-option label="装配" value="ASSEMBLY" />
            <el-option label="测试" value="TESTING" />
            <el-option label="激光加工" value="LASER" />
            <el-option label="冲压" value="STAMPING" />
            <el-option label="铸造" value="CASTING" />
            <el-option label="锻造" value="FORGING" />
            <el-option label="注塑" value="INJECTION" />
            <el-option label="PCB制造" value="PCB" />
            <el-option label="SMT贴片" value="SMT" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="工艺明细" prop="process_detail">
          <el-input v-model="form.process_detail" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="日产能" prop="daily_capacity">
          <el-input-number v-model="form.daily_capacity" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="产能单位" prop="capacity_unit">
          <el-input v-model="form.capacity_unit" style="width: 100%" />
        </el-form-item>
        <el-form-item label="质量评级">
          <el-rate v-model="form.quality_rating" />
        </el-form-item>
        <el-form-item label="已验证">
          <el-switch v-model="form.is_verified" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSupplierList } from '@/api/masterdata'
import {
getOutsourceCapabilities, createOutsourceCapability, updateOutsourceCapability, deleteOutsourceCapability
} from '@/api/purchase'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/purchase/outsource-capabilities/', { onSuccess: () => loadData() })


const loading = ref(false)
const saving = ref(false)
const tableData = ref<any[]>([])
const suppliers = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null, supplier: null, process_type: '', process_detail: '',
  daily_capacity: 0, capacity_unit: '件', quality_rating: 0, is_verified: false
})

const rules = {
  supplier: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  process_type: [{ required: true, message: '请选择加工类型', trigger: 'change' }]
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await getOutsourceCapabilities({ page: page.value, page_size: pageSize.value })
    tableData.value = res.results || res.results || []
    total.value = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadSuppliers = async () => {
  try {
    const res = await getSupplierList({ page_size: 1000 })
    suppliers.value = res.results || res.results || []
  } catch (error) {
    console.error('OutsourceCapabilityList getSupplierList error:', error)
  }
}

const handleCreate = () => {
  isEdit.value = false
  Object.assign(form, { id: null, supplier: null, process_type: '', process_detail: '', daily_capacity: 0, capacity_unit: '件', quality_rating: 0, is_verified: false })
  formRef.value?.resetFields()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, { id: row.id, supplier: row.supplier, process_type: row.process_type, process_detail: row.process_detail, daily_capacity: row.daily_capacity, capacity_unit: row.capacity_unit, quality_rating: row.quality_rating, is_verified: row.is_verified })
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    if (isEdit.value) {
      await updateOutsourceCapability(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createOutsourceCapability(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    if (error.response?.data) ElMessage.error(JSON.stringify(error.response.data))
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除此记录吗？', '提示', { type: 'warning' })
    await deleteOutsourceCapability(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => { loadSuppliers(); loadData() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.el-pagination { margin-top: 20px; }
</style>
