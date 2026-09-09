<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import BOMDemand from '../components/BOMDemand.vue'
</script>
<template>
  <ModulePage
    title="BOM"
    project-filter
    require-project
    v-slot="{ revision, projectId, refresh, projects }"
    ><BOMDemand
      v-if="projectId"
      :project-id="projectId"
      :status="projects.find((p) => p.id === projectId)?.status"
      :revision="revision"
      @changed="refresh"
    />
    <p v-else class="empty muted">选择项目，查看 BOM 与缺料需求。</p></ModulePage
  >
</template>
