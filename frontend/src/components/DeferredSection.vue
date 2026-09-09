<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ title: string }>()
const loaded = ref(false)
function toggle(event: Event) {
  if ((event.currentTarget as HTMLDetailsElement).open) loaded.value = true
}
</script>
<template>
  <details class="panel deferred-section" @toggle="toggle">
    <summary>{{ title }}</summary>
    <div v-if="loaded" class="deferred-content"><slot /></div>
  </details>
</template>
<style scoped>
summary { cursor: pointer; font-size: 16px; font-weight: 600; }
summary:focus-visible { outline: 2px solid #245cca; outline-offset: 5px; border-radius: 3px; }
.deferred-content { margin-top: 20px; }
.deferred-content :deep(.panel) { margin-bottom: 0; padding: 0; border: 0; }
</style>
