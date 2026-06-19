<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  useCreateReceivableMutation,
  useDeleteReceivableMutation,
  useReceivablesQuery,
  useUpdateReceivableMutation
} from '@/api/finance'
import type { Receivable, ReceivableListQuery } from '@/types'

// 表单本地模型(数字字段允许 undefined,el-input-number 清空会触发)。
interface ReceivableForm {
  customer_id: number | undefined
  invoice_no: string
  invoice_date: string
  amount_due: number | undefined
  amount_paid: number | undefined
  due_date: string
  status: string
}

// ===== 查询条件与分页 =====
const filters = reactive({ keyword: '', status: '' })
const page = ref(1)
const pageSize = ref(20)

const submittedQuery = reactive<ReceivableListQuery>({ keyword: '', status: '' })

const query = computed<ReceivableListQuery>(() => ({
  keyword: submittedQuery.keyword,
  status: submittedQuery.status,
  page: page.value,
  page_size: pageSize.value
}))

const { data, isFetching } = useReceivablesQuery(query)

const rows = computed<Receivable[]>(() => data.value?.results ?? [])
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

const form = reactive<ReceivableForm>({
  customer_id: 0,
  invoice_no: '',
  invoice_date: '',
  amount_due: 0,
  amount_paid: 0,
  due_date: '',
  status: ''
})

const rules: FormRules<ReceivableForm> = {
  customer_id: [{ required: true, message: '请输入客户 ID', trigger: 'blur' }],
  invoice_date: [{ required: true, message: '请输入开票日期', trigger: 'blur' }],
  amount_due: [{ required: true, message: '请输入应收金额', trigger: 'blur' }],
  due_date: [{ required: true, message: '请输入到期日期', trigger: 'blur' }]
}

const dialogTitle = computed(() => (editingId.value === null ? '新建应收' : '编辑应收'))

function resetForm() {
  form.customer_id = 0
  form.invoice_no = ''
  form.invoice_date = ''
  form.amount_due = 0
  form.amount_paid = 0
  form.due_date = ''
  form.status = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Receivable) {
  editingId.value = row.id
  form.customer_id = row.customer_id
  form.invoice_no = row.invoice_no
  form.invoice_date = row.invoice_date
  form.amount_due = row.amount_due
  form.amount_paid = row.amount_paid
  form.due_date = row.due_date
  form.status = row.status
  dialogVisible.value = true
}

// ===== Mutations =====
const createMutation = useCreateReceivableMutation()
const updateMutation = useUpdateReceivableMutation()
const deleteMutation = useDeleteReceivableMutation()

const submitting = computed(() => createMutation.isPending.value || updateMutation.isPending.value)

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    if (editingId.value === null) {
      await createMutation.mutateAsync({
        customer_id: form.customer_id ?? 0,
        invoice_no: form.invoice_no,
        invoice_date: form.invoice_date,
        amount_due: form.amount_due ?? 0,
        amount_paid: form.amount_paid ?? 0,
        due_date: form.due_date
      })
      ElMessage.success('创建成功')
    } else {
      await updateMutation.mutateAsync({
        id: editingId.value,
        input: {
          customer_id: form.customer_id ?? 0,
          invoice_no: form.invoice_no,
          invoice_date: form.invoice_date,
          amount_due: form.amount_due ?? 0,
          amount_paid: form.amount_paid ?? 0,
          due_date: form.due_date,
          status: form.status || null
        }
      })
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
  } catch {
    // 错误提示已由拦截器处理。
  }
}

async function handleDelete(row: Receivable) {
  const confirmed = await ElMessageBox.confirm(`确认删除应收「${row.ar_no}」?`, '提示', { type: 'warning' })
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
    <PageHeader title="应收账款" subtitle="finance / receivables">
      <template #actions>
        <el-button v-permission="'finance:receivable:create'" type="primary" @click="openCreate">新建应收</el-button>
      </template>
    </PageHeader>

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input v-model="filters.keyword" placeholder="应收单号/发票号" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="状态">
        <el-input v-model="filters.status" placeholder="状态" clearable @keyup.enter="handleSearch" />
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="rows" border stripe>
      <el-table-column prop="ar_no" label="应收单号" width="180" />
      <el-table-column prop="customer_id" label="客户 ID" width="100" />
      <el-table-column prop="invoice_no" label="发票号" width="160" />
      <el-table-column prop="amount_due" label="应收金额" width="140" align="right" />
      <el-table-column prop="amount_paid" label="已收金额" width="140" align="right" />
      <el-table-column prop="due_date" label="到期日期" width="140" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'finance:receivable:update'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-permission="'finance:receivable:delete'" link type="danger" @click="handleDelete(row)">
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
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="客户 ID" prop="customer_id">
          <el-input-number v-model="form.customer_id" :min="0" />
        </el-form-item>
        <el-form-item label="发票号">
          <el-input v-model="form.invoice_no" placeholder="发票号" />
        </el-form-item>
        <el-form-item label="开票日期" prop="invoice_date">
          <el-input v-model="form.invoice_date" placeholder="YYYY-MM-DDTHH:mm:ssZ" />
        </el-form-item>
        <el-form-item label="应收金额" prop="amount_due">
          <el-input-number v-model="form.amount_due" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="已收金额">
          <el-input-number v-model="form.amount_paid" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="到期日期" prop="due_date">
          <el-input v-model="form.due_date" placeholder="YYYY-MM-DDTHH:mm:ssZ" />
        </el-form-item>
        <el-form-item v-if="editingId !== null" label="状态">
          <el-input v-model="form.status" placeholder="如 PENDING" />
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
