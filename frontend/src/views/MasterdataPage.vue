<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import { operations } from '../session'
import { computed } from 'vue'
import ModuleTabs from '../components/ModuleTabs.vue'
const tabs = computed(() => [
  ...(operations() ? [{ key: 'items', label: '物料' }] : []),
  { key: 'partners', label: operations() ? '客户与供应商' : '客户资料' },
])
</script>
<template>
  <ModulePage title="基础资料" v-slot="{ revision, refresh }"
    ><ModuleTabs :tabs="tabs" storage-key="masterdata">
    <template #items><ResourcePanel v-if="operations()" resource="items" title="物料" :revision="revision" @changed="refresh" /></template>
    <template #partners><ResourcePanel
      resource="partners"
      :title="operations() ? '客户与供应商' : '客户资料'"
      :revision="revision"
      @changed="refresh"
  /></template></ModuleTabs></ModulePage>
</template>
