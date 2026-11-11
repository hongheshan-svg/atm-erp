<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { read } from '../api'
import { message } from '../utils/request'
import { ledgerStatus } from '../modules/shared'
import type { Row } from '../types'
import BusinessTable from './BusinessTable.vue'
import ListPagination from './ListPagination.vue'
import { pageSize } from '../pagination'

const props = defineProps<{ taskId: number }>()
const emit = defineEmits<{ close: [] }>()
const rows = ref<Row[]>([]), summary = ref<Row | null>(null)
const page = ref(1), count = ref(0), mine = ref(false), loading = ref(false), error = ref('')
let generation = 0
async function load() {
  const current = ++generation
  loading.value = true; error.value = ''; rows.value = []; summary.value = null; count.value = 0
  try {
    const result = await read(`/business/tasks/${props.taskId}/time-records/`, { page: page.value, page_size: pageSize.value, mine: String(mine.value) })
    if (generation !== current) return
    rows.value = result.results; count.value = result.count; summary.value = result.summary
  } catch (e) { if (generation === current) error.value = message(e) }
  finally { if (generation === current) loading.value = false }
}
// 每页条数沿用全局设置（与其他列表同一个 ListPagination）；换条数、换任务或切换「只看我的」回到第 1 页。
watch(() => [props.taskId, mine.value, pageSize.value], () => { page.value = 1; void load() }, { immediate: true })
onBeforeUnmount(() => { generation++ })
</script>
<template>
  <el-dialog :model-value="true" title="工时明细" width="min(1100px, calc(100vw - 24px))" top="5vh" class="task-time-records" @close="emit('close')">
    <h3 v-if="summary">{{ summary.task_title }}</h3>
    <div v-if="summary" class="time-totals" aria-label="工时合计">
      <strong>任务累计：{{ summary.logged_hours }} 小时</strong>
      <span>我的累计：{{ summary.my_hours }} 小时</span>
    </div>
    <p class="muted">按实际工作日期登记，单位为小时。合计已扣除冲销，不按任务历时计算；多人分别登记。“我的累计”按工作所属人员统计，代填记录归被代填人。</p>
    <div class="time-tools"><label><input v-model="mine" type="checkbox" />只看我的工时</label><el-button :loading="loading" @click="load">刷新</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" /><el-button v-if="error" @click="load">重试</el-button>
    <BusinessTable v-if="!error" label="任务工时明细" :data="rows" :row-offset="(page - 1) * pageSize" v-loading="loading" :empty-text="loading ? '正在加载工时…' : '暂无已提交的工时记录'" max-height="400">
      <el-table-column prop="id" label="记录号" width="90" />
      <el-table-column prop="user_name" label="人员" min-width="110" />
      <el-table-column prop="date" label="工作日期" min-width="120" />
      <el-table-column prop="hours" label="工时（小时）" min-width="120" />
      <el-table-column label="记录状态" min-width="180"><template #default="{ row }">{{ ledgerStatus(row) }}<small v-if="row.archived">已移至已删除记录</small><small v-if="row.reversal_of">冲销原记录号 {{ row.reversal_of }}</small><small v-else-if="row.correction_of">更正自记录号 {{ row.correction_of }}</small></template></el-table-column>
      <el-table-column prop="reason" label="说明" min-width="200" />
      <el-table-column label="提交时间" min-width="180"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN', { hour12: false }) }}</template></el-table-column>
    </BusinessTable>
    <p class="muted">已移至“已删除记录”的原始流水仍计入合计，并在这里保留用于核对；工时填错请到“工时记录”更正。</p>
    <ListPagination v-if="!error" :page="page" :total="count" @change="page = $event; load()" />
    <template #footer><el-button @click="emit('close')">关闭</el-button></template>
  </el-dialog>
</template>
<style scoped>
:global(.task-time-records) { max-height: 90vh; display: flex; flex-direction: column; }
:global(.task-time-records .el-dialog__body) { overflow-y: auto; min-height: 0; }
:global(.task-time-records .el-dialog__header), :global(.task-time-records .el-dialog__footer) { flex-shrink: 0; }
.time-totals, .time-tools { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin: 12px 0; }
.time-totals { background: var(--soft-bg, #f1f5ff); border-radius: 8px; padding: 14px; }
.time-tools label { display: flex; align-items: center; gap: 6px; }
small { display: block; color: var(--muted); }
h3 { overflow-wrap: anywhere; }
@media (max-width: 600px) {
  .time-tools label { min-height: 40px; }
  .time-tools .el-button, :global(.task-time-records .el-dialog__footer .el-button) { min-height: 40px; }
}
</style>
