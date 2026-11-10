<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
</script>
<template>
  <ModulePage title="采购" project-filter v-slot="{ revision, projectId, refresh }"
    ><ResourcePanel resource="purchases" title="采购订单" :params="{ project: projectId }" :project-id="projectId" :revision="revision" @changed="refresh"
  /></ModulePage>
</template>
