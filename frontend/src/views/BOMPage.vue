<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import BOMDemand from '../components/BOMDemand.vue'
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { read } from '../api'
import { user } from '../session'
import { sessionStore } from '../utils/storage'
import type { Row } from '../types'
const route = useRoute()
const currentProject = ref<Row | null>(null)
// 没选项目时不只给一个空输入框：直接列出还在推进的项目（需求中到交付中，按交期），点一下就进 BOM。
const openStatuses = new Set(['draft', 'quoted', 'active', 'delivering'])
const recent = ref<Row[]>([]), recentLoaded = ref(false)
onMounted(async () => {
  try { recent.value = ((await read('/business/projects/', { ordering: 'due_date', page_size: 40 })).results || []).filter((row: Row) => openStatuses.has(row.status)).slice(0, 9) }
  catch { recent.value = [] }
  finally { recentLoaded.value = true }
})
onMounted(async () => {
  const id = Number(sessionStore.get(`current-project-${user.value?.id}`))
  if (!Number.isSafeInteger(id) || id <= 0) return
  try { currentProject.value = await read(`/business/projects/${id}/`) }
  catch { sessionStore.remove(`current-project-${user.value?.id}`) }
})
</script>
<template>
  <ModulePage
    :key="String(route.query.project || '')"
    title="BOM"
    project-filter
    require-project
    compact
    v-slot="{ revision, projectId, refresh, projects }"
    ><p v-if="currentProject && projectId !== currentProject.id"><router-link :to="{ path: '/bom', query: { project: currentProject.id } }">继续查看当前项目：{{ currentProject.name }}</router-link></p>
    <BOMDemand
      v-if="projectId"
      :project-id="projectId"
      :status="projects.find((p) => p.id === projectId)?.status"
      :can-edit-bom="projects.find((p) => p.id === projectId)?.can_edit_bom"
      :can-edit-purchase="projects.find((p) => p.id === projectId)?.can_edit_purchase"
      :initial-view="route.query.view === 'purchase' ? 'purchase' : undefined"
      :revision="revision"
      @changed="refresh"
    />
    <section v-else class="panel bom-landing" aria-labelledby="bom-landing-heading">
      <h2 id="bom-landing-heading">选择项目查看 BOM</h2>
      <ul v-if="recent.length"><li v-for="item in recent" :key="item.id"><router-link :to="{ path: '/bom', query: { project: item.id } }"><strong>{{ item.name }}</strong><span>{{ [item.code, item.customer_name, item.due_date ? `交期 ${item.due_date}` : ''].filter(Boolean).join(' · ') }}</span></router-link></li></ul>
      <p v-else-if="recentLoaded" class="muted">没有在推进中的项目。可在上方输入项目名称或编号查找；找不到参与的项目时，请联系项目经理核对项目成员。</p>
      <p v-if="recent.length" class="muted">按交期列出在推进中的项目；已验收、已结项的项目请在上方输入名称或编号查找。</p>
    </section></ModulePage
  >
</template>
<style scoped>
.bom-landing h2 { margin: 0 0 12px; font-size: 16px; }
.bom-landing ul { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
.bom-landing a { display: flex; flex-direction: column; gap: 4px; padding: 12px 14px; border: 1px solid var(--surface-border); border-radius: var(--r-ctl); color: inherit; }
.bom-landing a:hover { border-color: var(--brand-line); background: var(--brand-wash-2); }
.bom-landing strong { color: var(--brand-ink); font-size: 14px; }
.bom-landing span { color: var(--ink-4); font-size: 12px; }
.bom-landing p { margin: 12px 0 0; font-size: 13px; }
</style>
