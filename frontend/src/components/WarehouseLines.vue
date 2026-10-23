<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import { read } from '../api'
import { sumQuantities } from '../modules/warehouse-lines'
import { message } from '../utils/request'
import type { Field, Row } from '../types'
const props = defineProps<{ field: Field; context: Row; disabled?: boolean; issues?: Record<string, string>; prefix: string }>()
const model = defineModel<Row[]>({ required: true })
const emit = defineEmits<{ touched: [path: string] }>()
const uid = useId(), root = ref<HTMLElement>(), page = ref(0)
const projectInfo = ref<Row>(), demand = ref<Row[]>([]), error = ref(''), loading = ref(false)
let generation = 0
const columns = computed(() => props.field.fields!.filter(field => !field.hidden))
const start = computed(() => Math.min(page.value, Math.max(0, Math.ceil(model.value.length / 20) - 1)) * 20)
const indices = computed(() => Array.from({ length: Math.min(20, model.value.length - start.value) }, (_, i) => start.value + i))
const path = (i: number, key: string) => `${props.prefix}.${i}.${key}`
const inputId = (i: number, key: string) => `${uid}-${i}-${key}`
function source(row: Row) {
  const identity = props.field.warehouse === 'receipt' ? 'line' : 'stock'
  return (props.field.initial as Row[]).find(item => item[identity] === row[identity]) || row
}
function shown(row: Row, key: string) {
  if (props.field.warehouse === 'issue') {
    if (key === 'project_code') return projectInfo.value?.code || (loading.value ? '读取中…' : '请先选择项目')
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
  if (props.field.warehouse !== 'issue' || !props.context.project) return
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
  <fieldset ref="root" class="warehouse-lines">
    <legend>{{ field.label }} · {{ model.length }} 行</legend>
    <p class="form-hint">{{ field.hint }}</p>
    <p v-if="error" role="alert">{{ error }} <button type="button" @click="loadProject">重试</button></p>
    <p class="table-guide">电脑上左右滚动可查看全部列；手机上按每款物料逐项填写。</p>
    <div class="warehouse-scroll" tabindex="0" :aria-label="`${field.label}明细表，可左右滚动`">
      <table :aria-label="`${field.label}明细`">
        <thead><tr><th scope="col">序号</th><th v-for="column in columns" :key="column.key" scope="col">{{ column.key === 'quantity' ? (field.warehouse === 'receipt' ? '本次合格数量' : '本次出库数量') : column.label }}</th></tr></thead>
        <tbody><tr v-for="i in indices" :key="model[i]!.line || model[i]!.stock">
          <td data-label="序号" class="line-index">{{ i + 1 }}</td>
          <td v-for="column in columns" :key="column.key" :data-label="column.key === 'quantity' ? (field.warehouse === 'receipt' ? '本次合格数量' : '本次出库数量') : column.label" :class="{ 'editable-cell': !column.displayOnly, 'remark-cell': column.key === 'remark' }" :data-field-path="path(i, column.key)">
            <span v-if="column.displayOnly" class="material-value">{{ shown(model[i]!, column.key) }}</span>
            <template v-else>
              <label class="input-label" :for="inputId(i, column.key)">{{ column.label }}</label>
              <textarea v-if="column.key === 'remark'" :id="inputId(i, column.key)" v-model="model[i]![column.key]" :aria-label="column.label" :disabled="disabled" :placeholder="column.placeholder" maxlength="500" rows="2" :aria-invalid="Boolean(issues?.[path(i, column.key)])" :aria-describedby="`${inputId(i, column.key)}-help`" @blur="emit('touched', path(i, column.key))" />
              <input v-else :id="inputId(i, column.key)" v-model="model[i]![column.key]" :aria-label="column.label" :disabled="disabled" inputmode="decimal" autocomplete="off" :aria-invalid="Boolean(issues?.[path(i, column.key)])" :aria-describedby="`${inputId(i, column.key)}-help`" @blur="emit('touched', path(i, column.key))" />
              <small :id="`${inputId(i, column.key)}-help`" :class="{ 'field-error': issues?.[path(i, column.key)] }">{{ issues?.[path(i, column.key)] || column.hint }}</small>
            </template>
          </td>
        </tr></tbody>
      </table>
    </div>
    <div v-if="model.length > 20" class="warehouse-pages"><button type="button" :disabled="start === 0" @click="page--">上一页明细</button><span>{{ start + 1 }}–{{ Math.min(start + 20, model.length) }} / {{ model.length }}</span><button type="button" :disabled="start + 20 >= model.length" @click="page++">下一页明细</button></div>
  </fieldset>
</template>
<style scoped>
.warehouse-lines { grid-column: 1 / -1; min-width: 0; margin: 0; border: 1px solid var(--field-line); border-radius: 10px; padding: 14px; }
legend { font-weight: 650; padding: 0 6px; }
.table-guide { color: var(--mute); font-size: 12px; margin: 8px 0; }
.warehouse-scroll { position: relative; overflow: auto; max-width: 100%; max-height: 520px; border: 1px solid var(--field-line); border-radius: 6px; }
table { border-collapse: separate; border-spacing: 0; width: 100%; font-size: 13px; }
th, td { padding: 10px; min-width: 92px; border-bottom: 1px solid var(--field-line); border-right: 1px solid var(--field-line); text-align: left; vertical-align: top; }
th { position: sticky; top: 0; background: var(--subtle-2); z-index: 1; white-space: nowrap; }
th:first-child, td:first-child { min-width: 44px; }
.material-value { display: block; white-space: pre-line; overflow-wrap: anywhere; min-width: 90px; max-width: 260px; }
td:nth-child(3) .material-value, td:nth-child(4) .material-value { min-width: 120px; }
.editable-cell { min-width: 145px; }
.remark-cell { min-width: 240px; }
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
  .editable-cell { grid-template-columns: minmax(0, 1fr); }
  td:last-child { border-bottom: none; }
  input, textarea { font-size: 16px; }
}
</style>
