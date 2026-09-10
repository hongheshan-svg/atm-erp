<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { read } from '../api'
import { options } from '../catalog'
import { message } from '../utils/request'
import type { Row } from '../types'
const props = defineProps<{ path: string; label: string; params?: Row; accept?: (row: Row) => boolean; disabled?: boolean; required?: boolean }>()
const model = defineModel<string | number | undefined>()
const search = ref(''), rows = ref<Row[]>([]), selected = ref<Row>(), page = ref(1), more = ref(false), busy = ref(false), error = ref('')
let generation = 0
let selectedGeneration = 0
const choices = computed(() => options(selected.value && !rows.value.some(r => String(r.id) === String(selected.value?.id)) ? [selected.value, ...rows.value] : rows.value))
async function load(next = 1) {
  const current = ++generation
  busy.value = true; error.value = ''
  try {
    const result = await read(props.path, { ...props.params, search: search.value, page: next, page_size: 20 })
    if (current !== generation) return
    const found = Array.isArray(result) ? result : result.results
    rows.value = found.filter((r: Row) => !props.accept || props.accept(r))
    page.value = next; more.value = Boolean(result.next)
  } catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) busy.value = false }
}
watch(() => [props.path, JSON.stringify(props.params || {})], () => { void load() }, { immediate: true })
watch(() => [model.value, props.path], async () => {
  const current = ++selectedGeneration
  selected.value = undefined
  if (!model.value) return
  const found = rows.value.find(r => String(r.id) === String(model.value))
  if (found) { selected.value = found; return }
  try {
    const result = await read(`${props.path}${model.value}/`)
    if (current === selectedGeneration && (!props.accept || props.accept(result))) selected.value = result
  } catch (e) { if (current === selectedGeneration) error.value = message(e) }
}, { immediate: true })
onBeforeUnmount(() => { generation++; selectedGeneration++ })
</script>
<template>
  <span class="remote-select">
    <span><input v-model="search" aria-label="搜索选项" :placeholder="`搜索${label}名称或编号`" :disabled="disabled" @keydown.enter.prevent="load()" /><button type="button" :disabled="disabled || busy" @click="load()">搜索</button></span>
    <select v-model="model" :aria-label="label" :required="required" :disabled="disabled"><option value="">请选择</option><option v-for="option in choices" :key="option.value" :value="option.value">{{ option.label }}</option></select>
    <span v-if="page > 1 || more"><button type="button" :disabled="busy || page === 1" @click="load(page - 1)">上一页</button>第 {{ page }} 页<button type="button" :disabled="busy || !more" @click="load(page + 1)">下一页</button></span>
    <small v-if="busy" role="status">加载中…</small><small v-if="error" role="alert">{{ error }}</small>
  </span>
</template>
<style scoped>
.remote-select { display: grid; gap: 6px; min-width: 0; }
.remote-select > span { display: flex; align-items: center; gap: 6px; min-width: 0; }
.remote-select input { flex: 1; width: 0; min-width: 0; }
.remote-select button { flex-shrink: 0; white-space: nowrap; border: 1px solid #d8e1ee; border-radius: 6px; padding: 7px 10px; background: white; color: #3b526e; cursor: pointer; }
.remote-select button:disabled { color: #9aa6b5; cursor: default; }
</style>
