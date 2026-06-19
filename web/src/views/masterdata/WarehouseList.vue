<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  useCreateWarehouseMutation,
  useDeleteWarehouseMutation,
  useUpdateWarehouseMutation,
  useWarehousesQuery
} from '@/api/masterdata'
import type { Warehouse, WarehouseListQuery } from '@/types'

// 表单本地模型。
interface WarehouseForm {
  code: string
  name: string
  warehouse_type: string
  address: string
  contact_phone: string
  is_active: boolean
  notes: string
}

// ===== 查询条件与分页 =====
const filters = reactive({ keyword: '', warehouse_type: '' })
const page = ref(1)
const pageSize = ref(20)

const submittedQuery = reactive<WarehouseListQuery>({ keyword: '', warehouse_type: '' })

const query = computed<WarehouseListQuery>(() => ({
  keyword: submittedQuery.keyword,
  warehouse_type: submittedQuery.warehouse_type,
  page: page.value,
  page_size: pageSize.value
}))

const { data, isFetching } = useWarehousesQuery(query)

const rows = computed<Warehouse[]>(() => data.value?.results ?? [])
const total = computed(() => data.value?.count ?? 0)

function handleSearch() {
  submittedQuery.keyword = filters.keyword
  submittedQuery.warehouse_type = filters.warehouse_type
  page.value = 1
}

function handleReset() {
  filters.keyword = ''
  filters.warehouse_type = ''
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

const form = reactive<WarehouseForm>({
  code: '',
  name: '',
  warehouse_type: '',
  address: '',
  contact_phone: '',
  is_active: true,
  notes: ''
})

const rules: FormRules<WarehouseForm> = {
  code: [{ required: true, message: '请输入仓库编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入仓库名称', trigger: 'blur' }]
}

const dialogTitle = computed(() => (editingId.value === null ? '新建仓库' : '编辑仓库'))

function resetForm() {
  form.code = ''
  form.name = ''
  form.warehouse_type = ''
  form.address = ''
  form.contact_phone = ''
  form.is_active = true
  form.notes = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Warehouse) {
  editingId.value = row.id
  form.code = row.code
  form.name = row.name
  form.warehouse_type = row.warehouse_type
  form.address = row.address
  form.contact_phone = row.contact_phone
  form.is_active = row.is_active
  form.notes = row.notes
  dialogVisible.value = true
}

// ===== Mutations =====
const createMutation = useCreateWarehouseMutation()
const updateMutation = useUpdateWarehouseMutation()
const deleteMutation = useDeleteWarehouseMutation()

const submitting = computed(() => createMutation.isPending.value || updateMutation.isPending.value)

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    if (editingId.value === null) {
      await createMutation.mutateAsync({
        code: form.code,
        name: form.name,
        warehouse_type: form.warehouse_type || undefined,
        address: form.address,
        contact_phone: form.contact_phone,
        is_active: form.is_active,
        notes: form.notes
      })
      ElMessage.success('创建成功')
    } else {
      await updateMutation.mutateAsync({
        id: editingId.value,
        input: {
          name: form.name,
          warehouse_type: form.warehouse_type || null,
          address: form.address,
          contact_phone: form.contact_phone,
          is_active: form.is_active,
          notes: form.notes
        }
      })
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
  } catch {
    // 错误提示已由拦截器处理。
  }
}

async function handleDelete(row: Warehouse) {
  const confirmed = await ElMessageBox.confirm(`确认删除仓库「${row.name}」?`, '提示', { type: 'warning' })
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
    <PageHeader title="仓库管理" subtitle="masterdata / warehouses">
      <template #actions>
        <el-button v-permission="'masterdata:warehouse:create'" type="primary" @click="openCreate">
          新建仓库
        </el-button>
      </template>
    </PageHeader>

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input v-model="filters.keyword" placeholder="编码/名称" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="仓库类型">
        <el-input v-model="filters.warehouse_type" placeholder="如 MAIN" clearable @keyup.enter="handleSearch" />
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="rows" border stripe>
      <el-table-column prop="code" label="仓库编码" width="150" />
      <el-table-column prop="name" label="仓库名称" min-width="180" />
      <el-table-column prop="warehouse_type" label="类型" width="120" />
      <el-table-column prop="address" label="地址" min-width="160" show-overflow-tooltip />
      <el-table-column prop="contact_phone" label="联系电话" width="140" />
      <el-table-column label="启用" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '是' : '否' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'masterdata:warehouse:update'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-permission="'masterdata:warehouse:delete'" link type="danger" @click="handleDelete(row)">
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
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="仓库编码" prop="code">
          <el-input v-model="form.code" :disabled="editingId !== null" placeholder="仓库编码" />
        </el-form-item>
        <el-form-item label="仓库名称" prop="name">
          <el-input v-model="form.name" placeholder="仓库名称" />
        </el-form-item>
        <el-form-item label="类型">
          <el-input v-model="form.warehouse_type" placeholder="如 MAIN" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.address" placeholder="地址" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.contact_phone" placeholder="联系电话" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" placeholder="备注" />
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
