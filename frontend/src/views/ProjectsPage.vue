<script setup lang="ts">
import ModulePage from '../components/ModulePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
</script>
<template>
  <ModulePage title="项目" v-slot="{ revision, refresh }"
    ><ResourcePanel resource="projects" title="项目列表" :revision="revision" @changed="refresh"
  /></ModulePage>
</template>
