<script setup lang="ts">
import { computed, inject, provide, type Ref } from 'vue'
const props = defineProps<{ active: boolean }>()
const parent = inject<Ref<boolean>>('panelActive', computed(() => true))
provide('panelActive', computed(() => props.active && parent.value))
</script>
<template><slot /></template>
