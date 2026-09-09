<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
</script>
<template>
  <ModulePage title="采购" v-slot="{ revision }"
    ><ResourcePanel resource="purchases" title="采购订单" :revision="revision"
  /></ModulePage>
</template>
