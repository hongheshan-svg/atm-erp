<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { CircleCheck, List, Document, Box, Wallet, ArrowRight } from '@element-plus/icons-vue'
import { ElSkeleton } from 'element-plus'
import { read } from '../api'
import { today } from '../forms'
import { user } from '../session'
import { message } from '../utils/request'
import { money } from '../utils/money'
import type { Row } from '../types'
type Bucket = { count: number; page: number; results: Row[]; overdue_count?: number; today_count?: number }
const work = ref<Record<string, Bucket>>({})
const loading = ref(false), initialized = ref(false), error = ref(''), updated = ref('')
const day = ref(today())
let generation = 0
const icons = { sales: Document, tasks: List, production_tasks: List, approvals: CircleCheck, receipts: Box, drafts: Document, settlements: Wallet, overdue_purchases: Box, prepayments: CircleCheck, reconciliations: Document, bank_records: Wallet }
const labels: Record<string, string> = {
  tasks: '我的待办', production_tasks: '生产与售后派工', overdue_purchases: '采购明细逾期', approvals: '待批准采购', prepayments: '待核准预付款',
  settlements: '到期收付 / 待退款', reconciliations: '待确认业务对账', bank_records: '银行待认领 / 匹配',
  receipts: '待收货', drafts: '采购草稿', sales: '我的销售订单',
}
const notes: Record<string, string> = {
  tasks: '按计划推进项目任务', production_tasks: '参与项目的装配、调试、安装与售后任务，安排人员并跟进完成', overdue_purchases: '跟进超出承诺交期的未到货物料', approvals: '确认采购，衔接后续执行',
  prepayments: '按合同条款核准预付款', settlements: '处理到期款项与退款', reconciliations: '核对差异，确认可结算额度',
  bank_records: '核实户名和用途后认领或匹配', receipts: '核对到货，及时更新库存', drafts: '完善采购明细后提交', sales: '跟进报价、签约、交付和回款',
}
const count = (key: string) => work.value[key]?.count || 0
const groups = computed(() => Object.keys(labels).filter(key => work.value[key]))
// Only categories with work are listed; the rest are summarised in one line so the page stays short.
const active = computed(() => groups.value.filter(key => count(key)))
const idleNote = computed(() => {
  const idle = groups.value.filter(key => !count(key))
  if (!idle.length || !active.value.length) return ''
  return idle.length === 1 ? `${labels[idle[0]]}当前没有待办` : `${labels[idle[0]]} 等 ${idle.length} 类当前没有待办`
})
const metrics = computed(() => [
  ...(work.value.tasks || work.value.overdue_purchases || work.value.production_tasks
    ? [{ label: '已逾期', value: (work.value.tasks?.overdue_count || 0) + count('overdue_purchases') + (work.value.production_tasks?.overdue_count || 0), note: '逾期任务 + 逾期采购 + 生产任务逾期', tone: 'danger' }] : []),
  ...(work.value.tasks ? [{ label: '今日到期', value: work.value.tasks.today_count || 0, note: '我的任务 · 今日截止', tone: 'primary' }] : []),
  ...(work.value.approvals || work.value.prepayments ? [{ label: '等待我审批', value: count('approvals') + count('prepayments'), note: '采购批准 + 预付款核准', tone: 'warning' }] : []),
])
function collection(key: string) {
  if (key === 'bank_records') return { path: '/finance', query: { section: 'bank', project: 'all' } }
  if (['prepayments', 'reconciliations'].includes(key)) return { path: '/finance', query: { section: 'reconciliations', project: 'all' } }
  if (key === 'settlements') return { path: '/finance', query: { section: 'entries', project: 'all' } }
  // 销售列表会沿用本人上次的搜索词，工作台进来必须看到完整清单，所以显式清空。
  if (key === 'sales') return { path: '/sales', query: { search: '' } }
  // 任务有自己的完整清单：以前这里只能落到项目列表，看自己的活还要逐个项目点进去。
  if (['tasks', 'production_tasks'].includes(key)) return { path: '/projects', query: { section: 'tasks' } }
  return { path: '/purchases' }
}
function target(key: string, row: Row) {
  if (key === 'bank_records') return { path: '/finance', query: { section: 'bank', project: 'all', resource: 'bank-records', focus: row.id } }
  if (['prepayments', 'reconciliations'].includes(key)) return { path: '/finance', query: { section: 'reconciliations', project: 'all', resource: 'reconciliations', focus: row.id } }
  if (key === 'sales') return { path: '/sales', query: { search: row.code } }
  const resource = ['tasks', 'production_tasks'].includes(key) ? 'tasks' : key === 'settlements' ? 'entries' : 'purchases'
  if (!row.project) return { ...collection(key), query: { ...collection(key).query, resource, focus: row.id } }
  return { path: `/projects/${row.project}`, query: { tab: resource === 'tasks' ? 'tasks' : resource === 'entries' ? 'finance' : 'purchases', resource, focus: row.id } }
}
function due(key: string, row: Row): string {
  if (!['sales', 'tasks', 'production_tasks', 'receipts', 'overdue_purchases', 'settlements'].includes(key)) return ''
  if (key === 'settlements' && Number(row.balance) < 0) return ''
  return row.next_delivery_date || row.due_date || ''
}
function urgency(key: string, row: Row) {
  const date = due(key, row)
  if (key === 'overdue_purchases' || (date && date < day.value)) return { text: '已逾期', tone: 'danger', rank: 0 }
  if (date === day.value) return { text: '今日到期', tone: 'warning', rank: 1 }
  if (['approvals', 'prepayments'].includes(key)) return { text: '待审批', tone: 'warning', rank: 2 }
  if (key === 'bank_records' && row.needs_review) return { text: '待核实户名', tone: 'warning', rank: 3 }
  return { text: '', tone: '', rank: 4 }
}
const priority = computed(() => Object.entries(work.value).flatMap(([key, bucket]) => bucket.results.map(row => ({ key, row, ...urgency(key, row) })))
  .filter((item, index, all) => !['tasks', 'production_tasks'].includes(item.key) || all.findIndex(other => ['tasks', 'production_tasks'].includes(other.key) && other.row.id === item.row.id) === index)
  .filter(item => item.rank < 4 && item.key !== 'receipts')
  .sort((a, b) => a.rank - b.rank || due(a.key, a.row).localeCompare(due(b.key, b.row))).slice(0, 7))
function title(key: string, row: Row) { return key === 'bank_records' ? row.counterparty || '待核实户名' : row.title || row.code || row.reference || '待处理事项' }

function amount(key: string, row: Row) {
  if (key === 'bank_records') return `${Number(row.amount) >= 0 ? '收入' : '支出'} · 待匹配 ${money(String(row.remaining_amount).replace(/^-/, ''), { currency: true })}`
  if (key === 'settlements' && row.balance != null) return `${Number(row.balance) < 0 ? '待退款' : row.kind === 'receivable' ? '待收' : '待付'} ${money(String(row.balance).replace(/^-/, ''), { currency: true })}`
  return ''
}
function context(key: string, row: Row) {
  return [row.project_name || row.supplier_name || row.customer_name || '—', amount(key, row)].filter(Boolean).join(' · ')
}
async function load() {
  const current = ++generation
  loading.value = true; error.value = ''
  try {
    const result = await read('/business/workbench/', { page_size: 5 })
    if (current !== generation) return
    work.value = result; day.value = today(); initialized.value = true
    updated.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) loading.value = false }
}
onMounted(load)
onBeforeUnmount(() => { generation++ })
</script>
<template>
  <div class="workbench-page">
    <header class="page-heading"><div><p class="eyebrow">今日协作 / {{ day }}</p><h1>工作台</h1><p class="muted">{{ user?.display_name }}，先处理紧急事项，再推进今天的工作。</p></div><div class="work-refresh"><span v-if="updated" role="status">{{ updated }} 更新</span><el-button :loading="loading" @click="load">刷新</el-button></div></header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <div v-if="!initialized && loading" class="panel" role="status" aria-label="正在加载工作台"><el-skeleton :rows="8" animated /></div>
    <template v-if="initialized">
      <section v-if="metrics.length" class="work-overview" aria-label="待办概览"><div v-for="metric in metrics" :key="metric.label" class="work-metric" :class="metric.value ? `tone-${metric.tone}` : ''"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><small>{{ metric.note }}</small></div></section>
      <section class="panel work-priority" aria-labelledby="priority-heading">
        <header><h2 id="priority-heading">今天要处理的</h2><span class="muted">按逾期、今日到期、待审批排序，最多 7 项</span></header>
        <el-table :data="priority" :max-height="420" empty-text="今天没有需要优先处理的事项" class="priority-table">
          <el-table-column label="事项 / 关联项目" min-width="220"><template #default="{ row: item }"><router-link :to="target(item.key, item.row)">{{ title(item.key, item.row) }}</router-link><small class="record-secondary">{{ context(item.key, item.row) }}</small></template></el-table-column>
          <el-table-column label="类型" min-width="110"><template #default="{ row: item }">{{ labels[item.key] }}</template></el-table-column>
          <el-table-column label="期限" width="110"><template #default="{ row: item }">{{ due(item.key, item.row) || '—' }}</template></el-table-column>
          <el-table-column label="状态" width="95"><template #default="{ row: item }"><span class="work-status" :class="`tone-${item.tone}`">{{ item.text }}</span></template></el-table-column>
          <el-table-column label="操作" width="60" fixed="right"><template #default="{ row: item }"><router-link :to="target(item.key, item.row)" :aria-label="`处理${title(item.key, item.row)}`">处理</router-link></template></el-table-column>
        </el-table>
      </section>
      <section class="panel work-categories" aria-labelledby="categories-heading">
        <header><h2 id="categories-heading">其他待办</h2><span class="muted">点击进入对应的完整列表</span></header>
        <router-link v-for="key in active" :key="key" :to="collection(key)" class="work-category" :aria-label="`查看全部${labels[key]}`"><el-icon aria-hidden="true"><component :is="icons[key as keyof typeof icons]" /></el-icon><span><strong>{{ labels[key] }}</strong><small>{{ notes[key] }}</small></span><b>{{ count(key) }}</b><el-icon aria-hidden="true"><ArrowRight /></el-icon></router-link>
        <p v-if="!active.length" class="work-calm"><el-icon aria-hidden="true"><CircleCheck /></el-icon>{{ groups.length ? '当前没有待处理事项。' : '当前岗位暂无工作台事项。' }}</p>
        <p v-if="idleNote" class="muted work-idle">{{ idleNote }}</p>
      </section>
    </template>
  </div>
</template>
<style scoped>
.work-refresh { display: flex; align-items: center; gap: 14px; color: var(--ink-4); font-size: 12px; }
.work-overview { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 20px; }
.work-metric { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: 16px 20px; background: white; border: 1px solid var(--surface-border); border-radius: 8px; color: var(--ink-2); }
.work-metric strong { font-size: 32px; line-height: 1.2; font-variant-numeric: tabular-nums; }
.work-metric small { color: var(--ink-4); font-size: 11px; }
.workbench-page :is(button, a):focus-visible { outline: 3px solid var(--brand-ink); outline-offset: 3px; }
.work-priority, .work-categories { padding: 0; overflow: hidden; }
.priority-table { border-radius: 0; }
.work-priority > header, .work-categories > header { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 20px; border-bottom: 1px solid var(--line); }
.work-priority h2, .work-categories h2 { margin: 0; font-size: 18px; }
.work-priority > header > span, .work-categories > header > span { font-size: 12px; }
.work-status { display: inline-flex; flex-shrink: 0; padding: 4px 8px; border-radius: 5px; font-size: 12px; font-weight: 500; white-space: nowrap; }
.tone-danger { color: var(--risk); }
.tone-warning { color: var(--warn); }
.tone-primary { color: var(--brand-ink); }
.work-status.tone-danger { background: var(--risk-wash); color: var(--risk); }
.work-status.tone-warning { background: var(--warn-wash); color: var(--warn); }
.work-calm { display: flex; align-items: center; justify-content: center; gap: 10px; padding: 24px; color: var(--ink-4); font-size: 13px; margin: 0; }
.work-category { display: flex; align-items: center; gap: 12px; padding: 12px 20px; border-top: 1px solid var(--line-3); color: var(--ink); }
.work-category:first-of-type { border-top: 0; }
.work-category:hover { background: var(--brand-wash-2); }
.work-category > span { min-width: 0; flex: 1; }
.work-category strong { display: block; font-size: 14px; font-weight: 500; }
.work-category small { display: block; margin-top: 4px; color: var(--ink-4); font-size: 12px; line-height: 1.4; }
.work-category b { color: var(--brand); font-size: 18px; font-variant-numeric: tabular-nums; }
.work-category > .el-icon { color: var(--brand); }
.work-idle { padding: 12px 20px; margin: 0; font-size: 12px; }
@media (max-width: 900px) { .work-overview { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) {
  .work-overview { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .work-metric { padding: 16px; }
  .work-metric strong { font-size: 28px; }
  .work-priority > header, .work-categories > header { align-items: flex-start; flex-direction: column; gap: 8px; padding: 16px; }
  .work-category { padding: 14px 16px; }
  .work-refresh { flex-wrap: wrap; gap: 8px; }
}
</style>
