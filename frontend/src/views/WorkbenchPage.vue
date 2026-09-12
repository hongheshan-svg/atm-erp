<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { CircleCheck, List, Document, Box, Wallet, ArrowRight } from '@element-plus/icons-vue'
import { ElSkeleton, ElSwitch } from 'element-plus'
import { read } from '../api'
import { today } from '../forms'
import { user } from '../session'
import { message } from '../utils/request'
import type { Row } from '../types'
type Bucket = { count: number; page: number; results: Row[]; overdue_count?: number; today_count?: number }
const work = ref<Record<string, Bucket>>({})
const highlights = ref<Record<string, Bucket>>({})
const loading = ref(false), initialized = ref(false), error = ref(''), updated = ref('')
const busy = ref<Record<string, boolean>>({}), errors = ref<Record<string, string>>({})
const filter = ref('all'), showEmpty = ref(false), day = ref(today())
let generation = 0
const sequences: Record<string, number> = {}
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
const groups = computed(() => Object.keys(labels).filter(key => work.value[key]))
const emptyGroups = computed(() => groups.value.filter(key => !work.value[key]!.count))
const visibleGroups = computed(() => groups.value.filter(key => (filter.value === 'all' || filter.value.split(',').includes(key)) && (work.value[key]!.count || showEmpty.value || filter.value !== 'all')))
const count = (key: string) => work.value[key]?.count || 0
const metrics = computed(() => [
  ...(work.value.tasks || work.value.overdue_purchases ? [{ label: '逾期待处理', value: (work.value.tasks?.overdue_count || 0) + count('overdue_purchases'), note: '逾期任务 + 逾期采购单', keys: ['tasks', 'overdue_purchases'], tone: 'danger' }] : []),
  ...(work.value.tasks ? [{ label: '今日到期任务', value: work.value.tasks.today_count || 0, note: '我的任务 · 今日截止', keys: ['tasks'], tone: 'primary' }] : []),
  ...(work.value.production_tasks ? [{ label: '生产任务逾期', value: work.value.production_tasks.overdue_count || 0, note: '参与项目 · 装配 / 调试 / 安装 / 售后', keys: ['production_tasks'], tone: 'danger' }] : []),
  ...(work.value.approvals || work.value.prepayments ? [{ label: '等待审批', value: count('approvals') + count('prepayments'), note: '采购批准 + 预付款核准', keys: ['approvals', 'prepayments'], tone: 'warning' }] : []),
  ...(work.value.bank_records ? [{ label: '银行待处理', value: count('bank_records'), note: '待认领 / 匹配的流水', keys: ['bank_records'], tone: 'primary' }] : []),
])
function collection(key: string) {
  if (key === 'bank_records') return { path: '/finance', query: { section: 'bank', project: 'all' } }
  if (['prepayments', 'reconciliations'].includes(key)) return { path: '/finance', query: { section: 'reconciliations', project: 'all' } }
  if (key === 'settlements') return { path: '/finance', query: { section: 'entries', project: 'all' } }
  return { path: key === 'sales' ? '/sales' : ['tasks', 'production_tasks'].includes(key) ? '/projects' : '/purchases' }
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
  if (!['tasks', 'production_tasks', 'receipts', 'overdue_purchases', 'settlements'].includes(key)) return ''
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
const priority = computed(() => Object.entries(highlights.value).flatMap(([key, bucket]) => bucket.results.map(row => ({ key, row, ...urgency(key, row) })))
  .filter((item, index, all) => !['tasks', 'production_tasks'].includes(item.key) || all.findIndex(other => ['tasks', 'production_tasks'].includes(other.key) && other.row.id === item.row.id) === index)
  .filter(item => item.rank < 4 && item.key !== 'receipts')
  .sort((a, b) => a.rank - b.rank || due(a.key, a.row).localeCompare(due(b.key, b.row))).slice(0, 5))
function title(key: string, row: Row) { return key === 'bank_records' ? row.counterparty || '待核实户名' : row.title || row.code || row.reference || '待处理事项' }
function detail(key: string, row: Row) {
  if (key === 'bank_records') return [row.reference, row.project ? row.project_name : '待指定项目', row.date].filter(Boolean).join(' · ')
  return [row.supplier_name || row.customer_name || row.entry_title, row.project_name || (row.project ? `项目 #${row.project}` : row.assignee_name), due(key, row) ? `截止 ${due(key, row)}` : ''].filter(Boolean).join(' · ') || '点击查看业务详情'
}
const money = (value: unknown) => Number(value).toLocaleString('zh-CN', { style: 'currency', currency: 'CNY' })
function amount(key: string, row: Row) {
  if (key === 'bank_records') return `${Number(row.amount) >= 0 ? '收入' : '支出'} · 待匹配 ${money(Math.abs(Number(row.remaining_amount)))}`
  if (key === 'settlements' && row.balance != null) return `${Number(row.balance) < 0 ? '待退款' : row.kind === 'receivable' ? '待收' : '待付'} ${money(Math.abs(Number(row.balance)))}`
  return ''
}
function choose(keys: string[]) {
  const selected = keys.filter(k => work.value[k])
  if (selected.length) { filter.value = selected.join(','); document.getElementById('workbench-categories')?.scrollIntoView({ block: 'start' }) }
}
async function load() {
  const current = ++generation
  const firstLoad = !initialized.value
  loading.value = true; busy.value = {}; errors.value = {}; error.value = ''
  try {
    const result = await read('/business/workbench/', { page_size: 5 })
    if (current !== generation) return
    work.value = result; highlights.value = result; day.value = today(); initialized.value = true
    updated.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    if (firstLoad || (filter.value !== 'all' && !filter.value.split(',').some(key => result[key]))) filter.value = Object.keys(labels).find(key => result[key]?.count) || Object.keys(result)[0] || 'all'
  } catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) loading.value = false }
}
async function changePage(key: string, page: number) {
  if (loading.value) return
  const current = generation, sequence = sequences[key] = (sequences[key] || 0) + 1
  busy.value[key] = true; errors.value[key] = ''
  try {
    const result = await read('/business/workbench/', { bucket: key, page_size: 5, [`${key}_page`]: page })
    if (current !== generation || sequence !== sequences[key]) return
    work.value = { ...work.value, [key]: result[key] || { count: 0, page: 1, results: [] } }
  } catch (e) { if (current === generation && sequence === sequences[key]) errors.value[key] = message(e) }
  finally { if (current === generation && sequence === sequences[key]) busy.value[key] = false }
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
      <section v-if="metrics.length" class="work-overview" aria-label="待办概览"><button v-for="metric in metrics" :key="metric.label" class="work-metric" :class="metric.value ? `tone-${metric.tone}` : ''" @click="choose(metric.keys)"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><small>{{ metric.note }}</small><el-icon aria-hidden="true"><ArrowRight /></el-icon></button></section>
      <div class="work-focus-grid"><section class="panel work-priority" aria-labelledby="priority-heading">
        <header><div><p class="eyebrow">先处理这些</p><h2 id="priority-heading">优先处理</h2></div><span class="muted">从各分类首页选取，最多 5 项</span></header>
        <el-table :data="priority" :max-height="300" empty-text="当前分类首页暂无紧急事项" class="priority-table">
          <el-table-column label="事项 / 关联项目" min-width="200"><template #default="{ row: item }"><router-link :to="target(item.key, item.row)">{{ title(item.key, item.row) }}</router-link><small class="record-secondary">{{ item.row.project_name || item.row.supplier_name || item.row.customer_name || '—' }}</small></template></el-table-column>
          <el-table-column label="类型" min-width="110"><template #default="{ row: item }">{{ labels[item.key] }}</template></el-table-column>
          <el-table-column label="期限" width="110"><template #default="{ row: item }">{{ due(item.key, item.row) || '—' }}</template></el-table-column>
          <el-table-column label="状态" width="95"><template #default="{ row: item }"><span class="work-status" :class="`tone-${item.tone}`">{{ item.text }}</span></template></el-table-column>
          <el-table-column label="操作" width="60" fixed="right"><template #default="{ row: item }"><router-link :to="target(item.key, item.row)" :aria-label="`处理${title(item.key, item.row)}`">处理</router-link></template></el-table-column>
        </el-table>
      </section>
      <aside class="panel work-category-summary" aria-label="分类入口"><h2>分类待办</h2><button v-for="key in groups.filter(key => count(key) || showEmpty)" :key="key" :aria-pressed="filter === key" @click="choose([key])"><el-icon aria-hidden="true"><component :is="icons[key as keyof typeof icons]" /></el-icon><span><strong>{{ labels[key] }}</strong><small>{{ notes[key] }}</small></span><b>{{ count(key) }}</b><el-icon aria-hidden="true"><ArrowRight /></el-icon></button><p v-if="!groups.some(key => count(key))" class="muted">当前没有待处理事项。</p></aside></div>
      <section id="workbench-categories" aria-label="分类待办">
        <header class="work-section-heading"><div><h2>分类待办</h2><p class="muted">每类展示 5 条，按需翻页或进入完整列表。</p></div><label v-if="emptyGroups.length" class="work-empty-toggle"><el-switch v-model="showEmpty" aria-label="显示空分类" /><span>显示空分类（{{ emptyGroups.length }}）</span></label></header>
        <div class="work-filters" aria-label="选择待办分类"><button :aria-pressed="filter === 'all'" @click="filter = 'all'">全部</button><button v-for="key in groups" :key="key" :aria-pressed="filter === key" @click="filter = key">{{ labels[key] }} <span>{{ count(key) }}</span></button></div>
        <div class="workbench-grid" :aria-busy="loading">
          <section v-for="key in visibleGroups" :key="key" class="panel work-card" :class="`work-card-${key}`" :aria-label="labels[key]" :aria-busy="busy[key] || loading">
            <header class="work-card-heading"><span class="work-card-icon" aria-hidden="true"><el-icon><component :is="icons[key as keyof typeof icons]" /></el-icon></span><div><h2>{{ labels[key] }}</h2><p>{{ notes[key] }}</p></div><span class="work-card-count">{{ count(key) }}</span></header>
            <el-alert v-if="errors[key]" :title="errors[key]" type="error" :closable="false" role="alert" />
            <p v-if="!work[key]!.results.length" class="work-calm"><el-icon aria-hidden="true"><CircleCheck /></el-icon>暂无需要处理的事项</p>
            <div :class="{ 'work-is-loading': busy[key] }"><router-link v-for="row in work[key]!.results" :key="row.id" :to="target(key, row)" class="work-item"><div class="work-item-heading"><strong>{{ title(key, row) }}</strong><span v-if="urgency(key, row).text" class="work-status" :class="`tone-${urgency(key, row).tone}`">{{ urgency(key, row).text }}</span></div><span>{{ detail(key, row) }}</span><b v-if="amount(key, row)" class="work-amount">{{ amount(key, row) }}</b></router-link></div>
            <div v-if="count(key) > 5" class="work-pagination"><span role="status">{{ busy[key] ? '正在加载…' : `第 ${work[key]!.page} 页` }}</span><el-pagination :current-page="work[key]!.page" :page-size="5" :total="count(key)" :disabled="busy[key] || loading" layout="prev, next" @current-change="changePage(key, $event)" /></div>
            <footer class="work-card-footer"><span>共 {{ count(key) }} 项</span><router-link :to="collection(key)" :aria-label="`查看全部${labels[key]}`">查看全部<el-icon aria-hidden="true"><ArrowRight /></el-icon></router-link></footer>
          </section>
        </div>
        <div v-if="!visibleGroups.length" class="panel work-calm"><el-icon aria-hidden="true"><CircleCheck /></el-icon>{{ groups.length ? '当前没有待处理事项。空分类可在上方展开。' : '当前岗位暂无工作台事项。' }}</div>
      </section>
    </template>
  </div>
</template>
<style scoped>
.work-refresh { display: flex; align-items: center; gap: 14px; color: #596b82; font-size: 12px; }
.work-focus-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(290px, 1fr); gap: 18px; align-items: start; }
.work-category-summary { max-height: 330px; overflow-y: auto; }
.work-category-summary > button { display: flex; align-items: center; gap: 12px; width: 100%; padding: 10px; margin-top: 8px; border: 1px solid #e8edf4; border-radius: 6px; background: #fff; color: #25364d; text-align: left; cursor: pointer; }
.work-category-summary > button[aria-pressed='true'] { border-color: #b9d1fc; background: #f4f8ff; }
.work-category-summary button > span { min-width: 0; flex: 1; }
.work-category-summary strong { font-size: 14px; }
.work-category-summary small { display: block; font-size: 12px; margin-top: 5px; line-height: 1.4; }
.work-category-summary b { color: #2563eb; font-size: 18px; }
.work-category-summary button > .el-icon { color: #2563eb; }
.workbench-grid { grid-template-columns: minmax(0, 1fr); }
.work-overview { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
.work-metric { position: relative; display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: 16px 20px; background: white; border: 1px solid var(--surface-border); border-radius: 8px; color: #3b526e; cursor: pointer; text-align: left; }
.work-metric strong { font-size: 32px; line-height: 1.2; font-variant-numeric: tabular-nums; }
.work-metric small { color: #596b82; font-size: 11px; }
.work-metric > .el-icon { position: absolute; right: 20px; top: 22px; }
.work-metric:hover { border-color: #7fa4db; background: #fafcff; }
.workbench-page :is(button, a):focus-visible { outline: 3px solid #245fc7; outline-offset: 3px; }
.work-priority { padding: 0; overflow: hidden; }
.priority-table { border-radius: 0; }
.work-priority > header, .work-section-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.work-priority > header { padding: 16px 20px; border-bottom: 1px solid #e3e9f1; }
.work-priority h2, .work-section-heading h2 { margin: 0; font-size: 18px; }
.work-priority .eyebrow { display: none; }
.work-priority > header > span { font-size: 12px; }
.work-priority-item { display: flex; align-items: center; gap: 16px; padding: 12px 20px; border-bottom: 1px solid #edf0f4; color: #25364d; }
.work-priority-item:hover { background: #f6f9fe; }
.work-priority-item > div { flex: 1; min-width: 0; }
.work-priority-item strong { font-size: 14px; overflow-wrap: anywhere; }
.work-priority-item p { margin: 6px 0 0; color: #596b82; font-size: 12px; overflow-wrap: anywhere; }
.work-status { display: inline-flex; flex-shrink: 0; padding: 4px 8px; border-radius: 5px; font-size: 12px; font-weight: 500; white-space: nowrap; }
.tone-danger { color: #ad3434; }
.tone-warning { color: #87520c; }
.tone-primary { color: #245fc7; }
.work-status.tone-danger { background: #fff0ef; color: #ad3434; }
.work-status.tone-warning { background: #fff6e6; color: #87520c; }
.work-calm { display: flex; align-items: center; justify-content: center; gap: 10px; padding: 24px; color: #596b82; font-size: 13px; margin: 0; }
.work-section-heading { margin: 8px 0 12px; }
.work-section-heading p { font-size: 13px; margin-bottom: 0; }
.work-empty-toggle { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #596b82; }
.work-filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }
.work-filters button { cursor: pointer; min-height: 40px; border: 1px solid #dce3ed; border-radius: 8px; background: white; color: #526178; padding: 8px 12px; font-size: 13px; }
.work-filters button[aria-pressed='true'] { background: #edf3ff; border-color: #245fc7; color: #245fc7; }
.work-filters span { margin-left: 5px; font-variant-numeric: tabular-nums; }
.workbench-grid { align-items: start; }
.work-card-heading { padding: 14px 20px; }
.work-card-heading > div { min-width: 0; }
.work-card-heading p, .work-item > span { color: #596b82; }
.work-card-count { font-size: 24px; }
.work-item { display: grid; grid-template-columns: minmax(160px, 1fr) minmax(180px, 2fr) auto; align-items: center; gap: 18px; padding: 14px 20px; color: #25364d; overflow-wrap: anywhere; }
.work-item-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.work-amount { font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; color: #245b88; }
.work-pagination { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 8px 20px; font-size: 12px; color: #596b82; }
.work-is-loading { opacity: .55; pointer-events: none; }
.work-card-footer { padding: 14px 20px; }
.work-card-footer > span { color: #596b82; }
#workbench-categories { scroll-margin-top: 20px; }
@media (max-width: 640px) {
  .work-overview { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .work-metric { padding: 16px; }
  .work-metric > .el-icon { display: none; }
  .work-metric strong { font-size: 28px; }
  .work-section-heading, .work-priority > header { align-items: flex-start; flex-direction: column; gap: 8px; }
  .work-priority > header, .work-priority-item { padding: 16px; }
  .work-priority-item { gap: 10px; }
  .work-refresh { flex-wrap: wrap; gap: 8px; }
  .work-item-heading { flex-wrap: wrap; }
  .work-item { grid-template-columns: 1fr; gap: 7px; }
}
@media (max-width: 1100px) { .work-focus-grid { grid-template-columns: minmax(0, 1fr); } .work-category-summary { max-height: 260px; } }
</style>
