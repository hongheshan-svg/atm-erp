<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  useCreateCustomerMutation,
  useCustomersQuery,
  useDeleteCustomerMutation,
  useUpdateCustomerMutation
} from '@/api/masterdata'
import type { Customer, CustomerListQuery } from '@/types'

// 表单本地模型(credit_limit 允许 undefined,el-input-number 清空会触发)。
interface CustomerForm {
  code: string
  name: string
  short_name: string
  contact_person: string
  phone: string
  email: string
  credit_limit: number | undefined
  status: string
  notes: string
}

// ===== 查询条件与分页 =====
const filters = reactive({ keyword: '', status: '' })
const page = ref(1)
const pageSize = ref(20)

const submittedQuery = reactive<CustomerListQuery>({ keyword: '', status: '' })

const query = computed<CustomerListQuery>(() => ({
  keyword: submittedQuery.keyword,
  status: submittedQuery.status,
  page: page.value,
  page_size: pageSize.value
}))

const { data, isFetching } = useCustomersQuery(query)

const rows = computed<Customer[]>(() => data.value?.results ?? [])
const total = computed(() => data.value?.count ?? 0)

function handleSearch() {
  submittedQuery.keyword = filters.keyword
  submittedQuery.status = filters.status
  page.value = 1
}

function handleReset() {
  filters.keyword = ''
  filters.status = ''
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

const form = reactive<CustomerForm>({
  code: '',
  name: '',
  short_name: '',
  contact_person: '',
  phone: '',
  email: '',
  credit_limit: 0,
  status: '',
  notes: ''
})

const rules: FormRules<CustomerForm> = {
  name: [{ required: true, message: '请输入客户名称', trigger: 'blur' }]
}

const dialogTitle = computed(() => (editingId.value === null ? '新建客户' : '编辑客户'))

function resetForm() {
  form.code = ''
  form.name = ''
  form.short_name = ''
  form.contact_person = ''
  form.phone = ''
  form.email = ''
  form.credit_limit = 0
  form.status = ''
  form.notes = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Customer) {
  editingId.value = row.id
  form.code = row.code
  form.name = row.name
  form.short_name = row.short_name
  form.contact_person = row.contact_person
  form.phone = row.phone
  form.email = row.email
  form.credit_limit = row.credit_limit
  form.status = row.status
  form.notes = row.notes
  dialogVisible.value = true
}

// ===== Mutations =====
const createMutation = useCreateCustomerMutation()
const updateMutation = useUpdateCustomerMutation()
const deleteMutation = useDeleteCustomerMutation()

const submitting = computed(() => createMutation.isPending.value || updateMutation.isPending.value)

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    if (editingId.value === null) {
      await createMutation.mutateAsync({
        code: form.code || undefined,
        name: form.name,
        short_name: form.short_name,
        contact_person: form.contact_person,
        phone: form.phone,
        email: form.email,
        credit_limit: form.credit_limit ?? 0,
        status: form.status || undefined,
        notes: form.notes
      })
      ElMessage.success('创建成功')
    } else {
      await updateMutation.mutateAsync({
        id: editingId.value,
        input: {
          name: form.name,
          short_name: form.short_name,
          contact_person: form.contact_person,
          phone: form.phone,
          email: form.email,
          credit_limit: form.credit_limit ?? 0,
          status: form.status || null,
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

async function handleDelete(row: Customer) {
  const confirmed = await ElMessageBox.confirm(`确认删除客户「${row.name}」?`, '提示', { type: 'warning' })
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
    <PageHeader title="客户管理" subtitle="masterdata / customers">
      <template #actions>
        <el-button v-permission="'masterdata:customer:create'" type="primary" @click="openCreate">新建客户</el-button>
      </template>
    </PageHeader>

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input v-model="filters.keyword" placeholder="编码/名称/简称" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="状态">
        <el-input v-model="filters.status" placeholder="状态" clearable @keyup.enter="handleSearch" />
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="rows" border stripe>
      <el-table-column prop="code" label="客户编码" width="150" />
      <el-table-column prop="name" label="客户名称" min-width="180" />
      <el-table-column prop="short_name" label="简称" width="120" />
      <el-table-column prop="contact_person" label="联系人" width="120" />
      <el-table-column prop="phone" label="电话" width="140" />
      <el-table-column prop="credit_limit" label="信用额度" width="130" align="right" />
      <el-table-column prop="status" label="状态" width="110" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'masterdata:customer:update'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-permission="'masterdata:customer:delete'" link type="danger" @click="handleDelete(row)">
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
        <el-form-item label="客户编码">
          <el-input v-model="form.code" :disabled="editingId !== null" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="客户名称" prop="name">
          <el-input v-model="form.name" placeholder="客户名称" />
        </el-form-item>
        <el-form-item label="简称">
          <el-input v-model="form.short_name" placeholder="简称" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact_person" placeholder="联系人" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" placeholder="电话" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="邮箱" />
        </el-form-item>
        <el-form-item label="信用额度">
          <el-input-number v-model="form.credit_limit" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="状态">
          <el-input v-model="form.status" placeholder="如 ACTIVE" />
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
