<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
</script>
<template>
  <ModulePage title="采购" v-slot="{ revision, refresh }"
    ><ResourcePanel resource="purchases" title="采购订单" :revision="revision" @changed="refresh"
  /></ModulePage>
</template>
