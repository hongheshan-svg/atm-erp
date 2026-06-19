<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  useCreateWorkOrderMutation,
  useDeleteWorkOrderMutation,
  useUpdateWorkOrderMutation,
  useWorkOrdersQuery
} from '@/api/production'
import type { WorkOrder, WorkOrderListQuery } from '@/types'

// 表单本地模型(数字字段允许 undefined,el-input-number 清空会触发)。
interface WorkOrderForm {
  order_no: string
  project_id: number | undefined
  item_id: number | undefined
  quantity: number | undefined
  required_date: string
  work_center_id: number | undefined
  priority: number | undefined
  remarks: string
}

// ===== 查询条件与分页 =====
const filters = reactive({ keyword: '', status: '' })
const page = ref(1)
const pageSize = ref(20)

const submittedQuery = reactive<WorkOrderListQuery>({ keyword: '', status: '' })

const query = computed<WorkOrderListQuery>(() => ({
  keyword: submittedQuery.keyword,
  status: submittedQuery.status,
  page: page.value,
  page_size: pageSize.value
}))

const { data, isFetching } = useWorkOrdersQuery(query)

const rows = computed<WorkOrder[]>(() => data.value?.results ?? [])
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

const form = reactive<WorkOrderForm>({
  order_no: '',
  project_id: 0,
  item_id: 0,
  quantity: 1,
  required_date: '',
  work_center_id: 0,
  priority: 3,
  remarks: ''
})

const rules: FormRules<WorkOrderForm> = {
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  required_date: [{ required: true, message: '请输入需求日期', trigger: 'blur' }]
}

const dialogTitle = computed(() => (editingId.value === null ? '新建工单' : '编辑工单'))

function resetForm() {
  form.order_no = ''
  form.project_id = 0
  form.item_id = 0
  form.quantity = 1
  form.required_date = ''
  form.work_center_id = 0
  form.priority = 3
  form.remarks = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: WorkOrder) {
  editingId.value = row.id
  form.order_no = row.order_no
  form.project_id = row.project_id ?? 0
  form.item_id = row.item_id ?? 0
  form.quantity = row.quantity
  form.required_date = row.required_date
  form.work_center_id = row.work_center_id ?? 0
  form.priority = row.priority
  form.remarks = row.remarks
  dialogVisible.value = true
}

// ===== Mutations =====
const createMutation = useCreateWorkOrderMutation()
const updateMutation = useUpdateWorkOrderMutation()
const deleteMutation = useDeleteWorkOrderMutation()

const submitting = computed(() => createMutation.isPending.value || updateMutation.isPending.value)

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    if (editingId.value === null) {
      await createMutation.mutateAsync({
        order_no: form.order_no || undefined,
        project_id: form.project_id || null,
        item_id: form.item_id || null,
        quantity: form.quantity ?? 0,
        required_date: form.required_date,
        work_center_id: form.work_center_id || null,
        priority: form.priority ?? 3,
        remarks: form.remarks
      })
      ElMessage.success('创建成功')
    } else {
      await updateMutation.mutateAsync({
        id: editingId.value,
        input: {
          project_id: form.project_id || null,
          item_id: form.item_id || null,
          quantity: form.quantity ?? 0,
          required_date: form.required_date,
          work_center_id: form.work_center_id || null,
          priority: form.priority ?? 3,
          remarks: form.remarks
        }
      })
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
  } catch {
    // 错误提示已由拦截器处理。
  }
}

async function handleDelete(row: WorkOrder) {
  const confirmed = await ElMessageBox.confirm(`确认删除工单「${row.order_no}」?`, '提示', { type: 'warning' })
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
    <PageHeader title="生产工单" subtitle="production / work-orders">
      <template #actions>
        <el-button v-permission="'production:work_order:create'" type="primary" @click="openCreate">
          新建工单
        </el-button>
      </template>
    </PageHeader>

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input v-model="filters.keyword" placeholder="工单号" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="状态">
        <el-input v-model="filters.status" placeholder="状态" clearable @keyup.enter="handleSearch" />
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="rows" border stripe>
      <el-table-column prop="order_no" label="工单号" width="180" />
      <el-table-column prop="item_id" label="物料 ID" width="100" />
      <el-table-column prop="quantity" label="数量" width="100" align="right" />
      <el-table-column prop="completed_qty" label="完成数量" width="110" align="right" />
      <el-table-column prop="priority" label="优先级" width="90" align="right" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="required_date" label="需求日期" width="140" />
      <el-table-column prop="remarks" label="备注" min-width="160" show-overflow-tooltip />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'production:work_order:update'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-permission="'production:work_order:delete'" link type="danger" @click="handleDelete(row)">
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
        <el-form-item label="工单号">
          <el-input v-model="form.order_no" :disabled="editingId !== null" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="项目 ID">
          <el-input-number v-model="form.project_id" :min="0" />
        </el-form-item>
        <el-form-item label="物料 ID">
          <el-input-number v-model="form.item_id" :min="0" />
        </el-form-item>
        <el-form-item label="数量" prop="quantity">
          <el-input-number v-model="form.quantity" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="需求日期" prop="required_date">
          <el-input v-model="form.required_date" placeholder="YYYY-MM-DDTHH:mm:ssZ" />
        </el-form-item>
        <el-form-item label="工作中心 ID">
          <el-input-number v-model="form.work_center_id" :min="0" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="1" :max="5" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remarks" type="textarea" placeholder="备注" />
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
