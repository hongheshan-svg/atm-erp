<script setup lang="ts">
import { computed, inject, nextTick, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { read, write, download } from '../api'
import { downloadBOM } from '../api/bom'
import { bomCommand, permission } from '../business'
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
import { canDeleteRecords } from '../modules/deletions'
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
  { key: 'quantity', label: '需求数量' }, { key: 'change_note', label: '变更说明' },
  { key: 'required_date', label: '需求日期' }, { key: 'application_date', label: '申请日期' }, { key: 'applicant', label: '申请人' },
  { key: 'material_action', label: '物料处理方式' },
  { key: 'drawing_number', label: '图号' }, { key: 'drawing_revision', label: '图档版本' },
  { key: 'product_category', label: '产品编码类别' }, { key: 'unit', label: '单位' },
]
const command = ref<Command | null>(null)
const search = ref(''), brand = ref(''), unit = ref(''), partType = ref(''), shortageOnly = ref(view.value === 'purchase')
const selected = ref<number[]>([])
const deletionAllowed = computed(() => canDeleteRecords('bom'))
const deletionSelection = ref<Row[]>([]), deleting = ref<Row[] | null>(null), deletionHistory = ref(false)
const deletionLoading = ref(false)
function openDeletion(rows: Row[]) { deleting.value = rows.map(row => ({ ...row, id: row.bom_line })) }
watch([() => props.projectId, search, brand, unit, partType, shortageOnly, view], () => { deletionSelection.value = []; deleting.value = null; deletionHistory.value = false })
const pickingBom = ref(false)
const moduleFocusedFlow = inject<Ref<boolean>>('moduleFocusedFlow', ref(false))
watch(pickingBom, value => { moduleFocusedFlow.value = value })
onBeforeUnmount(() => { moduleFocusedFlow.value = false })
const purchaseTrigger = ref<{ $el: HTMLElement }>()
const selectionTrigger = ref<{ $el: HTMLElement }>()
let openedFromSelection = false
async function closePurchase() {
  pickingBom.value = false
  await nextTick()
  ;(openedFromSelection && selected.value.length ? selectionTrigger : purchaseTrigger).value?.$el.focus()
}
function savedPurchase() { void closePurchase(); saved() }
const canPurchase = computed(() => permission.buyer() && ['active', 'delivering', 'warranty'].includes(props.status || ''))
const canEdit = computed(() => bomEditor({ can_edit_bom: props.canEditBom }))
const canMaintain = computed(() => canEdit.value && ['draft', 'quoted', 'active', 'delivering'].includes(props.status || ''))
watch(canMaintain, value => { if (!value) { closeImport(); command.value = null } })
watch(view, value => { shortageOnly.value = value === 'purchase' })
const options = (key: string) => [...new Set<string>(demand.value.lines.map((line: Row) => String(line[key] || '')).filter(Boolean))].sort()
const filtered = computed(() => demand.value.lines.filter((line: Row) =>
  (!brand.value || line.brand === brand.value) && (!unit.value || line.assembly_unit === unit.value) &&
  (!partType.value || line.part_type === partType.value) && (!shortageOnly.value || Number(line.shortage) > 0) &&
  [line.item_code, line.item_name, line.specification].join(' ').toLowerCase().includes(search.value.trim().toLowerCase()),
))
const eligible = (line: Row) => Number(line.shortage) > 0 && line.is_active !== false
const exporting = ref(false)
const exportSelection = computed<number[]>(() => view.value === 'purchase' ? selected.value : deletionSelection.value.map(row => row.bom_line))
const hiddenSelectionCount = computed(() => {
  const visibleIds = new Set(filtered.value.map((line: Row) => line.bom_line))
  return exportSelection.value.filter(id => !visibleIds.has(id)).length
})
async function exportRows(command: string) {
  if (exporting.value || deletionLoading.value || busy.value) return
  const [scope, format] = command.split(':')
  if (!['selected', 'filtered'].includes(scope || '') || !['xlsx', 'csv'].includes(format || '')) return
  const ids = scope === 'selected' ? [...exportSelection.value] : filtered.value.map((line: Row) => line.bom_line)
  if (!ids.length) return
  const project = props.projectId
  exporting.value = true; error.value = ''
  try {
    await downloadBOM(project, ids, format as 'xlsx' | 'csv', `BOM_${scope === 'selected' ? '已选' : '筛选结果'}${ids.length}项.${format}`)
  } catch (e) { if (project === props.projectId) error.value = message(e) }
  finally { exporting.value = false }
}
function toggle(line: Row) { selected.value = selected.value.includes(line.bom_line) ? selected.value.filter(id => id !== line.bom_line) : [...selected.value, line.bom_line] }
function purchase(event: MouseEvent) { openedFromSelection = (event.currentTarget as HTMLElement)?.textContent?.trim() === '按缺料采购'; pickingBom.value = true }
const impact = ref<Row | null>(null)
async function inspectImpact() {
  try { impact.value = await read(`/business/projects/${props.projectId}/bom-impact/`) } catch (e) { error.value = message(e) }
}
const page = ref(1)
const visibleLines = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
watch([pageSize, () => demand.value.lines], () => { page.value = 1 })
watch([search, brand, unit, partType, shortageOnly], () => { page.value = 1 })
watch(() => props.projectId, () => { selected.value = []; demand.value = { lines: [] }; search.value = ''; brand.value = ''; unit.value = ''; partType.value = ''; shortageOnly.value = view.value === 'purchase'; projectContext.value = null })
let generation = 0
async function load() {
  deletionSelection.value = []
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
  if (result.token) {
    command.value = {
      title: '确认导入 BOM 与物料',
      path: `/business/projects/${props.projectId}/bom-import-confirm/`,
      fields: [],
      notice: { type: 'info', text: result.note },
      prepare: () => ({ token: result.token }),
    }
    return
  }
  command.value = {
    title: '确认导入 BOM',
    path: `/business/projects/${props.projectId}/revise-bom/`,
    previewPath: `/business/projects/${props.projectId}/bom-change-preview/`,
    fields: [],
    prepare: () => ({
      expected_revision: result.expected_revision,
      lines: result.lines.map((r: Row) => ({
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
  <BOMPurchasePicker v-if="pickingBom && canPurchase" :project-id="projectId" :initial-selection="selected" @close="closePurchase" @saved="savedPurchase" />
  <section v-else class="panel" aria-label="BOM 缺料需求">
    <header class="panel-heading">
      <h2>BOM 与缺料</h2>
      <div class="toolbar">
        <el-button v-if="canMaintain && view === 'prepare'" type="primary" :disabled="busy" @click="start">维护 BOM</el-button>
        <el-button v-if="canPurchase && view === 'purchase'" ref="purchaseTrigger" type="primary" :disabled="busy" @click="purchase">从 BOM 多选下单</el-button>
        <el-button v-if="canMaintain" :disabled="busy" @click="openImport">导入 BOM</el-button>
        <el-button v-if="canMaintain" @click="inspectImpact">变更影响与处理</el-button>
        <el-dropdown :disabled="busy || deletionLoading || exporting || (!filtered.length && !exportSelection.length)" @command="exportRows">
          <el-button aria-label="导出BOM" :loading="exporting" :disabled="busy || deletionLoading || (!filtered.length && !exportSelection.length)">导出{{ exportSelection.length ? `已选 ${exportSelection.length} 项` : `筛选结果 ${filtered.length} 项` }} ▾</el-button>
          <template #dropdown><el-dropdown-menu>
            <template v-if="exportSelection.length">
              <el-dropdown-item command="selected:xlsx">已选 {{ exportSelection.length }} 项 · Excel</el-dropdown-item>
              <el-dropdown-item command="selected:csv">已选 {{ exportSelection.length }} 项 · CSV</el-dropdown-item>
            </template>
            <el-dropdown-item command="filtered:xlsx" :divided="Boolean(exportSelection.length)" :disabled="!filtered.length">筛选结果 {{ filtered.length }} 项 · Excel</el-dropdown-item>
            <el-dropdown-item command="filtered:csv" :disabled="!filtered.length">筛选结果 {{ filtered.length }} 项 · CSV</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
        <el-button @click="load">刷新需求</el-button>
        <el-button v-if="deletionAllowed && view === 'prepare'" type="danger" plain :disabled="busy || deletionLoading || !deletionSelection.length" @click="openDeletion(deletionSelection)">批量删除{{ deletionSelection.length ? `（${deletionSelection.length}）` : '' }}</el-button>
        <el-button v-if="deletionAllowed" :disabled="busy" @click="deletionHistory = true">已删除记录</el-button>
      </div>
    </header>
    <div class="bom-view-switch" role="group" aria-label="BOM 工作视图">
      <label><input v-model="view" type="radio" value="prepare" />编制用料</label>
      <label><input v-model="view" type="radio" value="purchase" />采购缺料</label>
      <label><input v-model="fullColumns" type="checkbox" />展开完整列</label>
    </div>
    <p v-if="view === 'prepare'" class="muted">按单元核对物料规格、需求数量和需求日期；切换采购缺料可查看库存、在途及缺口。</p>
    <p v-else class="muted">库存为共享库存，不预留，当前可用不保证后续可领；其他项目待领需协调。同物料不同单元独立选择，已领、在途及库存按行分摊，非单元实际领用记录。</p>
    <div class="bom-demand-filters"><label>搜索物料<input v-model="search" aria-label="搜索 BOM 物料" placeholder="编码、名称、规格" /></label><label>品牌<select v-model="brand" aria-label="筛选品牌"><option value="">全部品牌</option><option v-for="value in options('brand')" :key="value">{{ value }}</option></select></label><label>单元<select v-model="unit" aria-label="筛选单元"><option value="">全部单元</option><option v-for="value in options('assembly_unit')" :key="value">{{ value }}</option></select></label><label>类别<select v-model="partType" aria-label="筛选类别"><option value="">全部类别</option><option value="standard">标准件</option><option value="custom">非标件</option></select></label><label class="shortage-toggle"><input v-model="shortageOnly" type="checkbox" />仅看缺料</label></div>
    <p class="muted" role="status" aria-label="BOM导出范围">当前筛选 {{ filtered.length }} 项，导出包含所有分页。<template v-if="exportSelection.length">已选 {{ exportSelection.length }} 项，可单独导出已选项。</template><strong v-if="hiddenSelectionCount">其中 {{ hiddenSelectionCount }} 项在当前筛选外；只需当前类别时请选择“筛选结果”导出。</strong></p>
    <el-dialog :model-value="Boolean(impact)" title="BOM 变更影响与处理" width="min(900px, 94vw)" @close="impact = null">
      <template v-if="impact"><p>{{ impact.note }}</p><el-table :data="impact.items" max-height="360"><el-table-column prop="item_code" label="物料编码" /><el-table-column prop="item_name" label="物料" /><el-table-column prop="quantity" label="需求总量" /><el-table-column prop="issued" label="已领" /><el-table-column prop="incoming" label="在途/草稿" /><el-table-column prop="minimum" label="当前最低可改量" /></el-table><template v-if="purchaseReader()"><p v-for="purchase in impact.purchases" :key="purchase.id"><router-link :to="{ path: `/projects/${projectId}`, query: { tab: 'purchases', resource: 'purchases', focus: purchase.id } }" @click="impact = null">{{ purchase.code }}：查看采购并处理未收余量</router-link></p><router-link :to="{ path: '/inventory', query: { section: 'moves', project: projectId } }">查看本项目库存流水，处理未用材料退回</router-link></template><p v-else class="muted">涉及在途采购或领料时，请联系采购和仓库处理原单，再提交 BOM 变更。</p></template>
      <template #footer><el-button @click="impact = null">关闭</el-button></template>
    </el-dialog>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <el-table :data="visibleLines" :max-height="560" row-key="bom_line" :empty-text="shortageOnly ? '当前筛选下没有缺料，可取消仅看缺料查看全部用料' : '尚未维护 BOM'" @selection-change="deletionSelection = $event">
      <el-table-column v-if="deletionAllowed && view === 'prepare'" type="selection" width="44" fixed="left" />
      <el-table-column v-if="canPurchase && view === 'purchase'" label="选择" width="60" fixed><template #default="{ row }"><input type="checkbox" :aria-label="`选择 ${row.item_code} ${row.assembly_unit || ''}`" :checked="selected.includes(row.bom_line)" :disabled="busy || !eligible(row)" @change="toggle(row)" /></template></el-table-column>
      <el-table-column label="物料名称 / 编码" min-width="180" fixed="left"><template #default="{ row }"><strong>{{ row.item_name }}</strong><small class="bom-item-code">{{ row.item_code }}</small></template></el-table-column>
      <el-table-column v-if="view === 'prepare'" prop="specification" label="规格" min-width="140" />
      <el-table-column prop="assembly_unit" label="单元" min-width="100" />
      <el-table-column prop="quantity" label="需求数量" width="95" align="right" />
      <el-table-column prop="unit" label="单位" width="65" />
      <template v-if="view === 'purchase'">
        <el-table-column prop="issued" label="已领" width="80" align="right" />
        <el-table-column prop="incoming" label="在途" width="80" align="right" />
        <el-table-column prop="available" label="可用库存" width="100" align="right" />
        <el-table-column label="缺料" width="85" align="right"><template #default="{ row }"><strong :class="Number(row.shortage) > 0 ? 'shortage-number' : 'muted'">{{ row.shortage }}</strong></template></el-table-column>
      </template>
      <el-table-column prop="required_date" label="需求日期" min-width="110" />
      <el-table-column v-if="view === 'purchase' || fullColumns" label="其他项目待领" min-width="115" align="right"><template #default="{ row }"><span v-if="Number(row.other_demand) > 0" :class="Number(row.available) > 0 ? 'contested-number' : 'muted'">{{ row.other_demand }}<small> · {{ row.other_projects }} 个项目</small></span><span v-else class="muted">—</span></template></el-table-column>
      <template v-if="fullColumns">
        <el-table-column v-if="view === 'purchase'" prop="specification" label="规格" min-width="140" />
        <el-table-column prop="drawing_number" label="图号" min-width="150" /><el-table-column prop="drawing_revision" label="图档版本" min-width="90" />
        <el-table-column label="产品编码类别" min-width="125"><template #default="{ row }">{{ productCategories[row.product_category] || '未分类' }}</template></el-table-column>
        <el-table-column prop="application_date" label="申请日期" min-width="110" /><el-table-column prop="applicant" label="申请人" min-width="100" />
        <el-table-column prop="brand" label="品牌" min-width="95" /><el-table-column label="物料类别" min-width="100"><template #default="{ row }">{{ ({ standard: '标准件', custom: '非标件' } as Record<string, string>)[row.part_type] || '未分类' }}</template></el-table-column>
        <el-table-column prop="change_note" label="变更说明" min-width="150" />
        <template v-if="view === 'prepare'"><el-table-column prop="issued" label="已领" /><el-table-column prop="incoming" label="在途" /><el-table-column prop="available" label="可用库存" /><el-table-column prop="shortage" label="缺料" /></template>
      </template>
      <el-table-column v-if="deletionAllowed" label="操作" width="80" fixed="right"><template #default="{ row }"><el-button type="danger" text size="small" :disabled="busy || deletionLoading" @click="openDeletion([row])">删除</el-button></template></el-table-column>
    </el-table>
    <RecordDeletionDialog v-if="deletionAllowed && (deleting || deletionHistory)" resource="bom" title="BOM明细" :rows="deleting || undefined" :project-id="projectId" :show-original="false" @close="deleting = null; deletionHistory = false" @saved="saved" />
    <ListPagination :page="page" :total="filtered.length" @change="page = $event" />
    <footer v-if="canPurchase && view === 'purchase'" class="bom-selection-bar"><span>已选 <strong>{{ selected.length }}</strong> 项</span><el-button :disabled="busy" @click="selected = [...new Set([...selected, ...filtered.filter(eligible).map((line: Row) => line.bom_line)])]">全选筛选结果</el-button><el-button :disabled="busy || !selected.length" text @click="selected = []">清空选择</el-button><el-button ref="selectionTrigger" type="primary" :loading="busy" :disabled="!selected.length" @click="purchase">按缺料采购</el-button></footer>
    <el-dialog v-if="importOpen && !command" :model-value="true" title="导入BOM" class="bom-import-dialog" width="min(1200px, 94vw)" top="4vh" :close-on-click-modal="false" @update:model-value="closeImport" @opened="revealImportResult">
      <div class="import-preview" :aria-busy="busy">
        <p><strong>目标项目：{{ projectContext?.name ? `${projectContext.name}（${projectContext.code}）` : '当前页面所选项目' }}</strong> · 用于编制或修订本项目用料。预览不会保存业务数据。</p>
        <ol class="bom-import-steps">
          <li><strong>下载并填写模板</strong><div class="toolbar"><el-button :disabled="busy" @click="template()">下载 Excel 模板</el-button><el-button :disabled="busy" @click="template('html')">下载填写说明</el-button><details><summary>更多格式</summary><el-button :disabled="busy" @click="template('csv')">下载 CSV 模板</el-button></details></div>
            <details class="import-help"><summary>导入模板填写说明</summary><p>Excel 模板自带“填写说明”页和表头提示。产品编码类别、标准/非标可下拉选择，单位可选择或手填；缺少必填内容会标红。已有物料填写编码，后方资料留空或与现有资料一致；新物料编码留空，填写名称、规格、产品编码类别和单位，有图件再填图号。相同物料自动复用，多重匹配须明确编码。需求、单元和申请信息按项目填写，已有 BOM 修改须填写变更说明。旧版模板仍可使用。</p></details>
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
            <ImportFeedback :rows="(preview.lines || []).map((row: Row) => ({ row: row.row, data: row }))" :columns="[{ key: 'item_name', label: '物料名称' }, ...importColumns, { key: 'brand', label: '品牌' }, { key: 'specification', label: '规格' }]" :errors="preview.errors || []" :error-file="preview.error_file" :busy="busy" />
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
.bom-view-switch { display: flex; gap: 20px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
.bom-view-switch label { display: flex; gap: 6px; align-items: center; white-space:nowrap; }
.bom-view-switch input[type='radio'] { width:16px; height:16px; min-height:0; padding:0; flex:0 0 16px; }
.bom-item-code { display: block; color: var(--mute); font-weight: normal; }
.bom-import-steps { padding-left: 22px; }
.bom-import-steps li { margin-bottom: 14px; }
.bom-import-steps li > strong { display: block; margin-bottom: 8px; }
.bom-demand-filters { display: flex; align-items: end; flex-wrap: wrap; gap: 12px; padding: 16px 0; }
.bom-demand-filters > label { display: grid; gap: 6px; font-size: 13px; min-width: 130px; }
.bom-demand-filters .shortage-toggle { display: flex; align-items: center; min-height: 38px; }
.import-help { color: var(--mute); font-size: 13px; line-height: 1.7; }
.import-help summary { cursor: pointer; }
:deep(.bom-import-dialog) { display: flex; flex-direction: column; max-height: 92dvh; }
:deep(.bom-import-dialog .el-dialog__body) { min-height: 0; overflow-y: auto; }
:deep(.bom-import-dialog .el-dialog__header), :deep(.bom-import-dialog .el-dialog__footer) { flex-shrink: 0; }
.import-preview { min-width: 0; }
.import-filename { overflow-wrap: anywhere; }
.import-preview .import-errors { max-height: 160px; overflow: auto; }
.bom-selection-bar { position: sticky; bottom: 0; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; background: var(--brand-wash-2); padding: 14px 18px; border: 1px solid var(--brand-line); border-radius: 8px; margin-top: 18px; z-index: 5; }
.bom-selection-bar > .el-button--primary { margin-left: auto; }
@media (max-width: 760px) { .bom-demand-filters > label { flex: 1 1 140px; } }
</style>
