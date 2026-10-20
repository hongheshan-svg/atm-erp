<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { read } from '../api'
import { referenceLabel, referenceSession } from '../catalog'
import { createCommand, createLabel } from '../modules/masterdata'
import { customerOnly } from '../session'
import { message } from '../utils/request'
import type { Command, Row } from '../types'

// ActionDialog → FormFields → RemoteSelect；延迟加载避免同步循环依赖。
const ActionDialog = defineAsyncComponent(() => import('./ActionDialog.vue'))
const props = defineProps<{
  path: string; label: string; query?: string; params?: Row
  accept?: (row: Row) => boolean; disabled?: boolean
}>()
const emit = defineEmits<{ selected: [row: Row]; closed: [] }>()
const resource = computed(() => props.path === '/business/items/' ? 'items' : props.path === '/business/partners/' ? 'partners' : '')
const isSupplier = computed(() => props.params?.kind === 'supplier' || props.label.includes('供应商'))
const noun = computed(() => resource.value === 'items' ? '物料' : isSupplier.value ? '供应商' : '客户')
const allowed = computed(() => Boolean(resource.value && createLabel(resource.value)) && !(resource.value === 'partners' && isSupplier.value && customerOnly()))
const maintainer = computed(() => resource.value === 'items' ? '工程师、采购或项目经理' : isSupplier.value ? '采购或项目经理' : '销售经理、采购或项目经理')
const trigger = ref<HTMLButtonElement>()
const command = ref<Command | null>(null)
const similar = ref<Row[]>([])
const busy = ref(false), error = ref(''), checked = ref(false)
let generation = 0
function reset() {
  generation++
  command.value = null
  similar.value = []
  checked.value = false
  busy.value = false
  error.value = ''
}
watch(() => [props.path, JSON.stringify(props.params ?? {}), referenceSession.value, allowed.value], reset, { flush: 'sync' })
watch(() => props.query, () => {
  if (!command.value) reset()
})
async function showForm() {
  if (!allowed.value || props.disabled) return
  const current = ++generation
  busy.value = true
  error.value = ''
  try {
    const base = await createCommand(resource.value)
    if (current !== generation || !allowed.value) return
    const kind = props.params?.kind || (isSupplier.value ? 'supplier' : 'customer')
    command.value = { ...base, title: `新增${noun.value}`, initial: { ...base.initial, name: props.query?.trim() || '', ...(resource.value === 'partners' ? { kind } : {}) } }
  } catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) busy.value = false }
}
async function start() {
  if (!allowed.value || props.disabled || busy.value) return
  similar.value = []
  error.value = ''
  const query = props.query?.trim()
  if (!query) { await showForm(); return }
  const current = ++generation
  busy.value = true
  try {
    const result = await read(props.path, { ...props.params, is_active: true, search: query, page: 1, page_size: 10 })
    if (current !== generation || !allowed.value) return
    similar.value = (Array.isArray(result) ? result : result.results).filter((row: Row) => !props.accept || props.accept(row))
    checked.value = true
    if (!similar.value.length) await showForm()
  } catch (e) { if (current === generation) error.value = `未能核对相似资料：${message(e)}` }
  finally { if (current === generation) busy.value = false }
}
async function close() {
  command.value = null
  await nextTick()
  // 恢复原输入位置，父表单仍挂载并保留未提交内容。
  if (trigger.value?.isConnected) trigger.value.focus()
  emit('closed')
}
function saved(row: Row) {
  if (allowed.value && row?.id != null) emit('selected', row)
}
function useExisting(row: Row) {
  emit('selected', row)
  checked.value = false
  similar.value = []
}
onBeforeUnmount(() => { generation++ })
</script>
<template>
  <span v-if="resource" class="quick-reference">
    <template v-if="allowed">
      <button ref="trigger" type="button" :disabled="disabled" :aria-disabled="busy || disabled" @click="start">{{ busy ? '正在核对相似资料…' : `新增${noun}` }}</button>
      <span v-if="checked && similar.length" class="quick-similar" role="region" aria-label="相似资料核对">
        <span>已有相似资料，请先核对名称和编号：</span>
        <button v-for="row in similar" :key="row.id" type="button" :disabled="disabled || busy" @click="useExisting(row)">{{ referenceLabel(row).name }} · {{ referenceLabel(row).detail }} · 使用此项</button>
        <button type="button" :disabled="disabled || busy" @click="showForm">仍需新增{{ noun }}</button>
      </span>
    </template>
    <span v-else class="quick-help">需要新增{{ noun }}，请联系{{ maintainer }}维护。</span>
    <span v-if="error" role="alert">{{ error }}</span>
    <Teleport to="body">
      <!-- ElDialog 的焦点栈只关闭最上层；保留其 Escape 处理和未保存确认。 -->
      <ActionDialog v-if="command" :command="command" append-to-body @close="close" @saved="saved" />
    </Teleport>
  </span>
</template>
<style scoped>
.quick-reference, .quick-similar { display: grid; gap: 6px; min-width: 0; }
.quick-reference { border-top: 1px solid var(--field-line); padding-top: 6px; }
.quick-reference button { border: 1px solid var(--field-line); border-radius: 6px; padding: 7px 10px; background: white; color: var(--ink-2); cursor: pointer; font: inherit; text-align: left; overflow-wrap: anywhere; }
.quick-reference button:disabled { opacity: .55; cursor: default; }
.quick-help, .quick-similar, [role='alert'] { font-size: 13px; line-height: 1.6; }
[role='alert'] { color: #b42318; }
</style>
