<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
</script>
<template>
  <ModulePage title="库存" project-filter v-slot="{ revision, projectId, refresh }"
    ><ResourcePanel
      resource="stocks"
      title="现有库存"
      :revision="revision"
      @changed="refresh" /><ResourcePanel
      resource="moves"
      title="库存流水"
      :params="{ project: projectId }"
      :revision="revision"
      @changed="refresh"
  /></ModulePage>
</template>
