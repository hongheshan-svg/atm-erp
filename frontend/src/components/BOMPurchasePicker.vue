<script setup lang="ts">
import BusinessTable from './BusinessTable.vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElOption, ElSelect } from 'element-plus'
import { Close, InfoFilled, Refresh, Search } from '@element-plus/icons-vue'
import { read, write } from '../api'
import { buyer } from '../modules/shared'
import { purchaseFields } from '../modules/purchases'
import { termLabel, termLabels } from '../modules/payment-terms'
import { defaults, payload, today, validateFields } from '../forms'
import { formatPurchaseAmount, purchaseLineCents, quantityValue } from '../bom-purchase'
import { quantityText as qty } from '../utils/quantity'
import { message, recoveryActions, requestKey } from '../utils/request'
import { pageSize } from '../pagination'
import { partTypeLabel, productCategories } from '../product-categories'
import { fromScaled, QUANTITY_SCALE } from '../utils/decimal'
import type { Row } from '../types'
import RemoteSelect from './RemoteSelect.vue'
import ListPagination from './ListPagination.vue'

// shortageOnly：从 BOM 页打开时沿用该页当前的「仅看缺料」筛选；从采购页打开不传，默认显示全部。
const props = defineProps<{ projectId?: number; initialSelection?: number[]; shortageOnly?: boolean }>()
const emit = defineEmits<{ saved: [result: Row]; close: [] }>()
const fields = purchaseFields()
const freshForm = () => ({ ...defaults(fields), lines: [] })
const form = ref<Row>(freshForm())
const project = ref<number | string | undefined>(props.projectId)
const projectInfo = ref<Row>(), supplierInfo = ref<Row>()
const supplierLoading = ref(false)
const lines = ref<Row[]>([]), selected = ref<number[]>([])
const edits = ref<Record<number, Row>>({})
const search = ref(''), brands = ref<string[]>([]), units = ref<string[]>([]), types = ref<string[]>([]), categories = ref<string[]>([])
const sortBy = ref<'date' | 'shortage' | 'unit'>('date')
const shortageOnly = ref(Boolean(props.shortageOnly)), page = ref(1), loading = ref(false), saving = ref(false), error = ref('')
const moreFilters = ref(false)
const activeFilters = computed(() => brands.value.length + units.value.length + types.value.length + categories.value.length)
// 结果被筛过却看不见条件会造成漏采，凡有生效的筛选项就默认展开「更多筛选」。
watch(activeFilters, count => { if (count) moreFilters.value = true }, { immediate: true })
const recovery = ref<{ label: string; path: string }[]>([])
const heading = ref<HTMLElement>()
const draftPane = ref<HTMLElement>()
const materialsPane = ref<HTMLElement>()
const draftHeight = ref('calc(100dvh - 40px)')
function fitDraft() {
  const pane = draftPane.value
  if (!pane) return
  // 高度下限取表头、字段、至少一条明细和合计区的实际高度：可用空间不够时整块随页面滚动。
  // 否则保存按钮始终贴在视口下沿之外，越滚动越追不上。
  const block = (selector: string) => pane.querySelector<HTMLElement>(selector)?.offsetHeight ?? 0
  const rows = Math.min(Math.max(chosen.value.length, 1), 3)
  const needed = block('.purchase-pane-heading') + block('.draft-fields') + block('.draft-footer') + 50 + rows * 112 + (groups.value.some(group => group.multi) ? 110 : 0)
  draftHeight.value = `${Math.max(440, needed, window.innerHeight - Math.max(18, pane.getBoundingClientRect().top) - 20)}px`
}
const disabled = computed(() => loading.value || saving.value)
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
const todayText = today()
const overdue = (row: Row) => Number(row.shortage) > 0 && !!row.required_date && String(row.required_date) < todayText
// 采购员按需求日期定优先级：默认最早需求在前（无日期排后）、缺料多者优先；也可按单元核对。
function byText(a: unknown, b: unknown) { return String(a || '').localeCompare(String(b || ''), 'zh-CN') }
const sorted = computed(() => {
  const mode = sortBy.value
  const list = filtered.value.map((row, index) => ({ row, index }))
  list.sort((x, y) => {
    let diff: number
    if (mode === 'unit') diff = byText(x.row.assembly_unit, y.row.assembly_unit) || byText(x.row.item_code, y.row.item_code)
    else {
      const dx = x.row.required_date || '9999-12-31', dy = y.row.required_date || '9999-12-31'
      diff = (mode === 'date' ? byText(dx, dy) : 0) || Number(y.row.shortage) - Number(x.row.shortage)
    }
    return diff || x.index - y.index
  })
  return list.map(value => value.row)
})
const visible = computed(() => sorted.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
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
  return quantity != null && shortage != null && quantity > shortage ? `数量超过当前缺料 ${qty(latest.shortage)}，请调整。` : ''
}
// 单价模型：同物料一个组价（groupPrice），组内各行 unit_price 默认等于组价；
// 某行「单独定价」后（own_price）脱离组价，组价改动不再覆盖它。提交仍是逐 bom_line 的明细。
const groupPrice = ref<Record<number, string>>({})
function add(row: Row) {
  if (selected.value.includes(row.bom_line) || !eligible(row)) return
  edits.value[row.bom_line] = { ...row, quantity: qty(row.shortage, ''), unit_price: groupPrice.value[row.item] ?? '', own_price: false, due_date: '' }
  selected.value.push(row.bom_line)
}
const sameItemCount = (row: Row) => chosen.value.filter(value => value.item === row.item).length
function setGroupPrice(item: number, value: string) {
  groupPrice.value[item] = value
  for (const row of chosen.value) if (row.item === item && !row.own_price) row.unit_price = value
}
// 单个单元的行直接填价即是组价；多单元时行内填价视为单独定价。
function setRowPrice(row: Row, value: string) {
  if (sameItemCount(row) > 1) { row.own_price = true; row.unit_price = value } else setGroupPrice(row.item, value)
}
function useGroupPrice(row: Row) { row.own_price = false; row.unit_price = groupPrice.value[row.item] ?? '' }
const groups = computed(() => {
  const map = new Map<number, Row[]>()
  for (const row of chosen.value) map.set(row.item, [...(map.get(row.item) || []), row])
  return [...map.entries()].map(([item, rows]) => {
    const sums = rows.map(row => quantityValue(row.quantity))
    const sum = sums.some(value => value == null) ? null : sums.reduce<bigint>((acc, value) => acc + value!, 0n)
    return { item, first: rows[0]!, rows: rows.length > 1 ? [...rows].sort((x, y) => byText(x.assembly_unit, y.assembly_unit)) : rows, multi: rows.length > 1,
      quantity: sum == null ? '—' : qty(fromScaled(sum, QUANTITY_SCALE)) }
  })
})
function remove(id: number) { selected.value = selected.value.filter(value => value !== id); delete edits.value[id] }
function toggle(row: Row) {
  if (disabled.value) return
  if (selected.value.includes(row.bom_line)) remove(row.bom_line)
  else add(row)
}
function clearSelection() { selected.value = []; edits.value = {}; groupPrice.value = {} }
function selectFiltered() { filtered.value.filter(eligible).forEach(add) }
function handleRowClick(row: Row, column?: { label?: string; type?: string }) {
  if (disabled.value || column?.label === '选择' || column?.type === 'expand') return
  toggle(row)
}
function jumpToDraft() { draftPane.value?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }
function jumpToMaterials() { materialsPane.value?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }
watch([search, brands, units, types, categories, shortageOnly, sortBy, pageSize], () => { page.value = 1 }, { deep: true })
watch(effectiveTerm, term => { if (term !== 'manual') form.value.payment_due_date = ''; if (term !== 'custom') form.value.payment_days = '' })
watch([effectiveTerm, () => Math.min(chosen.value.length, 3), () => groups.value.some(group => group.multi)], async () => { await nextTick(); fitDraft() })
let generation = 0, supplierGeneration = 0
let key = requestKey(), signature = ''
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
  moreFilters.value = false
  form.value = freshForm(); key = requestKey(); signature = ''
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
    for (const row of chosen.value) {
      if (quantityValue(row.quantity) === 0n) throw new Error(`${row.item_name}：采购数量必须大于零。`)
      if (purchaseLineCents(row.quantity, row.unit_price) == null) throw new Error(`${row.item_name}：数量须为正数、最多3位小数；含税单价须为非负数字、最多2位小数，不含单位或科学计数法。`)
      const issue = selectedIssue(row)
      if (issue) throw new Error(`${row.item_name}：${issue}`)
    }
    validateFields(fields, data)
    if (effectiveTerm.value === 'custom' && form.value.payment_days !== '' && (!/^\d+$/.test(String(form.value.payment_days)) || Number(form.value.payment_days) > 365)) throw new Error('自定义月结天数须为0到365的整数。')
    const body = { ...payload(fields, data), from_demand: true,
      lines: chosen.value.map(row => ({ item: row.item, bom_line: row.bom_line, quantity: row.quantity, unit_price: row.unit_price, ...(row.due_date ? { due_date: row.due_date } : {}) })),
    }
    const next = JSON.stringify(body)
    if (signature && signature !== next) key = requestKey()
    signature = next
    saving.value = true
    const result = await write('/business/purchases/', body, key)
    ElMessage({ type: 'success', duration: 8000, showClose: true, message: `采购草稿${result?.code ? ` ${result.code}` : ''} 已保存，可在采购订单中提交审批。` })
    emit('saved', result)
  } catch (e) {
    error.value = message(e); recovery.value = recoveryActions(e)
    await nextTick()
    heading.value?.scrollIntoView({ block: 'nearest' })
  } finally { saving.value = false }
}
</script>
<template>
  <section v-if="buyer()" class="panel bom-purchase-workspace" aria-label="从 BOM 多选下单">
    <header class="panel-heading purchase-heading">
      <div><h2 ref="heading" tabindex="-1">从 BOM 多选下单</h2><p v-if="projectInfo" class="muted">{{ projectInfo.code }} · {{ projectInfo.name }}</p></div>
      <div class="toolbar"><router-link v-if="project" :to="`/projects/${project}`">查看项目</router-link><el-button :disabled="saving" @click="emit('close')">返回列表</el-button></div>
    </header>
    <details v-if="!projectId" class="purchase-project" :open="!project"><summary>{{ project ? '更换采购项目' : '选择采购项目' }}</summary><label>采购项目<RemoteSelect v-model="project" path="/business/projects/" label="采购项目" :disabled="disabled" :accept="row => ['active', 'delivering', 'warranty'].includes(row.status)" /></label><p class="muted">一张采购单对应一个项目和一个供应商；切换项目会清空当前草稿。</p></details>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
    <p v-for="action in recovery" :key="action.path"><router-link :to="action.path">{{ action.label }}</router-link></p>
    <div class="purchase-columns">
      <section ref="materialsPane" class="purchase-materials" aria-label="BOM 选料区">
        <header class="purchase-pane-heading"><h3>BOM 选料</h3></header>
        <div class="purchase-filters">
          <label class="material-search">搜索物料<div><el-icon><Search /></el-icon><input v-model="search" aria-label="搜索 BOM 物料" placeholder="编码、名称、规格、图号" :disabled="disabled" /></div></label>
          <label class="inline-check"><input v-model="shortageOnly" type="checkbox" :disabled="disabled" />仅看缺料 <span class="record-count">{{ lines.filter(row => Number(row.shortage) > 0).length }}</span></label>
          <el-button class="more-filters-toggle" :class="{ 'has-filters': activeFilters }" aria-controls="purchase-more-filters" :aria-expanded="moreFilters" :aria-label="activeFilters ? `更多筛选，已选 ${activeFilters} 个条件` : '更多筛选'" @click="moreFilters = !moreFilters">更多筛选<span v-if="activeFilters">&nbsp;·&nbsp;{{ activeFilters }}</span></el-button>
          <label class="sort-select">排序<select v-model="sortBy" aria-label="选料排序" :disabled="disabled"><option value="date">需求日期（早→晚）</option><option value="shortage">缺料（多→少）</option><option value="unit">单元 → 物料编码</option></select></label>
          <el-button text :icon="Refresh" :disabled="disabled || !project" @click="load">刷新缺料</el-button>
        </div>
        <div v-show="moreFilters" id="purchase-more-filters" class="purchase-more-filters">
          <label>品牌<ElSelect v-model="brands" multiple collapse-tags collapse-tags-tooltip clearable filterable aria-label="筛选品牌" placeholder="全部品牌" :disabled="disabled"><ElOption v-for="value in options('brand')" :key="value" :value="value" :label="value || '未填写'" /></ElSelect></label>
          <label>单元<ElSelect v-model="units" multiple collapse-tags collapse-tags-tooltip clearable filterable aria-label="筛选单元" placeholder="全部单元" :disabled="disabled"><ElOption v-for="value in options('assembly_unit')" :key="value" :value="value" :label="value || '未填写'" /></ElSelect></label>
          <label>类别<ElSelect v-model="types" multiple collapse-tags collapse-tags-tooltip clearable aria-label="筛选类别" placeholder="全部类别" :disabled="disabled"><ElOption v-for="value in options('part_type')" :key="value" :value="value" :label="partTypeLabel(value)" /></ElSelect></label>
          <label>产品编码类别<ElSelect v-model="categories" multiple collapse-tags clearable aria-label="筛选产品编码类别" placeholder="全部编码类别" :disabled="disabled"><ElOption v-for="value in options('product_category')" :key="value" :value="value" :label="productCategories[value] || '未分类'" /></ElSelect></label>
        </div>
        <div class="purchase-selection"><span role="status" aria-label="BOM 选择状态">已选 <strong>{{ selected.length }}</strong> 项 · 筛选结果 {{ filtered.length }} 项</span><el-button text :disabled="disabled || !filtered.some(eligible)" @click="selectFiltered">全选筛选结果</el-button><el-button text :disabled="disabled || !selected.length" @click="clearSelection">清空选择</el-button><el-button text class="mobile-jump" :disabled="!chosen.length" @click="jumpToDraft">采购草稿 ↓</el-button></div>
        <BusinessTable label="采购选料" :numbered="false" v-loading="loading" :data="visible" row-key="bom_line" :max-height="560" :row-class-name="({ row }: { row: Row }) => selected.includes(row.bom_line) ? 'selected-bom-row' : ''" :empty-text="project ? '没有符合条件的物料，请调整筛选条件' : '请先选择采购项目'" @row-click="handleRowClick">
          <el-table-column label="选择" width="44"><template #default="{ row }"><input class="material-checkbox" type="checkbox" :aria-label="`选择 ${row.item_code}`" :checked="selected.includes(row.bom_line)" :disabled="disabled || !eligible(row)" @change="toggle(row)" /></template></el-table-column>
          <el-table-column type="expand" width="28"><template #default="{ row }"><dl class="material-details"><div v-for="(label, field) in { drawing_number: '图号', drawing_revision: '图档版本', application_date: '申请日期', applicant: '申请人', issued: '已领', unit: '计量单位' }" :key="field"><dt>{{ label }}</dt><dd>{{ field === 'issued' ? qty(row[field]) : row[field] || '—' }}</dd></div><div><dt>类别</dt><dd>{{ partTypeLabel(row.part_type) }}</dd></div><div><dt>产品编码类别</dt><dd>{{ productCategories[row.product_category] || '未分类' }}</dd></div><div><dt>其他项目待领</dt><dd>{{ Number(row.other_demand) > 0 ? `${qty(row.other_demand)} · ${row.other_projects} 个在执行项目` : '—' }}</dd></div></dl></template></el-table-column>
          <el-table-column label="物料" min-width="150"><template #default="{ row }"><strong class="material-name">{{ row.item_name }}</strong><small v-if="row.is_active === false"> 已停用</small><small class="material-code material-spec" :title="[row.item_code, row.specification].filter(Boolean).join(' · ')">{{ [row.item_code, row.specification].filter(Boolean).join(' · ') }}</small><small class="material-narrow" :class="{ 'overdue-date': overdue(row) }">缺 {{ qty(row.shortage) }}{{ row.required_date ? ` · 需 ${String(row.required_date).slice(5)}` : '' }}</small></template></el-table-column>
          <el-table-column label="单元 / 品牌" min-width="92"><template #default="{ row }"><span>{{ row.assembly_unit || '未分单元' }}</span><small class="material-code">{{ row.brand || '—' }}</small></template></el-table-column>
          <el-table-column label="缺料" min-width="68" align="right" class-name="nowrap-col"><template #default="{ row }"><strong :class="Number(row.shortage) > 0 ? 'shortage-number' : 'muted'">{{ qty(row.shortage) }}</strong></template></el-table-column>
          <el-table-column label="需求" min-width="68" align="right" class-name="nowrap-col"><template #default="{ row }">{{ qty(row.quantity) }}</template></el-table-column>
          <el-table-column label="需求日期" min-width="104" class-name="nowrap-col"><template #default="{ row }"><span :class="{ 'overdue-date': overdue(row) }" :title="overdue(row) ? '需求日期已过' : ''">{{ row.required_date || '—' }}</span></template></el-table-column>
          <el-table-column label="库存" min-width="68" align="right" class-name="nowrap-col"><template #default="{ row }"><span :class="{ 'contested-number': Number(row.available) > 0 && Number(row.other_demand) > 0 }" :title="Number(row.other_demand) > 0 ? `其他 ${row.other_projects} 个在执行项目还需 ${qty(row.other_demand)}` : ''">{{ qty(row.available) }}</span><small class="material-code">在途 {{ qty(row.incoming) }}</small></template></el-table-column>
        </BusinessTable>
        <ListPagination :page="page" :total="filtered.length" @change="page = $event" />
        <p class="purchase-stock-note muted"><el-icon><InfoFilled /></el-icon>库存共享，不预留：标红的库存同时被其他在执行项目的 BOM 盯着，展开可看具体数量。跨单元的已领、在途和库存为按行分摊，并非单元实际领用记录。</p>
      </section>
      <section ref="draftPane" class="purchase-draft" aria-label="采购草稿" :style="{ '--draft-height': draftHeight }">
        <header class="purchase-pane-heading">
          <div><h3>采购草稿 <small class="muted">已选 {{ chosen.length }} 项</small></h3></div>
          <el-button text class="mobile-jump" @click="jumpToMaterials">← 返回选料</el-button>
        </header>
        <form @submit.prevent="save">
          <div class="draft-fields">
            <label>供应商 <span class="required">*</span><RemoteSelect v-model="form.supplier" path="/business/partners/" :params="{ is_active: true }" :accept="row => row.kind !== 'customer'" label="供应商" :disabled="saving || !project" required /></label>
            <div class="draft-field-row"><label>计划交期 <span class="required">*</span><input v-model="form.due_date" type="date" aria-label="交期" required :disabled="saving || !project" /></label><label>结算方式<select v-model="form.payment_term" aria-label="结算方式" :disabled="saving || !project"><option value="">{{ supplierInfo ? `沿用供应商：${termLabel(supplierInfo)}` : '沿用供应商' }}</option><option v-for="(label, value) in termLabels" :key="value" :value="value">{{ label }}</option></select></label></div>
            <small>{{ termHint }}</small>
            <label v-if="effectiveTerm === 'custom'">自定义月结天数<input v-model="form.payment_days" aria-label="自定义月结天数" inputmode="numeric" placeholder="0～365，留空沿用供应商" :disabled="saving" /></label>
            <label v-if="effectiveTerm === 'manual'">付款到期日<input v-model="form.payment_due_date" aria-label="付款到期日" type="date" :disabled="saving" /></label>
            <details class="draft-extra"><summary>采购单号、备注、质保与明细交期</summary><label>采购单号<input v-model="form.code" aria-label="采购单号" maxlength="30" placeholder="可自编，留空自动生成" :disabled="saving || !project" /></label><label>采购备注<textarea v-model="form.note" aria-label="采购备注" rows="2" :disabled="saving" placeholder="交付、包装等补充要求" /></label><label>供应商质保月数<input v-model="form.warranty_months" aria-label="供应商质保月数" inputmode="numeric" :disabled="saving" /><small>按每批合格收货日起算，写入采购合同；默认 12 个月。</small></label><label v-for="row in chosen" :key="row.bom_line">{{ row.item_name }} · {{ row.assembly_unit || '未分单元' }}<input v-model="row.due_date" type="date" :aria-label="`明细交期：${row.item_name} · ${row.assembly_unit || '未分单元'}`" :disabled="saving" /></label><small>明细交期留空时沿用订单交期。</small></details>
          </div>
          <div class="draft-items">
            <p v-if="!chosen.length" class="draft-empty">在 BOM 选料区勾选有缺料的物料，采购明细会显示在这里。</p>
            <div v-for="group in groups" :key="group.item" class="draft-group" :class="{ 'draft-group-multi': group.multi }" :role="group.multi ? 'group' : undefined" :aria-label="group.multi ? `物料组 ${group.first.item_code}` : undefined">
              <div v-if="group.multi" class="draft-group-head">
                <div class="draft-group-title"><strong>{{ group.first.item_name }}</strong><small>{{ group.first.item_code }} · {{ group.rows.length }} 个单元 · 合计 {{ group.quantity }} {{ group.first.unit }}</small><small v-if="group.first.specification" class="draft-spec" :title="group.first.specification">{{ group.first.specification }}</small></div>
                <label>组含税单价（元）<input :value="groupPrice[group.item] ?? ''" inputmode="decimal" :aria-label="`${group.first.item_code} 组含税单价（元）`" placeholder="填一次，各单元同价" :disabled="saving" @input="setGroupPrice(group.item, ($event.target as HTMLInputElement).value)" /></label>
              </div>
              <div v-for="row in group.rows" :key="row.bom_line" class="draft-item" role="group" :aria-label="`采购明细 ${row.item_code} ${row.assembly_unit || ''}`">
                <div class="draft-item-title"><div>
                  <strong v-if="group.multi">{{ row.assembly_unit || '未分单元' }}<small v-if="row.required_date" class="draft-due" :class="{ 'overdue-date': overdue(row) }">需求 {{ row.required_date }}</small></strong>
                  <template v-else><strong>{{ row.item_name }}</strong><small>{{ row.item_code }} · {{ row.assembly_unit || '未分单元' }}</small><small v-if="row.specification || row.required_date"><span v-if="row.specification" class="draft-spec" :title="row.specification">{{ row.specification }}</span><span v-if="row.required_date" :class="{ 'overdue-date': overdue(row) }">{{ row.specification ? ' · ' : '' }}需求 {{ row.required_date }}</span></small></template>
                </div><el-button text :icon="Close" :aria-label="`移除 ${row.item_code} ${row.assembly_unit || ''}`" :disabled="saving" @click="remove(row.bom_line)" /></div>
                <div class="draft-price-row" :class="{ 'draft-price-row-grouped': group.multi }"><label>数量<span><input v-model="row.quantity" inputmode="decimal" aria-label="采购数量" required :disabled="saving" /><small>{{ row.unit }}</small></span></label>
                  <label v-if="!group.multi">含税单价（元）<input :value="row.unit_price" inputmode="decimal" aria-label="含税单价（元）" placeholder="请填写" required :disabled="saving" @input="setRowPrice(row, ($event.target as HTMLInputElement).value)" /></label>
                  <div v-else class="draft-line-price"><small>单价 {{ row.unit_price === '' ? '待填' : row.unit_price }}<em v-if="row.own_price"> · 单独定价</em></small></div>
                  <div><small>小计（元）</small><output>{{ formatPurchaseAmount(purchaseLineCents(row.quantity, row.unit_price)) }}</output></div></div>
                <details v-if="group.multi" class="draft-own-price" :open="row.own_price"><summary>单独定价</summary><label>含税单价（元）<input :value="row.unit_price" inputmode="decimal" aria-label="含税单价（元）" required :disabled="saving" @input="setRowPrice(row, ($event.target as HTMLInputElement).value)" /></label><el-button v-if="row.own_price" text size="small" :disabled="saving" @click="useGroupPrice(row)">恢复组价</el-button></details>
                <p v-if="selectedIssue(row)" class="draft-line-error">{{ selectedIssue(row) }}</p>
              </div>
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
.purchase-filters { display: flex; align-items: flex-end; flex-wrap: wrap; gap: 10px 14px; padding: 8px 0 12px; }
.material-search, .purchase-more-filters label, .draft-fields label { display: grid; gap: 6px; min-width: 0; font-size: 13px; }
.material-search { flex: 1 1 220px; max-width: 340px; }
.material-search > div { position: relative; }
.material-search .el-icon { position: absolute; left: 10px; top: 12px; color: var(--ink-5); }
.material-search input { padding-left: 30px; }
.purchase-filters > .inline-check { padding-bottom: 9px; }
.more-filters-toggle { margin-bottom: 2px; }
.more-filters-toggle.has-filters { color: var(--el-color-primary); border-color: var(--el-color-primary); }
.purchase-filters > .el-button:last-child { margin-left: auto; }
.purchase-more-filters { display: grid; grid-template-columns: repeat(4, minmax(105px, 1fr)); gap: 10px; padding: 2px 0 12px; }
.purchase-more-filters :deep(.el-select__wrapper) { min-height: 38px; }
.purchase-selection { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; padding: 4px 0 10px; font-size: 12px; border-bottom: 1px solid var(--surface-border); }
.purchase-selection > span { margin-right: auto; }
.purchase-selection strong { color: var(--el-color-primary); }
.purchase-selection .el-button { margin: 0; padding: 6px; font-size: 12px; }
.mobile-jump { display: none; }
.material-checkbox { width: 17px; height: 17px; accent-color: var(--el-color-primary); cursor: pointer; }
.material-checkbox:disabled { cursor: not-allowed; }
.purchase-materials :deep(.el-table__row) { cursor: pointer; }
.material-name { font-size: 13px; font-weight: 600; }
.material-code { display: block; overflow-wrap: anywhere; line-height: 1.5; margin-top: 3px; font-size: 12px; }
.purchase-materials :deep(.nowrap-col .cell) { white-space: nowrap; word-break: normal; }
.material-spec { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; overflow-wrap: normal; max-width: 260px; }
.material-narrow { display: none; margin-top: 2px; font-size: 11px; }
.overdue-date { color: var(--el-color-danger); font-weight: 600; }
.sort-select { display: grid; gap: 6px; font-size: 13px; }
.sort-select select { min-height: 38px; }
.draft-spec { color: var(--ink-4); }
.purchase-materials :deep(.el-table .cell) { padding: 0 8px; }
.purchase-materials :deep(.el-table__cell) { padding: 5px 0; }
.purchase-materials :deep(.el-table .selected-bom-row) { --el-table-tr-bg-color: var(--brand-wash); }
.material-details { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; padding: 4px 20px; font-size: 12px; }
.material-details dt { color: var(--ink-5); }
.material-details dd { margin: 4px 0 0; overflow-wrap: anywhere; }
.purchase-stock-note { line-height: 1.65; font-size: 12px; }
.purchase-stock-note .el-icon { vertical-align: -2px; margin-right: 4px; }
.purchase-draft { min-width: 0; border-left: 1px solid var(--surface-border); padding-left: 24px; position: sticky; top: 18px; }
.purchase-draft form { display: flex; flex-direction: column; max-height: calc(var(--draft-height) - 44px); }
.draft-fields { display: grid; gap: 12px; flex-shrink: 0; }
.draft-field-row { display: grid; grid-template-columns: 1fr 1.15fr; gap: 12px; }
.required, .draft-line-error { color: var(--el-color-danger); }
.required { display: contents; }
.draft-extra { font-size: 12px; color: var(--mute); }
.draft-extra summary { cursor: pointer; }
.draft-extra[open] { max-height: 180px; overflow: auto; }
.draft-extra label { margin: 10px 0; }
.draft-items { overflow-y: auto; flex: 1 1 auto; min-height: 90px; max-height: 480px; margin-top: 16px; border-top: 1px solid var(--surface-border); }
.draft-empty { padding: 24px 0; line-height: 1.7; color: var(--ink-5); font-size: 13px; }
/* 明细加了规格与需求日期一行后变高；收紧上下留白，桌面 1080p 下三条明细与保存按钮仍同屏可见。 */
.draft-item { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--surface-border); }
.draft-item-title { display: flex; justify-content: space-between; align-items: center; position: relative; padding-right: 16px; }
.draft-item-title > div { min-width: 0; }
.draft-item-title strong { font-size: 13px; }
.draft-item-title small { display: block; font-size: 11px; line-height: 1.5; margin-top: 2px; overflow-wrap: anywhere; }
.draft-item-title .el-button { position: absolute; right: -3px; top: -4px; padding: 2px; height: 24px; }
.draft-price-row { display: grid; grid-template-columns: minmax(52px, .75fr) minmax(72px, 1fr) minmax(65px, 1fr); gap: 8px; align-items: end; }
.draft-price-row label { display: grid; gap: 5px; color: var(--mute); font-size: 11px; }
.draft-price-row label > span { display: flex; gap: 4px; align-items: center; }
.draft-price-row input { min-width: 0; min-height: 32px; padding: 6px; text-align: right; font-variant-numeric: tabular-nums; }
.draft-price-row > div { display: grid; gap: 10px; text-align: right; padding-bottom: 8px; }
.draft-price-row small { font-size: 11px; }
.draft-price-row output { font-size: 13px; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
.draft-group-head { display: grid; gap: 8px; padding: 10px 0 4px; border-bottom: 1px dashed var(--surface-border); }
.draft-group-title strong { font-size: 13px; }
.draft-group-title small { display: block; font-size: 11px; line-height: 1.5; margin-top: 3px; overflow-wrap: anywhere; }
.draft-group-head label { display: grid; gap: 5px; font-size: 11px; color: var(--mute); }
.draft-group-head input { min-height: 32px; padding: 6px; text-align: right; font-variant-numeric: tabular-nums; }
.draft-group-multi .draft-item { padding: 6px 0 6px 12px; gap: 4px; }
.draft-item-title strong .draft-due { display: inline; margin: 0 0 0 8px; font-weight: 400; }
.draft-group-multi .draft-price-row > label, .draft-group-multi .draft-price-row > div:last-child { font-size: 0; }
.draft-group-multi .draft-price-row > label > span { font-size: 11px; }
.draft-group-multi .draft-price-row > div:last-child { gap: 0; padding-bottom: 6px; }
.draft-group-multi .draft-price-row > div:last-child output { font-size: 13px; }
.draft-price-row-grouped { grid-template-columns: minmax(70px, 1fr) minmax(60px, 1fr) minmax(60px, 1fr); }
.draft-line-price { padding-bottom: 8px; font-size: 11px; color: var(--mute); text-align: center; }
.draft-line-price em { color: var(--el-color-warning); font-style: normal; }
.draft-own-price { font-size: 11px; color: var(--mute); }
.draft-own-price summary { cursor: pointer; }
.draft-own-price label { display: grid; gap: 4px; margin: 6px 0; max-width: 180px; }
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
  /* 窄屏上下排布时整页本身在滚动，明细区不再套一层固定高度的内滚动（手指易被困住、组标题被切）；
     合计与保存吸附在视口底部，滚到哪条明细都能直接保存。 */
  .draft-items { max-height: none; overflow: visible; }
  .draft-footer { position: sticky; bottom: 0; z-index: 2; padding-bottom: calc(12px + env(safe-area-inset-bottom)); box-shadow: 0 -10px 16px -14px rgb(15 23 42 / 35%); }
  .draft-item { grid-template-columns: minmax(0, 1fr); }
  .draft-price-row { margin-top: 8px; }
  .mobile-jump { display: inline-flex; }
  .material-checkbox { width: 22px; height: 22px; }
  .material-narrow { display: block; }
  .purchase-materials :deep(.el-table__cell) { padding: 11px 0; }
  .draft-price-row input { min-height: 40px; }
}
@media (max-width: 600px) {
  .purchase-heading { flex-wrap: wrap; }
  .purchase-heading h2 { font-size: 20px; }
  .purchase-project { display: block; }
  .purchase-filters { gap: 10px; }
  .material-search { flex-basis: 100%; max-width: none; }
  .purchase-more-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .draft-field-row { grid-template-columns: minmax(0, 1fr); }
  .material-details { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
