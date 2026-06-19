<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  useCreateQuotationMutation,
  useDeleteQuotationMutation,
  useQuotationsQuery,
  useUpdateQuotationMutation
} from '@/api/sales'
import type { Quotation, QuotationListQuery } from '@/types'

// 表单本地模型:数字字段允许 undefined(el-input-number 清空会触发),提交时回退/转后端入参。
interface QuotationForm {
  customer_id: number | undefined
  project_id: number | undefined
  valid_until: string
  tax_rate: number | undefined
  notes: string
}

// ===== 查询条件与分页 =====
const filters = reactive({ keyword: '', status: '', customer: '' })
const page = ref(1)
const pageSize = ref(20)

const submittedQuery = reactive<QuotationListQuery>({ keyword: '', status: '', customer: '' })

const query = computed<QuotationListQuery>(() => ({
  keyword: submittedQuery.keyword,
  status: submittedQuery.status,
  customer: submittedQuery.customer,
  page: page.value,
  page_size: pageSize.value
}))

const { data, isFetching } = useQuotationsQuery(query)

const rows = computed<Quotation[]>(() => data.value?.results ?? [])
const total = computed(() => data.value?.count ?? 0)

function handleSearch() {
  submittedQuery.keyword = filters.keyword
  submittedQuery.status = filters.status
  submittedQuery.customer = filters.customer
  page.value = 1
}

function handleReset() {
  filters.keyword = ''
  filters.status = ''
  filters.customer = ''
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

const form = reactive<QuotationForm>({
  customer_id: 0,
  project_id: 0,
  valid_until: '',
  tax_rate: 13,
  notes: ''
})

const rules: FormRules<QuotationForm> = {
  customer_id: [{ required: true, message: '请输入客户 ID', trigger: 'blur' }]
}

const dialogTitle = computed(() => (editingId.value === null ? '新建报价' : '编辑报价'))

function resetForm() {
  form.customer_id = 0
  form.project_id = 0
  form.valid_until = ''
  form.tax_rate = 13
  form.notes = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Quotation) {
  editingId.value = row.id
  form.customer_id = row.customer_id
  form.project_id = row.project_id ?? 0
  form.valid_until = row.valid_until ?? ''
  form.tax_rate = row.tax_rate
  form.notes = row.notes
  dialogVisible.value = true
}

// ===== Mutations =====
const createMutation = useCreateQuotationMutation()
const updateMutation = useUpdateQuotationMutation()
const deleteMutation = useDeleteQuotationMutation()

const submitting = computed(() => createMutation.isPending.value || updateMutation.isPending.value)

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  const payload = {
    customer_id: form.customer_id ?? 0,
    project_id: form.project_id || null,
    valid_until: form.valid_until || null,
    tax_rate: form.tax_rate ?? 0,
    notes: form.notes
  }

  try {
    if (editingId.value === null) {
      await createMutation.mutateAsync(payload)
      ElMessage.success('创建成功')
    } else {
      await updateMutation.mutateAsync({ id: editingId.value, input: payload })
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
  } catch {
    // 错误提示已由 request.ts 拦截器统一处理。
  }
}

async function handleDelete(row: Quotation) {
  const confirmed = await ElMessageBox.confirm(`确认删除报价「${row.quote_no}」?`, '提示', { type: 'warning' })
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
    <PageHeader title="销售报价" subtitle="sales / quotations">
      <template #actions>
        <el-button v-permission="'sales:quotation:create'" type="primary" @click="openCreate">新建报价</el-button>
      </template>
    </PageHeader>

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input v-model="filters.keyword" placeholder="报价单号" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="状态">
        <el-input v-model="filters.status" placeholder="状态" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="客户 ID">
        <el-input v-model="filters.customer" placeholder="客户 ID" clearable @keyup.enter="handleSearch" />
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="rows" border stripe>
      <el-table-column prop="quote_no" label="报价单号" width="180" />
      <el-table-column prop="customer_id" label="客户 ID" width="100" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="version" label="版本" width="80" align="right" />
      <el-table-column prop="valid_until" label="有效期至" width="140" />
      <el-table-column prop="tax_rate" label="税率%" width="90" align="right" />
      <el-table-column prop="total_with_tax" label="含税总额" width="140" align="right" />
      <el-table-column prop="notes" label="备注" min-width="160" show-overflow-tooltip />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'sales:quotation:update'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-permission="'sales:quotation:delete'" link type="danger" @click="handleDelete(row)">
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
        <el-form-item label="客户 ID" prop="customer_id">
          <el-input-number v-model="form.customer_id" :min="0" />
        </el-form-item>
        <el-form-item label="项目 ID">
          <el-input-number v-model="form.project_id" :min="0" />
        </el-form-item>
        <el-form-item label="有效期至">
          <el-input v-model="form.valid_until" placeholder="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="税率%">
          <el-input-number v-model="form.tax_rate" :min="0" :max="100" />
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
