<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import { can } from '../session'
import { computed } from 'vue'
import ModuleTabs from '../components/ModuleTabs.vue'
const tabs = computed(() => [
  ...(!can(['sales_manager']) ? [{ key: 'items', label: '物料' }] : []),
  { key: 'partners', label: can(['sales_manager']) ? '客户资料' : '客户与供应商' },
])
</script>
<template>
  <ModulePage title="基础资料" v-slot="{ revision }"
    ><ModuleTabs :tabs="tabs" storage-key="masterdata">
    <template #items><ResourcePanel v-if="!can(['sales_manager'])" resource="items" title="物料" :revision="revision" /></template>
    <template #partners><ResourcePanel
      resource="partners"
      :title="can(['sales_manager']) ? '客户资料' : '客户与供应商'"
      :revision="revision"
  /></template></ModuleTabs></ModulePage>
</template>
