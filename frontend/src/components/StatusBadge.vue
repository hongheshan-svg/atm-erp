<script setup lang="ts">
import { computed } from 'vue'
import { display } from '../business'
const props = defineProps<{ value: unknown; text?: string }>()
const tone = computed(() => {
  if (props.value === true || ['signed', 'done', 'received', 'closed', 'confirmed', 'warranty'].includes(String(props.value))) return 'success'
  if (props.value === false || ['cancelled', 'void', 'voided', 'rejected'].includes(String(props.value))) return 'neutral'
  if (['submitted', 'partial', 'pending', 'open', 'payable'].includes(String(props.value))) return 'warning'
  if (['overdue', 'over_budget'].includes(String(props.value))) return 'danger'
  if (['active', 'quoted', 'approved', 'delivering', 'receivable'].includes(String(props.value))) return 'primary'
  return 'neutral'
})
</script>
<template><span class="status-badge" :class="`status-${tone}`">{{ text || display(value) }}</span></template>
<style scoped>
.status-badge { display: inline-flex; align-items: center; padding: 3px 8px; border-radius: 5px; font-size: 12px; line-height: 20px; font-weight: 500; white-space: nowrap; }
.status-success { background: #e6f6f0; color: #087c70; }
.status-primary { background: #eaf1ff; color: #2563eb; }
.status-warning { background: #fff4da; color: #95600a; }
.status-danger { background: #ffebee; color: #ba3146; }
.status-neutral { background: #eef2f7; color: #61718a; }
</style>
