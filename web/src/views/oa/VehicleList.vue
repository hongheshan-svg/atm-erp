<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  useCreateVehicleMutation,
  useDeleteVehicleMutation,
  useUpdateVehicleMutation,
  useVehiclesQuery
} from '@/api/oa'
import type { Vehicle, VehicleListQuery } from '@/types'

// 表单本地模型(数字字段允许 undefined,el-input-number 清空会触发)。
interface VehicleForm {
  plate_number: string
  vehicle_type: string
  brand: string
  model: string
  color: string
  seats: number | undefined
  current_mileage: number | undefined
  status: string
  notes: string
}

// ===== 查询条件与分页(后端关键字参数为 search)=====
const filters = reactive({ search: '', status: '', vehicle_type: '' })
const page = ref(1)
const pageSize = ref(20)

const submittedQuery = reactive<VehicleListQuery>({ search: '', status: '', vehicle_type: '' })

const query = computed<VehicleListQuery>(() => ({
  search: submittedQuery.search,
  status: submittedQuery.status,
  vehicle_type: submittedQuery.vehicle_type,
  page: page.value,
  page_size: pageSize.value
}))

const { data, isFetching } = useVehiclesQuery(query)

const rows = computed<Vehicle[]>(() => data.value?.results ?? [])
const total = computed(() => data.value?.count ?? 0)

function handleSearch() {
  submittedQuery.search = filters.search
  submittedQuery.status = filters.status
  submittedQuery.vehicle_type = filters.vehicle_type
  page.value = 1
}

function handleReset() {
  filters.search = ''
  filters.status = ''
  filters.vehicle_type = ''
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

const form = reactive<VehicleForm>({
  plate_number: '',
  vehicle_type: '',
  brand: '',
  model: '',
  color: '',
  seats: 5,
  current_mileage: 0,
  status: '',
  notes: ''
})

const rules: FormRules<VehicleForm> = {
  plate_number: [{ required: true, message: '请输入车牌号', trigger: 'blur' }],
  brand: [{ required: true, message: '请输入品牌', trigger: 'blur' }],
  model: [{ required: true, message: '请输入型号', trigger: 'blur' }]
}

const dialogTitle = computed(() => (editingId.value === null ? '新建车辆' : '编辑车辆'))

function resetForm() {
  form.plate_number = ''
  form.vehicle_type = ''
  form.brand = ''
  form.model = ''
  form.color = ''
  form.seats = 5
  form.current_mileage = 0
  form.status = ''
  form.notes = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Vehicle) {
  editingId.value = row.id
  form.plate_number = row.plate_number
  form.vehicle_type = row.vehicle_type
  form.brand = row.brand
  form.model = row.model
  form.color = row.color
  form.seats = row.seats
  form.current_mileage = row.current_mileage
  form.status = row.status
  form.notes = row.notes
  dialogVisible.value = true
}

// ===== Mutations =====
const createMutation = useCreateVehicleMutation()
const updateMutation = useUpdateVehicleMutation()
const deleteMutation = useDeleteVehicleMutation()

const submitting = computed(() => createMutation.isPending.value || updateMutation.isPending.value)

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    if (editingId.value === null) {
      await createMutation.mutateAsync({
        plate_number: form.plate_number,
        vehicle_type: form.vehicle_type || undefined,
        brand: form.brand,
        model: form.model,
        color: form.color,
        seats: form.seats ?? 0,
        current_mileage: form.current_mileage ?? 0,
        status: form.status || undefined,
        notes: form.notes
      })
      ElMessage.success('创建成功')
    } else {
      await updateMutation.mutateAsync({
        id: editingId.value,
        input: {
          vehicle_type: form.vehicle_type || null,
          brand: form.brand,
          model: form.model,
          color: form.color,
          seats: form.seats ?? 0,
          current_mileage: form.current_mileage ?? 0,
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

async function handleDelete(row: Vehicle) {
  const confirmed = await ElMessageBox.confirm(`确认删除车辆「${row.plate_number}」?`, '提示', { type: 'warning' })
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
    <PageHeader title="车辆管理" subtitle="oa / vehicles">
      <template #actions>
        <el-button v-permission="'oa:vehicle:create'" type="primary" @click="openCreate">新建车辆</el-button>
      </template>
    </PageHeader>

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input v-model="filters.search" placeholder="车牌/品牌/型号" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="状态">
        <el-input v-model="filters.status" placeholder="状态" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="车辆类型">
        <el-input v-model="filters.vehicle_type" placeholder="车辆类型" clearable @keyup.enter="handleSearch" />
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="rows" border stripe>
      <el-table-column prop="plate_number" label="车牌号" width="140" />
      <el-table-column prop="vehicle_type" label="类型" width="100" />
      <el-table-column prop="brand" label="品牌" width="120" />
      <el-table-column prop="model" label="型号" width="120" />
      <el-table-column prop="seats" label="座位" width="80" align="right" />
      <el-table-column prop="current_mileage" label="里程" width="110" align="right" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="notes" label="备注" min-width="140" show-overflow-tooltip />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'oa:vehicle:update'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-permission="'oa:vehicle:delete'" link type="danger" @click="handleDelete(row)">
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
        <el-form-item label="车牌号" prop="plate_number">
          <el-input v-model="form.plate_number" :disabled="editingId !== null" placeholder="车牌号" />
        </el-form-item>
        <el-form-item label="类型">
          <el-input v-model="form.vehicle_type" placeholder="如 CAR" />
        </el-form-item>
        <el-form-item label="品牌" prop="brand">
          <el-input v-model="form.brand" placeholder="品牌" />
        </el-form-item>
        <el-form-item label="型号" prop="model">
          <el-input v-model="form.model" placeholder="型号" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-input v-model="form.color" placeholder="颜色" />
        </el-form-item>
        <el-form-item label="座位">
          <el-input-number v-model="form.seats" :min="0" />
        </el-form-item>
        <el-form-item label="里程">
          <el-input-number v-model="form.current_mileage" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-input v-model="form.status" placeholder="如 AVAILABLE" />
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
