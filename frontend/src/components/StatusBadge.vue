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
.status-success { background: var(--ok-wash); color: var(--ok); }
.status-primary { background: var(--brand-wash); color: var(--brand); }
.status-warning { background: var(--warn-wash); color: var(--warn); }
.status-danger { background: var(--risk-wash); color: var(--risk); }
.status-neutral { background: var(--line-2); color: var(--mute); }
</style>
