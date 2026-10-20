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
    v-slot="{ revision, projectId, refresh, projects }"
    ><p class="muted">物料清单（BOM） · 编制项目用料，跟进缺料。</p>
    <p v-if="currentProject && projectId !== currentProject.id"><router-link :to="{ path: '/bom', query: { project: currentProject.id } }">继续查看当前项目：{{ currentProject.name }}</router-link></p>
    <BOMDemand
      v-if="projectId"
      :project-id="projectId"
      :status="projects.find((p) => p.id === projectId)?.status"
      :can-edit-bom="projects.find((p) => p.id === projectId)?.can_edit_bom"
      :revision="revision"
      @changed="refresh"
    />
    <p v-else class="empty muted">请先选择项目，查看物料清单与缺料需求。找不到参与的项目时，请联系项目经理核对项目成员。</p></ModulePage
  >
</template>
