<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElOption, ElSelect } from 'element-plus'
import { Close, InfoFilled, Refresh, Search } from '@element-plus/icons-vue'
import { read, write } from '../api'
import { buyer } from '../modules/shared'
import { purchaseFields } from '../modules/purchases'
import { termLabel, termLabels } from '../modules/payment-terms'
import { defaults, payload, validateFields } from '../forms'
import { formatPurchaseAmount, purchaseLineCents, quantityValue } from '../bom-purchase'
import { message, recoveryActions } from '../utils/request'
import { pageSize } from '../pagination'
import { productCategories } from '../product-categories'
import type { Row } from '../types'
import RemoteSelect from './RemoteSelect.vue'
import ListPagination from './ListPagination.vue'

const props = defineProps<{ projectId?: number; initialSelection?: number[] }>()
const emit = defineEmits<{ saved: [result: Row]; close: [] }>()
const fields = purchaseFields({ projects: [], partners: [], items: [], users: [] })
const freshForm = () => ({ ...defaults(fields), lines: [] })
const form = ref<Row>(freshForm())
const project = ref<number | string | undefined>(props.projectId)
const projectInfo = ref<Row>(), supplierInfo = ref<Row>()
const supplierLoading = ref(false)
const lines = ref<Row[]>([]), selected = ref<number[]>([])
const edits = ref<Record<number, Row>>({})
const search = ref(''), brands = ref<string[]>([]), units = ref<string[]>([]), types = ref<string[]>([]), categories = ref<string[]>([])
const shortageOnly = ref(false), page = ref(1), loading = ref(false), saving = ref(false), error = ref('')
const recovery = ref<{ label: string; path: string }[]>([])
const heading = ref<HTMLElement>()
const draftPane = ref<HTMLElement>()
const draftHeight = ref('calc(100dvh - 40px)')
function fitDraft() {
  if (draftPane.value) draftHeight.value = `${Math.max(440, window.innerHeight - Math.max(18, draftPane.value.getBoundingClientRect().top) - 20)}px`
}
const disabled = computed(() => loading.value || saving.value)
const typeName = (value: string) => ({ standard: '标准件', custom: '非标件' }[value] || '未分类')
const eligible = (row: Row) => Number(row.shortage) > 0 && row.is_active !== false
const options = (key: string) => [...new Set(lines.value.map(row => String(row[key] || '')))].sort()
const filtered = computed(() => lines.value.filter(row =>
  (!brands.value.length || brands.value.includes(row.brand || '')) &&
  (!units.value.length || units.value.includes(row.assembly_unit || '')) &&
  (!types.value.length || types.value.includes(row.part_type || '')) &&
  (!categories.value.length || categories.value.includes(row.product_category || '')) &&
  (!shortageOnly.value || Number(row.shortage) > 0) &&
  [row.item_code, row.item_name, row.specification, row.drawing_number].join(' ').toLowerCase().includes(search.value.trim().toLowerCase()),
))
const visible = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const chosen = computed(() => selected.value.map(id => edits.value[id]!).filter(Boolean))
const total = computed(() => {
  if (!chosen.value.length) return null
  const amounts = chosen.value.map(row => purchaseLineCents(row.quantity, row.unit_price))
  return amounts.some(value => value == null) ? null : amounts.reduce<bigint>((sum, value) => sum + value!, 0n)
})
const effectiveTerm = computed(() => form.value.payment_term || supplierInfo.value?.payment_term || '')
const termHint = computed(() => {
  const term = effectiveTerm.value
  if (term === 'cash') return '按每批合格收货日到期。'
  if (term === 'manual') return '指定付款日期；留空时沿用订单交期。'
  if (term.startsWith('month') || term === 'custom') {
    const days = term === 'custom' ? (form.value.payment_days === '' ? supplierInfo.value?.payment_days || 0 : form.value.payment_days) : term.slice(5)
    return `每批合格收货当月月底 + ${days}天；跨月收货分别到期。`
  }
  return '请选择供应商，或单独约定本单账期。'
})
function selectedIssue(row: Row) {
  const latest = lines.value.find(line => line.bom_line === row.bom_line)
  if (!latest || !eligible(latest)) return '当前已无缺料或物料停用，请移除此项。'
  const quantity = quantityValue(row.quantity), shortage = quantityValue(latest.shortage)
  return quantity != null && shortage != null && quantity > shortage ? `数量超过当前缺料 ${latest.shortage}，请调整。` : ''
}
function add(row: Row) {
  if (selected.value.includes(row.bom_line) || !eligible(row)) return
  edits.value[row.bom_line] = { ...row, quantity: row.shortage, unit_price: '', due_date: '' }
  selected.value.push(row.bom_line)
}
function remove(id: number) { selected.value = selected.value.filter(value => value !== id); delete edits.value[id] }
function toggle(row: Row) {
  if (disabled.value) return
  if (selected.value.includes(row.bom_line)) remove(row.bom_line)
  else add(row)
}
function clearSelection() { selected.value = []; edits.value = {} }
function selectFiltered() { filtered.value.filter(eligible).forEach(add) }
watch([search, brands, units, types, categories, shortageOnly, pageSize], () => { page.value = 1 }, { deep: true })
watch(effectiveTerm, term => { if (term !== 'manual') form.value.payment_due_date = ''; if (term !== 'custom') form.value.payment_days = '' })
let generation = 0, supplierGeneration = 0
let key = crypto.randomUUID(), signature = ''
async function load() {
  const current = ++generation, id = Number(project.value)
  error.value = ''; recovery.value = []
  if (!id) { lines.value = []; projectInfo.value = undefined; loading.value = false; return }
  loading.value = true
  try {
    const [demand, detail] = await Promise.all([read(`/business/projects/${id}/demand/`), read(`/business/projects/${id}/`)])
    if (current !== generation) return
    lines.value = demand.lines; projectInfo.value = detail; page.value = 1
    await nextTick(); fitDraft()
  } catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) loading.value = false }
}
watch(() => form.value.supplier, async value => {
  const current = ++supplierGeneration
  supplierInfo.value = undefined; supplierLoading.value = false
  if (!value) return
  supplierLoading.value = true
  try {
    const result = await read(`/business/partners/${value}/`)
    if (current === supplierGeneration) supplierInfo.value = result
  } catch (e) { if (current === supplierGeneration) error.value = message(e) }
  finally { if (current === supplierGeneration) supplierLoading.value = false }
})
watch(project, async () => {
  clearSelection(); lines.value = []; projectInfo.value = undefined
  search.value = ''; brands.value = []; units.value = []; types.value = []; categories.value = []; shortageOnly.value = false
  form.value = freshForm(); key = crypto.randomUUID(); signature = ''
  await load()
})
watch(() => props.projectId, value => { project.value = value })
onMounted(async () => {
  window.addEventListener('resize', fitDraft)
  window.addEventListener('scroll', fitDraft, true)
  heading.value?.focus({ preventScroll: true })
  await load()
  if (Number(project.value) === props.projectId) lines.value.filter(row => props.initialSelection?.includes(row.bom_line)).forEach(add)
})
onBeforeUnmount(() => {
  generation++; supplierGeneration++
  window.removeEventListener('resize', fitDraft)
  window.removeEventListener('scroll', fitDraft, true)
})
async function save() {
  if (disabled.value || supplierLoading.value || !buyer()) return
  error.value = ''; recovery.value = []
  try {
    if (!chosen.value.length) throw new Error('请先勾选需要采购的物料。')
    const data = { ...form.value, project: project.value, lines: chosen.value }
    validateFields(fields, data)
    for (const row of chosen.value) {
      if (quantityValue(row.quantity) === 0n) throw new Error(`${row.item_name}：采购数量必须大于零。`)
      if (purchaseLineCents(row.quantity, row.unit_price) == null) throw new Error(`${row.item_name}：数量须为正数、最多3位小数；含税单价须为非负数字、最多2位小数，不含单位或科学计数法。`)
      const issue = selectedIssue(row)
      if (issue) throw new Error(`${row.item_name}：${issue}`)
    }
    if (effectiveTerm.value === 'custom' && form.value.payment_days !== '' && (!/^\d+$/.test(String(form.value.payment_days)) || Number(form.value.payment_days) > 365)) throw new Error('自定义月结天数须为0到365的整数。')
    const body = { ...payload(fields, data), from_demand: true,
      lines: chosen.value.map(row => ({ item: row.item, bom_line: row.bom_line, quantity: row.quantity, unit_price: row.unit_price, ...(row.due_date ? { due_date: row.due_date } : {}) })),
    }
    const next = JSON.stringify(body)
    if (signature && signature !== next) key = crypto.randomUUID()
    signature = next
    saving.value = true
    const result = await write('/business/purchases/', body, key)
    ElMessage.success('采购草稿已保存，可在采购订单中提交审批。')
    emit('saved', result)
  } catch (e) {
    error.value = message(e); recovery.value = recoveryActions(e)
    await nextTick()
    heading.value?.scrollIntoView({ block: 'nearest' })
  } finally { saving.value = false }
}
</script>
<template>
  <section v-if="buyer()" class="panel bom-purchase-workspace" aria-label="BOM 勾选采购">
    <header class="panel-heading purchase-heading">
      <div><h2 ref="heading" tabindex="-1">BOM 勾选采购</h2><p v-if="projectInfo" class="muted">{{ projectInfo.code }} · {{ projectInfo.name }}</p></div>
      <div class="toolbar"><router-link v-if="project" :to="`/projects/${project}`">查看项目</router-link><el-button :disabled="saving" @click="emit('close')">返回列表</el-button></div>
    </header>
    <details v-if="!projectId" class="purchase-project" :open="!project"><summary>{{ project ? '更换采购项目' : '选择采购项目' }}</summary><label>采购项目<RemoteSelect v-model="project" path="/business/projects/" label="采购项目" :disabled="disabled" :accept="row => ['active', 'delivering', 'warranty'].includes(row.status)" /></label><p class="muted">一张采购单对应一个项目和一个供应商；切换项目会清空当前草稿。</p></details>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
    <p v-for="action in recovery" :key="action.path"><router-link :to="action.path">{{ action.label }}</router-link></p>
    <div class="purchase-columns">
      <section class="purchase-materials" aria-label="BOM 选料区">
        <header class="purchase-pane-heading"><h3>BOM 选料</h3></header>
        <div class="purchase-filters">
          <label class="material-search">搜索物料<div><el-icon><Search /></el-icon><input v-model="search" aria-label="搜索 BOM 物料" placeholder="编码、名称、规格、图号" :disabled="disabled" /></div></label>
          <label>品牌<ElSelect v-model="brands" multiple collapse-tags collapse-tags-tooltip clearable filterable aria-label="筛选品牌" placeholder="全部品牌" :disabled="disabled"><ElOption v-for="value in options('brand')" :key="value" :value="value" :label="value || '未填写'" /></ElSelect></label>
          <label>单元<ElSelect v-model="units" multiple collapse-tags collapse-tags-tooltip clearable filterable aria-label="筛选单元" placeholder="全部单元" :disabled="disabled"><ElOption v-for="value in options('assembly_unit')" :key="value" :value="value" :label="value || '未填写'" /></ElSelect></label>
          <label>类别<ElSelect v-model="types" multiple collapse-tags collapse-tags-tooltip clearable aria-label="筛选类别" placeholder="全部类别" :disabled="disabled"><ElOption v-for="value in options('part_type')" :key="value" :value="value" :label="typeName(value)" /></ElSelect></label>
        </div>
        <div class="purchase-filter-extras"><label class="inline-check"><input v-model="shortageOnly" type="checkbox" :disabled="disabled" />仅看缺料 <span class="record-count">{{ lines.filter(row => Number(row.shortage) > 0).length }}</span></label><label class="category-filter">产品编码类别<ElSelect v-model="categories" multiple collapse-tags clearable aria-label="筛选产品编码类别" placeholder="全部编码类别" :disabled="disabled"><ElOption v-for="value in options('product_category')" :key="value" :value="value" :label="productCategories[value] || '未分类'" /></ElSelect></label><el-button text :icon="Refresh" :disabled="disabled || !project" @click="load">刷新缺料</el-button></div>
        <div class="purchase-selection"><span role="status" aria-label="BOM 选择状态">已选 <strong>{{ selected.length }}</strong> 项 · 筛选结果 {{ filtered.length }} 项</span><el-button text :disabled="disabled || !filtered.some(eligible)" @click="selectFiltered">全选筛选结果</el-button><el-button text :disabled="disabled || !selected.length" @click="clearSelection">清空选择</el-button></div>
        <el-table v-loading="loading" :data="visible" row-key="bom_line" :max-height="560" :row-class-name="({ row }: { row: Row }) => selected.includes(row.bom_line) ? 'selected-bom-row' : ''" :empty-text="project ? '没有符合条件的物料，请调整筛选条件' : '请先选择采购项目'">
          <el-table-column label="选择" width="48"><template #default="{ row }"><input class="material-checkbox" type="checkbox" :aria-label="`选择 ${row.item_code}`" :checked="selected.includes(row.bom_line)" :disabled="disabled || !eligible(row)" @change="toggle(row)" /></template></el-table-column>
          <el-table-column type="expand" width="32"><template #default="{ row }"><dl class="material-details"><div v-for="(label, field) in { specification: '规格', drawing_number: '图号', drawing_revision: '图档版本', required_date: '需求日期', application_date: '申请日期', applicant: '申请人', issued: '已领', unit: '计量单位' }" :key="field"><dt>{{ label }}</dt><dd>{{ row[field] || '—' }}</dd></div><div><dt>产品编码类别</dt><dd>{{ productCategories[row.product_category] || '未分类' }}</dd></div></dl></template></el-table-column>
          <el-table-column label="物料" min-width="160"><template #default="{ row }"><strong class="material-name">{{ row.item_name }}</strong><small class="material-code">{{ row.item_code }}</small><span class="material-kind">{{ typeName(row.part_type) }}</span><small v-if="row.is_active === false"> 已停用</small></template></el-table-column>
          <el-table-column label="品牌 / 单元" min-width="110"><template #default="{ row }"><span>{{ row.brand || '—' }}</span><small class="material-code">{{ row.assembly_unit || '未分单元' }}</small></template></el-table-column>
          <el-table-column prop="quantity" label="需求" min-width="62" align="right" /><el-table-column prop="available" label="库存" min-width="62" align="right" /><el-table-column prop="incoming" label="在途" min-width="62" align="right" />
          <el-table-column label="缺料" min-width="62" align="right"><template #default="{ row }"><strong :class="Number(row.shortage) > 0 ? 'shortage-number' : 'muted'">{{ row.shortage }}</strong></template></el-table-column>
        </el-table>
        <ListPagination :page="page" :total="filtered.length" @change="page = $event" />
        <p class="purchase-stock-note muted"><el-icon><InfoFilled /></el-icon>库存共享，不预留；跨单元的已领、在途和库存为按行分摊，并非单元实际领用记录。</p>
      </section>
      <section ref="draftPane" class="purchase-draft" aria-label="采购草稿" :style="{ '--draft-height': draftHeight }">
        <header class="purchase-pane-heading">
          <div><h3>采购草稿 <small class="muted">已选 {{ chosen.length }} 项</small></h3></div>
        </header>
        <form @submit.prevent="save">
          <div class="draft-fields">
            <label>供应商 <span class="required">*</span><RemoteSelect v-model="form.supplier" path="/business/partners/" :params="{ is_active: true }" :accept="row => row.kind !== 'customer'" label="供应商" :disabled="saving || !project" required /></label>
            <div class="draft-field-row"><label>计划交期 <span class="required">*</span><input v-model="form.due_date" type="date" aria-label="交期" required :disabled="saving || !project" /></label><label>结算方式<select v-model="form.payment_term" aria-label="结算方式" :disabled="saving || !project"><option value="">{{ supplierInfo ? `沿用供应商：${termLabel(supplierInfo)}` : '沿用供应商' }}</option><option v-for="(label, value) in termLabels" :key="value" :value="value">{{ label }}</option></select></label></div>
            <small>{{ termHint }}</small>
            <label v-if="effectiveTerm === 'custom'">自定义月结天数<input v-model="form.payment_days" aria-label="自定义月结天数" inputmode="numeric" placeholder="0～365，留空沿用供应商" :disabled="saving" /></label>
            <label v-if="effectiveTerm === 'manual'">付款到期日<input v-model="form.payment_due_date" aria-label="付款到期日" type="date" :disabled="saving" /></label>
            <details class="draft-extra"><summary>备注与明细交期</summary><label>采购备注<textarea v-model="form.note" aria-label="采购备注" rows="2" :disabled="saving" placeholder="交付、包装等补充要求" /></label><label v-for="row in chosen" :key="row.bom_line">{{ row.item_name }} · {{ row.assembly_unit || '未分单元' }}<input v-model="row.due_date" type="date" aria-label="明细交期" :disabled="saving" /></label><small>明细交期留空时沿用订单交期。</small></details>
          </div>
          <div class="draft-items">
            <p v-if="!chosen.length" class="draft-empty">在 BOM 选料区勾选有缺料的物料，采购明细会显示在这里。</p>
            <div v-for="row in chosen" :key="row.bom_line" class="draft-item" :aria-label="`采购明细 ${row.item_code} ${row.assembly_unit || ''}`">
              <div class="draft-item-title"><div><strong>{{ row.item_name }}</strong><small>{{ row.item_code }} · {{ row.assembly_unit || '未分单元' }}</small></div><el-button text :icon="Close" :aria-label="`移除 ${row.item_code} ${row.assembly_unit || ''}`" :disabled="saving" @click="remove(row.bom_line)" /></div>
              <div class="draft-price-row"><label>数量<span><input v-model="row.quantity" inputmode="decimal" aria-label="采购数量" required :disabled="saving" /><small>{{ row.unit }}</small></span></label><label>含税单价（元）<input v-model="row.unit_price" inputmode="decimal" aria-label="含税单价（元）" placeholder="请填写" required :disabled="saving" /></label><div><small>小计（元）</small><output>{{ formatPurchaseAmount(purchaseLineCents(row.quantity, row.unit_price)) }}</output></div></div>
              <p v-if="selectedIssue(row)" class="draft-line-error">{{ selectedIssue(row) }}</p>
            </div>
          </div>
          <footer class="draft-footer"><div class="draft-total"><strong>含税合计</strong><output aria-label="含税合计">{{ total == null ? '待填写' : `¥ ${formatPurchaseAmount(total)}` }}</output></div><el-button type="primary" native-type="submit" :loading="saving" :disabled="loading || supplierLoading || !chosen.length">保存采购草稿</el-button><small>保存后可提交审批</small></footer>
        </form>
      </section>
    </div>
  </section>
</template>
<style scoped>
.bom-purchase-workspace { min-width: 0; container-type: inline-size; }
.purchase-heading { align-items: center; }
.purchase-heading h2 { font-size: 22px; margin: 0; }
.purchase-heading p { margin: 8px 0 0; }
.purchase-project { margin-bottom: 16px; font-size: 13px; }
.purchase-project summary { cursor: pointer; color: var(--el-color-primary); }
.purchase-project > label { display: grid; gap: 6px; max-width: 400px; margin-top: 12px; font-size: 13px; }
.purchase-columns { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(350px, 1fr); gap: 24px; align-items: start; }
.purchase-pane-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 32px; margin-bottom: 12px; }
.purchase-pane-heading > div { min-width: 0; }
.purchase-pane-heading h3 { margin: 0; font-size: 17px; }
.purchase-pane-heading h3 small { margin-left: 6px; font-size: 12px; font-weight: 400; white-space: nowrap; }
.purchase-materials { min-width: 0; }
.purchase-filters { display: grid; grid-template-columns: minmax(140px, 1.5fr) repeat(3, minmax(105px, 1fr)); gap: 10px; padding: 8px 0 14px; }
.purchase-filters label, .draft-fields label { display: grid; gap: 6px; min-width: 0; font-size: 13px; }
.material-search > div { position: relative; }
.material-search .el-icon { position: absolute; left: 10px; top: 12px; color: #78869a; }
.material-search input { padding-left: 30px; }
.purchase-filters :deep(.el-select__wrapper) { min-height: 38px; }
.purchase-filter-extras { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; padding-bottom: 12px; }
.category-filter { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.category-filter .el-select { width: 155px; }
.purchase-filter-extras > .el-button { margin-left: auto; }
.purchase-selection { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; padding: 4px 0 10px; font-size: 12px; border-bottom: 1px solid var(--surface-border); }
.purchase-selection > span { margin-right: auto; }
.purchase-selection strong { color: var(--el-color-primary); }
.purchase-selection .el-button { margin: 0; padding: 6px; font-size: 12px; }
.material-checkbox { width: 17px; height: 17px; accent-color: var(--el-color-primary); cursor: pointer; }
.material-checkbox:disabled { cursor: not-allowed; }
.material-name { font-size: 13px; font-weight: 600; }
.material-code { display: block; overflow-wrap: anywhere; line-height: 1.5; margin-top: 3px; font-size: 12px; }
.material-kind { display: inline-block; font-size: 11px; line-height: 18px; padding: 0 5px; background: #f1f4f8; color: #617087; border-radius: 4px; margin-top: 4px; }
.shortage-number { color: #b56913; font-variant-numeric: tabular-nums; }
.purchase-materials :deep(.el-table .cell) { padding: 0 8px; }
.purchase-materials :deep(.el-table__cell) { padding: 8px 0; }
.purchase-materials :deep(.el-table .selected-bom-row) { --el-table-tr-bg-color: #edf4fe; }
.material-details { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; padding: 4px 20px; font-size: 12px; }
.material-details dt { color: #78869a; }
.material-details dd { margin: 4px 0 0; overflow-wrap: anywhere; }
.purchase-stock-note { line-height: 1.65; font-size: 12px; }
.purchase-stock-note .el-icon { vertical-align: -2px; margin-right: 4px; }
.purchase-draft { min-width: 0; border-left: 1px solid var(--surface-border); padding-left: 24px; position: sticky; top: 18px; }
.purchase-draft form { display: flex; flex-direction: column; max-height: calc(var(--draft-height) - 44px); }
.draft-fields { display: grid; gap: 12px; flex-shrink: 0; }
.draft-fields > label:first-child { display: block; }
.draft-fields > label:first-child :deep(.remote-select) { margin-top: 6px; }
.draft-field-row { display: grid; grid-template-columns: 1fr 1.15fr; gap: 12px; }
.required, .draft-line-error { color: var(--el-color-danger); }
.required { display: contents; }
.draft-extra { font-size: 12px; color: #63748b; }
.draft-extra summary { cursor: pointer; }
.draft-extra[open] { max-height: 180px; overflow: auto; }
.draft-extra label { margin: 10px 0; }
.draft-items { overflow-y: auto; min-height: 90px; max-height: 370px; margin-top: 16px; border-top: 1px solid var(--surface-border); }
.draft-empty { padding: 24px 0; line-height: 1.7; color: #78869a; font-size: 13px; }
.draft-item { display: grid; grid-template-columns: minmax(70px, .85fr) minmax(228px, 2.5fr); align-items: center; gap: 8px; padding: 12px 0; border-bottom: 1px solid var(--surface-border); }
.draft-item-title { display: flex; justify-content: space-between; align-items: center; position: relative; padding-right: 16px; }
.draft-item-title > div { min-width: 0; }
.draft-item-title strong { font-size: 13px; }
.draft-item-title small { display: block; font-size: 11px; line-height: 1.5; margin-top: 4px; overflow-wrap: anywhere; }
.draft-item-title .el-button { position: absolute; right: -3px; top: -4px; padding: 2px; height: 24px; }
.draft-price-row { display: grid; grid-template-columns: minmax(52px, .75fr) minmax(72px, 1fr) minmax(65px, 1fr); gap: 8px; align-items: end; }
.draft-price-row label { display: grid; gap: 5px; color: #63748b; font-size: 11px; }
.draft-price-row label > span { display: flex; gap: 4px; align-items: center; }
.draft-price-row input { min-width: 0; min-height: 32px; padding: 6px; text-align: right; font-variant-numeric: tabular-nums; }
.draft-price-row > div { display: grid; gap: 10px; text-align: right; padding-bottom: 8px; }
.draft-price-row small { font-size: 11px; }
.draft-price-row output { font-size: 13px; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
.draft-line-error { grid-column: 1 / -1; font-size: 12px; margin: 8px 0 0; }
.draft-footer { flex-shrink: 0; padding-top: 18px; background: white; display: grid; gap: 12px; }
.draft-total { display: flex; gap: 8px; align-items: baseline; justify-content: space-between; }
.draft-total strong { font-size: 14px; }
.draft-total output { color: var(--el-color-primary); font-size: 24px; font-weight: 650; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.draft-footer .el-button { width: 100%; height: 42px; }
.draft-footer > small { text-align: center; font-size: 12px; }
@container (max-width: 940px) {
  .purchase-columns { grid-template-columns: minmax(0, 1fr); }
  .purchase-draft { position: static; border-left: 0; border-top: 1px solid var(--surface-border); padding: 20px 0 0; }
  .purchase-draft form { max-height: none; }
  .draft-items { max-height: 420px; }
  .draft-item { grid-template-columns: minmax(0, 1fr); }
  .draft-price-row { margin-top: 8px; }
}
@media (max-width: 600px) {
  .purchase-heading { flex-wrap: wrap; }
  .purchase-heading h2 { font-size: 20px; }
  .purchase-project { display: block; }
  .purchase-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .purchase-filter-extras { gap: 8px; }
  .category-filter { flex: 1 1 200px; }
  .draft-field-row { grid-template-columns: minmax(0, 1fr); }
  .material-details { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
