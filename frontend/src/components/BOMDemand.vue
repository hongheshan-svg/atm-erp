<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { read, write, download } from '../api'
import { bomCommand, permission } from '../business'
import { manager } from '../session'
import type { Row, Command } from '../types'
import { message } from '../utils/request'
import ActionDialog from './ActionDialog.vue'
import ListPagination from './ListPagination.vue'
import TransferTools from './TransferTools.vue'
import { shortageCommand } from '../modules/purchases'
import { pageSize } from '../pagination'
import { productCategories } from '../product-categories'
const props = defineProps<{ projectId: number; revision?: number; status?: string }>()
const emit = defineEmits<{ changed: [] }>()
const demand = ref<Row>({ lines: [] })
const preview = ref<Row | null>(null)
const error = ref('')
const busy = ref(false)
const templateFormat = ref('xlsx')
const importColumns = [
  { key: 'item_code', label: '物料编码' }, { key: 'assembly_unit', label: '单元' },
  { key: 'quantity', label: '需求数量' }, { key: 'change_note', label: '变更说明' },
  { key: 'required_date', label: '需求日期' }, { key: 'application_date', label: '申请日期' }, { key: 'applicant', label: '申请人' },
  { key: 'material_action', label: '物料处理方式' },
  { key: 'drawing_number', label: '图号' }, { key: 'drawing_revision', label: '图档版本' },
  { key: 'product_category', label: '产品编码类别' }, { key: 'unit', label: '单位' },
]
const command = ref<Command | null>(null)
const search = ref(''), brand = ref(''), unit = ref(''), partType = ref(''), shortageOnly = ref(false)
const selected = ref<number[]>([])
const canPurchase = computed(() => permission.buyer() && ['active', 'delivering', 'warranty'].includes(props.status || ''))
const options = (key: string) => [...new Set<string>(demand.value.lines.map((line: Row) => String(line[key] || '')).filter(Boolean))].sort()
const filtered = computed(() => demand.value.lines.filter((line: Row) =>
  (!brand.value || line.brand === brand.value) && (!unit.value || line.assembly_unit === unit.value) &&
  (!partType.value || line.part_type === partType.value) && (!shortageOnly.value || Number(line.shortage) > 0) &&
  [line.item_code, line.item_name, line.specification].join(' ').toLowerCase().includes(search.value.trim().toLowerCase()),
))
const eligible = (line: Row) => Number(line.shortage) > 0 && line.is_active !== false
function toggle(line: Row) { selected.value = selected.value.includes(line.bom_line) ? selected.value.filter(id => id !== line.bom_line) : [...selected.value, line.bom_line] }
async function purchase() {
  const projectId = props.projectId
  busy.value = true; error.value = ''
  try {
    const next = await shortageCommand(projectId, selected.value)
    if (props.projectId === projectId) command.value = next
  }
  catch (e) { if (props.projectId === projectId) error.value = message(e) }
  finally { busy.value = false }
}
const impact = ref<Row | null>(null)
async function inspectImpact() {
  try { impact.value = await read(`/business/projects/${props.projectId}/bom-impact/`) } catch (e) { error.value = message(e) }
}
const page = ref(1)
const previewPage = ref(1)
const visibleLines = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const visiblePreview = computed(() => (preview.value?.lines || []).slice((previewPage.value - 1) * pageSize.value, previewPage.value * pageSize.value))
watch([pageSize, () => demand.value.lines], () => { page.value = 1 })
watch([search, brand, unit, partType, shortageOnly], () => { page.value = 1 })
watch(() => props.projectId, () => { selected.value = []; search.value = ''; brand.value = ''; unit.value = ''; partType.value = ''; shortageOnly.value = false })
watch([pageSize, preview], () => { previewPage.value = 1 })
let generation = 0
async function load() {
  const id = ++generation
  try {
    const result = await read(`/business/projects/${props.projectId}/demand/`)
    if (id === generation) {
      demand.value = result
      selected.value = selected.value.filter(key => result.lines.some((line: Row) => line.bom_line === key && eligible(line)))
    }
  } catch (e) {
    if (id === generation) error.value = message(e)
  }
}
watch(
  () => [props.projectId, props.revision],
  () => {
    preview.value = null
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
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  busy.value = true
  error.value = ''
  preview.value = null
  const importingProject = props.projectId
  try {
    const body = new FormData()
    body.append('file', file)
    const result = await write(
      `/business/projects/${importingProject}/import-preview/`,
      body,
      crypto.randomUUID(),
    )
    if (props.projectId === importingProject) preview.value = result
  } catch (e) {
    error.value = message(e)
  } finally {
    busy.value = false
    input.value = ''
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
  preview.value = null
  void load()
  emit('changed')
}
</script>
<template>
  <section class="panel" aria-label="BOM 缺料需求">
    <header class="panel-heading">
      <h2>BOM 与缺料</h2>
      <div class="toolbar">
        <TransferTools resource="bom" path="/business/bom/" :params="{ project: projectId }" />
        <el-button @click="load">刷新需求</el-button
        ><template v-if="manager() && ['draft', 'quoted', 'active', 'delivering'].includes(status || '')"
          ><select v-model="templateFormat" aria-label="BOM 模板格式"><option value="xlsx">Excel</option><option value="csv">CSV</option></select><el-button
            @click="
              download('/business/projects/bom-template/', `bom-template.${templateFormat}`, { file_format: templateFormat }).catch(
                (e) => (error = message(e)),
              )
            "
            >下载模板</el-button
          ><label class="file-button"
            >导入预览<input type="file" accept=".csv,.xlsx" :disabled="busy" @change="importFile" /></label
          ><el-button @click="inspectImpact">变更影响与处理</el-button><el-button type="primary" @click="start">维护 BOM</el-button></template
        >
      </div>
    </header>
    <p class="muted">库存为共享库存，不预留，当前可用不保证后续可领。同物料可分属多个单元；已领、在途及库存按行顺序分摊，非单元实际领用记录。</p>
    <details v-if="manager()" class="import-help"><summary>导入模板填写说明</summary><p class="muted">已有物料填写编码，后方物料资料可留空；填写时必须与已有资料一致。新物料编码留空，填写名称、规格、产品编码类别和单位，有图件再填图号，品牌与版本分别填写。完全相同物料自动复用，存在多个匹配时须明确编码；新编号只在确认后生成。需求、单元与申请信息按项目填写；修改已有BOM必须填写变更说明。已领、在途、库存、缺料由系统计算，旧版模板仍可使用。</p></details>
    <div class="bom-demand-filters"><label>搜索物料<input v-model="search" aria-label="搜索 BOM 物料" placeholder="编码、名称、规格" /></label><label>品牌<select v-model="brand" aria-label="筛选品牌"><option value="">全部品牌</option><option v-for="value in options('brand')" :key="value">{{ value }}</option></select></label><label>单元<select v-model="unit" aria-label="筛选单元"><option value="">全部单元</option><option v-for="value in options('assembly_unit')" :key="value">{{ value }}</option></select></label><label>类别<select v-model="partType" aria-label="筛选类别"><option value="">全部类别</option><option value="standard">标准件</option><option value="custom">非标件</option></select></label><label class="shortage-toggle"><input v-model="shortageOnly" type="checkbox" />仅看缺料</label></div>
    <el-dialog :model-value="Boolean(impact)" title="BOM 变更影响与处理" width="min(900px, 94vw)" @close="impact = null">
      <template v-if="impact"><p>{{ impact.note }}</p><el-table :data="impact.items" max-height="360"><el-table-column prop="item_code" label="物料编码" /><el-table-column prop="item_name" label="物料" /><el-table-column prop="quantity" label="需求总量" /><el-table-column prop="issued" label="已领" /><el-table-column prop="incoming" label="在途/草稿" /><el-table-column prop="minimum" label="当前最低可改量" /></el-table><p v-for="purchase in impact.purchases" :key="purchase.id"><router-link :to="{ path: `/projects/${projectId}`, query: { tab: 'purchases', resource: 'purchases', focus: purchase.id } }" @click="impact = null">{{ purchase.code }}：查看采购并处理未收余量</router-link></p><router-link :to="{ path: '/inventory', query: { project: projectId } }">查看本项目库存流水，处理未用材料退回</router-link></template>
      <template #footer><el-button @click="impact = null">关闭</el-button></template>
    </el-dialog>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <el-table :data="visibleLines" :max-height="560" empty-text="尚未维护 BOM"
      ><el-table-column v-if="canPurchase" label="选择" width="60" fixed><template #default="{ row }"><input type="checkbox" :aria-label="`选择 ${row.item_code} ${row.assembly_unit || ''}`" :checked="selected.includes(row.bom_line)" :disabled="busy || !eligible(row)" @change="toggle(row)" /></template></el-table-column><el-table-column prop="item_code" label="物料编码" min-width="145" /><el-table-column
        prop="item_name"
        label="物料名称" min-width="160" /><el-table-column prop="specification" label="规格" min-width="140" /><el-table-column prop="drawing_number" label="图号" min-width="150" /><el-table-column prop="drawing_revision" label="图档版本" min-width="90" /><el-table-column label="产品编码类别" min-width="125"><template #default="{ row }">{{ productCategories[row.product_category] || '未分类' }}</template></el-table-column><el-table-column prop="required_date" label="需求日期" min-width="110" /><el-table-column prop="application_date" label="申请日期" min-width="110" /><el-table-column prop="applicant" label="申请人" min-width="100" /><el-table-column prop="brand" label="品牌" min-width="95" /><el-table-column label="物料类别" min-width="100"><template #default="{ row }">{{ ({ standard: '标准件', custom: '非标件' } as Record<string, string>)[row.part_type] || '未分类' }}</template></el-table-column><el-table-column prop="assembly_unit" label="单元" min-width="110" /><el-table-column prop="quantity" label="需求数量" min-width="95" align="right" /><el-table-column prop="change_note" label="变更说明" min-width="150" /><el-table-column
        prop="issued"
        label="已领" /><el-table-column prop="incoming" label="在途" /><el-table-column
        prop="available"
        label="可用库存" /><el-table-column prop="shortage" label="缺料"
    /></el-table>
    <ListPagination :page="page" :total="filtered.length" @change="page = $event" />
    <footer v-if="canPurchase" class="bom-selection-bar"><span>已选 <strong>{{ selected.length }}</strong> 项</span><el-button :disabled="busy" @click="selected = [...new Set([...selected, ...filtered.filter(eligible).map((line: Row) => line.bom_line)])]">全选筛选结果</el-button><el-button :disabled="busy || !selected.length" text @click="selected = []">清空选择</el-button><el-button type="primary" :loading="busy" :disabled="!selected.length" @click="purchase">按缺料采购</el-button></footer>
    <div v-if="preview" class="import-preview">
      <h3>导入预览</h3>
      <el-alert
        v-if="!preview.can_import"
        :title="JSON.stringify(preview.errors)"
        type="error"
        :closable="false"
      /><el-table :data="visiblePreview" :max-height="560"
        ><el-table-column prop="row" label="文件行号" width="100" /><el-table-column v-for="column in importColumns" :key="column.key" :prop="column.key" :label="column.label" min-width="140" /><el-table-column prop="item_name" label="物料名称（关联）" min-width="160" /><el-table-column prop="brand" label="品牌（关联）" /><el-table-column prop="specification" label="规格（关联）" /></el-table
      ><ListPagination :page="previewPage" :total="preview.lines.length" @change="previewPage = $event" />
      <el-button type="primary" :disabled="!preview.can_import" @click="confirmImport">确认导入</el-button
      ><el-button @click="preview = null">取消导入</el-button>
    </div>
    <ActionDialog :command="command" @close="command = null" @saved="saved" />
  </section>
</template>
<style scoped>
.bom-demand-filters { display: flex; align-items: end; flex-wrap: wrap; gap: 12px; padding: 16px 0; }
.bom-demand-filters > label { display: grid; gap: 6px; font-size: 13px; min-width: 130px; }
.bom-demand-filters .shortage-toggle { display: flex; align-items: center; min-height: 38px; }
.import-help { color: #64748b; font-size: 13px; line-height: 1.7; }
.import-help summary { cursor: pointer; }
.bom-selection-bar { position: sticky; bottom: 0; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; background: #f4f8ff; padding: 14px 18px; border: 1px solid #d8e5fa; border-radius: 8px; margin-top: 18px; z-index: 5; }
.bom-selection-bar > .el-button--primary { margin-left: auto; }
@media (max-width: 760px) { .bom-demand-filters > label { flex: 1 1 140px; } }
</style>
