<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  useCreateStockMoveMutation,
  useDeleteStockMoveMutation,
  useStockMovesQuery,
  useUpdateStockMoveMutation
} from '@/api/inventory'
import type { StockMove, StockMoveListQuery } from '@/types'

// 表单本地模型(数字字段允许 undefined,el-input-number 清空会触发)。
interface StockMoveForm {
  item_id: number | undefined
  warehouse_from: number | undefined
  warehouse_to: number | undefined
  qty: number | undefined
  unit_cost: number | undefined
  move_type: string
  move_date: string
  notes: string
}

// 移动类型选项(对齐后端 choices)。
const moveTypeOptions = [
  { label: '采购入库', value: 'IN_PURCHASE' },
  { label: '销售出库', value: 'OUT_SALES' },
  { label: '项目领料', value: 'OUT_PROJECT' },
  { label: '调拨', value: 'TRANSFER' },
  { label: '调整', value: 'ADJUSTMENT' }
]

// ===== 查询条件与分页 =====
const filters = reactive({ move_type: '', status: '' })
const itemIdFilter = ref<number | undefined>(0)
const page = ref(1)
const pageSize = ref(20)

const submittedQuery = reactive<StockMoveListQuery>({ move_type: '', status: '' })

const query = computed<StockMoveListQuery>(() => ({
  item_id: submittedQuery.item_id,
  move_type: submittedQuery.move_type,
  status: submittedQuery.status,
  page: page.value,
  page_size: pageSize.value
}))

const { data, isFetching } = useStockMovesQuery(query)

const rows = computed<StockMove[]>(() => data.value?.results ?? [])
const total = computed(() => data.value?.count ?? 0)

function handleSearch() {
  submittedQuery.item_id = itemIdFilter.value || undefined
  submittedQuery.move_type = filters.move_type
  submittedQuery.status = filters.status
  page.value = 1
}

function handleReset() {
  itemIdFilter.value = 0
  filters.move_type = ''
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

const form = reactive<StockMoveForm>({
  item_id: 0,
  warehouse_from: 0,
  warehouse_to: 0,
  qty: 0,
  unit_cost: 0,
  move_type: '',
  move_date: '',
  notes: ''
})

const rules: FormRules<StockMoveForm> = {
  item_id: [{ required: true, message: '请输入物料 ID', trigger: 'blur' }],
  qty: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  move_type: [{ required: true, message: '请选择移动类型', trigger: 'change' }],
  move_date: [{ required: true, message: '请输入移动日期', trigger: 'blur' }]
}

const dialogTitle = computed(() => (editingId.value === null ? '新建库存移动' : '编辑库存移动'))

function resetForm() {
  form.item_id = 0
  form.warehouse_from = 0
  form.warehouse_to = 0
  form.qty = 0
  form.unit_cost = 0
  form.move_type = ''
  form.move_date = ''
  form.notes = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: StockMove) {
  editingId.value = row.id
  form.item_id = row.item_id
  form.warehouse_from = row.warehouse_from ?? 0
  form.warehouse_to = row.warehouse_to ?? 0
  form.qty = row.qty
  form.unit_cost = row.unit_cost
  form.move_type = row.move_type
  form.move_date = row.move_date
  form.notes = row.notes
  dialogVisible.value = true
}

// ===== Mutations =====
const createMutation = useCreateStockMoveMutation()
const updateMutation = useUpdateStockMoveMutation()
const deleteMutation = useDeleteStockMoveMutation()

const submitting = computed(() => createMutation.isPending.value || updateMutation.isPending.value)

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    if (editingId.value === null) {
      await createMutation.mutateAsync({
        item_id: form.item_id ?? 0,
        warehouse_from: form.warehouse_from || null,
        warehouse_to: form.warehouse_to || null,
        qty: form.qty ?? 0,
        unit_cost: form.unit_cost ?? 0,
        move_type: form.move_type,
        move_date: form.move_date,
        notes: form.notes
      })
      ElMessage.success('创建成功')
    } else {
      await updateMutation.mutateAsync({
        id: editingId.value,
        input: {
          warehouse_from: form.warehouse_from || null,
          warehouse_to: form.warehouse_to || null,
          qty: form.qty ?? 0,
          unit_cost: form.unit_cost ?? 0,
          move_type: form.move_type,
          move_date: form.move_date,
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

async function handleDelete(row: StockMove) {
  const confirmed = await ElMessageBox.confirm(`确认删除库存移动「${row.move_no}」?`, '提示', { type: 'warning' })
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
    <PageHeader title="库存移动" subtitle="inventory / stock-moves">
      <template #actions>
        <el-button v-permission="'inventory:stock_move:create'" type="primary" @click="openCreate">
          新建库存移动
        </el-button>
      </template>
    </PageHeader>

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="物料 ID">
        <el-input-number v-model="itemIdFilter" :min="0" />
      </el-form-item>
      <el-form-item label="移动类型">
        <el-select v-model="filters.move_type" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="o in moveTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-input v-model="filters.status" placeholder="状态" clearable @keyup.enter="handleSearch" />
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="rows" border stripe>
      <el-table-column prop="move_no" label="移动单号" width="180" />
      <el-table-column prop="item_id" label="物料 ID" width="100" />
      <el-table-column prop="move_type" label="移动类型" width="120" />
      <el-table-column prop="qty" label="数量" width="110" align="right" />
      <el-table-column prop="unit_cost" label="单位成本" width="120" align="right" />
      <el-table-column prop="warehouse_from" label="源仓" width="90" />
      <el-table-column prop="warehouse_to" label="目标仓" width="90" />
      <el-table-column prop="status" label="状态" width="110" />
      <el-table-column prop="move_date" label="移动日期" width="130" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'inventory:stock_move:update'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-permission="'inventory:stock_move:delete'" link type="danger" @click="handleDelete(row)">
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
        <el-form-item label="物料 ID" prop="item_id">
          <el-input-number v-model="form.item_id" :min="0" :disabled="editingId !== null" />
        </el-form-item>
        <el-form-item label="移动类型" prop="move_type">
          <el-select v-model="form.move_type" placeholder="请选择" style="width: 100%">
            <el-option v-for="o in moveTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="数量" prop="qty">
          <el-input-number v-model="form.qty" :precision="2" />
        </el-form-item>
        <el-form-item label="单位成本">
          <el-input-number v-model="form.unit_cost" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="源仓库 ID">
          <el-input-number v-model="form.warehouse_from" :min="0" />
        </el-form-item>
        <el-form-item label="目标仓 ID">
          <el-input-number v-model="form.warehouse_to" :min="0" />
        </el-form-item>
        <el-form-item label="移动日期" prop="move_date">
          <el-input v-model="form.move_date" placeholder="YYYY-MM-DD" />
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
