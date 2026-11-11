<script setup lang="ts">
import BusinessTable from '../components/BusinessTable.vue'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { CircleCheck, List, Document, Box, Wallet, ArrowRight } from '@element-plus/icons-vue'
import { ElSkeleton } from 'element-plus'
import { read } from '../api'
import { today } from '../forms'
import { can, operations, user } from '../session'
import TaskNotices from '../components/TaskNotices.vue'
import RoleTaskGuide from '../components/RoleTaskGuide.vue'
import { message } from '../utils/request'
import { money } from '../utils/money'
import type { Row } from '../types'
type Bucket = { count: number; page: number; results: Row[]; overdue_count?: number; overdue_total?: number; today_count?: number }
const work = ref<Record<string, Bucket>>({})
const loading = ref(false), initialized = ref(false), error = ref(''), updated = ref('')
const day = ref(today())
let generation = 0
// 手机宽度（与列表组件同一判定）：待办表改为「事项 / 状态 / 处理」三列，类型和截止日期并入事项下方的副行。
const narrow = ref(typeof window !== 'undefined' && !!window.matchMedia?.('(max-width: 600px)').matches)
if (typeof window !== 'undefined' && window.matchMedia) {
  const query = window.matchMedia('(max-width: 600px)')
  const sync = () => { narrow.value = query.matches }
  query.addEventListener?.('change', sync)
  onBeforeUnmount(() => query.removeEventListener?.('change', sync))
}
const icons = { handover_projects: List, supervised_tasks: List, sales: Document, quoted_sales: Document, sale_receivables: Wallet, tasks: List, production_tasks: List, approvals: CircleCheck, receipts: Box, drafts: Document, approved_purchases: Document, shortage_projects: Box, settlements: Wallet, overdue_purchases: Box, prepayments: CircleCheck, reconciliations: Document, bank_records: Wallet }
// 交接待办：签约后待启动的项目、批准后待下单的采购、有缺料的项目、本人合同的逾期应收，各自成类，不再只能逐个项目翻找。
const labels: Record<string, string> = {
  handover_projects: '待启动项目', supervised_tasks: '我负责确认的任务', tasks: '我的待办', production_tasks: '生产与售后派工', overdue_purchases: '采购明细逾期', approvals: '待批准采购', prepayments: '待核准预付款',
  settlements: '到期收付 / 待退款', reconciliations: '待确认业务对账', bank_records: '银行待认领 / 匹配',
  receipts: '待收货', drafts: '采购草稿', approved_purchases: '已批准待下单', shortage_projects: '缺料待采购项目',
  sale_receivables: '我的合同逾期应收', quoted_sales: '已报价待签约', sales: '我的销售订单',
}
const notes: Record<string, string> = {
  handover_projects: '本人负责的新项目，尽快排任务计划、建 BOM、设预算', supervised_tasks: '按负责专业确认完成，并按人员和日期登记实际工时', tasks: '按计划推进项目任务', production_tasks: '参与项目的装配、调试、安装与售后任务，安排人员并跟进完成', overdue_purchases: '跟进超出承诺交期的未到货物料', approvals: '确认采购，衔接后续执行',
  prepayments: '按合同条款核准预付款', settlements: '处理到期款项与退款', reconciliations: '核对差异，确认可结算额度',
  bank_records: '核实户名和用途后认领或匹配', receipts: '核对到货，及时更新库存', drafts: '完善采购明细后提交',
  approved_purchases: '归档采购合同、向供应商下单并跟进到货', shortage_projects: '项目 BOM 仍有缺料，进入后用「从 BOM 多选下单」补齐',
  sale_receivables: '本人销售合同已过到期日的应收，联系客户回款', quoted_sales: '跟进客户确认，及时签约', sales: '跟进报价、签约、交付和回款',
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
    // 逾期任务含我负责确认的任务（服务端按任务去重给出 overdue_total），与下方「今天要处理的」同一口径。
    ? [{ label: work.value.overdue_purchases ? '任务 / 到货逾期' : '任务逾期', value: (work.value.tasks?.overdue_total ?? work.value.tasks?.overdue_count ?? 0) + count('overdue_purchases') + (work.value.production_tasks?.overdue_count || 0), note: work.value.production_tasks ? '本人及生产任务分类计数；兼岗任务可能重叠' : work.value.overdue_purchases ? '我的逾期任务与采购到货逾期' : work.value.supervised_tasks ? '我的任务与我负责确认的任务 · 已超过计划完成日期' : '我的任务 · 已超过计划完成日期', tone: 'danger' }] : []),
  ...(work.value.tasks ? [{ label: '我的任务今日截止', value: work.value.tasks.today_count || 0, note: '任务计划完成日期，不含款项到期', tone: 'primary' }] : []),
  ...(work.value.receipts && can(['admin', 'warehouse']) ? [{ label: '待收货采购', value: count('receipts'), note: '已批准，等待到货入库', tone: 'primary' }] : []),
  ...(work.value.approvals || work.value.prepayments ? [{ label: '等待我审批', value: count('approvals') + count('prepayments'), note: '采购批准 + 预付款核准', tone: 'warning' }] : []),
])
function collection(key: string) {
  if (key === 'bank_records') return { path: '/finance', query: { section: 'bank', project: 'all' } }
  if (['prepayments', 'reconciliations'].includes(key)) return { path: '/finance', query: { section: 'reconciliations', project: 'all' } }
  if (key === 'settlements') return { path: '/finance', query: { section: 'entries', project: 'all' } }
  // 销售列表会沿用本人上次的搜索词，工作台进来必须看到完整清单，所以显式清空。
  if (['sales', 'quoted_sales', 'sale_receivables'].includes(key)) return { path: '/sales', query: { search: '' } }
  if (key === 'handover_projects') return { path: '/projects' }
  // 任务有自己的完整清单：以前这里只能落到项目列表，看自己的活还要逐个项目点进去。
  if (key === 'supervised_tasks') return { path: '/projects', query: { section: 'tasks', supervisor: String(user.value?.id) } }
  if (['tasks', 'production_tasks'].includes(key)) return { path: '/projects', query: { section: 'tasks' } }
  return { path: '/purchases' }
}
function target(key: string, row: Row) {
  if (key === 'bank_records') return { path: '/finance', query: { section: 'bank', project: 'all', resource: 'bank-records', focus: row.id } }
  if (['prepayments', 'reconciliations'].includes(key)) return { path: '/finance', query: { section: 'reconciliations', project: 'all', resource: 'reconciliations', focus: row.id } }
  if (['sales', 'quoted_sales'].includes(key)) return { path: '/sales', query: { search: row.code } }
  // 销售经理看本人合同的逾期应收：落到该销售单，从「交付与回款」查看；收款由财务登记。
  if (key === 'sale_receivables') return { path: '/sales', query: { search: row.sale_code || '' } }
  if (key === 'handover_projects') return { path: `/projects/${row.project}` }
  // 缺料项目直接进入该项目的采购页，用「从 BOM 多选下单」补缺。
  if (key === 'shortage_projects') return { path: '/purchases', query: { project: String(row.project) } }
  const resource = ['tasks', 'production_tasks', 'supervised_tasks'].includes(key) ? 'tasks' : key === 'settlements' ? 'entries' : 'purchases'
  if (!row.project) return { ...collection(key), query: { ...collection(key).query, resource, focus: row.id } }
  return { path: `/projects/${row.project}`, query: { tab: resource === 'tasks' ? 'tasks' : resource === 'entries' ? 'finance' : 'purchases', resource, focus: row.id } }
}
function due(key: string, row: Row): string {
  if (!['sales', 'tasks', 'production_tasks', 'supervised_tasks', 'receipts', 'overdue_purchases', 'settlements', 'sale_receivables', 'handover_projects', 'shortage_projects'].includes(key)) return ''
  if (['settlements', 'sale_receivables'].includes(key) && Number(row.balance) < 0) return ''
  // 交付逾期只统计执行中/交付中项目：已验收、已结项、已取消项目的销售单不再按交期标逾期。
  if (key === 'sales' && row.project_status && !['active', 'delivering'].includes(String(row.project_status))) return ''
  return row.next_delivery_date || row.due_date || ''
}
function urgency(key: string, row: Row) {
  if (key === 'approvals' && row.change_request) return { text: '修改申请待处理', tone: 'warning', rank: 2 }
  const date = due(key, row)
  if (key === 'overdue_purchases' || (date && date < day.value)) return { text: '已逾期', tone: 'danger', rank: 0 }
  if (date === day.value) return { text: '今日到期', tone: 'warning', rank: 1 }
  if (['approvals', 'prepayments'].includes(key)) return { text: '待审批', tone: 'warning', rank: 2 }
  if (key === 'handover_projects') return { text: '待启动', tone: 'warning', rank: 2 }
  if (key === 'approved_purchases') return { text: '待下单', tone: 'warning', rank: 3 }
  if (key === 'shortage_projects') return { text: '缺料', tone: 'warning', rank: 3 }
  if (key === 'quoted_sales') return { text: '待签约', tone: 'warning', rank: 3 }
  if (key === 'bank_records' && row.needs_review) return { text: '待核实户名', tone: 'warning', rank: 3 }
  return { text: '', tone: '', rank: 4 }
}
// 同一任务、销售单或款项可能同时出现在多个分类里（如我的销售与已报价、到期收付与合同逾期应收），只列最紧急的一次。
function identity(key: string, row: Row) {
  if (['tasks', 'production_tasks', 'supervised_tasks'].includes(key)) return `task:${row.id}`
  if (['sales', 'quoted_sales'].includes(key)) return `sale:${row.id}`
  if (['settlements', 'sale_receivables'].includes(key)) return `entry:${row.id}`
  return `${key}:${row.id}`
}
const priority = computed(() => Object.entries(work.value).flatMap(([key, bucket]) => (bucket.results || []).map(row => ({ key, row, ...urgency(key, row) })))
  .filter(item => item.rank < 4 && item.key !== 'receipts')
  .sort((a, b) => a.rank - b.rank || due(a.key, a.row).localeCompare(due(b.key, b.row)))
  .filter((item, index, all) => all.findIndex(other => identity(other.key, other.row) === identity(item.key, item.row)) === index)
  .slice(0, 7))
const ongoing = computed(() => work.value.tasks?.results || [])
const emptyTaskNote = computed(() => can(['mechanical_engineer', 'electrical_engineer', 'member', 'production_manager'])
  ? '目前没有分配给你的未完成任务。可查看参与项目；如需派工，请联系项目经理。'
  : '目前没有分配给你的未完成任务。可从下方岗位指引继续处理日常工作。')
function title(key: string, row: Row) { return key === 'bank_records' ? row.counterparty || '待核实户名' : row.title || row.code || row.reference || '待处理事项' }

function amount(key: string, row: Row) {
  if (key === 'approvals' && row.change_request) return row.self_requested ? '本人修改申请，需填写例外原因' : '先处理修改申请，再继续采购审批'
  if (key === 'bank_records') return `${Number(row.amount) >= 0 ? '收入' : '支出'} · 待匹配 ${money(String(row.remaining_amount).replace(/^-/, ''), { currency: true })}`
  if (['settlements', 'sale_receivables'].includes(key) && row.balance != null) {
    const abs = (value: unknown) => money(String(value).replace(/^-/, ''), { currency: true })
    if (Number(row.balance) < 0) return `待退款 ${abs(row.balance)}`
    // 优先显示当前到期金额，余额同时可见；分期未到期的部分不应被当作已到期待办。
    if (row.due_amount != null && Number(row.due_amount) > 0) return `${row.kind === 'receivable' ? '到期待收' : '到期待付'} ${abs(row.due_amount)} · 余额 ${abs(row.balance)}`
    return `${row.kind === 'receivable' ? '待收' : '待付'}余额 ${abs(row.balance)}`
  }
  if (key === 'approvals' && row.self_requested) return '本人申请，需填写例外原因'
  if (key === 'handover_projects' && row.missing?.length) return `缺${row.missing.join('、')}`
  if (key === 'shortage_projects') return `缺料 ${row.shortage_lines} 行`
  return ''
}
function context(key: string, row: Row) {
  const party = key === 'sale_receivables' ? [row.partner_name, row.project_name].filter(Boolean).join(' · ') : ['handover_projects', 'shortage_projects'].includes(key) ? '' : row.project_name || row.supplier_name || row.customer_name || '—'
  return [party, amount(key, row)].filter(Boolean).join(' · ')
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
    <nav v-if="can(['admin', 'warehouse'])" class="panel warehouse-shortcuts" aria-label="日常库存入口"><router-link to="/inventory?section=receipts&project=all">采购收货</router-link><router-link to="/inventory?section=stocks&intent=issue">项目领料</router-link><router-link to="/inventory?section=moves&intent=return&project=all">项目退料</router-link><router-link to="/inventory?section=stocks&issue=bom&project=all">按 BOM 领料</router-link></nav>
    <template v-if="initialized">
      <section v-if="metrics.length" class="work-overview" aria-label="待办概览"><div v-for="metric in metrics" :key="metric.label" class="work-metric" :class="metric.value ? `tone-${metric.tone}` : ''"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><small>{{ metric.note }}</small></div></section>
      <div class="work-main" :class="{ 'no-priority': !priority.length }">
      <section class="panel work-priority" aria-labelledby="priority-heading">
        <header><h2 id="priority-heading">今天要处理的</h2><span class="muted">按逾期、今日到期、待审批排序，最多 7 项</span></header>
        <BusinessTable label="待办事项" v-if="priority.length" :data="priority" :numbered="!narrow" :max-height="narrow ? undefined : 420" class="priority-table">
          <el-table-column label="事项 / 关联项目" :min-width="narrow ? 150 : 220"><template #default="{ row: item }"><router-link :to="target(item.key, item.row)">{{ title(item.key, item.row) }}</router-link><small class="record-secondary">{{ narrow ? [labels[item.key], context(item.key, item.row)].filter(Boolean).join(' · ') : context(item.key, item.row) }}</small><small v-if="narrow && due(item.key, item.row)" class="record-secondary">{{ due(item.key, item.row) }}</small></template></el-table-column>
          <el-table-column v-if="!narrow" label="类型" min-width="110"><template #default="{ row: item }">{{ labels[item.key] }}</template></el-table-column>
          <el-table-column v-if="!narrow" label="截止 / 到期日期" width="135"><template #default="{ row: item }">{{ due(item.key, item.row) || '—' }}</template></el-table-column>
          <el-table-column label="状态" :width="narrow ? 92 : 95"><template #default="{ row: item }"><span class="work-status" :class="`tone-${item.tone}`">{{ item.text }}</span></template></el-table-column>
          <el-table-column label="操作" width="60" fixed="right"><template #default="{ row: item }"><router-link :to="target(item.key, item.row)" :aria-label="`处理${title(item.key, item.row)}`">处理</router-link></template></el-table-column>
        </BusinessTable>
        <p v-else class="priority-empty muted">今天没有需要优先处理的事项</p>
      </section>
      <section v-if="work.tasks" class="panel work-ongoing" aria-labelledby="ongoing-heading">
        <header><h2 id="ongoing-heading">我正在做的工作</h2><router-link :to="collection('tasks')">查看我的全部任务（{{ count('tasks') }}）</router-link></header>
        <ul v-if="ongoing.length"><li v-for="task in ongoing" :key="task.id"><div><strong>{{ title('tasks', task) }}</strong><span>{{ task.project_name || '关联项目' }}</span><span>计划完成日期：{{ task.due_date || '未设置' }}</span></div><router-link :to="target('tasks', task)" :aria-label="`继续处理${title('tasks', task)}`">继续处理 →</router-link></li></ul>
        <p v-else class="muted">{{ emptyTaskNote }}</p>
      </section>
      </div>
      <section class="panel work-categories" aria-labelledby="categories-heading">
        <header><h2 id="categories-heading">其他待办</h2><span class="muted">点击进入对应的完整列表</span></header>
        <router-link v-for="key in active" :key="key" :to="collection(key)" class="work-category" :aria-label="`查看全部${labels[key]}`"><el-icon aria-hidden="true"><component :is="icons[key as keyof typeof icons]" /></el-icon><span><strong>{{ labels[key] }}</strong><small>{{ notes[key] }}</small></span><b>{{ count(key) }}</b><el-icon aria-hidden="true"><ArrowRight /></el-icon></router-link>
        <p v-if="!active.length" class="work-calm"><el-icon aria-hidden="true"><CircleCheck /></el-icon>{{ groups.length ? '当前没有待处理事项。' : '当前岗位暂无工作台事项。' }}</p>
        <p v-if="idleNote" class="muted work-idle">{{ idleNote }}</p>
      </section>
    </template>
    <TaskNotices v-if="operations()" />
    <RoleTaskGuide />
  </div>
</template>
<style scoped>
.work-refresh { display: flex; align-items: center; gap: 14px; color: var(--ink-4); font-size: 12px; }
.work-main { display: flex; flex-direction: column; }
.no-priority .work-ongoing { order: -1; }
.priority-empty { padding: 16px 20px; margin: 0; font-size: 14px; }
.warehouse-shortcuts { display: flex; flex-wrap: wrap; gap: 16px; }
.work-ongoing header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
.work-ongoing h2 { font-size: 18px; margin: 0; }
.work-ongoing ul { list-style: none; padding: 0; margin-bottom: 0; }
.work-ongoing li { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding: 9px 0; border-bottom: 1px solid var(--surface-border); }
.work-ongoing li:last-child { border-bottom: 0; }
.work-ongoing li div { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 16px; }
.work-ongoing li span { color: var(--ink-4); font-size: 13px; }
.work-overview { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }
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
/* 手机端：列由模板按窄屏判定渲染（事项 / 状态 / 处理），这里只收紧单元格内边距。 */
@media (max-width: 600px) {
  .work-metric { padding: 12px; gap: 4px; }
  .work-metric > span { font-size: 13px; line-height: 1.35; }
  .work-metric strong { font-size: 24px; }
  .warehouse-shortcuts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px 12px; padding: 8px 16px; }
  .warehouse-shortcuts a { display: flex; align-items: center; min-height: 40px; }
  .work-priority :deep(.el-table__cell) { padding: 8px 4px; }
  .work-priority .work-status { padding: 3px 6px; font-size: 11px; white-space: nowrap; }
  .work-priority :deep(td a) { white-space: nowrap; }
  .work-priority :deep(.record-secondary) { white-space: normal; margin-top: 3px; }
}
</style>
