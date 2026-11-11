<script setup lang="ts">
import BusinessTable from './BusinessTable.vue'
import { taskSyncHint, taskElapsedLabel, taskVarianceLabel } from '../modules/milestones'
import { computed, inject, nextTick, onBeforeUnmount, ref, useId, watch, type Ref } from 'vue'
import type { Row, Command } from '../types'
import { all, read, download } from '../api'
import {
  columns,
  endpoint,
  display,
  createLabel,
  createCommand,
  actionNames,
  actionCommand,
} from '../business'
import { message } from '../utils/request'
import { money } from '../utils/money'
import { sessionStore } from '../utils/storage'
import { savedTarget, wideCommand } from '../form-experience'
import ActionDialog from './ActionDialog.vue'
import TaskTimeRecords from './TaskTimeRecords.vue'
import ListPagination from './ListPagination.vue'
import TransferTools from './TransferTools.vue'
import BOMPurchasePicker from './BOMPurchasePicker.vue'
import AttachmentDialog from './AttachmentDialog.vue'
import { pageSize as globalPageSize } from '../pagination'
import { Refresh } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { user, operations, hasRoles } from '../session'
import StatusBadge from './StatusBadge.vue'
import RecordContext from './RecordContext.vue'
import RemoteSelect from './RemoteSelect.vue'
import { scopedImportProject } from '../utils/import-context'
import { extraFilters, filterQuery, isOverdueCell, resourceFilters, searchableResources, sidePanelResources } from '../resource-ui'
import { today } from '../forms'
import { actionGroup, actionGroups, primaryActions } from '../row-actions'
import { flowFor } from '../flows'
import { buyer, labels } from '../modules/shared'
import { canDeleteRecords, deletionLimit, deletionLabel } from '../modules/deletions'
import { useBatchSelection } from '../utils/batch-selection'
import RecordDeletionDialog from './RecordDeletionDialog.vue'
import { openDocumentPreview } from '../document-preview'
import { batchMode, setBatchMode } from '../batch-mode'
const route = useRoute()
const router = useRouter()
const props = withDefaults(defineProps<{
  resource: string
  title: string
  params?: Row
  projectId?: number
  revision?: number
  allowCreate?: boolean
  // 覆盖内置的空状态说明；页面在别处提供了入口（如页签内的按钮）时用它给出准确指引。
  emptyHint?: string
  // 不显示「可联系负责此业务的同事处理」（页面已提供其他入口，或联系同事没有意义）。
  hideContactHint?: boolean
  // 每页条数下限（全局设置更小时按它显示）；项目内任务表默认 50，免得六阶段任务翻页。
  defaultPageSize?: number
}>(), { allowCreate: true })
const pageFloor = computed(() => props.defaultPageSize ?? (props.resource === 'tasks' && props.projectId ? 50 : 0))
const pageSize = computed(() => Math.max(globalPageSize.value, pageFloor.value))
// 手机宽度下任务表改成「名称格内带主操作」，不依赖横向滑动。
const mobile = ref(typeof window !== 'undefined' && !!window.matchMedia?.('(max-width: 600px)').matches)
if (typeof window !== 'undefined' && window.matchMedia) {
  const query = window.matchMedia('(max-width: 600px)')
  const sync = () => { mobile.value = query.matches }
  query.addEventListener?.('change', sync)
  onBeforeUnmount(() => query.removeEventListener?.('change', sync))
}
// 手机宽度的窄屏列表：只留名称、状态和操作，其余信息并入名称格的副行（完整信息在详情里）。
const mobileTasks = computed(() => mobile.value && (sidePanelResources.includes(props.resource) || props.resource === 'projects'))
const emit = defineEmits<{ changed: [] }>()
const records = ref<Row[]>([])
const count = ref(0)
const page = ref(1)
const searchKey = () => `resource-search-${user.value?.id}-${props.resource}-${JSON.stringify(props.params || {})}`
const initialSearch = () => props.resource === 'sales' && typeof route.query.search === 'string' ? route.query.search : sessionStore.get(searchKey()) || ''
const search = ref(initialSearch())
const appliedSearch = ref(search.value)
const loading = ref(false)
const error = ref('')
const command = ref<Command | null>(null)
const actionDialog = ref<{ confirmLeave: () => Promise<boolean> }>()
const wide = computed(() => wideCommand(command.value))
const savedRecord = ref<{ title: string; resource: string; id: number; project?: number; timeTask?: number } | null>(null)
const timeTask = ref<number | null>(null)
const hasFilter = computed(() => !!(appliedSearch.value || filterValue.value || Object.keys(appliedExtra.value).length))
const fallbackHint = computed(() => ({
  purchases: '按项目缺料可从 BOM 多选下单；零星物料可新建采购。',
  projects: '已签约销售请从销售单生成项目，避免重复创建。',
  entries: '签约、批准采购会自动产生应收应付；费用通过登记费用添加。',
  stocks: '采购收货后自动增加库存；首次启用可登记期初库存。',
  documents: '上传图纸、合同或业务凭证，便于项目成员协作。',
  tasks: '先新增任务，选择执行人和计划完成日期，任务会出现在执行人的工作台。',
} as Record<string, string>)[props.resource] || (createLabel(props.resource) && props.allowCreate ? '可通过页面上方的新增或导入入口建立记录。' : '当前账号可查看的业务尚无记录。'))
async function leaveCurrent() { return !actionBusy.value && (!actionDialog.value?.confirmLeave || await actionDialog.value.confirmLeave()) }
async function openBom() { if (await leaveCurrent()) { command.value = null; pickingBom.value = true } }
const pickingBom = ref(false)
const moduleFocusedFlow = inject<Ref<boolean>>('moduleFocusedFlow', ref(false))
watch(pickingBom, value => { moduleFocusedFlow.value = value })
onBeforeUnmount(() => { moduleFocusedFlow.value = false })
const bomTrigger = ref<{ $el: HTMLElement }>()
async function closeBom() { pickingBom.value = false; await nextTick(); bomTrigger.value?.$el.focus() }
function savedBom() { void closeBom(); saved() }
const actionBusy = ref(false)
const filterValue = ref('')
const enabledFilter = ref(''), locationFilter = ref(''), brandFilter = ref('')
const dateFrom = ref(''), dateTo = ref('')
const supplierFilter = ref<string | number>()
const notCustomer = (partner: Row) => partner.kind !== 'customer'
watch(supplierFilter, (value, before) => { if (value !== before) searchRecords() })
const appliedExtra = ref<Row>({})
const unsettled = ref(false)
const extraConfig = computed(() => extraFilters[props.resource] || [])
const filterId = useId()
const filtersOpen = ref(false)
// 窄屏下筛选控件多于 2 个时收起，只留搜索框和「筛选 · N」；N 为已填写的筛选数。
const filterControls = computed(() => (props.resource === 'users' && filterConfig.value ? 1 : 0) + (['users', 'items', 'partners'].includes(props.resource) ? 1 : 0) + (props.resource === 'stocks' ? 1 : 0) + (['stocks', 'items'].includes(props.resource) ? 1 : 0) + (['purchases', 'entries'].includes(props.resource) ? 1 : 0) + (props.resource === 'audit' ? 2 : 0) + extraConfig.value.length)
const collapsible = computed(() => mobile.value && filterControls.value > 2)
const activeFilters = computed(() => [
  props.resource === 'users' && filterValue.value, enabledFilter.value, locationFilter.value, brandFilter.value, unsettled.value, dateFrom.value, dateTo.value, supplierFilter.value != null && props.resource === 'purchases',
  ...Object.values(extraValues.value),
].filter(Boolean).length)
const blankExtra = () => Object.fromEntries(extraConfig.value.map(item => [item.key, '']))
const extraValues = ref<Record<string, string>>(blankExtra())
const directory = ref<Row[]>([])
watch(() => props.resource, async () => {
  if (!extraConfig.value.some(item => item.kind === 'person')) return
  try { directory.value = await all('/auth/directory/') } catch { directory.value = [] }
}, { immediate: true })
const personOptions = (roles: string[] = []) => directory.value.filter(u => !roles.length || hasRoles(u, roles)).map(u => ({ value: u.id, label: String(u.display_name || u.username) }))
const filterConfig = computed(() => resourceFilters[props.resource])
const filterParams = computed(() => ({
  ...filterQuery(filterConfig.value, filterValue.value),
  ...appliedExtra.value,
}))
const sidePanel = computed(() => sidePanelResources.includes(props.resource))
const selectedId = ref<number | null>(null)
const selectedRow = ref<Row | null>(null)
const deletionAllowed = computed(() => canDeleteRecords(props.resource))
const deletionSelection = ref<Row[]>([])
const batchVisible = computed(() => deletionAllowed.value && batchMode.value)
watch(batchVisible, visible => { if (!visible) { selectionGeneration++; selectingAll.value = false; deletionSelection.value = [] } })
const batch = useBatchSelection(deletionSelection, 'id', () => deletionLimit(props.resource))
const selectingAll = ref(false)
let selectionGeneration = 0
onBeforeUnmount(() => { selectionGeneration++ })
watch(deletionAllowed, allowed => {
  if (!allowed) { selectionGeneration++; selectingAll.value = false; deletionSelection.value = [] }
})
async function selectFilteredRows() {
  if (!deletionAllowed.value || loading.value || actionBusy.value || selectingAll.value) return
  const current = ++selectionGeneration
  const params = { ...props.params, ...filterParams.value, search: appliedSearch.value }
  selectingAll.value = true; error.value = ''
  try {
    const path = endpoint(props.resource)
    await batch.replacePages(
      (page, page_size) => read(path, { ...params, page, page_size }),
      () => current === selectionGeneration && deletionAllowed.value,
    )
  } catch (e) { if (current === selectionGeneration) error.value = message(e) }
  finally { if (current === selectionGeneration) selectingAll.value = false }
}
const deleting = ref<Row[] | null>(null)
const deletionHistory = ref(false)
async function openDeletion(rows: Row[]) {
  if (deletionAllowed.value && rows.length && await leaveCurrent()) deleting.value = [...rows]
}
async function openDeletionHistory() {
  if (deletionAllowed.value && await leaveCurrent()) deletionHistory.value = true
}
function deleted() {
  deletionSelection.value = []; command.value = null; selectedRow.value = null; selectedId.value = null; savedRecord.value = null
  page.value = 1; void load(); emit('changed')
}
async function openRemoved(id: number) {
  try { const row = await read(`${endpoint(props.resource)}${id}/`); deletionHistory.value = false; await inspect(row) }
  catch (e) { error.value = message(e) }
}
const active = inject<Ref<boolean>>('panelActive', computed(() => true))
const toolbarTarget = inject<Ref<HTMLElement | null>>('moduleToolbar', ref(null))
const preparing = ref(false)
let commandGeneration = 0
let dirty = true
onBeforeUnmount(() => { generation++; commandGeneration++ })
const attachmentRow = ref<Row | null>(null)
let generation = 0
let focused = ''
// Columns merged as "main value + secondary line": the secondary column is dropped from the
// header so the table fits its container. A right-fixed action column overlaps whatever sits
// under it and the body never scrolls horizontally, so an extra column would be unreachable.
const merged: Record<string, Record<string, string | string[]>> = {
  sales: { code: 'project_code', name: 'customer_name' },
  projects: { name: 'code' },
  users: { display_name: 'username' },
  entries: { title: 'kind', partner_name: 'project_name', due_date: ['due_amount', 'agreed_payment_date'], balance: 'paid_amount' },
  tasks: { title: 'project_name', stage_label: 'milestone_label', assignee_name: ['supervisor_name', 'discipline_label'], due_date: ['completed_date', 'schedule_variance_days'], logged_hours: ['elapsed_days', 'started_date'] },
  time: { task_title: 'project_name' },
  stocks: { item_name: 'item_code', specification: 'brand' },
  purchases: { supplier_name: 'project_name', payment_term: 'payment_due_date' },
  items: { drawing_number: 'drawing_revision', specification: ['unit', 'brand'], product_category: 'part_type' },
}
// 项目页里的列表已经限定了项目，副行不再重复项目名。
const pairs = computed<Record<string, string[]>>(() => Object.fromEntries(
  Object.entries(merged[props.resource] || {})
    .map(([key, secondary]) => [key, [secondary].flat().filter(name => !props.projectId || name !== 'project_name')] as [string, string[]])
    .filter(([, secondary]) => secondary.length),
))
const combinedKey = computed(() => Object.keys(pairs.value)[0])
const secondaryKeys = computed(() => new Set(Object.values(pairs.value).flat()))
// 副行没有内容（空值、「—」）时不画一行空白。
function secondaryText(row: Row, key: string) {
  const format = columns[props.resource]?.find(c => c.key === key)?.format
  const text = format ? format(row) : cell(row, key)
  return text === '—' ? '' : text
}
// 合并列的表头里，副列名用简称，免得表头折成三四行。
const shortLabels: Record<string, string> = { supervisor_name: '主管', discipline_label: '专业', completed_date: '实际完成', schedule_variance_days: '提前/延期', started_date: '开始日', elapsed_days: '历时', milestone_label: '节点', due_amount: '到期金额', agreed_payment_date: '约定付款日' }
function columnLabel(col: { key: string; label: string }) {
  const secondary = pairs.value[col.key]
  return secondary ? [col.label, ...secondary.map(key => shortLabels[key] || labelOf(key))].join(' / ') : col.label
}
// 列宽按内容类型定：名称类给足宽度承担弹性，日期、金额、短状态收窄，1366 宽下不出现底部横向滚动。
const nameColumns = new Set(['supplier_name', 'project_name', 'customer_name', 'partner_name', 'item_name', 'task_title'])
function columnWidth(col: { key: string; format?: unknown }) {
  const key = col.key
  if (key === 'stage_label') return 150
  if (key === combinedKey.value || key === 'title' || key === 'name') return props.resource === 'tasks' ? 180 : props.resource === 'projects' ? 260 : 190
  if (key === 'status' && col.format) return 150
  if (key === 'payment_term') return 130
  if (['status', 'is_active'].includes(key)) return 100
  if (['discipline_label', 'logged_hours'].includes(key)) return 104
  if (nameColumns.has(key)) return 180
  if (key === 'specification') return 150
  if (key.endsWith('_date') || key === 'date') return 110
  if (moneyKeys.has(key)) return 110
  return 125
}
const labelOf = (key: string) => columns[props.resource]?.find(c => c.key === key)?.label
// 只调整列表里的先后：状态和日期紧跟名称，窄屏下不会被右侧固定的操作列挡住。导出与字段定义的顺序不变。
const leading: Record<string, string[]> = {
  tasks: ['title', 'status', 'assignee_name', 'due_date'],
  purchases: ['code', 'status', 'next_delivery_date', 'supplier_name', 'project_name'],
  entries: ['title', 'status', 'balance', 'partner_name'],
}
const shownColumns = computed(() => {
  const visible = (columns[props.resource] || []).filter(col => (!props.projectId || col.key !== 'project_name') && !secondaryKeys.value.has(col.key))
  const first = leading[props.resource] || []
  const rank = (key: string) => first.includes(key) ? first.indexOf(key) : first.length
  const sorted = columns[props.resource] ? visible.map((col, index) => ({ col, index })).sort((a, b) => rank(a.col.key) - rank(b.col.key) || a.index - b.index).map(item => item.col) : undefined
  return mobileTasks.value && sorted ? sorted.filter((col, index) => index === 0 || ['status', 'is_active'].includes(col.key)) : sorted
})
// 窄屏下被收进名称格副行的列（不含首列自己的合并副行，那些本来就显示在名称下面）。
const hiddenColumns = computed(() => (columns[props.resource] || []).filter(col => {
  const first = shownColumns.value?.[0]?.key
  return !shownColumns.value?.some(c => c.key === col.key) && !pairs.value[first || '']?.includes(col.key) && (!props.projectId || col.key !== 'project_name')
}))
// 按钮写明方向：应收是收款，应付和费用是付款；动作本身仍是同一个「登记收付款」。
function actionLabel(row: Row, name: string) {
  if (props.resource !== 'entries' || name !== '登记收付款' || String(row.balance).startsWith('-')) return name
  return row.kind === 'receivable' ? '登记收款' : '登记付款'
}
// 操作列宽度随内容走：只有「操作 ▾」或只有一个主按钮的资源收窄到 96，腾出空间给数据列。
const actionWidth = computed(() => {
  if (batchVisible.value) return 230
  // 窄屏：操作列按最长的单个文字按钮收窄/放宽，不让「查看银行明细」这类按钮被裁掉。
  if (mobileTasks.value) return Math.max(84, ...records.value.map(row => { const sole = soleAction(row); return sole ? sole.length * 13 + 30 : 84 }))
  if (!records.value.length) return 180
  return Math.max(...records.value.map(row => {
    if (props.resource === 'tasks' && taskSyncHint(row)) return 180
    const primary = !mobileTasks.value && primaryAction(row)
    const menu = menuGroups(row).length > 0
    return primary && menu ? 180 : menu || primary ? 96 : 60
  }))
})
// 菜单里只有一项（且没有主按钮）时直接显示成文字按钮，不套下拉。
function soleAction(row: Row) {
  if (primaryAction(row) && !mobileTasks.value) return undefined
  const groups = menuGroups(row)
  return groups.length === 1 && groups[0]!.actions.length === 1 ? groups[0]!.actions[0] : undefined
}
function primaryAction(row: Row) {
  const actions = actionNames(props.resource, row)
  return primaryActions.find(name => actions.includes(name))
}
// The menu never repeats the headline button, and only labels its groups when there is more than one.
function menuGroups(row: Row) {
  const rest = actionNames(props.resource, row).filter(name => name !== primaryAction(row))
  return actionGroups
    .map(group => ({ ...group, actions: rest.filter(name => actionGroup(name) === group.key) }))
    .filter(group => group.actions.length)
}
const moneyKeys = new Set(['amount', 'credit_amount', 'paid_amount', 'balance', 'due_amount', 'value', 'unit_price', 'contract_amount', 'quote_amount', 'fee', 'hourly_cost', 'supplier_credit'])
const day = today()
function cell(row: Row, key: string) {
  // 签约默认的应收标题都是「合同款」；跨项目列表里把项目名放在前面，一眼能分清是哪一笔。
  if (props.resource === 'entries' && key === 'title' && row.kind === 'receivable' && !props.projectId && row.project_name) return `${row.project_name} · ${row.title}`
  if (!moneyKeys.has(key) || row[key] == null) return display(row[key], key)
  return money(row[key], { refund: key === 'balance' })
}
// 每行 1~2 行摘要；窄屏模式下把被隐藏的列并进来，关键信息不丢。
const joined = (...parts: unknown[]) => parts.filter(part => part != null && part !== '' && part !== '—').join(' · ')
function mobileSummary(row: Row): string[] {
  const lines = (...rows: string[]) => rows.filter(Boolean)
  if (props.resource === 'purchases' && row.change_request) return ['修改申请待处理']
  if (props.resource === 'entries') return lines(`待结算 ${cell(row, 'balance')} · ${display(row.kind)}`, mobileTasks.value ? joined(row.partner_name, props.projectId ? '' : row.project_name, row.due_date ? `到期 ${row.due_date}` : '') : '')
  if (props.resource === 'payments' && !mobileTasks.value) return [`${cell(row, 'amount')} 元 · ${row.date}`]
  // 状态已有独立的列，窄屏的名称格下改写成「计划日期 · 执行人」，不再把状态重复一遍。
  if (props.resource === 'tasks') return lines(joined(row.due_date ? `计划 ${row.due_date}` : '', row.assignee_name), mobileTasks.value ? joined(props.projectId ? '' : row.project_name, row.stage_label, row.milestone_label) : '')
  if (props.resource === 'projects') return [joined(row.customer_name, row.due_date ? `交期 ${row.due_date}` : '', row.manager_name)]
  if (mobileTasks.value) {
    if (props.resource === 'purchases') {
      const amount = row.total_amount ?? row.amount
      return lines(joined(row.supplier_name, props.projectId ? '' : row.project_name), joined(amount != null && amount !== '' ? `金额 ${money(amount)}` : '', row.next_delivery_date ? `下一交期 ${row.next_delivery_date}` : ''))
    }
    if (props.resource === 'items') return lines(joined(row.name, row.specification, row.brand), joined(row.unit, row.drawing_number, columns.items?.find(col => col.key === 'part_type')?.format?.(row)))
    // 对账、银行流水、收付款流水：两行摘要，金额统一走 money。
    if (props.resource === 'reconciliations') return lines(joined(row.partner_name || row.entry_title, props.projectId ? '' : row.project_name), joined(row.approved_amount != null && row.approved_amount !== '' ? `额度 ${money(row.approved_amount)}` : '', row.difference != null && row.difference !== '' ? `差异 ${money(row.difference)}` : '', row.confirmed_name))
    if (props.resource === 'bank-records') {
      const amountValue = Number(row.amount)
      const statusText = columns[props.resource]?.find(col => col.key === 'void_reason')?.format?.(row)
      return lines(joined(Number.isNaN(amountValue) ? '' : `${amountValue < 0 ? '支出' : '收入'} ${money(String(row.amount).replace(/^-/, ''))}`, row.account), joined(row.counterparty, row.remaining_amount != null && row.remaining_amount !== '' ? `待匹配 ${money(row.remaining_amount)}` : '', statusText))
    }
    if (props.resource === 'payments') return lines(joined(row.date, columns[props.resource]?.find(col => col.key === 'amount')?.format?.(row)), joined(row.partner_name, row.reconciliation_code, props.projectId ? '' : row.project_name))
    if (props.resource === 'users') return lines(joined(row.username, (row.roles || [row.role]).map((role: string) => labels[role] || role).join('、')))
    const rest = hiddenColumns.value.filter(col => !['roles', 'management_reports'].includes(col.key)).map(col => col.format ? col.format(row) : cell(row, col.key))
    return lines(joined(...rest))
  }
  return [joined(row.status && !shownColumns.value?.some(col => col.key === 'status') ? display(row.status) : '', row.quantity ? `数量 ${row.quantity}` : '')]
}
// 窄屏下摘要里逾期的计划日期标红。
const summaryOverdue = (row: Row) => (props.resource === 'tasks' && isOverdueCell('tasks', 'due_date', row, day)) || (props.resource === 'purchases' && isOverdueCell('purchases', 'next_delivery_date', row, day)) || (props.resource === 'projects' && isOverdueCell('projects', 'due_date', row, day))
async function load(preserveSelection: unknown = false) {
  selectionGeneration++; selectingAll.value = false
  if (preserveSelection !== true) deletionSelection.value = []
  if (!active.value) { dirty = true; return }
  dirty = false
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = await read(endpoint(props.resource), {
      ...props.params,
      ...filterParams.value,
      page: page.value,
      page_size: pageSize.value,
      search: appliedSearch.value,
    })
    if (current !== generation) return
    records.value = result.results
    count.value = result.count
    const focus = String(route.query.focus || '')
    if (route.query.resource === props.resource && /^\d+$/.test(focus) && focused !== focus) {
      const row = await read(`${endpoint(props.resource)}${focus}/`)
      if (current !== generation) return
      // 先记下已处理的 focus：这条记录不属于当前项目时也不该在每次刷新、翻页时重新取一遍。
      focused = focus
      const scopedProject = scopedImportProject(props.params, props.projectId)
      if (scopedProject && Number(row.project) !== scopedProject) return
      if (props.resource === 'purchases') await action(row, '查看明细')
      else if (props.resource === 'entries') await action(row, '查看收付流水')
      else if (props.resource === 'reconciliations') await action(row, '查看对账明细')
      else if (props.resource === 'bank-records') await action(row, '查看银行明细')
      else if (props.resource === 'tasks') { command.value = { title: '待办详情', path: '', readonly: true, initial: { ...row, description: row.description || '未填写', elapsed_label: taskElapsedLabel(row), variance_label: taskVarianceLabel(row) }, flow: flowFor(props.resource, row), fields: [{ key: 'title', label: '任务' }, { key: 'discipline_label', label: '负责专业' }, { key: 'supervisor_name', label: '负责主管' }, { key: 'description', label: '完成要求', type: 'textarea', wide: true }, { key: 'logged_hours', label: '已登记工时（小时）' }, { key: 'due_date', label: '计划完成日期' }, { key: 'completed_date', label: '实际完成日期' }, { key: 'started_date', label: '实际开始日期' }, { key: 'elapsed_label', label: '任务历时（自然日，含首尾日）' }, { key: 'variance_label', label: '提前／延期' }], actions: actionNames(props.resource, row).map(label => ({ label, run: () => action(row, label) })) } }
      else await inspect(row)
    }
  } catch (e) {
    if (current === generation) error.value = message(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
watch(
  [() => props.resource, () => JSON.stringify(props.params || {}), () => props.projectId, () => props.resource === 'sales' ? route.query.search : undefined],
  (_now, before) => {
    if (before?.length) { commandGeneration++; command.value = null; selectedId.value = null; selectedRow.value = null; preparing.value = false; deleting.value = null; deletionHistory.value = false; timeTask.value = null; savedRecord.value = null }
    page.value = 1
    search.value = initialSearch()
    appliedSearch.value = search.value
    focused = ''
    void load()
  },
  { immediate: true },
)
watch(pageSize, () => { page.value = 1; void load(true) })
watch(() => props.revision, () => { void load() })
watch(active, value => { if (value && dirty) void load() })
watch([() => route.query.focus, () => route.query.resource], () => {
  if (route.query.resource === props.resource && route.query.focus) void load()
})
async function create() {
  if (!(await leaveCurrent())) return
  selectedId.value = null
  selectedRow.value = null
  const current = ++commandGeneration
  preparing.value = true
  try {
    const next = await createCommand(props.resource, props.projectId)
    if (current === commandGeneration) command.value = next
  } catch (e) {
    if (current === commandGeneration) error.value = message(e)
  } finally { if (current === commandGeneration) preparing.value = false }
}
async function action(row: Row, name: string) {
  if (!(await leaveCurrent())) return
  selectedId.value = row.id
  selectedRow.value = row
  const current = ++commandGeneration
  preparing.value = true
  try {
    if (props.resource === 'tasks' && name === '查看工时') {
      command.value = null
      timeTask.value = row.id
      return
    }
    if (props.resource === 'purchases' && name === '预览采购合同') {
      await router.push(`/purchases/${row.id}/contract`)
      return
    }
    if (name === '附件' && ['sales', 'purchases'].includes(props.resource)) {
      command.value = null
      attachmentRow.value = row
      return
    }
    if (name === '预览附件') openDocumentPreview(row.id, row.original_name)
    else if (name === '预览凭证') openDocumentPreview(row.document, row.document_name)
    else if (name === '下载') await download(row.download_url, row.original_name)
    else if (name === '下载凭证') {
      const doc = await read(`/business/documents/${row.document}/`)
      await download(doc.download_url, doc.original_name)
    }
    else {
      const next = await actionCommand(props.resource, row, name)
      if (current !== commandGeneration) return
      if (next.readonly) next.actions = [...(next.actions || []), ...actionNames(props.resource, row).filter(label => label !== name).map(label => ({ label, run: () => action(row, label) }))]
      next.subject = row.code || row.title || row.reference || `#${row.id}`
      next.flow = flowFor(props.resource, row)
      command.value = next
    }
  } catch (e) {
    if (current === commandGeneration) error.value = message(e)
  } finally { if (current === commandGeneration) preparing.value = false }
}
const flashId = ref<number | null>(null)
let flashTimer: ReturnType<typeof setTimeout> | undefined
onBeforeUnmount(() => clearTimeout(flashTimer))
function saved(result?: Row) {
  // 任务的开始、完成、改期等行内动作只留顶部提示，不再把表格往下推；登记工时和新建仍保留回执。
  const quiet = props.resource === 'tasks' && selectedId.value != null && command.value?.title !== '登记工时'
  if (quiet && command.value) {
    savedRecord.value = null
    flashId.value = selectedId.value
    clearTimeout(flashTimer); flashTimer = setTimeout(() => { flashId.value = null }, 2000)
  } else if (result && command.value) {
    const target = savedTarget(command.value, result, selectedId.value)
    savedRecord.value = target ? { title: `${command.value.title}成功${result.code ? ` · ${result.code}` : ''}`, ...target, project: Number(selectedRow.value?.project || command.value.initial?.project || props.projectId) || undefined } : null
    if (savedRecord.value && command.value.title === '登记工时') {
      savedRecord.value.timeTask = Number(result.task || selectedId.value)
      if (result.hours != null) savedRecord.value.title = `工时已提交：${result.user_name} · ${result.date} · ${result.hours} 小时`
    }
  }
  if (props.revision === undefined) void load()
  emit('changed')
}
async function viewSaved() {
  const record = savedRecord.value
  if (!record || !(await leaveCurrent())) return
  if (record.timeTask) { command.value = null; timeTask.value = record.timeTask; return }
  if (record.resource === 'projects') { await router.push(`/projects/${record.id}`); return }
  if (record.resource !== props.resource) {
    const module = ['entries', 'payments', 'reconciliations', 'bank-records'].includes(record.resource) ? 'finance' : ['items', 'partners'].includes(record.resource) ? 'masterdata' : record.resource
    await router.push({ path: `/${module}`, query: { section: record.resource === 'bank-records' ? 'bank' : record.resource, resource: record.resource, focus: record.id, project: record.project || 'all' } }); return
  }
  try { await inspect(await read(`${endpoint(record.resource)}${record.id}/`)) } catch (e) { error.value = message(e) }
}
function resetFilters() {
  search.value = ''; filterValue.value = ''; enabledFilter.value = ''; locationFilter.value = ''; brandFilter.value = ''; unsettled.value = false; dateFrom.value = ''; dateTo.value = ''; extraValues.value = blankExtra()
  // 清空供应商由上面的 watch 触发查询；没有选供应商时才需要自己查。
  if (supplierFilter.value == null) searchRecords(); else supplierFilter.value = undefined
}
function searchRecords() {
  appliedExtra.value = {
    ...(enabledFilter.value && ['users', 'items', 'partners'].includes(props.resource) ? { is_active: enabledFilter.value } : {}),
    ...(locationFilter.value && props.resource === 'stocks' ? { location__icontains: locationFilter.value } : {}),
    // 精确匹配要求输对完整品牌名，输「施耐德」而库里存的是「Schneider」就只会得到空列表。
    ...(brandFilter.value && ['stocks', 'items'].includes(props.resource) ? { [props.resource === 'stocks' ? 'item__brand__icontains' : 'brand__icontains']: brandFilter.value } : {}),
    ...(unsettled.value && props.resource === 'entries' ? { unsettled: 'true' } : {}),
    ...(supplierFilter.value != null && props.resource === 'purchases' ? { supplier: supplierFilter.value } : {}),
    ...(props.resource === 'audit' && dateFrom.value ? { date_from: dateFrom.value } : {}),
    ...(props.resource === 'audit' && dateTo.value ? { date_to: dateTo.value } : {}),
    ...Object.fromEntries(Object.entries(extraValues.value).filter(([, value]) => value)),
  }
  appliedSearch.value = search.value
  sessionStore.set(searchKey(), appliedSearch.value)
  page.value = 1
  void load()
}
function closeCommand() {
  commandGeneration++
  preparing.value = false
  command.value = null
  selectedId.value = null
  selectedRow.value = null
  focused = ''
  if (route.query.resource === props.resource && route.query.focus) {
    const { focus: _focus, resource: _resource, ...query } = route.query
    void router.replace({ query })
  }
}
function changeFilter(value: string) {
  if (actionBusy.value) return
  filterValue.value = value
  page.value = 1
  void load()
}
async function inspect(row: Row) {
  if (!(await leaveCurrent())) return
  const names = actionNames(props.resource, row)
  const view = names.find(name => ['查看明细', '查看收付流水', '查看对账明细', '查看银行明细'].includes(name))
  if (view && props.resource !== 'entries') return action(row, view)
  if (['users', 'items', 'partners', 'company', 'codes'].includes(props.resource) && names.includes('编辑')) return action(row, '编辑')
  selectedId.value = row.id
  selectedRow.value = row
  command.value = { title: `${props.title}详情`, path: '', readonly: true, subject: row.code || row.name || row.title, flow: flowFor(props.resource, row),
    initial: Object.fromEntries((columns[props.resource] || []).map(col => [col.key, col.format ? col.format(row) : cell(row, col.key)])),
    fields: (columns[props.resource] || []).map(col => ({ key: col.key, label: col.label, wide: props.resource === 'audit' && col.key === 'detail' })),
    actions: names.map(label => ({ label, run: () => action(row, label) })),
  }
  // 执行人要在任务详情里读到交付标准：模板和新建任务都会填「完成要求」，空值明确显示「未填写」。
  if (props.resource === 'tasks') {
    const detail = command.value
    detail.initial = { ...detail.initial, description: row.description || '未填写' }
    detail.fields = [detail.fields[0]!, { key: 'description', label: '完成要求', type: 'textarea', wide: true }, ...detail.fields.slice(1)]
  }
}
</script>
<template>
  <BOMPurchasePicker v-if="pickingBom && resource === 'purchases'" :project-id="projectId" @close="closeBom" @saved="savedBom" />
  <div v-else class="resource-workspace" :class="{ 'with-detail': sidePanel && command, 'wide-workspace': sidePanel && wide }">
  <section class="panel resource-list" :aria-label="title">
    <header class="panel-heading">
      <h2>
        {{ title }} <span class="record-count">{{ count }}</span>
      </h2>
      <div v-if="filterConfig && resource !== 'users'" class="resource-status-tabs" :aria-label="filterConfig.label">
        <button :aria-pressed="!filterValue" :disabled="actionBusy" @click="changeFilter('')">全部</button>
        <button v-for="(label, value) in filterConfig.options" :key="value" :aria-pressed="filterValue === value" :disabled="actionBusy" @click="changeFilter(value)">{{ label }}</button>
      </div>
      <Teleport :to="toolbarTarget || 'body'" :disabled="!toolbarTarget || !active"><div class="toolbar">
        <!-- Leading with the entries that create work; BOM selection is the intended purchase path. -->
        <el-button v-if="resource === 'purchases' && buyer()" ref="bomTrigger" type="primary" :disabled="actionBusy" @click="openBom">从 BOM 多选下单</el-button>
        <el-button v-if="createLabel(resource) && allowCreate !== false" :type="resource === 'purchases' ? undefined : 'primary'" @click="create">{{
          createLabel(resource)
        }}</el-button>
        <TransferTools v-if="!['users', 'company', 'codes', 'audit'].includes(resource)" :resource="resource" :allow-import="resource !== 'stocks'" :path="endpoint(resource)" :project-id="scopedImportProject(params, projectId)" :params="{ ...params, ...filterParams, search: appliedSearch }" :table-columns="columns[resource]" @changed="saved" />
        <el-button :icon="Refresh" aria-label="刷新列表" title="刷新列表" @click="load" />
        <el-button v-if="deletionAllowed" :type="batchMode ? 'primary' : undefined" :plain="batchMode" :aria-pressed="batchMode" :disabled="actionBusy" @click="setBatchMode(!batchMode)">{{ batchMode ? '退出批量管理' : '批量管理' }}</el-button>
      </div></Teleport>
    </header>
    <form v-if="searchableResources.includes(resource)" class="resource-search" @submit.prevent="searchRecords">
      <input v-model="search" type="search" :aria-label="`搜索${title}`" placeholder="输入名称、编号或关键词" />
      <el-button v-if="collapsible" class="filter-toggle" :aria-expanded="filtersOpen" :aria-controls="`${filterId}-filters`" @click="filtersOpen = !filtersOpen">筛选{{ activeFilters ? ` · ${activeFilters}` : '' }} {{ filtersOpen ? '▴' : '▾' }}</el-button>
      <div :id="`${filterId}-filters`" class="resource-filter-group" :class="{ 'is-collapsed': collapsible && !filtersOpen }">
      <select v-if="resource === 'users' && filterConfig" v-model="filterValue" aria-label="筛选用户角色" @change="searchRecords"><option value="">全部角色</option><option v-for="(label, value) in filterConfig.options" :key="value" :value="value">{{ label }}</option></select>
      <select v-if="['users', 'items', 'partners'].includes(resource)" v-model="enabledFilter" aria-label="筛选启用状态" @change="searchRecords"><option value="">全部状态</option><option value="true">启用</option><option value="false">停用</option></select>
      <input v-if="resource === 'stocks'" v-model="locationFilter" aria-label="筛选库位" placeholder="库位关键词" />
      <input v-if="['stocks', 'items'].includes(resource)" v-model="brandFilter" aria-label="筛选品牌" placeholder="品牌关键词" />
      <RemoteSelect v-if="resource === 'purchases'" v-model="supplierFilter" path="/business/partners/" label="供应商筛选" :accept="notCustomer" commit-on-select />
      <label v-if="resource === 'entries'" class="inline-check"><input v-model="unsettled" type="checkbox" @change="searchRecords" />仅看未结</label>
      <template v-if="resource === 'audit'"><input v-model="dateFrom" type="date" aria-label="开始日期" title="开始日期" /><input v-model="dateTo" type="date" aria-label="结束日期" title="结束日期" /></template>
      <template v-for="item in extraConfig" :key="item.key">
        <select v-if="item.kind === 'person'" v-model="extraValues[item.key]" :aria-label="`筛选${item.label}`" @change="searchRecords"><option value="">全部{{ item.label }}</option><option v-for="option in personOptions(item.roles)" :key="option.value" :value="String(option.value)">{{ option.label }}</option></select>
        <select v-else-if="item.kind === 'sort'" v-model="extraValues[item.key]" :aria-label="item.label" @change="searchRecords"><option v-for="(label, value) in item.options" :key="value" :value="value">{{ label }}</option></select>
        <label v-else class="inline-check"><input type="checkbox" :checked="extraValues[item.key] === item.value" @change="extraValues[item.key] = ($event.target as HTMLInputElement).checked ? item.value! : ''; searchRecords()" />{{ item.label }}</label>
      </template>
      </div>
      <el-button native-type="submit" :loading="loading">搜索</el-button>
      <el-button v-if="search || filterValue || enabledFilter || locationFilter || brandFilter || unsettled || dateFrom || dateTo || supplierFilter != null || Object.values(extraValues).some(Boolean)" text @click="resetFilters">重置</el-button>
    </form>
    <p v-if="resource === 'tasks' && records.some(row => !row.can_confirm && !row.system_managed)" class="task-confirm-note">本项目任务由对应专业主管确认完成并登记工时。</p>
    <section v-if="savedRecord" class="saved-result" role="status"><strong>{{ savedRecord.title }}</strong><span>{{ savedRecord.timeTask ? '可查看本次记录及任务累计工时。' : '下一步：查看结果并继续处理。' }}</span><el-button @click="viewSaved">{{ savedRecord.timeTask ? '查看工时明细' : '查看结果并继续' }}</el-button><el-button text aria-label="关闭结果提示" @click="savedRecord = null">关闭提示</el-button></section>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
    <p v-if="preparing" role="status">正在准备操作…</p>
    <section v-if="!loading && !error && !records.length" class="empty-guidance" role="status"><strong>{{ hasFilter ? '没有符合当前筛选条件的记录' : projectId ? '当前项目还没有此类记录' : `还没有${title}记录` }}</strong><p>{{ hasFilter ? '可清除搜索和状态筛选后再查看。' : emptyHint || fallbackHint }}</p><el-button v-if="hasFilter" @click="resetFilters">清除筛选</el-button><p v-else-if="!emptyHint && !hideContactHint && (!createLabel(resource) || !allowCreate)">可联系负责此业务的同事处理；你能查看的记录以当前账号权限为准。</p></section>
    <div v-if="batchVisible" class="record-batch-selection" :aria-label="title + '批量选择'">
      <span>已选 <strong>{{ deletionSelection.length }}</strong> 项（跨页保留），每批最多 {{ deletionLimit(resource) }} 项</span>
      <el-button :loading="selectingAll" :disabled="loading || actionBusy || !count" @click="selectFilteredRows">{{ count > deletionLimit(resource) ? '选择筛选结果前' + deletionLimit(resource) + '项（跨页）' : '全选筛选结果（' + count + '项，跨页）' }}</el-button>
      <el-button text :disabled="selectingAll || loading || actionBusy || !deletionSelection.length" @click="deletionSelection = []">清空选择</el-button>
      <el-button type="danger" plain :disabled="!deletionSelection.length || loading || actionBusy || selectingAll" @click="openDeletion(deletionSelection)">批量删除{{ deletionSelection.length ? `（${deletionSelection.length}）` : '' }}</el-button>
      <el-button :disabled="actionBusy" @click="openDeletionHistory">已删除记录</el-button>
    </div>
    <BusinessTable :label="title" :numbered="!mobileTasks" :row-offset="(page - 1) * pageSize" :max-height="pageSize > 20 ? 560 : undefined" v-show="records.length || loading"
      v-loading="loading"
      :data="records"
      stripe
      row-key="id"
      :row-class-name="({ row }: { row: Row }) => [row.id === selectedId ? 'selected-record' : '', row.id === flashId ? 'flash-record' : ''].join(' ').trim()"
      empty-text="暂无记录"
      style="width: 100%"
    >
      <el-table-column v-if="batchVisible" label="选择" width="44">
        <template #header><input type="checkbox" :aria-label="'选择本页' + title" :checked="batch.all(records)" :indeterminate="batch.some(records)" :disabled="actionBusy || loading || selectingAll || !records.length || (deletionSelection.length >= deletionLimit(resource) && !batch.all(records))" @change="batch.togglePage(records)" /></template>
        <template #default="{ row }"><input type="checkbox" :aria-label="'选择' + title + ' ' + deletionLabel(row)" :checked="batch.has(row)" :disabled="actionBusy || loading || selectingAll || !batch.selectable(row)" @change="batch.toggle(row)" /></template>
      </el-table-column>
      <el-table-column
        v-for="col in shownColumns"
        :key="col.key"
        :label="columnLabel(col)"
        :align="moneyKeys.has(col.key) ? 'right' : 'left'"
        :min-width="mobileTasks ? (col.key === shownColumns?.[0]?.key ? 130 : 84) : columnWidth(col)"
        show-overflow-tooltip
      >
        <template #default="{ row }"
          ><router-link v-if="resource === 'projects' && col.key === 'name'" :to="`/projects/${row.id}`">{{
            row.name
          }}</router-link
          ><router-link v-else-if="resource === 'sales' && col.key === 'project_code' && row.project && operations()" :to="`/projects/${row.project}`">{{ row.project_code }}</router-link
          ><router-link v-else-if="col.link?.(row)" :to="col.link!(row)!">{{ col.format ? col.format(row) : cell(row, col.key) }}</router-link
          ><StatusBadge v-else-if="['status', 'is_active', 'kind'].includes(col.key)" :value="row[col.key]" :text="col.format?.(row)" :title="col.format?.(row)" :class="{ 'status-wrap': col.format }" />
          <el-button v-else-if="resource === 'tasks' && col.key === 'logged_hours'" link type="primary" @click="action(row, '查看工时')">{{ row.time_entry_count ? `${row.logged_hours} 小时` : '未登记 · 查看' }}</el-button>
          <span v-else-if="col.key === 'roles'" class="role-tags"><StatusBadge v-for="role in row.roles || [row.role]" :key="role" :value="role" :text="labels[role] || role" /></span>
          <StatusBadge v-else-if="col.key === 'management_reports'" :value="row[col.key] || row.is_superuser || (row.roles || [row.role]).includes('admin')" :text="row.is_superuser || (row.roles || [row.role]).includes('admin') ? '管理员默认' : row[col.key] ? '已授权' : '未授权'" />
          <button v-else-if="sidePanel && col.key === shownColumns?.[0]?.key" class="record-link" :disabled="actionBusy" @click="inspect(row)">{{ col.format ? col.format(row) : cell(row, col.key) }}</button>
          <span v-else-if="isOverdueCell(resource, col.key, row, day)" class="overdue-cell">{{ cell(row, col.key) }}<strong class="overdue-flag">已逾期</strong></span>
          <span v-else :title="col.tip?.(row) ?? (col.format ? col.format(row) : undefined)">{{ col.format ? col.format(row) : cell(row, col.key) }}</span><template v-for="secondary in pairs[col.key]" :key="secondary"><small v-if="secondaryText(row, secondary)" class="record-secondary">{{ secondaryText(row, secondary) }}</small></template><small v-if="col.key === shownColumns?.[0]?.key" class="mobile-row-summary" :class="{ 'is-overdue': mobileTasks && summaryOverdue(row) }"><span v-for="(line, index) in mobileSummary(row)" :key="index">{{ line }}</span></small><el-button v-if="mobileTasks && col.key === shownColumns?.[0]?.key && primaryAction(row)" class="mobile-primary-action" type="primary" size="small" :disabled="actionBusy" @click="action(row, primaryAction(row)!)">{{ actionLabel(row, primaryAction(row)!) }}</el-button></template
        >
      </el-table-column>
      <el-table-column label="操作" fixed="right" :width="actionWidth"
        ><template #default="{ row }"
          ><div class="row-actions"
            ><el-button v-if="primaryAction(row) && !mobileTasks" type="primary" size="small" @click="action(row, primaryAction(row)!)">{{ actionLabel(row, primaryAction(row)!) }}</el-button
            ><el-button v-if="soleAction(row)" size="small" @click="action(row, soleAction(row)!)">{{ soleAction(row) }}</el-button
            ><el-dropdown
              v-else-if="menuGroups(row).length"
              trigger="click"
              :persistent="false"
              @command="(name: string) => action(row, String(name))"
              ><el-button size="small">操作 ▾</el-button
              ><template #dropdown
                ><el-dropdown-menu
                  ><template v-for="group in menuGroups(row)" :key="group.key"
                    ><li v-if="menuGroups(row).length > 1" class="action-group-label" role="presentation">{{ group.label }}</li
                    ><el-dropdown-item v-for="name in group.actions" :key="name" :command="name">{{
                      name
                    }}</el-dropdown-item></template
                  ></el-dropdown-menu
                ></template
              ></el-dropdown
            ><span v-else-if="(!primaryAction(row) || mobileTasks) && !batchVisible" class="muted">—</span><el-button v-if="batchVisible" type="danger" text size="small" :disabled="actionBusy || loading" @click="openDeletion([row])">删除</el-button></div
          ><small v-if="resource === 'tasks' && taskSyncHint(row)" class="task-sync-hint">{{ taskSyncHint(row) }}<router-link :to="{ path: `/projects/${row.project}`, query: { tab: 'deliveries', section: 'deliveries' } }">查看交付进度</router-link></small></template
        ></el-table-column
      >
    </BusinessTable>
    <ListPagination :page="page" :total="count" :min-size="pageFloor" @change="page = $event; load(true)" />
    <AttachmentDialog v-if="attachmentRow" :owner="resource === 'sales' ? 'sale' : 'purchase'" :record="attachmentRow" @close="attachmentRow = null" />
    <RecordDeletionDialog v-if="deletionAllowed && (deleting || deletionHistory)" :resource="resource" :title="title" :rows="deleting || undefined" :project-id="scopedImportProject(params, projectId)" @close="deleting = null; deletionHistory = false" @saved="deleted" @open="openRemoved" />
  </section>
  <TaskTimeRecords v-if="timeTask" :task-id="timeTask" @close="timeTask = null" />
  <ActionDialog ref="actionDialog" :command="command" @replace="command = $event" :inline="sidePanel" @busy="actionBusy = $event" @close="closeCommand" @saved="saved"><template #context><RecordContext v-if="selectedRow && (['stocks', 'entries'].includes(resource) || (['sales', 'purchases'].includes(resource) && actionNames(resource, selectedRow).includes('附件')))" :resource="resource" :record="selectedRow" @attachments="action(selectedRow!, '附件')" /></template></ActionDialog>
  </div>
</template>

<style scoped>
.record-batch-selection { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 12px 0; }
.task-confirm-note { margin: 0 0 10px; font-size: 13px; color: var(--el-text-color-secondary); }
.resource-list :deep(.flash-record > td.el-table__cell) { background: var(--brand-wash) !important; transition: background .4s; }
.mobile-row-summary.is-overdue { color: var(--risk); }
.mobile-row-summary > span { display: block; }
.resource-filter-group { display: contents; }
.resource-search .filter-toggle { display: none; }
@media (max-width: 600px) {
  .resource-search .filter-toggle { display: inline-flex; min-height: 40px; }
  .resource-filter-group { display: flex; flex-wrap: wrap; gap: 8px; flex: 1 1 100%; order: 5; }
  .resource-filter-group.is-collapsed { display: none; }
  .resource-filter-group > * { flex: 1 1 140px; min-width: 0; }
  .resource-filter-group :is(select, input:not([type='checkbox'])) { width: 100%; max-width: none; }
  .resource-filter-group .inline-check { flex: 1 1 100%; min-height: 40px; }
  .resource-list :deep(.record-link) { white-space: normal; overflow-wrap: anywhere; }
  .resource-search { gap: 8px; }
  .resource-search > input[type='search'] { flex: 1 1 140px; min-width: 0; }
}
.mobile-primary-action { display: none; margin-top: 6px; }
@media (max-width: 600px) { .mobile-primary-action { display: inline-flex; min-height: 40px; } .row-actions :deep(.el-button) { min-height: 40px; } }
.task-sync-hint { display: flex; flex-direction: column; gap: 4px; margin-top: 6px; line-height: 1.5; color: var(--el-text-color-secondary); }
</style>
