<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
</script>
<template>
  <ModulePage title="销售" v-slot="{ revision }"
    ><ResourcePanel resource="sales" title="销售订单" :revision="revision"
  /></ModulePage>
</template>
