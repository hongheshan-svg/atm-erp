<script setup lang="ts">
import TableScroll from './TableScroll.vue'
import { computed, nextTick, onBeforeUnmount, ref, useId, watch, type Directive } from 'vue'
import { read } from '../api'
import { sumQuantities } from '../modules/warehouse-lines'
import { message } from '../utils/request'
import { quantityText } from '../utils/quantity'
import type { Field, Row } from '../types'
const props = defineProps<{ field: Field; context: Row; disabled?: boolean; issues?: Record<string, string>; prefix: string }>()
const model = defineModel<Row[]>({ required: true })
const emit = defineEmits<{ touched: [path: string] }>()
const uid = useId(), root = ref<HTMLElement>(), page = ref(0)
const projectInfo = ref<Row>(), demand = ref<Row[]>([]), error = ref(''), loading = ref(false)
let generation = 0
const columns = computed(() => props.field.fields!.filter(field => !field.hidden))
// 按 BOM 批量领料：行数据（需求、BOM 未领、可用）由服务端按项目算好，不再逐行读取项目需求。
const batch = computed(() => props.field.fields!.some(field => field.key === 'bom_remaining'))
const receipt = computed(() => props.field.warehouse === 'receipt')
// 收货：每行勾选「本次到货」，未勾选的行数量为 0、不能填写、不提交；有采购权限时未收足的行可勾选「余量不再到货」。
const selectable = computed(() => receipt.value && props.field.fields!.some(field => field.key === 'selected'))
const cancellable = computed(() => receipt.value && props.field.fields!.some(field => field.key === 'cancel_remainder'))
const picked = (row: Row) => !selectable.value || row.selected !== false
// 库存页勾选多行领料（与收货的逐行勾选无关）：没有建议数量，提供「全部按可用填入」和「全部清空」。
const stockPicks = computed(() => props.field.warehouse === 'issue' && !batch.value)
const start = computed(() => Math.min(page.value, Math.max(0, Math.ceil(model.value.length / 20) - 1)) * 20)
const indices = computed(() => Array.from({ length: Math.min(20, model.value.length - start.value) }, (_, i) => start.value + i))
const path = (i: number, key: string) => `${props.prefix}.${i}.${key}`
const inputId = (i: number, key: string) => `${uid}-${i}-${key}`
function source(row: Row) {
  const identity = props.field.warehouse === 'receipt' ? 'line' : 'stock'
  return (props.field.initial as Row[]).find(item => item[identity] === row[identity]) || row
}
// 同一张单据的明细必然同项目：项目号放在表头，不在每行重复。
const projectLabel = computed(() => {
  if (receipt.value || batch.value) {
    const first = (props.field.initial as Row[])[0] || {}
    return [first.project_code, first.project_name].filter(Boolean).join(' · ')
  }
  return projectInfo.value ? [projectInfo.value.code, projectInfo.value.name].filter(Boolean).join(' · ') : loading.value ? '读取中…' : '请先选择项目'
})
const decimal = /^\d+(\.\d{1,3})?$/
const sum = (values: unknown[]) => sumQuantities(values.map(value => String(value ?? '').trim()).filter(value => decimal.test(value)))
const total = (key: string) => sum(model.value.map(row => row[key]))
const pickedRows = computed(() => model.value.filter(picked))
const allPicked = computed(() => model.value.length > 0 && pickedRows.value.length === model.value.length)
const summary = computed(() => receipt.value
  ? `${props.context.received_date ? `入库日期 ${props.context.received_date} · ` : ''}已勾选 ${pickedRows.value.length}/${model.value.length} 行，本次合格 ${sum(pickedRows.value.map(row => row.quantity))} / 待收 ${sum(pickedRows.value.map(row => source(row).remaining))}`
  : `本次出库 ${total('quantity')}${batch.value ? ` / BOM 未领 ${total('bom_remaining')}` : ''}，共 ${model.value.length} 行`)
// 数量按千分之一取整数比较，避免浮点误差；格式不对时交给通用校验提示。
function milli(value: unknown) {
  const text = String(value ?? '').trim() || '0'
  if (!decimal.test(text)) return null
  const [whole = '0', fraction = ''] = text.split('.')
  return BigInt(whole) * 1000n + BigInt(fraction.padEnd(3, '0'))
}
// 待收 − 本次合格 − 本次隔离：正数是余量，负数是多送。
function rest(row: Row) {
  const limit = source(row).remaining
  const quantity = milli(row.quantity), pending = milli(row.pending_quantity), remaining = limit == null || limit === '' ? null : milli(limit)
  return quantity == null || pending == null || remaining == null ? null : remaining - quantity - pending
}
const restText = (row: Row) => { const left = rest(row); return left == null ? '' : quantityText(`${left / 1000n}.${String(left % 1000n).padStart(3, '0')}`) }
// 多送不能直接入本单（已批准采购不能改数量）：在数量下方直接说明，提交前即拦下。
function excess(row: Row) {
  if (!receipt.value || !picked(row)) return ''
  const left = rest(row)
  return left != null && left < 0n ? `超过待收 ${quantityText(source(row).remaining)}：多送部分不能入本单，请联系采购「新建采购」补单后再收。` : ''
}
const errorOf = (i: number, key: string) => (key === 'quantity' ? excess(model.value[i]!) : '') || props.issues?.[path(i, key)] || ''
// 取消余量沿用「取消未收余量」规则：本次或原有隔离数量须先处理。
function cancelBlocked(row: Row) {
  if ((milli(row.pending_quantity) ?? 0n) > 0n) return '本次有隔离数量，隔离品处理后才能取消余量。'
  if ((milli(source(row).quarantined) ?? 0n) > 0n) return `本行已有隔离待处理 ${quantityText(source(row).quarantined)}，处理后才能取消余量。`
  return ''
}
function cancelShown(row: Row) {
  const left = rest(row)
  return cancellable.value && picked(row) && (left == null || left > 0n)
}
// 收足、取消勾选或出现隔离数量后，原先勾选的「余量不再到货」自动撤销，不悄悄提交。
watch(() => model.value.map(row => Boolean(row.cancel_remainder) && (!cancelShown(row) || Boolean(cancelBlocked(row)))), stale => {
  stale.forEach((value, i) => { if (value) model.value[i]!.cancel_remainder = false })
})
// 部分到货时提醒逐行核对：合格＋隔离与待收不一致的行高亮；已确认余量不再到货的行不再提醒。
function partial(row: Row) {
  if (!receipt.value || !picked(row) || row.cancel_remainder) return false
  const left = rest(row)
  return left == null || left !== 0n
}
function pick(row: Row, on: boolean) {
  row.selected = on
  // 重新勾选默认按待收填入；取消勾选清零，不再提交本行。
  row.quantity = on ? source(row).remaining : '0'
  row.pending_quantity = '0'
  if (cancellable.value) row.cancel_remainder = false
}
function pickAll(on: boolean) { for (const row of model.value) if (picked(row) !== on) pick(row, on) }
function fill(mode: 'pending' | 'suggested' | 'zero' | 'clear') {
  for (const row of model.value) {
    if (selectable.value && mode === 'pending') row.selected = true
    if (mode === 'zero' || mode === 'clear') row.quantity = mode === 'zero' ? '0' : ''
    else row.quantity = mode === 'pending' ? source(row).remaining : source(row).quantity
    if (receipt.value) row.pending_quantity = '0'
    if (cancellable.value) row.cancel_remainder = false
  }
}
const itemName = (row: Row) => source(row).item_name || String(source(row).material_label || '').split('\n').pop() || ''
// 多送等前端可判定的错误同时写入输入框的校验状态，保存时由对话框统一拦下并定位。
const vValidity: Directive<HTMLInputElement, string> = {
  mounted: (el, binding) => el.setCustomValidity(binding.value || ''),
  updated: (el, binding) => el.setCustomValidity(binding.value || ''),
}
function shown(row: Row, key: string) {
  if (props.field.warehouse === 'issue' && !batch.value) {
    if (key === 'required_quantity') {
      if (props.context.task) return '按售后任务领用'
      if (!projectInfo.value || error.value) return '—'
      const values = demand.value.filter(line => line.item === source(row).item).map(line => String(line.quantity))
      return sumQuantities(values)
    }
  }
  return source(row)[key] || '—'
}
async function loadProject() {
  const current = ++generation
  projectInfo.value = undefined; demand.value = []; error.value = ''; loading.value = false
  if (props.field.warehouse !== 'issue' || batch.value || !props.context.project) return
  loading.value = true
  try {
    const id = props.context.project
    const [project, needs] = await Promise.all([read(`/business/projects/${id}/`), props.context.task ? Promise.resolve({ lines: [] }) : read(`/business/projects/${id}/demand/`)])
    if (current !== generation) return
    projectInfo.value = project; demand.value = needs.lines
  } catch (e) { if (current === generation) error.value = `项目需求读取失败：${message(e)}。可重试，提交时仍会校验实际需求。` }
  finally { if (current === generation) loading.value = false }
}
watch(() => [props.context.project, props.context.task], loadProject, { immediate: true })
onBeforeUnmount(() => { generation++ })
async function focusPath(target: string) {
  const [index, key] = target.slice(props.prefix.length + 1).split('.')
  page.value = Math.floor(Number(index) / 20)
  await nextTick()
  const input = root.value?.querySelector<HTMLElement>(`[id="${inputId(Number(index), key!)}"]`)
  input?.scrollIntoView?.({ block: 'center', inline: 'center' }); input?.focus()
}
defineExpose({ focusPath })
</script>
<template>
  <fieldset ref="root" class="warehouse-lines" :class="{ 'receipt-lines': receipt }">
    <legend>{{ field.label }} · {{ model.length }} 行<template v-if="projectLabel"> · 项目 {{ projectLabel }}</template></legend>
    <p class="form-hint">{{ field.hint }}</p>
    <p v-if="error" role="alert">{{ error }} <button type="button" @click="loadProject">重试</button></p>
    <div class="warehouse-summary" role="status"><strong>{{ summary }}</strong><span v-if="receipt || model.length > 1" class="warehouse-fill"
      ><label v-if="selectable" class="pick-all-mobile"><input type="checkbox" :checked="allPicked" :indeterminate="pickedRows.length > 0 && !allPicked" :disabled="disabled || !model.length" aria-label="全选本次到货明细" @change="pickAll(($event.target as HTMLInputElement).checked)" />全选</label
      ><button v-if="receipt || stockPicks" type="button" :disabled="disabled" @click="fill('pending')">{{ receipt ? '全部按待收填入' : '全部按可用填入' }}</button
      ><button v-else type="button" :disabled="disabled" @click="fill('suggested')">恢复建议数量</button
      ><button type="button" :disabled="disabled" @click="fill(stockPicks ? 'clear' : 'zero')">{{ stockPicks ? '全部清空' : '全部清零' }}</button></span
    ><small v-if="receipt" class="muted">未到货的行取消勾选；合格与隔离合计少于待收的行已高亮，余量继续待收。{{ cancellable ? '供应商不再补货时，勾选该行的「余量不再到货」一并取消余量。' : '供应商不再补货时，请采购在「取消未收余量」中处理。' }}</small></div>
    <p class="table-guide">手机上按每款物料逐项填写。</p>
    <TableScroll :label="field.label"><div data-table-scroll class="warehouse-scroll" tabindex="0" :aria-label="`${field.label}明细表，可左右滚动`">
      <table :aria-label="`${field.label}明细`">
        <thead><tr><th scope="col" class="col-index"><label v-if="selectable" class="line-pick"><input type="checkbox" :checked="allPicked" :indeterminate="pickedRows.length > 0 && !allPicked" :disabled="disabled || !model.length" aria-label="全选本次到货明细" @change="pickAll(($event.target as HTMLInputElement).checked)" /><span>到货</span></label><template v-else>序号</template></th><th v-for="column in columns" :key="column.key" scope="col" :class="`col-${column.key}`">{{ column.key === 'quantity' ? (field.warehouse === 'receipt' ? '本次合格数量' : '本次出库数量') : column.label }}</th></tr></thead>
        <tbody><tr v-for="i in indices" :key="model[i]!.line || model[i]!.stock" :class="{ 'partial-line': partial(model[i]!), 'unpicked-line': !picked(model[i]!), 'excess-line': Boolean(excess(model[i]!)) }">
          <td :data-label="selectable ? '到货' : '序号'" class="line-index"><label v-if="selectable" class="line-pick" :for="inputId(i, 'selected')"><input :id="inputId(i, 'selected')" type="checkbox" :checked="picked(model[i]!)" :disabled="disabled" :aria-label="`本次到货：第 ${i + 1} 行 ${itemName(model[i]!)}`" @change="pick(model[i]!, ($event.target as HTMLInputElement).checked)" /><span>{{ i + 1 }}</span></label><template v-else>{{ i + 1 }}</template></td>
          <td v-for="column in columns" :key="column.key" :data-label="column.key === 'quantity' ? (field.warehouse === 'receipt' ? '本次合格数量' : '本次出库数量') : column.label" :class="[`col-${column.key}`, { 'editable-cell': !column.displayOnly, 'remark-cell': column.key === 'remark', 'material-cell': column.key === 'material_label' }]" :data-field-path="path(i, column.key)">
            <span v-if="column.displayOnly" class="material-value">{{ shown(model[i]!, column.key) }}</span>
            <template v-else>
              <label class="input-label" :for="inputId(i, column.key)">{{ column.label }}</label>
              <textarea v-if="column.key === 'remark'" :id="inputId(i, column.key)" v-model="model[i]![column.key]" :aria-label="column.label" :disabled="disabled || !picked(model[i]!)" :placeholder="column.placeholder" maxlength="500" rows="2" :aria-invalid="Boolean(issues?.[path(i, column.key)])" :aria-describedby="`${inputId(i, column.key)}-help`" @blur="emit('touched', path(i, column.key))" />
              <input v-else :id="inputId(i, column.key)" v-model="model[i]![column.key]" v-validity="column.key === 'quantity' ? excess(model[i]!) : ''" :aria-label="column.label" :disabled="disabled || !picked(model[i]!)" inputmode="decimal" autocomplete="off" :aria-invalid="Boolean(errorOf(i, column.key))" :aria-describedby="`${inputId(i, column.key)}-help`" @blur="emit('touched', path(i, column.key))" />
              <small :id="`${inputId(i, column.key)}-help`" :class="{ 'field-error': errorOf(i, column.key) }">{{ errorOf(i, column.key) || column.hint }}</small>
              <template v-if="column.key === 'quantity' && cancelShown(model[i]!)">
                <label class="remainder-cancel" :class="{ 'is-on': model[i]!.cancel_remainder }"><input v-model="model[i]!.cancel_remainder" type="checkbox" :disabled="disabled || Boolean(cancelBlocked(model[i]!))" :aria-label="`第 ${i + 1} 行余量不再到货`" />余量 {{ restText(model[i]!) }} 不再到货</label>
                <p v-if="cancelBlocked(model[i]!)" class="remainder-note">{{ cancelBlocked(model[i]!) }}</p>
              </template>
            </template>
          </td>
        </tr></tbody>
      </table>
    </div></TableScroll>
    <div v-if="model.length > 20" class="warehouse-pages"><button type="button" :disabled="start === 0" @click="page--">上一页明细</button><span>{{ start + 1 }}–{{ Math.min(start + 20, model.length) }} / {{ model.length }}</span><button type="button" :disabled="start + 20 >= model.length" @click="page++">下一页明细</button></div>
  </fieldset>
</template>
<style scoped>
.warehouse-lines { grid-column: 1 / -1; min-width: 0; margin: 0; border: 1px solid var(--field-line); border-radius: 10px; padding: 14px; }
legend { font-weight: 650; padding: 0 6px; }
.table-guide { color: var(--mute); font-size: 12px; margin: 8px 0; }
.warehouse-scroll { position: relative; overflow: auto; max-width: 100%; max-height: 520px; border: 1px solid var(--field-line); border-radius: 6px; }
table { border-collapse: separate; border-spacing: 0; width: 100%; font-size: 13px; }
/* 列宽按「1366 桌面侧栏约 1040px 内放下全部列」收紧：只读数量列窄、表头可换行，数量与备注输入列不再需要横向滚动。 */
th, td { padding: 8px; min-width: 64px; border-bottom: 1px solid var(--field-line); border-right: 1px solid var(--field-line); text-align: left; vertical-align: top; }
th { position: sticky; top: 0; background: var(--subtle-2); z-index: 1; white-space: nowrap; }
th.col-material_label, th.col-spec_label { white-space: normal; }
th:first-child, td:first-child { min-width: 36px; }
.line-pick { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; font-weight: inherit; }
.line-pick input { width: 16px; height: 16px; min-height: 0; margin: 0; padding: 0; flex: none; accent-color: var(--brand); }
.unpicked-line td:not(.line-index) { color: var(--ink-5); background: var(--subtle); }
.unpicked-line td:not(.line-index) .material-value { opacity: .7; }
.remainder-cancel { display: flex; align-items: flex-start; gap: 6px; margin-top: 6px; font-size: 12px; line-height: 1.4; color: var(--ink-3); cursor: pointer; }
.remainder-cancel input { width: 14px; height: 14px; min-height: 0; margin: 1px 0 0; padding: 0; flex: none; accent-color: var(--risk); }
.remainder-cancel.is-on { color: var(--risk); font-weight: 600; }
.remainder-note { margin: 4px 0 0; font-size: 11px; line-height: 1.4; color: var(--warn); }
.pick-all-mobile { display: none; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; }
.pick-all-mobile input { width: 16px; height: 16px; min-height: 0; margin: 0; accent-color: var(--brand); }
.material-value { display: block; white-space: pre-line; overflow-wrap: anywhere; max-width: 220px; }
.material-cell .material-value { min-width: 110px; }
.col-spec_label .material-value { min-width: 120px; }
.editable-cell { min-width: 96px; }
.remark-cell { min-width: 120px; }
.warehouse-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin: 8px 0; }
.warehouse-fill { display: inline-flex; gap: 6px; }
.warehouse-fill button { min-height: 30px; padding: 4px 12px; font: inherit; font-size: 13px; color: var(--brand-ink); background: var(--paper, #fff); border: 1px solid var(--field-line); border-radius: 5px; cursor: pointer; }
.warehouse-fill button:disabled { cursor: not-allowed; opacity: .6; }
.partial-line td { background: var(--warn-wash); }
.excess-line td { background: var(--risk-wash); }
input, textarea { box-sizing: border-box; width: 100%; min-height: 38px; padding: 8px; font: inherit; border: 1px solid var(--field-line); border-radius: 5px; background: var(--paper, #fff); }
textarea { resize: vertical; }
small { display: block; color: var(--mute); font-size: 11px; line-height: 1.4; margin-top: 4px; }
.field-error { color: var(--risk); }
[aria-invalid='true'] { border-color: var(--risk); }
.input-label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.warehouse-pages { display: flex; gap: 12px; align-items: center; margin-top: 12px; }
@media (max-width: 800px) {
  .warehouse-lines { padding: 10px; }
  .warehouse-scroll { max-height: none; border: none; overflow: visible; }
  table, tbody, tr, td { display: block; width: 100%; box-sizing: border-box; }
  thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
  tr { border: 1px solid var(--field-line); border-radius: 8px; margin-bottom: 12px; overflow: hidden; }
  td { min-width: 0 !important; border-right: 0; padding: 8px 10px; display: grid; grid-template-columns: 100px minmax(0, 1fr); gap: 6px; }
  td::before { content: attr(data-label); color: var(--mute); font-size: 12px; }
  .material-value { min-width: 0 !important; max-width: none; }
  .line-index { background: var(--subtle-2); font-weight: 650; }
  .pick-all-mobile { display: inline-flex; min-height: 36px; padding: 0 4px; }
  .editable-cell { grid-template-columns: minmax(0, 1fr); }
  td:last-child { border-bottom: none; }
  input, textarea { font-size: 16px; }
}
/* 手机（≤600px）：每行一张紧凑卡片——标题为序号＋物料，单元/库位与单位同行，
   需求、BOM 未领、待收/可用三项并排，下面是本次数量（收货时合格与隔离并排）和备注。 */
@media (max-width: 600px) {
  .warehouse-lines { padding: 8px; }
  .warehouse-fill { display: flex; width: 100%; }
  .warehouse-fill button { flex: 1 1 0; min-height: 40px; }
  .table-guide { display: none; }
  tr { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); grid-auto-flow: row dense; margin-bottom: 10px; }
  td { display: block; grid-column: span 6; padding: 6px 10px; border-bottom: 0; }
  td::before { display: block; font-size: 11px; line-height: 1.4; margin-bottom: 2px; }
  .line-index { grid-column: span 1; display: flex; align-items: center; justify-content: center; padding: 8px 0; font-size: 13px; }
  .line-index::before { content: none; }
  .line-pick { min-height: 40px; min-width: 40px; justify-content: center; }
  .line-pick input { width: 20px; height: 20px; }
  .pick-all-mobile { flex: none; min-height: 40px; }
  .pick-all-mobile input { width: 20px; height: 20px; }
  .remainder-cancel { min-height: 32px; align-items: center; font-size: 13px; }
  .remainder-cancel input { width: 18px; height: 18px; margin: 0; }
  .material-cell { grid-column: span 5; background: var(--subtle-2); font-weight: 650; padding: 8px 10px; }
  .material-cell::before { content: none; }
  .material-cell .material-value { white-space: normal; }
  .col-spec_label .material-value { white-space: normal; color: var(--ink-3); }
  .col-assembly_unit, .col-location { grid-column: span 4; }
  .col-unit, .col-required_quantity, .col-bom_remaining, .col-remaining { grid-column: span 2; }
  .receipt-lines .col-quantity, .col-pending_quantity { grid-column: span 3; }
  .editable-cell small:not(.field-error) { display: none; }
  .remark-cell textarea { min-height: 40px; }
  .partial-line .material-cell { background: var(--warn-wash); }
  .excess-line .material-cell { background: var(--risk-wash); }
  .unpicked-line .material-cell { background: var(--subtle); }
}
</style>
