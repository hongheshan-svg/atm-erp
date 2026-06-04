<template>
  <div class="spare-part-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>备件管理</span>
          <el-button type="primary" v-permission="'inventory:stock:create'" @click="handleCreate">新增备件</el-button>
        </div>
      </template>
      
      <el-form :inline="true" class="filter-form">
        <el-form-item label="分类">
          <el-select v-model="filters.category" clearable @change="loadData">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键字">
          <el-input v-model="filters.search" placeholder="搜索备件" clearable @clear="loadData" @keyup.enter="loadData" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
        </el-form-item>
      </el-form>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="spare_part_no" label="备件编号" width="140" />
        <el-table-column prop="name" label="备件名称" />
        <el-table-column prop="category_name" label="分类" width="120" />
        <el-table-column prop="specification" label="规格" width="120" />
        <el-table-column prop="current_stock" label="当前库存" width="100" align="right" />
        <el-table-column prop="safety_stock" label="安全库存" width="100" align="right" />
        <el-table-column prop="unit_price" label="单价" width="100" align="right">
          <template #default="{ row }">¥ {{ row.unit_price }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" v-permission="'inventory:stock:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="handleConsume(row)">消耗</el-button>
            <el-button link type="danger" v-permission="'inventory:stock:delete'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadData" />
    </el-card>

    <!-- 新增/编辑 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑备件' : '新增备件'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="备件名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" placeholder="选择分类" style="width: 100%">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="form.specification" />
        </el-form-item>
        <el-form-item label="单价">
          <el-input-number v-model="form.unit_price" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="安全库存">
          <el-input-number v-model="form.safety_stock" :min="0" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 消耗 -->
    <el-dialog v-model="consumeDialogVisible" title="备件消耗" width="500px">
      <el-form ref="consumeFormRef" :model="consumeForm" :rules="consumeRules" label-width="100px">
        <el-form-item label="备件">{{ currentRow?.name }}</el-form-item>
        <el-form-item label="当前库存">{{ currentRow?.current_stock }}</el-form-item>
        <el-form-item label="消耗数量" prop="quantity">
          <el-input-number v-model="consumeForm.quantity" :min="1" :max="currentRow?.current_stock || 99999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="消耗原因">
          <el-input v-model="consumeForm.reason" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="consumeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleConsumeSubmit">确认消耗</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSpareParts, getSparePartCategories, updateSparePart, createSparePart, consumeSparePart, deleteSparePart } from '@/api/inventory'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/inventory/spare-parts/', { onSuccess: () => loadData() })


const loading = ref(false)
const saving = ref(false)
const tableData = ref<any[]>([])
const categories = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filters = ref({ category: null, search: '' })
const dialogVisible = ref(false)
const consumeDialogVisible = ref(false)
const isEdit = ref(false)
const currentRow = ref(null)
const formRef = ref(null)
const consumeFormRef = ref(null)

const form = reactive({ id: null, name: '', category: null, specification: '', unit_price: 0, safety_stock: 0 })
const consumeForm = reactive({ quantity: 1, reason: '' })
const rules = { name: [{ required: true, message: '请输入备件名称', trigger: 'blur' }] }
const consumeRules = { quantity: [{ required: true, message: '请输入消耗数量', trigger: 'change' }] }

const loadData = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value, ...filters.value }
    const res = await getSpareParts(params)
    tableData.value = res.results || res.results || []
    total.value = res.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadCategories = async () => {
  try {
    const res = await getSparePartCategories()
    categories.value = res.results || res.results || []
  } catch (error) {
    console.error('SparePartList getSparePartCategories error:', error)
  }
}

const handleCreate = () => {
  isEdit.value = false
  Object.assign(form, { id: null, name: '', category: null, specification: '', unit_price: 0, safety_stock: 0 })
  formRef.value?.resetFields()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  Object.assign(form, { id: row.id, name: row.name, category: row.category, specification: row.specification, unit_price: row.unit_price, safety_stock: row.safety_stock })
  dialogVisible.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    saving.value = true
    if (isEdit.value) {
      await updateSparePart(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createSparePart(form)
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

const handleConsume = (row) => {
  currentRow.value = row
  Object.assign(consumeForm, { quantity: 1, reason: '' })
  consumeFormRef.value?.resetFields()
  consumeDialogVisible.value = true
}

const handleConsumeSubmit = async () => {
  try {
    await consumeFormRef.value?.validate()
    saving.value = true
    await consumeSparePart(currentRow.value.id, consumeForm)
    ElMessage.success('消耗记录已保存')
    consumeDialogVisible.value = false
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该备件吗？', '提示', { type: 'warning' })
    await deleteSparePart(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => { loadCategories(); loadData() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filter-form { margin-bottom: 20px; }
.el-pagination { margin-top: 20px; }
</style>
