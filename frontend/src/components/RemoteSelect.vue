<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import { read } from '../api'
import { recentReferences, referenceLabel, referenceSession, rememberReference } from '../catalog'
import { message } from '../utils/request'
import type { Row } from '../types'
import QuickReferenceCreate from './QuickReferenceCreate.vue'

const props = defineProps<{
  path: string; label: string; params?: Row; accept?: (row: Row) => boolean
  describe?: (row: Row) => string; disabled?: boolean; required?: boolean
  inputId?: string; invalid?: boolean; describedBy?: string
  // 页面筛选只在确认候选/清空时变更上下文；业务字段默认输入即清除旧 ID。
  commitOnSelect?: boolean
}>()
const model = defineModel<string | number | undefined>()
const uid = useId()
const input = ref<HTMLInputElement>()
const root = ref<HTMLElement>()
const search = ref(''), rows = ref<Row[]>([]), selected = ref<Row>()
const page = ref(1), more = ref(false), busy = ref(false), error = ref(''), selectedError = ref('')
const opened = ref(false), editing = ref(false), active = ref(-1), selecting = ref(false)
const locked = computed(() => props.disabled || selecting.value)
const recentRows = ref<Row[]>([])
let generation = 0, selectedGeneration = 0
let attemptedPage = 1
let timer: ReturnType<typeof setTimeout> | undefined
const hasValue = (value: unknown) => value !== '' && value != null
const idOf = (row: Row) => String(row.id)
const valid = (row: Row) => (!props.accept || props.accept(row)) &&
  (props.params?.is_active !== true || row.is_active !== false)
function labelOf(row: Row) {
  const parts = referenceLabel(row)
  if (props.describe) {
    const extra = props.describe(row).split(' · ').filter(part => part !== parts.name && part !== row.code)
    parts.detail = [row.code, ...extra].filter(Boolean).join(' · ')
  }
  return parts
}
const textOf = (row: Row) => Object.values(labelOf(row)).filter(Boolean).join(' · ')
const inputValue = computed(() => editing.value ? search.value : selected.value ? textOf(selected.value) : search.value)
const choices = computed(() => {
  const keepSelected = selected.value && !(props.commitOnSelect && editing.value && search.value)
  const candidates = [...(keepSelected ? [selected.value!] : []), ...(!search.value ? recentRows.value : []), ...rows.value]
  return [...new Map(candidates.map(row => [idOf(row), row])).values()]
})
const isRecent = (row: Row) => !search.value && recentRows.value.some(item => idOf(item) === idOf(row))
const activeId = computed(() => active.value >= 0 && choices.value[active.value] ? `${uid}-option-${active.value}` : undefined)
const description = computed(() => [props.describedBy, `${uid}-hint`, error.value || selectedError.value ? `${uid}-error` : ''].filter(Boolean).join(' '))
function cancelSearch() {
  clearTimeout(timer)
  generation++
  busy.value = false
}
async function load(next = 1) {
  clearTimeout(timer)
  const current = ++generation
  attemptedPage = next
  busy.value = true
  error.value = ''
  if (next === 1) { rows.value = []; recentRows.value = []; more.value = false; active.value = -1 }
  try {
    const result = await read(props.path, { ...props.params, search: search.value, page: next, page_size: 20 })
    if (current !== generation) return
    const found: Row[] = (Array.isArray(result) ? result : result.results).filter(valid)
    rows.value = [...new Map([...(next > 1 ? rows.value : []), ...found].map(row => [idOf(row), row])).values()]
    recentRows.value = recentReferences(props.path, rows.value)
    page.value = next
    more.value = Boolean(result.next)
  } catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) busy.value = false }
}
function requestPage(next: number) {
  if (busy.value || locked.value) return
  // 分页按钮进入 loading 或末页消失前先归还焦点，避免浏览器 focusout 收起候选。
  input.value?.focus()
  void load(next)
}
async function returnFromCreate() {
  await nextTick()
  if (!locked.value) input.value?.focus()
}
function open() {
  if (locked.value || opened.value) return
  opened.value = true
  if (selected.value) search.value = ''
  editing.value = Boolean(search.value && !selected.value)
  active.value = -1
  void load()
}
function type(event: Event) {
  if (locked.value) return
  if (!props.commitOnSelect) {
    selectedGeneration++
    selected.value = undefined
    selectedError.value = ''
    model.value = ''
  }
  search.value = (event.target as HTMLInputElement).value
  opened.value = true
  editing.value = true
  cancelSearch() // 输入一变就作废旧响应，不能等防抖结束才防竞态。
  rows.value = []; recentRows.value = []; more.value = false; error.value = ''; active.value = -1
  busy.value = true
  timer = setTimeout(() => { void load() }, 250)
}
function close() {
  opened.value = false
  active.value = -1
  if (selected.value || props.commitOnSelect) { editing.value = false; search.value = '' }
}
function leave(event: FocusEvent) {
  if (!root.value?.contains(event.relatedTarget as Node | null)) close()
}
function select(row: Row) {
  if (props.disabled || !valid(row)) return
  selected.value = row
  selectedError.value = ''
  model.value = row.id
  rememberReference(props.path, row.id)
  editing.value = false
  search.value = ''
  close()
  void nextTick(() => {
    // 父表单可能等待离开确认，甚至拒绝本次修改；显示以父级实际接受的值为准。
    if (String(model.value) !== idOf(row)) {
      selecting.value = false
      void resolveSelected()
    }
  })
}
function clear() {
  if (locked.value) return
  selectedGeneration++
  model.value = ''
  selected.value = undefined
  selectedError.value = ''
  search.value = ''
  editing.value = false
  if (props.commitOnSelect) {
    close()
    void nextTick(() => { if (hasValue(model.value)) void resolveSelected() })
    return
  }
  input.value?.focus()
  opened.value = true
  void load()
}
async function move(index: number) {
  active.value = Math.max(0, Math.min(index, choices.value.length - 1))
  await nextTick()
  root.value?.querySelector<HTMLElement>(`[id="${activeId.value}"]`)?.scrollIntoView?.({ block: 'nearest' })
}
function keydown(event: KeyboardEvent) {
  if (locked.value || event.isComposing) return
  if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
    event.preventDefault()
    if (!opened.value) { open(); return }
    if (choices.value.length) void move(active.value < 0 ? event.key === 'ArrowDown' ? 0 : choices.value.length - 1 : active.value + (event.key === 'ArrowDown' ? 1 : -1))
  } else if (opened.value && ['Home', 'End'].includes(event.key)) {
    event.preventDefault()
    if (choices.value.length) void move(event.key === 'Home' ? 0 : choices.value.length - 1)
  } else if (opened.value && event.key === 'Enter') {
    event.preventDefault()
    const row = choices.value[active.value]
    if (row && !busy.value) select(row)
  } else if (opened.value && event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    close()
  } else if (event.key === 'Tab') close()
}
async function resolveSelected() {
  const current = ++selectedGeneration
  selectedError.value = ''
  if (!hasValue(model.value)) { selected.value = undefined; return }
  const found = rows.value.find(row => idOf(row) === String(model.value))
  if (found) { selected.value = found; return }
  if (selected.value && idOf(selected.value) === String(model.value) && valid(selected.value)) return
  selected.value = undefined
  try {
    const result = await read(`${props.path}${encodeURIComponent(String(model.value))}/`, props.params)
    if (current !== selectedGeneration) return
    if (!valid(result)) throw new Error('原选项已不在可选范围，请重新选择。')
    selected.value = result
  } catch (e) { if (current === selectedGeneration) selectedError.value = message(e) }
}
async function created(row: Row) {
  const current = ++selectedGeneration
  selecting.value = true
  selectedError.value = ''
  try {
    // 新建沿用原 API；选回父表单前，仍按当前会话、参数与调用方筛选重新读取。
    const result = await read(`${props.path}${encodeURIComponent(String(row.id))}/`, props.params)
    if (current !== selectedGeneration) return
    if (!valid(result)) throw new Error('已保存的资料不符合当前选择范围，请检查类型或启用状态。')
    select(result)
    await nextTick()
    input.value?.focus()
    close()
  } catch (e) { if (current === selectedGeneration) selectedError.value = `资料已保存，但未能选回：${message(e)}` }
  finally { if (current === selectedGeneration) selecting.value = false }
}
// 父组件重绘会新建同值 params；逐项比较上下文，避免填写其他字段时清空已选资料。
watch([() => props.path, () => JSON.stringify(props.params ?? {}), () => referenceSession.value], (_now, before) => {
  cancelSearch()
  selectedGeneration++
  selected.value = undefined
  selectedError.value = ''
  selecting.value = false
  rows.value = []; recentRows.value = []; search.value = ''; editing.value = false
  // 切换账号不能把上一位使用者的选中记录带入新会话。
  if (before.length && before[2] !== referenceSession.value) { model.value = ''; close() }
  void load()
  void resolveSelected()
}, { immediate: true, flush: 'sync' })
watch(() => model.value, () => { selecting.value = false; void resolveSelected() })
watch(() => props.accept, () => {
  rows.value = rows.value.filter(valid)
  recentRows.value = recentRows.value.filter(valid)
  if (selected.value && !valid(selected.value)) {
    selected.value = undefined
    selectedError.value = '原选项已不在可选范围，请重新选择。'
  }
})
watch(() => props.disabled, value => { if (value) close() })
watch([input, inputValue, selected, model, selectedError], () => {
  input.value?.setCustomValidity(hasValue(model.value) && !selected.value
    ? selectedError.value || '正在核对已选资料，请稍候。'
    : !selected.value && search.value ? '请从候选列表选择一项，或清空输入。' : '')
}, { flush: 'post' })
onBeforeUnmount(() => { cancelSearch(); selectedGeneration++ })
</script>
<template>
  <span ref="root" class="remote-select" @focusout="leave">
    <span class="remote-input">
      <input ref="input" :id="inputId || `${uid}-input`" role="combobox" :value="inputValue" :aria-label="label"
        aria-autocomplete="list" aria-haspopup="listbox" :aria-expanded="opened" :aria-controls="`${uid}-list`"
        :aria-activedescendant="opened ? activeId : undefined" :aria-invalid="invalid || Boolean(selectedError) || undefined"
        :aria-describedby="description" :required="required" :disabled="locked" autocomplete="off"
        :placeholder="`输入${label}名称或编号`" @input="type" @focus="open" @click="open" @keydown="keydown" />
      <button v-if="hasValue(model) || search" type="button" class="remote-clear" :aria-label="`清空${label}`" :disabled="locked" @click="clear">×</button>
      <button type="button" class="remote-toggle" :aria-label="`展开${label}选项`" :disabled="locked" tabindex="-1" @mousedown.prevent @click="opened ? close() : (input?.focus(), open())">⌄</button>
    </span>
    <span :id="`${uid}-hint`" class="remote-hint">{{ selecting ? '正在核对新建资料…' : '输入即搜索，↑↓ 移动，回车选择' }}</span>
    <span v-if="error || selectedError" :id="`${uid}-error`" class="remote-error" role="alert">{{ [selectedError, error].filter(Boolean).join('；') }}</span>
    <span v-show="opened" class="remote-popup">
      <span v-if="busy" role="status" class="remote-feedback">正在搜索…</span>
      <span v-else-if="!error && !rows.length" role="status" class="remote-feedback">无匹配结果{{ more ? '，可继续加载更多' : '' }}</span>
      <ul :id="`${uid}-list`" role="listbox" :aria-label="`${label}候选`" :aria-busy="busy">
        <!-- 阻止外层 label 将候选点击转发给输入框，避免选中后立即重新展开。 -->
        <li v-for="(row, index) in choices" :id="`${uid}-option-${index}`" :key="row.id" role="option" :data-value="row.id"
          :aria-selected="String(model) === String(row.id)" :class="{ 'is-active': index === active }"
          @mousedown.prevent @click.prevent="select(row)" @mousemove="active = index">
          <span class="remote-name">{{ labelOf(row).name }}<small v-if="String(model) === String(row.id)">已选</small><small v-else-if="isRecent(row)">最近使用</small></span>
          <span v-if="labelOf(row).detail" class="remote-detail">{{ labelOf(row).detail }}</span>
        </li>
      </ul>
      <button v-if="error" type="button" :disabled="busy" @mousedown.prevent @click="requestPage(attemptedPage)">重新加载</button>
      <button v-else-if="more" type="button" :disabled="busy" @mousedown.prevent @click="requestPage(page + 1)">继续加载更多</button>
      <QuickReferenceCreate :path="path" :label="label" :query="search" :params="params" :accept="accept" :disabled="disabled || busy || selecting" @selected="created" @closed="returnFromCreate" />
    </span>
  </span>
</template>
<style scoped>
.remote-select { display: grid; position: relative; gap: 5px; min-width: 0; }
.remote-select, :global(.project-filter) .remote-select { grid-template-columns: minmax(0, 1fr); align-items: stretch; }
.remote-input { display: flex; position: relative; min-width: 0; }
.remote-input input { width: 100%; min-width: 0; padding-right: 64px; }
.remote-select button { cursor: pointer; border: 1px solid var(--field-line); border-radius: 6px; background: white; color: var(--ink-2); padding: 7px 10px; font: inherit; }
.remote-select button:disabled { cursor: default; opacity: .55; }
.remote-input button { position: absolute; right: 0; top: 0; bottom: 0; border: 0; background: transparent; padding: 0 9px; }
.remote-input .remote-clear { right: 27px; }
.remote-hint, .remote-detail { font-size: 12px; color: var(--ink-2); line-height: 1.5; }
.remote-error { font-size: 13px; color: #b42318; }
.remote-popup { display: grid; gap: 5px; padding: 6px; border: 1px solid var(--field-line); border-radius: 8px; background: white; box-shadow: 0 4px 12px #00000012; }
.remote-popup ul { list-style: none; margin: 0; padding: 0; max-height: 240px; overflow-y: auto; }
.remote-popup li { padding: 8px; cursor: pointer; border-radius: 5px; display: grid; gap: 3px; overflow-wrap: anywhere; }
.remote-popup li.is-active, .remote-popup li:hover { background: #eaf3ff; outline: 1px solid #b3d3ff; outline-offset: -1px; }
.remote-popup li[aria-selected='true'] .remote-name { font-weight: 600; }
.remote-name { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.remote-name small { font-size: 12px; color: var(--ink-2); }
.remote-feedback { padding: 6px; font-size: 13px; }
</style>
