<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  useCreatePurchaseOrderMutation,
  useDeletePurchaseOrderMutation,
  usePurchaseOrdersQuery,
  useUpdatePurchaseOrderMutation
} from '@/api/purchase'
import type { PurchaseOrder, PurchaseOrderListQuery } from '@/types'

// 表单本地模型:数字字段允许 undefined(el-input-number 清空会触发),提交时回退/转后端入参。
interface PurchaseOrderForm {
  supplier_id: number | undefined
  project_id: number | undefined
  delivery_date: string
  tax_rate: number | undefined
  payment_terms: string
  payment_method: string
  notes: string
}

// ===== 查询条件与分页 =====
const filters = reactive({ keyword: '', status: '' })
const page = ref(1)
const pageSize = ref(20)

const submittedQuery = reactive<PurchaseOrderListQuery>({ keyword: '', status: '' })

const query = computed<PurchaseOrderListQuery>(() => ({
  keyword: submittedQuery.keyword,
  status: submittedQuery.status,
  page: page.value,
  page_size: pageSize.value
}))

const { data, isFetching } = usePurchaseOrdersQuery(query)

const rows = computed<PurchaseOrder[]>(() => data.value?.results ?? [])
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

const form = reactive<PurchaseOrderForm>({
  supplier_id: 0,
  project_id: 0,
  delivery_date: '',
  tax_rate: 13,
  payment_terms: '',
  payment_method: '',
  notes: ''
})

const rules: FormRules<PurchaseOrderForm> = {
  supplier_id: [{ required: true, message: '请输入供应商 ID', trigger: 'blur' }],
  delivery_date: [{ required: true, message: '请输入交货日期', trigger: 'blur' }]
}

const dialogTitle = computed(() => (editingId.value === null ? '新建采购订单' : '编辑采购订单'))

function resetForm() {
  form.supplier_id = 0
  form.project_id = 0
  form.delivery_date = ''
  form.tax_rate = 13
  form.payment_terms = ''
  form.payment_method = ''
  form.notes = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: PurchaseOrder) {
  editingId.value = row.id
  form.supplier_id = row.supplier_id
  form.project_id = row.project_id ?? 0
  form.delivery_date = row.delivery_date
  form.tax_rate = row.tax_rate
  form.payment_terms = row.payment_terms
  form.payment_method = row.payment_method
  form.notes = row.notes
  dialogVisible.value = true
}

// ===== Mutations =====
const createMutation = useCreatePurchaseOrderMutation()
const updateMutation = useUpdatePurchaseOrderMutation()
const deleteMutation = useDeletePurchaseOrderMutation()

const submitting = computed(() => createMutation.isPending.value || updateMutation.isPending.value)

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  const payload = {
    supplier_id: form.supplier_id ?? 0,
    project_id: form.project_id || null,
    delivery_date: form.delivery_date,
    tax_rate: form.tax_rate ?? 0,
    payment_terms: form.payment_terms,
    payment_method: form.payment_method,
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
    // 错误提示已由拦截器处理。
  }
}

async function handleDelete(row: PurchaseOrder) {
  const confirmed = await ElMessageBox.confirm(`确认删除采购订单「${row.order_no}」?`, '提示', { type: 'warning' })
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
    <PageHeader title="采购订单" subtitle="purchase / orders">
      <template #actions>
        <el-button v-permission="'purchase:order:create'" type="primary" @click="openCreate">新建采购订单</el-button>
      </template>
    </PageHeader>

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input v-model="filters.keyword" placeholder="订单号" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="状态">
        <el-input v-model="filters.status" placeholder="状态" clearable @keyup.enter="handleSearch" />
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="rows" border stripe>
      <el-table-column prop="order_no" label="订单号" width="180" />
      <el-table-column prop="supplier_id" label="供应商 ID" width="110" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="order_date" label="下单日期" width="140" />
      <el-table-column prop="delivery_date" label="交货日期" width="140" />
      <el-table-column prop="tax_rate" label="税率%" width="90" align="right" />
      <el-table-column prop="total_with_tax" label="含税总额" width="140" align="right" />
      <el-table-column prop="notes" label="备注" min-width="160" show-overflow-tooltip />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'purchase:order:update'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-permission="'purchase:order:delete'" link type="danger" @click="handleDelete(row)">
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
        <el-form-item label="供应商 ID" prop="supplier_id">
          <el-input-number v-model="form.supplier_id" :min="0" />
        </el-form-item>
        <el-form-item label="项目 ID">
          <el-input-number v-model="form.project_id" :min="0" />
        </el-form-item>
        <el-form-item label="交货日期" prop="delivery_date">
          <el-input v-model="form.delivery_date" placeholder="YYYY-MM-DDTHH:mm:ssZ" />
        </el-form-item>
        <el-form-item label="税率%">
          <el-input-number v-model="form.tax_rate" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="付款条款">
          <el-input v-model="form.payment_terms" placeholder="如 NET30" />
        </el-form-item>
        <el-form-item label="付款方式">
          <el-input v-model="form.payment_method" placeholder="如 WIRE" />
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
