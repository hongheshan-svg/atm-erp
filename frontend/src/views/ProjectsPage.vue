<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
</script>
<template>
  <ModulePage title="项目" v-slot="{ revision }"
    ><ResourcePanel resource="projects" title="项目列表" :revision="revision"
  /></ModulePage>
</template>
