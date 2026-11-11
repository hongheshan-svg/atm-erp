<script setup lang="ts">
import { batchMode, setBatchMode } from '../batch-mode'
import BusinessTable from './BusinessTable.vue'
import { computed, inject, nextTick, onBeforeUnmount, ref, useId, watch, type Ref } from 'vue'
import { read, write, download } from '../api'
import { downloadBOM, type BOMExportLayout } from '../api/bom'
import { actionCommand, bomCommand, permission } from '../business'
import { batchRemoveCommand, batchReviseCommand, unitNames } from '../modules/bom'
import { warehouse } from '../modules/shared'
import { today } from '../forms'
import { bomEditor, engineer, purchaseReader } from '../session'
import type { Row, Command } from '../types'
import { message, requestKey } from '../utils/request'
import ActionDialog from './ActionDialog.vue'
import ListPagination from './ListPagination.vue'
import BOMPurchasePicker from './BOMPurchasePicker.vue'
import { pageSize } from '../pagination'
import { productCategories } from '../product-categories'
import ImportFeedback from './ImportFeedback.vue'
import { importDestination, templateMismatch } from '../utils/import-context'
import RecordDeletionDialog from './RecordDeletionDialog.vue'
import { canDeleteRecords, deletionLimit } from '../modules/deletions'
import { useBatchSelection } from '../utils/batch-selection'
import { quantityText as qty } from '../utils/quantity'
const qtyCell = (_row: Row, _column: unknown, value: unknown) => qty(value)
const props = defineProps<{ projectId: number; revision?: number; status?: string; canEditBom?: boolean }>()
const emit = defineEmits<{ changed: [] }>()
const demand = ref<Row>({ lines: [] })
const preview = ref<Row | null>(null)
const error = ref('')
const busy = ref(false)
const importOpen = ref(false)
const importError = ref('')
const importFilename = ref('')
const importResult = ref<HTMLElement>()
const projectContext = ref<Row | null>(null)
const mismatch = ref<ReturnType<typeof templateMismatch>>(null)
const destination = computed(() => mismatch.value ? importDestination(mismatch.value.resource, props.projectId) : null)
const view = ref<'prepare' | 'purchase'>(bomEditor({ can_edit_bom: props.canEditBom }) || engineer() ? 'prepare' : 'purchase')
const fullColumns = ref(false)
// 手机宽度（≤600px）走窄屏模式：明细只留勾选、物料（名称、编码与摘要）和操作，不再左右翻；筛选和说明默认收起。
const mobile = ref(typeof window !== 'undefined' && !!window.matchMedia?.('(max-width: 600px)').matches)
if (typeof window !== 'undefined' && window.matchMedia) {
  const query = window.matchMedia('(max-width: 600px)')
  const sync = () => { mobile.value = query.matches }
  query.addEventListener?.('change', sync)
  onBeforeUnmount(() => query.removeEventListener?.('change', sync))
}
const filterId = useId()
const filtersOpen = ref(false), helpOpen = ref(false)
// 视图说明：桌面放在切换按钮旁的「?」悬停提示里，手机点「说明 ▾」展开。
const viewHelp = computed(() => view.value === 'prepare'
  ? '按单元核对规格、数量和需求日期；行尾「操作」可改单行或移除。'
  : '库存为共享库存，不预留，当前可用不保证后续可领；其他项目待领需协调。同物料不同单元独立选择，已领、在途及库存按行分摊，非单元实际领用记录。橙色「待批」是仍为草稿或待批准的采购，缺料已扣除，请跟进提交和审批。')
let importGeneration = 0
function closeImport() {
  importGeneration++
  importOpen.value = false
  preview.value = null
  importError.value = ''
  mismatch.value = null
  importFilename.value = ''
  busy.value = false
}
onBeforeUnmount(() => { importGeneration++ })
const importColumns = [
  { key: 'item_code', label: '物料编码' }, { key: 'assembly_unit', label: '单元' },
  { key: 'bom_change', label: '变更' }, { key: 'quantity', label: '需求数量' }, { key: 'change_note', label: '变更说明' },
  { key: 'required_date', label: '需求日期' }, { key: 'application_date', label: '申请日期' }, { key: 'applicant', label: '申请人' },
  { key: 'material_action', label: '物料处理方式' },
  { key: 'drawing_number', label: '图号' }, { key: 'drawing_revision', label: '图档版本' },
  { key: 'product_category', label: '产品编码类别' }, { key: 'unit', label: '单位' },
]
const importActions: Record<string, string> = { create: '新增', unchanged: '不变' }
// 预览表一眼分出新增行和修改行，修改行直接给出原数量；产品编码类别显示中文。
const previewRows = computed(() => (preview.value?.lines || []).map((row: Row) => ({ row: row.row, data: {
  ...row,
  bom_change: row.bom_action === 'update' ? `修改 ${qty(row.before_quantity)} → ${qty(row.quantity)}` : importActions[row.bom_action] || '',
  product_category: productCategories[row.product_category] || row.product_category,
  quantity: qty(row.quantity),
} })))
const command = ref<Command | null>(null)
const search = ref(''), brand = ref(''), unit = ref(''), partType = ref(''), shortageOnly = ref(view.value === 'purchase')
// 草稿和待批采购照常扣减缺料（防止重复下单），但「仅看缺料」默认仍保留这些行，草稿被遗忘时还有人看得到。
const includeUnapproved = ref(true), overdueOnly = ref(false), inactiveOnly = ref(false)
// 窄屏「筛选 · N」：N 为当前生效的筛选条件数（采购视图默认的「仅看缺料」也算）。
const activeFilters = computed(() => [brand.value, unit.value, partType.value, shortageOnly.value, overdueOnly.value, inactiveOnly.value].filter(Boolean).length)
// 已停用物料：不能采购、不能改数量，只能替换或移除；整页提示并在行内标出。
const inactive = (line: Row) => line.is_active === false
const UNASSIGNED = '\u0000'
const selected = ref<number[]>([])
const deletionAllowed = computed(() => canDeleteRecords('bom'))
const batchVisible = computed(() => deletionAllowed.value && batchMode.value)
const deletionSelection = ref<Row[]>([]), deleting = ref<Row[] | null>(null), deletionHistory = ref(false)
const deletionLoading = ref(false)
const deletionMax = deletionLimit('bom')
const batch = useBatchSelection(deletionSelection, 'bom_line', () => deletionMax)
watch(batchVisible, allowed => { if (!allowed) { deletionSelection.value = []; deleting.value = null } })
function openDeletion(rows: Row[]) { deleting.value = rows.map(row => ({ ...row, id: row.bom_line })) }
watch([() => props.projectId, search, brand, unit, partType, shortageOnly, inactiveOnly, view], () => { deletionSelection.value = []; deleting.value = null; deletionHistory.value = false })
// 工程师的批量修订选择：与管理员的批量删除互斥，按稳定 BOM 行号跨页保留。
const maintainSelection = ref<Row[]>([])
const maintainMax = 500
const maintain = useBatchSelection(maintainSelection, 'bom_line', () => maintainMax)
const pickingBom = ref(false)
const moduleFocusedFlow = inject<Ref<boolean>>('moduleFocusedFlow', ref(false))
watch(pickingBom, value => { moduleFocusedFlow.value = value })
onBeforeUnmount(() => { moduleFocusedFlow.value = false })
const selectionTrigger = ref<{ $el: HTMLElement }>()
async function closePurchase() {
  pickingBom.value = false
  await nextTick()
  selectionTrigger.value?.$el.focus()
}
function savedPurchase() { void closePurchase(); saved() }
const canPurchase = computed(() => permission.buyer() && ['active', 'delivering', 'warranty'].includes(props.status || ''))
const canEdit = computed(() => bomEditor({ can_edit_bom: props.canEditBom }))
const canMaintain = computed(() => canEdit.value && ['draft', 'quoted', 'active', 'delivering'].includes(props.status || ''))
watch(canMaintain, value => { if (!value) { closeImport(); command.value = null } })
const maintainVisible = computed(() => canMaintain.value && view.value === 'prepare' && !batchVisible.value)
const canIssue = computed(() => warehouse() && ['active', 'delivering', 'warranty'].includes(props.status || ''))
watch(view, value => { shortageOnly.value = value === 'purchase'; sortKey.value = value === 'purchase' ? 'required_date' : 'unit'; sortAsc.value = true })
const options = (key: string) => [...new Set<string>(demand.value.lines.map((line: Row) => String(line[key] || '')).filter(Boolean))].sort()
const unapproved = (line: Row) => Number(line.unapproved || 0)
// 「在途」主数字只算已批准的采购，草稿和待批准的单独以「待批」标出。
const approvedIncoming = (line: Row) => (Number(line.incoming || 0) - unapproved(line)).toFixed(3)
const day = today()
// 需求日期已过、料还没到手（需求 − 已领 − 可用库存 > 0）就提示；已下单未到货的也要看得出来。
function overdue(line: Row) {
  if (!line.required_date || line.required_date >= day || !(Number(line.quantity) - Number(line.issued || 0) - Number(line.available || 0) > 0)) return ''
  if (Number(line.shortage) > 0) return '已逾期·缺料'
  return unapproved(line) > 0 ? '已逾期·采购待批' : '已逾期·在途未到'
}
type SortKey = 'unit' | 'required_date' | 'shortage'
const sortKey = ref<SortKey>(view.value === 'purchase' ? 'required_date' : 'unit'), sortAsc = ref(true)
const collator = new Intl.Collator('zh-CN', { numeric: true })
const byDate = (a: Row, b: Row) => (a.required_date ? 0 : 1) - (b.required_date ? 0 : 1) || String(a.required_date || '').localeCompare(String(b.required_date || ''))
const byShortage = (a: Row, b: Row) => Number(b.shortage || 0) - Number(a.shortage || 0)
const byUnit = (a: Row, b: Row) => (a.assembly_unit ? 0 : 1) - (b.assembly_unit ? 0 : 1) || collator.compare(a.assembly_unit || '', b.assembly_unit || '') || collator.compare(a.item_code || '', b.item_code || '')
const sorters: Record<SortKey, (a: Row, b: Row) => number> = {
  unit: byUnit,
  required_date: (a, b) => byDate(a, b) || byShortage(a, b),
  shortage: (a, b) => byShortage(a, b) || byDate(a, b),
}
// 编制按单元核对、采购按需求日期排优先级；分摊计算仍按物料顺序，这里只调整展示顺序（全部筛选结果，不只本页）。
function sortBy(key: SortKey) { if (sortKey.value === key) sortAsc.value = !sortAsc.value; else { sortKey.value = key; sortAsc.value = true } }
const sortMark = (key: SortKey) => sortKey.value !== key ? '' : (key === 'shortage' ? !sortAsc.value : sortAsc.value) ? ' ↑' : ' ↓'
const unitLabel = (value: string) => value === UNASSIGNED ? '未分单元' : value
const filtered = computed(() => demand.value.lines.filter((line: Row) =>
  (!brand.value || line.brand === brand.value) && (!unit.value || (unit.value === UNASSIGNED ? !line.assembly_unit : line.assembly_unit === unit.value)) &&
  (!partType.value || line.part_type === partType.value) && (!shortageOnly.value || Number(line.shortage) > 0 || (includeUnapproved.value && unapproved(line) > 0)) &&
  (!overdueOnly.value || Boolean(overdue(line))) && (!inactiveOnly.value || inactive(line)) &&
  [line.item_code, line.item_name, line.specification, line.drawing_number, line.brand].join(' ').toLowerCase().includes(search.value.trim().toLowerCase()),
).sort((a: Row, b: Row) => (sortAsc.value ? 1 : -1) * sorters[sortKey.value](a, b)))
// 单元齐套概览：每个单元多少行、缺几行、逾期几行，点一下就按该单元筛选。
const unitSummary = computed(() => {
  const groups = new Map<string, { unit: string; rows: number; short: number; overdue: number }>()
  for (const line of demand.value.lines as Row[]) {
    const key = line.assembly_unit || UNASSIGNED
    const group = groups.get(key) || { unit: key, rows: 0, short: 0, overdue: 0 }
    group.rows++
    if (Number(line.shortage) > 0) group.short++
    if (overdue(line)) group.overdue++
    groups.set(key, group)
  }
  return [...groups.values()].sort((a, b) => (a.unit === UNASSIGNED ? 1 : 0) - (b.unit === UNASSIGNED ? 1 : 0) || collator.compare(a.unit, b.unit))
})
watch([() => props.projectId, search, brand, unit, partType, shortageOnly, overdueOnly, inactiveOnly, view, maintainVisible], () => { maintainSelection.value = [] })
const inactiveCount = computed(() => demand.value.lines.filter(inactive).length)
watch(inactiveCount, count => { if (!count) inactiveOnly.value = false })
// 采购视图里「其他项目待领」整页都为 0 时不占列宽。
const showOtherDemand = computed(() => filtered.value.some((line: Row) => Number(line.other_demand) > 0))
const purchaseBlocked = (line: Row) => inactive(line) ? '物料已停用，不能采购；请联系工程师在 BOM 里用「替换物料」换成在用物料' : !eligible(line) ? '这一行没有缺料，不需要采购' : undefined
const eligible = (line: Row) => Number(line.shortage) > 0 && line.is_active !== false
const exporting = ref(false)
const exportSelection = computed<number[]>(() => view.value === 'purchase' ? selected.value : deletionSelection.value.map(row => row.bom_line))
const hiddenSelectionCount = computed(() => {
  const visibleIds = new Set(filtered.value.map((line: Row) => line.bom_line))
  return exportSelection.value.filter(id => !visibleIds.has(id)).length
})
async function exportRows(command: string) {
  if (exporting.value || deletionLoading.value || busy.value) return
  const [scope, format, template] = command.split(':')
  if (!['selected', 'filtered'].includes(scope || '') || !['xlsx', 'csv'].includes(format || '')) return
  const ids = scope === 'selected' ? [...exportSelection.value] : filtered.value.map((line: Row) => line.bom_line)
  if (!ids.length) return
  const project = props.projectId
  // 采购缺料视图导出缺料清单（带已领、在途、库存、缺料）；可回导模板按导入表头输出，改完直接回导。
  const layout: BOMExportLayout = template === 'import' ? 'import' : view.value === 'purchase' ? 'purchase' : 'standard'
  const prefix = { import: 'BOM回导模板', purchase: '缺料清单', standard: 'BOM' }[layout]
  exporting.value = true; error.value = ''
  try {
    await downloadBOM(project, ids, format as 'xlsx' | 'csv', `${prefix}_${scope === 'selected' ? '已选' : '筛选结果'}${ids.length}项.${format}`, layout)
  } catch (e) { if (project === props.projectId) error.value = message(e) }
  finally { exporting.value = false }
}
function toggle(line: Row) { selected.value = selected.value.includes(line.bom_line) ? selected.value.filter(id => id !== line.bom_line) : [...selected.value, line.bom_line] }
// 与采购页同名的唯一入口：带上已勾选的缺料行进入选料，未勾选时在选料页里再选。
function purchase() { pickingBom.value = true }
const impact = ref<Row | null>(null)
const impactAll = ref(false)
// 默认只列有已领或在途的物料，其余几百行全是 0 的物料折叠起来。
const impactRows = computed(() => (impact.value?.items || []).filter((row: Row) => impactAll.value || Number(row.issued) > 0 || Number(row.incoming) > 0))
const impactHidden = computed(() => (impact.value?.items.length || 0) - impactRows.value.length)
const purchaseStatus: Record<string, string> = { draft: '草稿', submitted: '待批准', approved: '待收货', partial: '部分收货' }
async function inspectImpact() {
  impactAll.value = false
  try { impact.value = await read(`/business/projects/${props.projectId}/bom-impact/`) } catch (e) { error.value = message(e) }
}
// BOM 变更记录：谁在什么时候把哪行从多少改成多少，取自修订审计，项目成员可读。
const changesOpen = ref(false), changeRows = ref<Row[]>([]), changeTotal = ref(0), changePage = ref(1), changeLoading = ref(false), changeError = ref('')
const changeSearch = ref(''), changeStart = ref(''), changeEnd = ref('')
const changeActions: Record<string, string> = { create: '新增', update: '修改', remove: '移除' }
let changeGeneration = 0
async function loadChanges(target = 1) {
  const id = ++changeGeneration
  changeLoading.value = true; changeError.value = ''
  try {
    const result = await read('/business/bom/changes/', {
      project: props.projectId, page: target, page_size: pageSize.value,
      ...(changeSearch.value.trim() ? { search: changeSearch.value.trim() } : {}),
      ...(changeStart.value ? { start: changeStart.value } : {}), ...(changeEnd.value ? { end: changeEnd.value } : {}),
    })
    if (id === changeGeneration) { changeRows.value = result.results; changeTotal.value = result.count; changePage.value = target }
  } catch (e) { if (id === changeGeneration) changeError.value = message(e) }
  finally { if (id === changeGeneration) changeLoading.value = false }
}
function openChanges() {
  changeSearch.value = ''; changeStart.value = ''; changeEnd.value = ''; changeRows.value = []; changeTotal.value = 0
  changesOpen.value = true
  void loadChanges(1)
}
watch(pageSize, () => { if (changesOpen.value) void loadChanges(1) })
watch(() => props.projectId, () => { changesOpen.value = false; changeGeneration++ })
const changeTime = (value: string) => String(value || '').replace('T', ' ').slice(0, 16)
const page = ref(1)
const visibleLines = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
watch([pageSize, () => demand.value.lines], () => { page.value = 1 })
watch([search, brand, unit, partType, shortageOnly, includeUnapproved, overdueOnly, inactiveOnly, sortKey, sortAsc], () => { page.value = 1 })
watch(() => props.projectId, () => { selected.value = []; demand.value = { lines: [] }; search.value = ''; brand.value = ''; unit.value = ''; partType.value = ''; shortageOnly.value = view.value === 'purchase'; overdueOnly.value = false; inactiveOnly.value = false; projectContext.value = null })
let generation = 0
async function load() {
  deletionSelection.value = []
  maintainSelection.value = []
  const id = ++generation
  deletionLoading.value = true
  try {
    const result = await read(`/business/projects/${props.projectId}/demand/`)
    if (id === generation) {
      demand.value = result
      selected.value = selected.value.filter(key => result.lines.some((line: Row) => line.bom_line === key && eligible(line)))
    }
  } catch (e) {
    if (id === generation) error.value = message(e)
  } finally { if (id === generation) deletionLoading.value = false }
}
watch(
  () => [props.projectId, props.revision],
  () => {
    if (importOpen.value) command.value = null
    closeImport()
    void load()
  },
  { immediate: true },
)
async function start() {
  error.value = ''
  try {
    command.value = await bomCommand(props.projectId)
  } catch (e) {
    error.value = message(e)
  }
}
// 行内直接改一条、替换物料或移除一条，不必再切到另一张「BOM 明细」表；提交仍走修订、替换与移除接口。
async function rowAction(line: Row, name: string) {
  error.value = ''
  try { command.value = await actionCommand('bom', { ...line, id: line.bom_line, project: props.projectId }, name) }
  catch (e) { error.value = message(e) }
}
function batchRevise(kind: 'date' | 'unit') {
  if (!maintainSelection.value.length) return
  command.value = batchReviseCommand(props.projectId, demand.value.revision, maintainSelection.value, kind, unitNames(demand.value.lines))
}
function batchRemove() { if (maintainSelection.value.length) command.value = batchRemoveCommand(props.projectId, maintainSelection.value) }
function batchCommand(name: string) {
  if (name === 'date' || name === 'unit') batchRevise(name)
  else if (name === 'remove') batchRemove()
  else if (name === 'all') maintain.replace(filtered.value)
  else maintainSelection.value = []
}
function more(name: string) {
  if (name === 'impact') void inspectImpact()
  else if (name === 'changes') openChanges()
  else if (name === 'refresh') void load()
  else if (name === 'deleted') deletionHistory.value = true
}
async function openImport() {
  closeImport()
  importOpen.value = true
  const projectId = props.projectId
  try {
    const context = await read(`/business/projects/${projectId}/`)
    if (projectId === props.projectId && importOpen.value) projectContext.value = context
  } catch (e) { if (projectId === props.projectId && importOpen.value) importError.value = message(e) }
}
async function template(format = 'xlsx') {
  try {
    await download('/business/projects/bom-template/', format === 'html' ? 'BOM导入填写说明.html' : `BOM导入模板.${format}`, { file_format: format })
  } catch (e) { importError.value = message(e) }
}
async function revealImportResult() {
  await nextTick()
  if (!preview.value && !importError.value) return
  const result = importResult.value
  const body = result?.closest<HTMLElement>('.el-dialog__body')
  if (!result || !body) return
  // Scroll only the dialog body; the confirmation footer and surrounding page stay in place.
  body.scrollTop += result.getBoundingClientRect().top - body.getBoundingClientRect().top
}
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const generation = ++importGeneration
  input.value = ''
  busy.value = true
  error.value = ''
  importError.value = ''
  mismatch.value = null
  importFilename.value = file.name
  importOpen.value = true
  preview.value = null
  const importingProject = props.projectId
  try {
    const body = new FormData()
    body.append('file', file)
    const result = await write(
      `/business/projects/${importingProject}/import-preview/`,
      body,
      requestKey(),
    )
    if (generation === importGeneration) preview.value = result
  } catch (e) {
    if (generation === importGeneration) { mismatch.value = templateMismatch(e); importError.value = mismatch.value?.message || message(e) }
  } finally {
    if (generation === importGeneration) {
      busy.value = false
      await revealImportResult()
    }
  }
}
function confirmImport() {
  if (!preview.value?.can_import) return
  const result = preview.value
  const summary = result.summary || {}
  const materials = (result.lines || []).filter((row: Row) => row.new_material).length
  const text = `将新增 ${summary.create ?? 0} 行、修改 ${summary.update ?? 0} 行${summary.unchanged ? `，与现有一致的 ${summary.unchanged} 行跳过` : ''}${result.token ? `，新建物料 ${materials} 个` : ''}。`
  if (result.token) {
    command.value = {
      title: '确认导入 BOM 与物料',
      submitLabel: '确认导入',
      path: `/business/projects/${props.projectId}/bom-import-confirm/`,
      fields: [],
      notice: { type: 'info', text: `${text}${result.note || ''}` },
      prepare: () => ({ token: result.token }),
    }
    return
  }
  command.value = {
    title: '确认导入 BOM',
    submitLabel: '确认导入',
    path: `/business/projects/${props.projectId}/revise-bom/`,
    previewPath: `/business/projects/${props.projectId}/bom-change-preview/`,
    fields: [],
    notice: { type: 'info', text },
    prepare: () => ({
      expected_revision: result.expected_revision,
      lines: result.lines.filter((r: Row) => r.bom_action !== 'unchanged').map((r: Row) => ({
        item: r.item,
        quantity: r.quantity,
        change_note: r.change_note,
        assembly_unit: r.assembly_unit,
        ...Object.fromEntries(['required_date', 'application_date', 'applicant'].filter(key => key in r).map(key => [key, r[key]])),
      })),
    }),
  }
}
function saved() {
  selected.value = []
  closeImport()
  void load()
  emit('changed')
}
</script>
<template>
  <BOMPurchasePicker v-if="pickingBom && canPurchase" :project-id="projectId" :initial-selection="selected" :shortage-only="shortageOnly" @close="closePurchase" @saved="savedPurchase" />
  <section v-else class="panel bom-demand-panel" aria-label="BOM 缺料需求">
    <!-- 桌面一行：标题、视图切换（说明在「?」悬停提示里）、工具栏；手机工具栏在上、视图切换另起一行。 -->
    <header class="panel-heading bom-panel-heading">
      <h2 class="bom-panel-title">BOM 与缺料</h2>
      <div class="bom-view-switch" role="group" aria-label="BOM 工作视图">
        <label><input v-model="view" type="radio" value="prepare" />编制用料</label>
        <label><input v-model="view" type="radio" value="purchase" />采购缺料</label>
        <button v-if="mobile" type="button" class="bom-help-toggle" :aria-expanded="helpOpen" @click="helpOpen = !helpOpen">说明 {{ helpOpen ? '▴' : '▾' }}</button>
        <el-tooltip v-else :content="viewHelp" placement="bottom-start" popper-class="bom-help-popper"><button type="button" class="bom-help-icon" :aria-label="`视图说明：${viewHelp}`">?</button></el-tooltip>
        <small v-if="mobile && helpOpen" class="muted">{{ viewHelp }}</small>
      </div>
      <div class="toolbar">
        <el-button v-if="canMaintain && view === 'prepare'" type="primary" :disabled="busy" @click="start">维护 BOM</el-button>
        <el-button v-if="canMaintain" :disabled="busy" @click="openImport">导入 BOM</el-button>
        <router-link v-if="canIssue" class="el-button bom-issue-link" :to="{ path: '/inventory', query: { project: String(projectId), issue: 'bom' } }">按 BOM 领料</router-link>
        <el-dropdown :disabled="busy || deletionLoading || exporting || (!filtered.length && !exportSelection.length)" @command="exportRows">
          <el-button aria-label="导出BOM" :loading="exporting" :disabled="busy || deletionLoading || (!filtered.length && !exportSelection.length)">导出<span class="export-scope-label">（{{ exportSelection.length ? `已选 ${exportSelection.length} 项` : `筛选结果 ${filtered.length} 项` }}）</span> ▾</el-button>
          <template #dropdown><el-dropdown-menu>
            <template v-if="exportSelection.length">
              <el-dropdown-item command="selected:xlsx">已选 {{ exportSelection.length }} 项 · Excel</el-dropdown-item>
              <el-dropdown-item command="selected:csv">已选 {{ exportSelection.length }} 项 · CSV</el-dropdown-item>
            </template>
            <el-dropdown-item command="filtered:xlsx" :divided="Boolean(exportSelection.length)" :disabled="!filtered.length">筛选结果 {{ filtered.length }} 项 · Excel</el-dropdown-item>
            <el-dropdown-item command="filtered:csv" :disabled="!filtered.length">筛选结果 {{ filtered.length }} 项 · CSV</el-dropdown-item>
            <el-dropdown-item v-if="canMaintain" :command="`${exportSelection.length ? 'selected' : 'filtered'}:xlsx:import`" divided>可回导模板 · Excel（{{ exportSelection.length || filtered.length }} 项，改完直接导入）</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
        <el-button v-if="!mobile" :aria-pressed="fullColumns" :aria-label="fullColumns ? '收起完整列' : '展开完整列（图号、品牌等）'" :title="fullColumns ? undefined : '加列显示图号、图档版本、品牌、申请人、变更说明等'" @click="fullColumns = !fullColumns">{{ fullColumns ? '收起完整列' : '展开完整列' }}</el-button>
        <el-button v-if="deletionAllowed" :type="batchMode ? 'primary' : undefined" :plain="batchMode" :aria-pressed="batchMode" :disabled="busy" @click="setBatchMode(!batchMode)">{{ batchMode ? '退出批量删除' : '批量删除（管理员）' }}</el-button>
        <el-button v-if="batchVisible && view === 'prepare'" type="danger" plain :disabled="busy || deletionLoading || !deletionSelection.length" @click="openDeletion(deletionSelection)">批量删除{{ deletionSelection.length ? `（${deletionSelection.length}）` : '' }}</el-button>
        <el-dropdown trigger="click" :persistent="false" @command="more">
          <el-button aria-label="更多BOM操作">更多 ▾</el-button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item command="changes">变更记录</el-dropdown-item>
            <el-dropdown-item v-if="canMaintain" command="impact">变更影响与处理</el-dropdown-item>
            <el-dropdown-item command="refresh">刷新需求</el-dropdown-item>
            <el-dropdown-item v-if="batchVisible" command="deleted" :disabled="busy">已删除记录</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
      </div>
    </header>
    <div v-if="unitSummary.length > 1" class="bom-unit-summary" role="group" aria-label="单元齐套概览">
      <button v-for="group in unitSummary" :key="group.unit" type="button" class="bom-unit-chip" :class="{ active: unit === group.unit }" :aria-pressed="unit === group.unit" @click="unit = unit === group.unit ? '' : group.unit"><strong>{{ unitLabel(group.unit) }}</strong><small><span class="bom-unit-rows">{{ group.rows }} 行 · </span><span :class="{ 'shortage-number': group.short }">缺 {{ group.short }}</span><template v-if="group.overdue"> · <span class="overdue-count">逾期 {{ group.overdue }}</span></template></small></button>
    </div>
    <p v-if="inactiveCount" class="bom-inactive-note" role="status"><el-tag size="small" type="info">已停用</el-tag><span>{{ view === 'purchase' ? `${inactiveCount} 行物料已停用，不能采购；请联系工程师在 BOM 里替换为在用物料。` : `${inactiveCount} 行物料已停用，不能修改数量或采购；请在行尾「操作」用「替换物料」换成在用物料，或移除。` }}</span><button type="button" class="bom-link-button" :aria-pressed="inactiveOnly" @click="inactiveOnly = !inactiveOnly">{{ inactiveOnly ? '显示全部' : '只看这些行' }}</button></p>
    <div class="bom-demand-filters">
      <label class="bom-search"><span class="bom-search-label">搜索物料</span><input v-model="search" aria-label="搜索 BOM 物料" placeholder="编码、名称、规格、图号、品牌" /></label>
      <el-button v-if="mobile" class="bom-filter-toggle" :aria-expanded="filtersOpen" :aria-controls="filterId" @click="filtersOpen = !filtersOpen">筛选{{ activeFilters ? ` · ${activeFilters}` : '' }} {{ filtersOpen ? '▴' : '▾' }}</el-button>
      <div :id="filterId" class="bom-filter-group" :class="{ 'is-collapsed': mobile && !filtersOpen }">
        <label><span class="bom-filter-caption">品牌</span><select v-model="brand" aria-label="筛选品牌"><option value="">全部品牌</option><option v-for="value in options('brand')" :key="value">{{ value }}</option></select></label><label><span class="bom-filter-caption">单元</span><select v-model="unit" aria-label="筛选单元"><option value="">全部单元</option><option v-for="value in options('assembly_unit')" :key="value">{{ value }}</option><option v-if="demand.lines.some((line: Row) => !line.assembly_unit)" :value="UNASSIGNED">未分单元</option></select></label><label><span class="bom-filter-caption">类别</span><select v-model="partType" aria-label="筛选类别"><option value="">全部类别</option><option value="standard">标准件</option><option value="custom">非标件</option></select></label>
        <label v-if="mobile"><span class="bom-filter-caption">排序</span><select v-model="sortKey" aria-label="排序方式" @change="sortAsc = true"><option value="unit">按单元</option><option value="required_date">按需求日期</option><option value="shortage">按缺料（多的在前）</option></select></label>
        <label class="shortage-toggle"><input v-model="shortageOnly" type="checkbox" />仅看缺料</label><label v-if="shortageOnly" class="shortage-toggle" title="草稿或待批准的采购已扣减缺料，勾选后这些行仍留在列表里"><input v-model="includeUnapproved" type="checkbox" />含待批采购</label><label class="shortage-toggle"><input v-model="overdueOnly" type="checkbox" />仅看逾期</label>
      </div>
    </div>
    <div v-if="batchVisible && view === 'prepare'" class="bom-batch-selection" aria-label="BOM批量选择">
      <span>已选 <strong>{{ deletionSelection.length }}</strong> 项（跨页保留），每批最多 {{ deletionMax }} 项</span>
      <el-button :disabled="busy || deletionLoading || !filtered.length" @click="batch.replace(filtered)">{{ filtered.length > deletionMax ? '选择筛选结果前' + deletionMax + '项（跨页）' : '全选筛选结果（' + filtered.length + '项，跨页）' }}</el-button>
      <el-button text :disabled="busy || deletionLoading || !deletionSelection.length" @click="deletionSelection = []">清空选择</el-button>
    </div>
    <div v-if="maintainVisible && filtered.length && maintainSelection.length" class="bom-batch-selection" aria-label="BOM批量修订">
      <span>已选 <strong>{{ maintainSelection.length }}</strong> 行（跨页保留）</span>
      <el-button v-if="!mobile" :disabled="busy || deletionLoading" @click="maintain.replace(filtered)">选择筛选结果（{{ Math.min(filtered.length, maintainMax) }} 行）</el-button>
      <el-dropdown v-if="mobile && maintainSelection.length" trigger="click" :persistent="false" @command="batchCommand">
        <el-button type="primary" plain :disabled="busy">批量操作 ▾</el-button>
        <template #dropdown><el-dropdown-menu><el-dropdown-item command="all" :disabled="deletionLoading">选择筛选结果（{{ Math.min(filtered.length, maintainMax) }} 行）</el-dropdown-item><el-dropdown-item command="date" divided>批量改需求日期</el-dropdown-item><el-dropdown-item command="unit">批量改单元</el-dropdown-item><el-dropdown-item command="remove">批量移除</el-dropdown-item><el-dropdown-item command="clear" divided>清空选择</el-dropdown-item></el-dropdown-menu></template>
      </el-dropdown>
      <template v-else>
        <el-button :disabled="busy" @click="batchRevise('date')">批量改需求日期</el-button>
        <el-button :disabled="busy" @click="batchRevise('unit')">批量改单元</el-button>
        <el-button type="danger" plain :disabled="busy" @click="batchRemove">批量移除</el-button>
        <el-button text :disabled="busy" @click="maintainSelection = []">清空选择</el-button>
      </template>
    </div>
    <el-dialog :model-value="Boolean(impact)" title="BOM 变更影响与处理" class="bom-mobile-dialog" width="min(900px, 94vw)" @close="impact = null">
      <template v-if="impact"><p>{{ impact.note }}</p><BusinessTable label="BOM变更影响" :data="impactRows" :numbered="!mobile" :max-height="mobile ? undefined : 360" empty-text="本项目物料都没有已领或在途"><el-table-column v-if="mobile" label="物料"><template #default="{ row }"><strong>{{ row.item_name }}</strong><small class="bom-item-code">{{ row.item_code }}</small><small class="bom-mobile-summary"><span>需求 {{ qty(row.quantity) }} · 已领 {{ qty(row.issued) }} · 在途 {{ qty(row.incoming) }}<template v-if="Number(row.unapproved) > 0">（待批 {{ qty(row.unapproved) }}）</template></span><span>当前最低可改量 <strong>{{ qty(row.minimum) }}</strong></span></small></template></el-table-column><template v-else><el-table-column prop="item_code" label="物料编码" /><el-table-column prop="item_name" label="物料" /><el-table-column prop="quantity" label="需求总量" :formatter="qtyCell" /><el-table-column prop="issued" label="已领" :formatter="qtyCell" /><el-table-column prop="incoming" label="在途（含待批）" :formatter="qtyCell" /><el-table-column prop="unapproved" label="其中待批" :formatter="qtyCell" /><el-table-column prop="minimum" label="当前最低可改量" :formatter="qtyCell" /></template></BusinessTable><p v-if="impactHidden && !impactAll" class="muted">其余 {{ impactHidden }} 种物料没有已领或在途，可直接修改。<el-button link type="primary" @click="impactAll = true">展开全部</el-button></p><template v-if="purchaseReader()"><p v-for="purchase in impact.purchases" :key="purchase.id"><router-link :to="{ path: `/projects/${projectId}`, query: { tab: 'purchases', resource: 'purchases', focus: purchase.id } }" @click="impact = null">{{ purchase.code }}（{{ purchaseStatus[purchase.status] || purchase.status }}）：查看采购并处理未收余量</router-link></p><router-link :to="{ path: '/inventory', query: { section: 'moves', project: projectId } }">查看本项目库存流水，处理未用材料退回</router-link></template><p v-else class="muted">涉及在途采购或领料时，请联系采购和仓库处理原单，再提交 BOM 变更。</p></template>
      <template #footer><el-button @click="impact = null">关闭</el-button></template>
    </el-dialog>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <BusinessTable label="BOM" :numbered="!mobile" :row-offset="(page - 1) * pageSize" :max-height="pageSize > 20 && !mobile ? 560 : undefined" class="bom-details-table" :data="visibleLines" row-key="bom_line" :empty-text="shortageOnly ? '当前筛选下没有缺料，可取消仅看缺料查看全部用料' : '尚未维护 BOM'">
      <el-table-column v-if="batchVisible && view === 'prepare'" label="选择" :width="mobile ? 40 : 44" fixed="left">
        <template #header><input type="checkbox" aria-label="选择本页BOM明细" :checked="batch.all(visibleLines)" :indeterminate="batch.some(visibleLines)" :disabled="busy || deletionLoading || !visibleLines.length || (deletionSelection.length >= deletionMax && !batch.all(visibleLines))" @change="batch.togglePage(visibleLines)" /></template>
        <template #default="{ row }"><input type="checkbox" :aria-label="'选择BOM明细 ' + row.item_code + ' ' + (row.assembly_unit || '')" :checked="batch.has(row)" :disabled="busy || deletionLoading || !batch.selectable(row)" @change="batch.toggle(row)" /></template>
      </el-table-column>
      <el-table-column v-if="maintainVisible" label="选择" :width="mobile ? 40 : 44" fixed="left">
        <template #header><input type="checkbox" aria-label="选择本页BOM行" title="勾选后可批量改需求日期、改单元或移除" :checked="maintain.all(visibleLines)" :indeterminate="maintain.some(visibleLines)" :disabled="busy || !visibleLines.length" @change="maintain.togglePage(visibleLines)" /></template>
        <template #default="{ row }"><input type="checkbox" :aria-label="'选择BOM行 ' + row.item_code + ' ' + (row.assembly_unit || '')" :checked="maintain.has(row)" :disabled="busy || !maintain.selectable(row)" @change="maintain.toggle(row)" /></template>
      </el-table-column>
      <el-table-column v-if="canPurchase && view === 'purchase'" :label="mobile ? '' : '选择'" :width="mobile ? 40 : 48" fixed="left"><template #default="{ row }"><input type="checkbox" :aria-label="`选择 ${row.item_code} ${row.assembly_unit || ''}`" :checked="selected.includes(row.bom_line)" :disabled="busy || !eligible(row)" :title="purchaseBlocked(row)" @change="toggle(row)" /></template></el-table-column>
      <el-table-column :label="mobile ? '物料' : '物料名称 / 编码'" :min-width="mobile ? 150 : 160" fixed="left"><template #default="{ row }"><strong>{{ row.item_name }}</strong><el-tag v-if="inactive(row)" size="small" type="info" class="bom-inactive-tag" :title="purchaseBlocked(row)">已停用</el-tag><small class="bom-item-code" :class="{ 'is-inline': !mobile }">{{ row.item_code }}</small>
        <small v-if="mobile && view === 'purchase'" class="bom-mobile-summary"><span><b :class="{ 'shortage-number': Number(row.shortage) > 0 }">缺 {{ qty(row.shortage) }}</b> · <i>在途 {{ qty(approvedIncoming(row)) }}</i><em v-if="unapproved(row) > 0" class="unapproved-inline">（待批 {{ qty(row.unapproved) }}）</em> · <i>可用 {{ qty(row.available) }}</i></span><span>{{ row.assembly_unit || '未分单元' }}<template v-if="row.required_date"> · <i>需 {{ row.required_date }}</i></template></span><strong v-if="overdue(row)" :class="Number(row.shortage) > 0 ? 'overdue-flag' : 'overdue-flag pending'">{{ overdue(row) }}</strong></small>
        <small v-else-if="mobile" class="bom-mobile-summary"><span>{{ [row.specification, row.assembly_unit || '未分单元'].filter(Boolean).join(' · ') }}</span><span><i>需求 {{ qty(row.quantity) }}{{ row.unit ? ` ${row.unit}` : '' }}</i> · <b :class="{ 'shortage-number': Number(row.shortage) > 0 }">缺 {{ qty(row.shortage) }}</b><template v-if="row.required_date"> · <i>{{ row.required_date }}</i></template></span><strong v-if="overdue(row)" :class="Number(row.shortage) > 0 ? 'overdue-flag' : 'overdue-flag pending'">{{ overdue(row) }}</strong></small>
      </template></el-table-column>
      <template v-if="!mobile">
      <el-table-column v-if="view === 'prepare'" prop="specification" label="规格" min-width="140" />
      <el-table-column prop="assembly_unit" label="单元" min-width="130" class-name="bom-unit-cell" show-overflow-tooltip><template #header><button type="button" class="sort-header" title="按单元、物料编码排序" @click="sortBy('unit')">单元{{ sortMark('unit') }}</button></template></el-table-column>
      <el-table-column prop="quantity" label="需求数量" width="78" align="right" :formatter="qtyCell" />
      <el-table-column prop="unit" label="单位" width="48" />
      <template v-if="view === 'purchase'">
        <el-table-column prop="issued" label="已领" width="64" align="right" :formatter="qtyCell" />
        <el-table-column label="在途" width="76" align="right"><template #default="{ row }">{{ qty(approvedIncoming(row)) }}<small v-if="unapproved(row) > 0" class="unapproved-number" :title="'草稿或待批准的采购 ' + qty(row.unapproved) + '，缺料已扣除，批准后转为在途'">待批 {{ qty(row.unapproved) }}</small></template></el-table-column>
        <el-table-column prop="available" label="可用库存" width="78" align="right" :formatter="qtyCell" />
        <el-table-column label="缺料" width="68" align="right"><template #header><button type="button" class="sort-header" title="缺料多的排前" @click="sortBy('shortage')">缺料{{ sortMark('shortage') }}</button></template><template #default="{ row }"><strong :class="Number(row.shortage) > 0 ? 'shortage-number' : 'muted'">{{ qty(row.shortage) }}</strong></template></el-table-column>
      </template>
      <el-table-column v-if="(view === 'purchase' && showOtherDemand) || fullColumns" label="其他项目待领" min-width="104" align="right" class-name="bom-nowrap-cell"><template #default="{ row }"><span v-if="Number(row.other_demand) > 0" :class="Number(row.available) > 0 ? 'contested-number' : 'muted'">{{ qty(row.other_demand) }}<small> · {{ row.other_projects }} 个项目</small></span><span v-else class="muted">—</span></template></el-table-column>
      <el-table-column label="需求日期" min-width="108"><template #header><button type="button" class="sort-header" title="需求日期早的排前" @click="sortBy('required_date')">需求日期{{ sortMark('required_date') }}</button></template><template #default="{ row }"><span v-if="overdue(row)" class="overdue-cell">{{ row.required_date }}<strong :class="Number(row.shortage) > 0 ? 'overdue-flag' : 'overdue-flag pending'">{{ overdue(row) }}</strong></span><span v-else>{{ row.required_date }}</span></template></el-table-column>
      <template v-if="fullColumns">
        <el-table-column v-if="view === 'purchase'" prop="specification" label="规格" min-width="140" />
        <el-table-column prop="drawing_number" label="图号" min-width="150" /><el-table-column prop="drawing_revision" label="图档版本" min-width="90" />
        <el-table-column label="产品编码类别" min-width="125"><template #default="{ row }">{{ productCategories[row.product_category] || '未分类' }}</template></el-table-column>
        <el-table-column prop="application_date" label="申请日期" min-width="110" /><el-table-column prop="applicant" label="申请人" min-width="100" />
        <el-table-column prop="brand" label="品牌" min-width="95" /><el-table-column label="物料类别" min-width="100"><template #default="{ row }">{{ ({ standard: '标准件', custom: '非标件' } as Record<string, string>)[row.part_type] || '未分类' }}</template></el-table-column>
        <el-table-column prop="change_note" label="变更说明" min-width="150" />
        <template v-if="view === 'prepare'"><el-table-column prop="issued" label="已领" :formatter="qtyCell" /><el-table-column prop="incoming" label="在途（含待批）" min-width="110" :formatter="qtyCell" /><el-table-column prop="available" label="可用库存" :formatter="qtyCell" /><el-table-column prop="shortage" label="缺料" :formatter="qtyCell" /></template>
      </template>
      </template>
      <el-table-column v-if="batchVisible || (canMaintain && view === 'prepare')" label="操作" :width="mobile ? 76 : batchVisible && canMaintain && view === 'prepare' ? 150 : 96" fixed="right"><template #default="{ row }"><div class="row-actions">
        <el-dropdown v-if="canMaintain && view === 'prepare'" trigger="click" :persistent="false" @command="(name: string) => rowAction(row, String(name))">
          <el-button size="small" :disabled="busy">操作 ▾</el-button>
          <template #dropdown><el-dropdown-menu><el-dropdown-item command="修改此行" :disabled="inactive(row)">{{ inactive(row) ? '修改此行（物料已停用，请替换）' : '修改此行' }}</el-dropdown-item><el-dropdown-item command="替换物料">替换物料</el-dropdown-item><el-dropdown-item v-if="!batchVisible" command="移除">移除</el-dropdown-item></el-dropdown-menu></template>
        </el-dropdown>
        <el-button v-if="batchVisible" type="danger" text size="small" :disabled="busy || deletionLoading" @click="openDeletion([row])">删除</el-button>
      </div></template></el-table-column>
    </BusinessTable>
    <el-dialog v-if="changesOpen" :model-value="true" title="BOM 变更记录" class="bom-change-dialog bom-mobile-dialog" width="min(1100px, 94vw)" top="6vh" @update:model-value="changesOpen = false">
      <form class="bom-demand-filters" aria-label="筛选变更记录" @submit.prevent="loadChanges(1)">
        <label>物料或单元<input v-model="changeSearch" aria-label="搜索变更记录" placeholder="编码、名称或单元" /></label>
        <label>起始日期<input v-model="changeStart" type="date" aria-label="变更起始日期" /></label>
        <label>截止日期<input v-model="changeEnd" type="date" aria-label="变更截止日期" /></label>
        <el-button native-type="submit" :loading="changeLoading">查询</el-button>
      </form>
      <el-alert v-if="changeError" :title="changeError" type="error" :closable="false" role="alert" />
      <BusinessTable label="BOM变更记录" :data="changeRows" :numbered="!mobile" :row-offset="(changePage - 1) * pageSize" :max-height="mobile ? undefined : 420" :empty-text="changeLoading ? '正在加载……' : '暂无变更记录'">
        <el-table-column v-if="mobile" label="变更"><template #default="{ row }"><span class="bom-change-head"><el-tag size="small" :type="row.action === 'remove' ? 'danger' : row.action === 'create' ? 'warning' : 'info'">{{ changeActions[row.action] || row.action }}</el-tag><strong>{{ row.item_name }}</strong></span><small class="bom-item-code">{{ row.item_code }} · {{ row.assembly_unit || '未分单元' }}</small><small class="bom-mobile-summary"><span>数量 {{ row.before ?? '—' }} → {{ row.after ?? '移除' }}</span><span>{{ changeTime(row.created_at) }} · {{ row.actor }}</span><span>{{ row.reason || '—' }}</span><span v-for="detail in row.details" :key="detail">{{ detail }}</span></small></template></el-table-column>
        <template v-else>
        <el-table-column label="时间" width="140"><template #default="{ row }">{{ changeTime(row.created_at) }}</template></el-table-column>
        <el-table-column prop="actor" label="操作人" width="96" />
        <el-table-column label="动作" width="70"><template #default="{ row }"><el-tag size="small" :type="row.action === 'remove' ? 'danger' : row.action === 'create' ? 'warning' : 'info'">{{ changeActions[row.action] || row.action }}</el-tag></template></el-table-column>
        <el-table-column label="物料" min-width="170"><template #default="{ row }"><strong>{{ row.item_name }}</strong><small class="bom-item-code">{{ row.item_code }}</small></template></el-table-column>
        <el-table-column label="单元" min-width="110"><template #default="{ row }">{{ row.assembly_unit || '未分单元' }}</template></el-table-column>
        <el-table-column label="数量 改前 → 改后" min-width="130"><template #default="{ row }">{{ row.before ?? '—' }} → {{ row.after ?? '移除' }}</template></el-table-column>
        <el-table-column label="说明" min-width="220"><template #default="{ row }">{{ row.reason || '—' }}<small v-for="detail in row.details" :key="detail" class="bom-item-code">{{ detail }}</small></template></el-table-column>
        </template>
      </BusinessTable>
      <ListPagination :page="changePage" :total="changeTotal" @change="loadChanges" />
      <template #footer><el-button @click="changesOpen = false">关闭</el-button></template>
    </el-dialog>
    <RecordDeletionDialog v-if="deletionAllowed && (deleting || deletionHistory)" resource="bom" title="BOM明细" :rows="deleting || undefined" :project-id="projectId" :show-original="false" @close="deleting = null; deletionHistory = false" @saved="saved" />
    <p class="muted bom-export-scope" role="status" aria-label="BOM导出范围">当前筛选 {{ filtered.length }} 项，导出包含所有分页。<template v-if="exportSelection.length">已选 {{ exportSelection.length }} 项，可单独导出已选项。</template><strong v-if="hiddenSelectionCount">其中 {{ hiddenSelectionCount }} 项在当前筛选外；只需当前类别时请选择“筛选结果”导出。</strong></p>
    <ListPagination :page="page" :total="filtered.length" @change="page = $event" />
    <footer v-if="canPurchase && view === 'purchase'" class="bom-selection-bar"><span>已选 <strong>{{ selected.length }}</strong> 项</span><el-button :aria-label="mobile ? '全选筛选结果' : undefined" :disabled="busy" @click="selected = [...new Set([...selected, ...filtered.filter(eligible).map((line: Row) => line.bom_line)])]">{{ mobile ? '全选' : '全选筛选结果' }}</el-button><el-button :aria-label="mobile ? '清空选择' : undefined" :disabled="busy || !selected.length" text @click="selected = []">{{ mobile ? '清空' : '清空选择' }}</el-button><el-button ref="selectionTrigger" type="primary" :loading="busy" @click="purchase">从 BOM 多选下单</el-button></footer>
    <el-dialog v-if="importOpen && !command" :model-value="true" title="导入BOM" class="bom-import-dialog" width="min(1200px, 94vw)" top="4vh" :close-on-click-modal="false" @update:model-value="closeImport" @opened="revealImportResult">
      <div class="import-preview" :aria-busy="busy">
        <p><strong>目标项目：{{ projectContext?.name ? `${projectContext.name}（${projectContext.code}）` : '当前页面所选项目' }}</strong> · 用于编制或修订本项目用料。预览不会保存业务数据。</p>
        <ol class="bom-import-steps">
          <li v-if="preview" class="bom-import-step-done"><details><summary>下载并填写模板（需要时可重新下载）</summary><div class="toolbar"><el-button :disabled="busy" @click="template()">下载 Excel 模板</el-button><el-button :disabled="busy" @click="template('html')">下载填写说明</el-button><el-button :disabled="busy" @click="template('csv')">下载 CSV 模板</el-button></div></details></li>
          <li v-else><strong>下载并填写模板</strong><div class="toolbar"><el-button :disabled="busy" @click="template()">下载 Excel 模板</el-button><el-button :disabled="busy" @click="template('html')">下载填写说明</el-button><details><summary>更多格式</summary><el-button :disabled="busy" @click="template('csv')">下载 CSV 模板</el-button></details></div>
            <details class="import-help"><summary>导入模板填写说明</summary><p>改现有 BOM 时，可在列表「导出 ▾」里选「可回导模板」，改数量后只给改过的行写变更说明，未改动的行会自动跳过。Excel 模板自带“填写说明”页和表头提示。产品编码类别、标准/非标可下拉选择，单位可选择或手填；缺少必填内容会标红。已有物料填写编码，后方资料留空或与现有资料一致；新物料可填自编编码，并填写名称、完整型号和单位；编码留空时还须选择产品编码类别自动生成，有图件再填图号。型号按厂家确认原文保存，不自动补全。完全相同物料可复用，疑似重复先人工核对，多重匹配须明确编码。需求、单元和申请信息按项目填写，已有 BOM 修改须填写变更说明。旧版模板仍可使用。</p></details>
          </li>
          <li><strong>上传并检查问题</strong><label class="file-button">{{ preview ? '重新选择文件并预览' : '选择文件并预览' }}<input type="file" accept=".csv,.xlsx" :disabled="busy" @change="importFile" /></label></li>
          <li><strong>核对后确认导入</strong> · 任一行失败整批不保存，修正后重新上传。</li>
        </ol>
        <p v-if="importFilename" class="import-filename">文件：{{ importFilename }}</p>
        <div ref="importResult" class="bom-import-result">
          <p v-if="busy" role="status">正在读取文件并校验物料，请稍候……</p>
          <el-alert v-if="importError" :title="importError" type="error" :closable="false" role="alert" />
          <p v-if="mismatch"><router-link v-if="destination" :to="destination" @click="closeImport">前往{{ mismatch.title }}导入入口</router-link><span v-else>请联系具备相应权限的同事，在{{ mismatch.entry }}操作。</span> 切换后请重新选择文件。</p>
          <template v-if="preview">
            <p role="status">{{ preview.can_import ? `校验通过，共 ${preview.lines.length} 条明细。请核对后确认导入。` : '校验未通过，尚未导入任何数据。请按文件行号修改后重新上传。' }}</p>
            <p v-if="preview.summary" class="bom-import-summary">新增 <strong>{{ preview.summary.create }}</strong> 行、修改 <strong>{{ preview.summary.update }}</strong> 行、不变 <strong>{{ preview.summary.unchanged }}</strong> 行<template v-if="preview.summary.unchanged">（与现有一致，跳过，不需要变更说明）</template>。</p>
            <details v-if="preview.untouched?.length" class="bom-import-untouched"><summary>文件中未出现的现有行 {{ preview.untouched.length }} 条：导入不会移除这些行，需移除请在列表行尾「操作」里移除</summary><ul><li v-for="line in preview.untouched" :key="`${line.item_code}-${line.assembly_unit}`">{{ line.assembly_unit || '未分单元' }} · {{ line.item_code }} {{ line.item_name }} · {{ qty(line.quantity) }}</li></ul></details>
            <ImportFeedback :rows="previewRows" :columns="[{ key: 'item_name', label: '物料名称' }, ...importColumns, { key: 'brand', label: '品牌' }, { key: 'specification', label: '规格' }]" :errors="preview.errors || []" :error-file="preview.error_file" :busy="busy" />
          </template>
        </div>
      </div>
      <template #footer>
        <el-button @click="closeImport">关闭</el-button>
        <el-button type="primary" :disabled="busy || !preview?.can_import" @click="confirmImport">确认导入</el-button>
      </template>
    </el-dialog>
    <ActionDialog :command="command" @close="command = null" @saved="saved" />
  </section>
</template>
<style scoped>
.bom-view-switch { display: flex; gap: 6px 16px; align-items: center; flex-wrap: wrap; }
.bom-view-switch small { font-size: 12px; line-height: 1.5; flex: 1 1 320px; }
.bom-help-icon { width: 18px; height: 18px; padding: 0; border: 1px solid var(--field-line); border-radius: 50%; background: #fff; color: var(--mute); font-size: 12px; line-height: 16px; cursor: help; flex: none; margin-left: -6px; }
.bom-help-icon:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.bom-export-scope { margin: 8px 0 0; font-size: 12px; }
/* 手机上工具栏按钮缩成两行：导出范围在下拉项和表格下方的范围说明里都有。 */
@media (max-width: 640px) { .export-scope-label { display: none; } .panel-heading .toolbar { gap: 6px; } .panel-heading .toolbar :deep(.el-button) { padding-left: 10px; padding-right: 10px; } }
.bom-view-switch label { display: flex; gap: 6px; align-items: center; white-space:nowrap; }
.bom-view-switch input[type='radio'] { width:16px; height:16px; min-height:0; padding:0; flex:0 0 16px; }
.bom-item-code { display: block; color: var(--mute); font-weight: normal; }
.bom-import-steps { padding-left: 22px; }
.bom-import-steps li { margin-bottom: 14px; }
.bom-import-steps li > strong { display: block; margin-bottom: 8px; }
.bom-demand-filters { display: flex; align-items: end; flex-wrap: wrap; gap: 8px 12px; padding: 8px 0 10px; }
.bom-demand-filters label { display: grid; gap: 6px; font-size: 13px; min-width: 130px; }
/* 筛选下拉的首项已写明「全部品牌 / 全部单元 / 全部类别」，标题只留给读屏，筛选行压成一行。 */
.bom-filter-caption, .bom-search-label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.bom-item-code.is-inline { display: inline; margin-left: 6px; }
.bom-inactive-tag { margin-left: 6px; vertical-align: 1px; }
.bom-inactive-note { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 8px 0 0; font-size: 13px; color: var(--ink-3); }
.bom-link-button { border: 0; padding: 0; background: transparent; color: var(--brand); font: inherit; cursor: pointer; }
/* 单元名、其他项目待领不换行（单元列的 show-overflow-tooltip 负责省略和悬停全名）。 */
.bom-demand-panel :deep(.bom-details-table :is(.bom-unit-cell, .bom-nowrap-cell) .cell) { white-space: nowrap; }
.bom-filter-group { display: contents; }
.bom-demand-filters .shortage-toggle { display: flex; align-items: center; min-height: 38px; }
.import-help { color: var(--mute); font-size: 13px; line-height: 1.7; }
.import-help summary { cursor: pointer; }
:deep(.bom-import-dialog) { display: flex; flex-direction: column; max-height: 92dvh; }
:deep(.bom-import-dialog .el-dialog__body) { min-height: 0; overflow-y: auto; }
:deep(.bom-import-dialog .el-dialog__header), :deep(.bom-import-dialog .el-dialog__footer) { flex-shrink: 0; }
.import-preview { min-width: 0; }
.import-filename { overflow-wrap: anywhere; }
.import-preview .import-errors { max-height: 160px; overflow: auto; }
.bom-batch-selection { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 12px 0; }
.bom-unit-summary { display: flex; flex-wrap: wrap; gap: 6px; padding-top: 8px; }
.bom-unit-chip { display: inline-flex; align-items: baseline; gap: 6px; text-align: left; padding: 4px 10px; border: 1px solid var(--field-line); border-radius: 6px; background: var(--subtle-2); color: inherit; cursor: pointer; font-size: 13px; line-height: 1.35; white-space: nowrap; }
.bom-unit-chip small { color: var(--mute); font-size: 12px; }
.bom-unit-chip.active { border-color: var(--brand-line); background: var(--brand-wash-2); }
.bom-unit-chip .overdue-count { color: var(--risk); }
.sort-header { border: 0; padding: 0; background: transparent; color: inherit; font: inherit; font-weight: inherit; cursor: pointer; }
.sort-header:hover { text-decoration: underline; }
.unapproved-number { display: block; color: var(--warn); font-size: 12px; white-space: nowrap; }
.overdue-flag.pending { color: var(--warn); }
.bom-issue-link { text-decoration: none; }
.bom-import-summary { margin: 4px 0 8px; }
.bom-import-untouched { margin-bottom: 8px; font-size: 13px; }
.bom-import-untouched summary { cursor: pointer; color: var(--ink-3); }
.bom-import-untouched ul { max-height: 160px; overflow: auto; margin: 6px 0; padding-left: 20px; }
.bom-import-step-done summary { cursor: pointer; color: var(--ink-3); }
.bom-selection-bar { position: sticky; bottom: 0; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; background: var(--brand-wash-2); padding: 8px 14px; border: 1px solid var(--brand-line); border-radius: 8px; margin-top: 10px; z-index: 5; }
.bom-selection-bar > .el-button--primary { margin-left: auto; }
@media (max-width: 760px) { .bom-demand-filters label { flex: 1 1 140px; } }
/* 桌面首屏密度（1366×768 编制、采购视图各 7 行以上）：标题、视图切换和工具栏一行，单元概览、筛选和表格行距收紧，底部选择条变矮。 */
@media (min-width: 601px) {
  .bom-demand-panel { padding: 12px 16px 16px; }
  /* 放不下时工具栏整体换到下一行并靠右，不把页面撑出横向滚动。 */
  .bom-panel-heading { flex-wrap: wrap; justify-content: flex-start; row-gap: 8px; margin-bottom: 6px; }
  .bom-panel-heading .bom-panel-title { white-space: nowrap; }
  .bom-panel-heading .bom-view-switch { flex-wrap: nowrap; }
  .bom-panel-heading .toolbar { margin-left: auto; justify-content: flex-end; }
  .bom-unit-summary { padding-top: 2px; }
  .bom-unit-chip { padding: 2px 9px; }
  .bom-demand-filters { padding: 6px 0 8px; }
  /* el-table 根节点不带本组件的 scoped 属性，从面板往下选。 */
  .bom-demand-panel :deep(.bom-details-table td.el-table__cell) { padding: 6px 0; }
  .bom-demand-panel :deep(.bom-details-table th.el-table__cell) { height: 38px; padding: 4px 0; }
  .bom-demand-panel :deep(.bom-details-table .el-table__body .cell) { line-height: 20px; }
  /* 单元格左右留白 12→8px，固定宽度的数量列相应收窄：采购视图连同「其他项目待领」在 1366 宽也不出横向滚动。 */
  .bom-demand-panel :deep(.bom-details-table .cell) { padding: 0 8px; }
  .bom-demand-panel :deep(.bom-details-table .el-table__body :is(.overdue-flag, .unapproved-number)) { line-height: 16px; }
  .panel .bom-selection-bar { padding: 4px 12px; gap: 10px; }
  .panel .bom-selection-bar .el-button { height: 30px; min-height: 30px; }
}
.bom-mobile-summary { display: block; margin-top: 4px; color: var(--ink-3); font-size: 12px; font-weight: normal; line-height: 1.55; white-space: normal; overflow-wrap: anywhere; }
.bom-mobile-summary > span { display: block; }
.bom-mobile-summary b, .bom-mobile-summary i { font-style: normal; white-space: nowrap; }
.bom-mobile-summary b { font-weight: 600; }
.bom-mobile-summary .unapproved-inline { color: var(--warn); font-style: normal; }
.bom-help-toggle { display: inline-flex; align-items: center; min-height: 40px; padding: 0 4px; border: 0; background: transparent; color: var(--brand); font: inherit; font-size: 13px; cursor: pointer; }
.bom-change-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
/* 窄屏模式（≤600px）：桌面布局不受影响。 */
@media (max-width: 600px) {
  .panel-heading .toolbar :deep(.el-button) { padding-left: 8px; padding-right: 8px; }
  .bom-link-button { min-height: 40px; }
  /* 窄屏下标签、说明和「只看这些行」连成一段，不各占一行。 */
  .bom-inactive-note { display: block; line-height: 1.6; }
  .bom-inactive-note > .el-tag { margin-right: 6px; vertical-align: 1px; }
  .bom-inactive-note .bom-link-button { display: inline-flex; align-items: center; margin-left: 4px; vertical-align: middle; }
  .bom-panel-title { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
  /* 视图切换在页头里，手机上排到工具栏下方单独一行。 */
  .bom-panel-heading { row-gap: 8px; margin-bottom: 0; }
  .bom-panel-heading .bom-view-switch { order: 2; flex: 1 1 100%; }
  .bom-view-switch { gap: 0 16px; }
  .bom-view-switch label { min-height: 40px; }
  .bom-view-switch small { flex-basis: 100%; }
  .bom-unit-summary { flex-wrap: nowrap; overflow-x: auto; overscroll-behavior-x: contain; padding: 4px 0; scrollbar-width: thin; }
  .bom-unit-chip { display: grid; gap: 2px; flex: 0 0 auto; min-height: 40px; padding: 4px 10px; }
  .bom-unit-rows { display: none; }
  .bom-demand-filters { align-items: center; gap: 8px; padding: 8px 0; }
  .bom-demand-filters .bom-search { display: block; flex: 1 1 140px; min-width: 0; }
  .bom-search input { width: 100%; min-height: 40px; }
  .bom-filter-toggle { flex: 0 0 auto; min-height: 40px; }
  .bom-filter-group { display: flex; flex-wrap: wrap; gap: 8px; flex: 1 1 100%; }
  .bom-filter-group.is-collapsed { display: none; }
  .bom-filter-group label { flex: 1 1 140px; min-width: 0; }
  .bom-filter-group select { width: 100%; min-height: 40px; }
  .bom-filter-group .shortage-toggle { flex: 1 1 120px; min-height: 40px; }
  .bom-batch-selection { gap: 8px; margin: 8px 0; }
  .bom-batch-selection .el-button { min-height: 40px; margin-left: 0; }
  .bom-details-table :deep(.row-actions .el-button) { min-height: 40px; }
  .bom-details-table :deep(input[type='checkbox']) { width: 20px; height: 20px; margin: 0; }
  .bom-details-table :deep(.el-table__cell) { padding: 8px 0; }
  .bom-details-table :deep(.el-table .cell) { padding: 0 6px; }
  .bom-selection-bar { flex-wrap: nowrap; gap: 6px; padding: 8px 10px; margin-top: 12px; }
  .bom-selection-bar > span { white-space: nowrap; }
  .bom-selection-bar .el-button { min-height: 40px; padding-left: 10px; padding-right: 10px; margin-left: 0; }
  .bom-selection-bar > .el-button--primary { margin-left: auto; }
}
</style>
<style>
/* 视图说明悬停提示挂在 body 下：限宽折行，长说明不拉成一条。 */
.bom-help-popper { max-width: 420px; line-height: 1.6; }
/* 窄屏对话框：标题和底部按钮固定，只让正文滚动（对话框挂在 body 下，scoped 样式够不到）。 */
@media (max-width: 600px) {
  .el-dialog.bom-mobile-dialog, .el-dialog.bom-import-dialog { display: flex; flex-direction: column; max-height: calc(100dvh - 24px); margin: 12px auto; }
  .el-dialog.bom-mobile-dialog .el-dialog__body, .el-dialog.bom-import-dialog .el-dialog__body { min-height: 0; overflow-y: auto; overscroll-behavior: contain; }
  .el-dialog.bom-mobile-dialog .el-dialog__header, .el-dialog.bom-mobile-dialog .el-dialog__footer { flex-shrink: 0; }
  :is(.el-dialog.bom-mobile-dialog, .el-dialog.bom-import-dialog) .el-button { min-height: 40px; }
  /* 正文已是唯一的滚动区，里面的列表不再各自限高滚动。 */
  .el-dialog.bom-import-dialog .bom-import-untouched ul { max-height: none; overflow: visible; }
}
</style>
