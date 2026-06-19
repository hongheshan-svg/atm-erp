<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  useCreateProjectMutation,
  useDeleteProjectMutation,
  useProjectsQuery,
  useUpdateProjectMutation
} from '@/api/projects'
import type { Project, ProjectListQuery } from '@/types'

// 表单本地模型(数字字段允许 undefined,el-input-number 清空会触发)。
interface ProjectForm {
  code: string
  name: string
  customer_id: number | undefined
  manager_id: number | undefined
  status: string
  budget_total: number | undefined
  description: string
  notes: string
}

// ===== 查询条件与分页 =====
const filters = reactive({ keyword: '', status: '' })
const page = ref(1)
const pageSize = ref(20)

const submittedQuery = reactive<ProjectListQuery>({ keyword: '', status: '' })

const query = computed<ProjectListQuery>(() => ({
  keyword: submittedQuery.keyword,
  status: submittedQuery.status,
  page: page.value,
  page_size: pageSize.value
}))

const { data, isFetching } = useProjectsQuery(query)

const rows = computed<Project[]>(() => data.value?.results ?? [])
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

const form = reactive<ProjectForm>({
  code: '',
  name: '',
  customer_id: 0,
  manager_id: 0,
  status: '',
  budget_total: 0,
  description: '',
  notes: ''
})

const rules: FormRules<ProjectForm> = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  customer_id: [{ required: true, message: '请输入客户 ID', trigger: 'blur' }],
  manager_id: [{ required: true, message: '请输入负责人 ID', trigger: 'blur' }]
}

const dialogTitle = computed(() => (editingId.value === null ? '新建项目' : '编辑项目'))

function resetForm() {
  form.code = ''
  form.name = ''
  form.customer_id = 0
  form.manager_id = 0
  form.status = ''
  form.budget_total = 0
  form.description = ''
  form.notes = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Project) {
  editingId.value = row.id
  form.code = row.code
  form.name = row.name
  form.customer_id = row.customer_id
  form.manager_id = row.manager_id
  form.status = row.status
  form.budget_total = row.budget_total
  form.description = row.description
  form.notes = row.notes
  dialogVisible.value = true
}

// ===== Mutations =====
const createMutation = useCreateProjectMutation()
const updateMutation = useUpdateProjectMutation()
const deleteMutation = useDeleteProjectMutation()

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
        customer_id: form.customer_id ?? 0,
        manager_id: form.manager_id ?? 0,
        status: form.status || undefined,
        budget_total: form.budget_total ?? 0,
        description: form.description,
        notes: form.notes
      })
      ElMessage.success('创建成功')
    } else {
      await updateMutation.mutateAsync({
        id: editingId.value,
        input: {
          name: form.name,
          customer_id: form.customer_id ?? 0,
          manager_id: form.manager_id ?? 0,
          status: form.status || null,
          budget_total: form.budget_total ?? 0,
          description: form.description,
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

async function handleDelete(row: Project) {
  const confirmed = await ElMessageBox.confirm(`确认删除项目「${row.name}」?`, '提示', { type: 'warning' })
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
    <PageHeader title="项目管理" subtitle="projects / projects">
      <template #actions>
        <el-button v-permission="'projects:project:create'" type="primary" @click="openCreate">新建项目</el-button>
      </template>
    </PageHeader>

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input v-model="filters.keyword" placeholder="编码/名称" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="状态">
        <el-input v-model="filters.status" placeholder="状态" clearable @keyup.enter="handleSearch" />
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="rows" border stripe>
      <el-table-column prop="code" label="项目编码" width="160" />
      <el-table-column prop="name" label="项目名称" min-width="180" />
      <el-table-column prop="customer_id" label="客户 ID" width="100" />
      <el-table-column prop="manager_id" label="负责人 ID" width="110" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="budget_total" label="总预算" width="140" align="right" />
      <el-table-column prop="start_date" label="开始日期" width="140" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'projects:project:update'" link type="primary" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-permission="'projects:project:delete'" link type="danger" @click="handleDelete(row)">
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
        <el-form-item label="项目编码">
          <el-input v-model="form.code" :disabled="editingId !== null" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="form.name" placeholder="项目名称" />
        </el-form-item>
        <el-form-item label="客户 ID" prop="customer_id">
          <el-input-number v-model="form.customer_id" :min="0" />
        </el-form-item>
        <el-form-item label="负责人 ID" prop="manager_id">
          <el-input-number v-model="form.manager_id" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-input v-model="form.status" placeholder="如 DRAFT" />
        </el-form-item>
        <el-form-item label="总预算">
          <el-input-number v-model="form.budget_total" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" placeholder="描述" />
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
