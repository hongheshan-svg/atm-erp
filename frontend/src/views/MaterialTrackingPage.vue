<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import MaterialTrackingTable from '../components/MaterialTrackingTable.vue'
import { useRoute } from 'vue-router'
const route = useRoute()
</script>
<template>
  <ModulePage :key="String(route.query.project || '')" title="物料跟踪" project-filter compact v-slot="{ projectId }">
    <MaterialTrackingTable :project-id="projectId" />
  </ModulePage>
</template>
