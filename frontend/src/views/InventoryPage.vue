<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
import { useRoute } from 'vue-router'
const route = useRoute()
const tabs = [{ key: 'stocks', label: '现有库存' }, { key: 'moves', label: '库存流水' }]
</script>
<template>
  <ModulePage title="库存" :project-filter="route.query.section === 'moves'" v-slot="{ revision, projectId, refresh }"
    ><ModuleTabs :tabs="tabs" storage-key="inventory"><template #stocks><p class="muted">现有库存为全公司共享库存；项目筛选用于库存流水。</p><ResourcePanel
      resource="stocks"
      title="现有库存"
      :revision="revision"
      @changed="refresh" /></template><template #moves><ResourcePanel
      resource="moves"
      title="库存流水"
      :params="{ project: projectId }"
      :revision="revision"
      @changed="refresh"
  /></template></ModuleTabs></ModulePage>
</template>
