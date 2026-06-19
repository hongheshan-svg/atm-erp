<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import {
  addMilestone,
  addRecord,
  fetchPlanDetail,
  useCreatePlanMutation,
  usePlansQuery
} from '@/api/collection'
import type {
  CollectionMilestone,
  CollectionPlan,
  CollectionPlanCreateInput,
  CollectionPlanListQuery
} from '@/types'

// ===== 列表 =====
const filters = reactive({ keyword: '', status: '' })
const page = ref(1)
const pageSize = ref(20)
const submitted = reactive<CollectionPlanListQuery>({ keyword: '', status: '' })

const query = computed<CollectionPlanListQuery>(() => ({
  keyword: submitted.keyword,
  status: submitted.status,
  page: page.value,
  page_size: pageSize.value
}))
const { data, isFetching, refetch } = usePlansQuery(query)
const plans = computed<CollectionPlan[]>(() => data.value?.results ?? [])
const total = computed(() => data.value?.count ?? 0)

function handleSearch() {
  submitted.keyword = filters.keyword
  submitted.status = filters.status
  page.value = 1
}
function handleReset() {
  filters.keyword = ''
  filters.status = ''
  handleSearch()
}

const planStatusTag: Record<string, string> = { DRAFT: 'info', IN_PROGRESS: 'warning', COMPLETED: 'success' }
const msStatusTag: Record<string, string> = { PENDING: 'info', PARTIAL: 'warning', COLLECTED: 'success' }

// ===== 新建计划 =====
const createVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<CollectionPlanCreateInput>({ name: '', customer_id: 0, total_amount: 0 })
const rules: FormRules<CollectionPlanCreateInput> = {
  name: [{ required: true, message: '请输入计划名称', trigger: 'blur' }],
  customer_id: [{ required: true, message: '请输入客户 ID', trigger: 'blur' }]
}
const createMutation = useCreatePlanMutation()

function openCreate() {
  form.name = ''
  form.customer_id = 0
  form.total_amount = 0
  createVisible.value = true
}
async function submitCreate() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    await createMutation.mutateAsync({ ...form })
    ElMessage.success('创建成功')
    createVisible.value = false
  } catch {
    /* 拦截器已提示 */
  }
}

// ===== 明细弹窗 =====
const detailVisible = ref(false)
const detailLoading = ref(false)
const currentPlan = ref<CollectionPlan | null>(null)
const milestones = ref<CollectionMilestone[]>([])

async function openDetail(row: CollectionPlan) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    const d = await fetchPlanDetail(row.id)
    currentPlan.value = d.plan
    milestones.value = d.milestones
  } finally {
    detailLoading.value = false
  }
}
async function reloadDetail() {
  if (!currentPlan.value) return
  const d = await fetchPlanDetail(currentPlan.value.id)
  currentPlan.value = d.plan
  milestones.value = d.milestones
  void refetch()
}

// 加节点
const msForm = reactive({ name: '', planned_amount: 0 })
async function submitMilestone() {
  if (!currentPlan.value || !msForm.name) {
    ElMessage.warning('请填写节点名称')
    return
  }
  try {
    await addMilestone(currentPlan.value.id, { name: msForm.name, planned_amount: msForm.planned_amount })
    msForm.name = ''
    msForm.planned_amount = 0
    await reloadDetail()
    ElMessage.success('节点已添加')
  } catch {
    /* 拦截器已提示 */
  }
}

// 记一笔收款
async function recordPayment(m: CollectionMilestone) {
  const res = await ElMessageBox.prompt(`节点「${m.name}」收款金额`, '记收款', {
    inputPattern: /^\d+(\.\d{1,2})?$/,
    inputErrorMessage: '请输入有效金额'
  }).catch(() => null)
  if (!res) return
  try {
    await addRecord(m.id, { amount: Number(res.value) })
    await reloadDetail()
    ElMessage.success('收款已记录')
  } catch {
    /* 拦截器已提示 */
  }
}
</script>

<template>
  <div>
    <PageHeader title="回款核销" subtitle="finance / collection">
      <template #actions>
        <el-button v-permission="'finance:collection_plan:create'" type="primary" @click="openCreate">
          新建回款计划
        </el-button>
      </template>
    </PageHeader>

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input v-model="filters.keyword" placeholder="单号/名称" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" placeholder="全部" clearable style="width: 140px">
          <el-option label="草稿" value="DRAFT" />
          <el-option label="执行中" value="IN_PROGRESS" />
          <el-option label="已完成" value="COMPLETED" />
        </el-select>
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="plans" border stripe>
      <el-table-column prop="plan_no" label="计划单号" width="180" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="total_amount" label="合同总额" width="130" align="right" />
      <el-table-column prop="collected_amount" label="已回款" width="130" align="right" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="(planStatusTag[row.status] as any) || 'info'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">明细</el-button>
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
      @current-change="(v: number) => (page = v)"
      @size-change="(v: number) => { pageSize = v; page = 1 }"
    />

    <!-- 新建计划 -->
    <el-dialog v-model="createVisible" title="新建回款计划" width="460px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="计划名称" />
        </el-form-item>
        <el-form-item label="客户 ID" prop="customer_id">
          <el-input-number v-model="form.customer_id" :min="0" />
        </el-form-item>
        <el-form-item label="合同总额">
          <el-input-number v-model="form.total_amount" :min="0" :precision="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createMutation.isPending.value" @click="submitCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- 明细:节点 + 加节点 + 记收款 -->
    <el-dialog v-model="detailVisible" title="回款计划明细" width="720px">
      <div v-loading="detailLoading">
        <el-descriptions v-if="currentPlan" :column="3" border size="small" class="mb">
          <el-descriptions-item label="单号">{{ currentPlan.plan_no }}</el-descriptions-item>
          <el-descriptions-item label="总额">{{ currentPlan.total_amount }}</el-descriptions-item>
          <el-descriptions-item label="已回款">{{ currentPlan.collected_amount }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="(planStatusTag[currentPlan.status] as any) || 'info'">{{ currentPlan.status }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <el-table :data="milestones" border size="small">
          <el-table-column prop="name" label="节点" min-width="120" />
          <el-table-column prop="planned_amount" label="计划金额" width="120" align="right" />
          <el-table-column prop="collected_amount" label="已收" width="120" align="right" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="(msStatusTag[row.status] as any) || 'info'" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button link type="primary" @click="recordPayment(row)">记收款</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-form :inline="true" class="mt">
          <el-form-item label="新增节点">
            <el-input v-model="msForm.name" placeholder="节点名称" style="width: 160px" />
          </el-form-item>
          <el-form-item label="计划金额">
            <el-input-number v-model="msForm.planned_amount" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="submitMilestone">添加节点</el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.mb {
  margin-bottom: 12px;
}
.mt {
  margin-top: 12px;
}
</style>
