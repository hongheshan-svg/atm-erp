<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  useCreateItemMutation,
  useDeleteItemMutation,
  useItemsQuery,
  useUpdateItemMutation
} from '@/api/masterdata'
import type { Item, ItemCreateInput, ItemListQuery } from '@/types'

// ===== 查询条件与分页 =====
const filters = reactive({ keyword: '' })
const page = ref(1)
const pageSize = ref(20)

const submittedQuery = reactive<ItemListQuery>({ keyword: '' })

const query = computed<ItemListQuery>(() => ({
  keyword: submittedQuery.keyword,
  page: page.value,
  page_size: pageSize.value
}))

const { data, isFetching } = useItemsQuery(query)

const items = computed<Item[]>(() => data.value?.results ?? [])
const total = computed(() => data.value?.count ?? 0)

function handleSearch() {
  submittedQuery.keyword = filters.keyword
  page.value = 1
}

function handleReset() {
  filters.keyword = ''
  handleSearch()
}

function handlePageChange(val: number) {
  page.value = val
}

function handleSizeChange(val: number) {
  pageSize.value = val
  page.value = 1
}

// ===== 新建/编辑对话框 =====
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const form = reactive<ItemCreateInput>({
  sku: '',
  name: '',
  specification: '',
  unit: '',
  standard_cost: 0
})

const rules: FormRules<ItemCreateInput> = {
  sku: [{ required: true, message: '请输入 SKU', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }]
}

const dialogTitle = computed(() => (editingId.value === null ? '新建物料' : '编辑物料'))

function resetForm() {
  form.sku = ''
  form.name = ''
  form.specification = ''
  form.unit = ''
  form.standard_cost = 0
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Item) {
  editingId.value = row.id
  form.sku = row.sku
  form.name = row.name
  form.specification = row.specification
  form.unit = row.unit
  form.standard_cost = row.standard_cost
  dialogVisible.value = true
}

// ===== Mutations =====
const createMutation = useCreateItemMutation()
const updateMutation = useUpdateItemMutation()
const deleteMutation = useDeleteItemMutation()

const submitting = computed(() => createMutation.isPending.value || updateMutation.isPending.value)

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    if (editingId.value === null) {
      await createMutation.mutateAsync({ ...form })
      ElMessage.success('创建成功')
    } else {
      await updateMutation.mutateAsync({
        id: editingId.value,
        input: {
          name: form.name,
          specification: form.specification,
          unit: form.unit,
          standard_cost: form.standard_cost
        }
      })
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
  } catch {
    // 错误提示已由 request.ts 拦截器统一处理。
  }
}

async function handleDelete(row: Item) {
  const confirmed = await ElMessageBox.confirm(`确认删除物料「${row.name}」?`, '提示', { type: 'warning' })
    .then(() => true)
    .catch(() => false)
  if (!confirmed) return

  try {
    await deleteMutation.mutateAsync(row.id)
    ElMessage.success('删除成功')
  } catch {
    // 错误提示已由拦截器处理。
  }
}
</script>

<template>
  <div>
    <PageHeader title="物料管理" subtitle="masterdata / items">
      <template #actions>
        <el-button v-permission="'masterdata:item:create'" type="primary" @click="openCreate">新建物料</el-button>
      </template>
    </PageHeader>

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input v-model="filters.keyword" placeholder="SKU/名称" clearable @keyup.enter="handleSearch" />
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="items" border stripe>
      <el-table-column prop="sku" label="SKU" width="160" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="specification" label="规格" min-width="140" />
      <el-table-column prop="unit" label="单位" width="90" />
      <el-table-column prop="standard_cost" label="标准成本" width="120" align="right" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'masterdata:item:update'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-permission="'masterdata:item:delete'" link type="danger" @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      layout="total, prev, pager, next, sizes"
      :total="total"
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      @current-change="handlePageChange"
      @size-change="handleSizeChange"
    />

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="SKU" prop="sku">
          <el-input v-model="form.sku" :disabled="editingId !== null" placeholder="物料 SKU" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="物料名称" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="form.specification" placeholder="规格" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="form.unit" placeholder="单位" />
        </el-form-item>
        <el-form-item label="标准成本">
          <el-input-number v-model="form.standard_cost" :min="0" :precision="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
