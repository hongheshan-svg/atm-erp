<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
</script>
<template>
  <ModulePage title="基础资料" v-slot="{ revision }"
    ><ResourcePanel resource="items" title="物料" :revision="revision" /><ResourcePanel
      resource="partners"
      title="客户与供应商"
      :revision="revision"
  /></ModulePage>
</template>
