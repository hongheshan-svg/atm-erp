<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import ModuleTabs from '../components/ModuleTabs.vue'
const tabs = [{ key: 'entries', label: '应收应付与费用' }, { key: 'payments', label: '收付款流水' }]
</script>
<template>
  <ModulePage title="收付款" project-filter v-slot="{ revision, projectId, refresh }"
    ><p class="muted">CNY 含税经营口径。正余额需收付，负余额需退款；原记录通过冲销纠正。</p>
    <ModuleTabs :tabs="tabs" storage-key="finance"><template #entries><ResourcePanel
      resource="entries"
      title="应收应付与费用"
      :params="{ project: projectId }"
      :project-id="projectId"
      :revision="revision"
      @changed="refresh" /></template><template #payments><ResourcePanel
      resource="payments"
      title="收付款流水"
      :params="{ entry__project: projectId }"
      :revision="revision"
      @changed="refresh"
  /></template></ModuleTabs></ModulePage>
</template>
