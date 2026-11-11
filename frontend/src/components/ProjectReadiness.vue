<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { read } from '../api'
import { readinessPath } from '../modules/projects'
import { message } from '../utils/request'
import type { Row } from '../types'

// 项目推进检查：与服务端发货、验收、结项共用同一组检查，页头直接说明下一步还差什么。
type Check = { key: string; ok: boolean; label: string; detail: string; blocking?: boolean; target?: Row }
const props = defineProps<{ project: Row; revision: number }>()
const emit = defineEmits<{ act: [name: string] }>()
const result = ref<Row | null>(null)
const error = ref(''), open = ref(false)
const listId = useId()
watch(() => [props.project.id, props.project.status, props.revision], async (_, __, onCleanup) => {
  let current = true
  onCleanup(() => { current = false })
  try {
    const value = await read(`/business/projects/${props.project.id}/readiness/`)
    if (current) { result.value = value && typeof value === 'object' ? value : null; error.value = '' }
  } catch (e) {
    if (current) { result.value = null; error.value = message(e) }
  }
}, { immediate: true })
const checks = (key: string): Check[] => (Array.isArray(result.value?.[key]) ? result.value![key] : []).filter((item: unknown) => item && typeof item === 'object')
const groups = computed(() => [
  { key: 'ship', title: '发货', action: '发货', button: '登记发货', items: checks('ship') },
  { key: 'accept', title: '验收', action: '', button: '', items: checks('accept') },
  { key: 'close', title: '结项', action: '结项', button: '结项', items: checks('close') },
].filter(group => group.items.length).map(group => ({
  ...group,
  missing: group.items.filter(item => item.blocking !== false && !item.ok),
  warnings: group.items.filter(item => item.blocking === false && !item.ok),
})))
const path = (item: Check) => readinessPath(props.project.id, item.target)
</script>

<template>
  <div v-if="groups.length || error" class="project-readiness" aria-label="项目推进检查">
    <span class="readiness-title">下一步</span>
    <span v-if="error" class="readiness-error" role="alert">推进检查未加载：{{ error }}</span>
    <span v-for="group in groups" :key="group.key" class="readiness-group" :data-group="group.key">
      <template v-if="group.missing.length">
        <strong class="readiness-blocked">{{ group.title }}前还差</strong>
        <router-link v-for="item in group.missing" :key="item.key" class="readiness-chip" :to="path(item)" :title="item.detail">{{ item.label }} · {{ item.detail }}</router-link>
      </template>
      <template v-else-if="group.action">
        <strong class="readiness-ready">{{ group.title }}条件已满足</strong>
        <el-button type="primary" size="small" @click="emit('act', group.action)">{{ group.button }}</el-button>
      </template>
      <router-link v-for="item in group.warnings" :key="item.key" class="readiness-chip readiness-warning" :to="path(item)" :title="item.detail">{{ item.label }} · {{ item.detail }}</router-link>
    </span>
    <button v-if="groups.length" type="button" class="readiness-toggle" :aria-expanded="open" :aria-controls="listId" @click="open = !open">{{ open ? '收起检查' : '全部检查' }}</button>
    <ul v-if="groups.length" v-show="open" :id="listId" class="readiness-list">
      <li v-for="item in groups.flatMap(group => group.items.map(check => ({ ...check, group: group.title })))" :key="`${item.group}-${item.key}`" :class="item.ok ? 'readiness-ok' : item.blocking === false ? 'readiness-note' : 'readiness-missing'">
        <span class="readiness-mark"><span aria-hidden="true">{{ item.ok ? '✓' : item.blocking === false ? '!' : '✗' }}</span><span class="visually-hidden">{{ item.ok ? '已满足' : item.blocking === false ? '提示' : '未满足' }}</span></span>
        <small>{{ item.group }}</small><strong>{{ item.label }}</strong><span>{{ item.detail }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.project-readiness { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; min-width: 0; font-size: 13px; }
.readiness-title { color: var(--mute); font-size: 12px; }
/* 分组只用于语义，芯片与「下一步」同一行连续排布、按需换行。 */
.readiness-group { display: contents; }
.readiness-blocked { color: var(--warn); font-weight: 600; }
.readiness-ready { color: var(--ok); font-weight: 600; }
.readiness-chip { display: inline-block; max-width: 230px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding: 2px 10px; border: 1px solid var(--warn-line); border-radius: 999px; background: var(--warn-wash); color: var(--warn); font-size: 12px; line-height: 18px; }
.readiness-chip:hover { text-decoration: underline; }
.readiness-warning { border-color: var(--risk); background: var(--risk-wash); color: var(--risk); }
.readiness-error { color: var(--risk); font-size: 12px; }
.readiness-toggle { border: 0; background: transparent; color: var(--brand); cursor: pointer; font: inherit; font-size: 12px; padding: 2px 0; }
.readiness-toggle:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; border-radius: 3px; }
.readiness-list { flex-basis: 100%; list-style: none; margin: 4px 0 0; padding: 8px 12px; border: 1px solid var(--surface-border); border-radius: 8px; background: var(--subtle-2, #f8fafc); display: grid; gap: 4px; }
.readiness-list li { display: grid; grid-template-columns: 16px 36px minmax(120px, auto) 1fr; align-items: baseline; gap: 8px; font-size: 12px; }
.readiness-list small { color: var(--mute); }
.readiness-ok .readiness-mark { color: var(--ok); }
.readiness-missing .readiness-mark { color: var(--risk); font-weight: 700; }
.readiness-note .readiness-mark { color: var(--warn); font-weight: 700; }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
@media (max-width: 600px) { .readiness-chip { max-width: 100%; } .readiness-list li { grid-template-columns: 16px 36px 1fr; } .readiness-list li > span:last-child { grid-column: 3; } }
</style>
