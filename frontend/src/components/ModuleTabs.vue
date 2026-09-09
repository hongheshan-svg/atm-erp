<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TabsInstance } from 'element-plus'
import { useRoute, useRouter, type LocationQueryRaw } from 'vue-router'
import { user } from '../session'
import { revealActiveTab } from '../utils/tabs'

const props = defineProps<{
  tabs: { key: string; label: string; resources?: string[] }[]
  storageKey: string
  parentTab?: string
}>()
const route = useRoute()
const router = useRouter()
const tabsRef = ref<TabsInstance>()
const memoryKey = computed(() => `module-tab-${user.value?.id}-${props.storageKey}`)
const valid = (value: unknown) => props.tabs.some(item => item.key === value)
function selected() {
  const section = String(route.query.section || '')
  if (valid(section)) return section
  const resource = String(route.query.resource || '')
  const target = props.tabs.find(item => item.resources?.includes(resource))
  if (target) return target.key
  const saved = sessionStorage.getItem(memoryKey.value)
  return saved && valid(saved) ? saved : props.tabs[0]?.key || ''
}
const active = ref(selected())
async function reveal() {
  await revealActiveTab(() => tabsRef.value)
}
function choose(value: string | number) {
  const key = String(value)
  if (!valid(key)) return
  active.value = key
  sessionStorage.setItem(memoryKey.value, key)
  const query: LocationQueryRaw = { ...route.query, ...(props.parentTab ? { tab: props.parentTab } : {}), section: key }
  // A user-selected module must not reopen a previous workbench action.
  delete query.resource
  delete query.focus
  void router.replace({ query })
  void reveal()
}
function activateByKeyboard(event: KeyboardEvent) {
  if (!['Enter', ' '].includes(event.key)) return
  const target = (event.target as HTMLElement).closest<HTMLElement>('[role="tab"]')
  if (!target) return
  event.preventDefault()
  event.stopPropagation()
  target.click()
}
watch(() => [route.query.tab, route.query.section, route.query.resource, props.tabs.map(item => item.key).join(','), memoryKey.value], () => {
  // Parent navigation owns query.tab; wait for it before normalizing the child.
  if (props.parentTab && route.query.tab && route.query.tab !== props.parentTab) return
  active.value = selected()
  if (active.value) {
    sessionStorage.setItem(memoryKey.value, active.value)
    if (route.query.section !== active.value) void router.replace({ query: { ...route.query, section: active.value } })
  }
  void reveal()
}, { immediate: true })
</script>

<template>
  <el-tabs ref="tabsRef" class="module-tabs scrollable-tabs" :model-value="active" @tab-change="choose" @keydown="activateByKeyboard">
    <el-tab-pane v-for="item in tabs" :key="item.key" :name="item.key" :label="item.label" lazy>
      <slot :name="item.key" />
    </el-tab-pane>
  </el-tabs>
</template>

<style scoped>
.module-tabs { min-width: 0; }
.module-tabs :deep(.el-tabs__header) { margin-bottom: 20px; }
.module-tabs :deep(.el-tabs__item:focus-visible) { outline: 2px solid #245cca; outline-offset: -3px; border-radius: 4px; }
</style>
