<script setup lang="ts">
import { computed } from 'vue'
import type { Flow } from '../types'
// compact renders inside a table cell, where a full node chain would not fit; inline is a one-line
// chain of step labels for page headers, with each node's explanation kept as a hover tip.
const props = defineProps<{ flow: Flow; compact?: boolean; inline?: boolean }>()
const stopped = computed(() => Boolean(props.flow.aborted))
function state(index: number) {
  if (stopped.value) return 'skipped'
  if (index < props.flow.current) return 'done'
  return index === props.flow.current ? 'current' : 'todo'
}
const summary = computed(() =>
  props.flow.aborted
    ? `${props.flow.label}：${props.flow.aborted.label}`
    : `${props.flow.label}：第 ${props.flow.current + 1} / ${props.flow.nodes.length} 步 ${props.flow.nodes[props.flow.current]?.label}`,
)
</script>
<template>
  <nav v-if="compact" class="process-compact" :aria-label="summary">
    <span class="process-dots" aria-hidden="true"
      ><i v-for="(item, index) in flow.nodes" :key="item.key" :class="`process-${state(index)}`" /><i
        v-if="flow.aborted" class="process-aborted"
    /></span>
    <small>{{ flow.aborted ? flow.aborted.label : flow.nodes[flow.current]?.label }}</small>
  </nav>
  <nav v-else-if="inline" class="process-inline" :aria-label="summary">
    <ol>
      <li v-for="(item, index) in flow.nodes" :key="item.key" :class="`process-${state(index)}`" :aria-current="state(index) === 'current' ? 'step' : undefined" :title="item.hint">
        <span class="process-pill"><span v-if="state(index) === 'done'" class="process-check" aria-hidden="true">✓</span>{{ item.label }}</span>
      </li>
      <li v-if="flow.aborted" class="process-aborted" aria-current="step" :title="flow.aborted.hint"><span class="process-pill">{{ flow.aborted.label }}</span></li>
    </ol>
  </nav>
  <nav v-else class="process-steps" :aria-label="summary">
    <ol>
      <li v-for="(item, index) in flow.nodes" :key="item.key" :class="`process-${state(index)}`" :aria-current="state(index) === 'current' ? 'step' : undefined">
        <span class="process-marker" aria-hidden="true">{{ state(index) === 'done' ? '✓' : index + 1 }}</span>
        <span class="process-text"><strong>{{ item.label }}</strong><small v-if="item.hint">{{ item.hint }}</small></span>
      </li>
      <li v-if="flow.aborted" class="process-aborted" aria-current="step">
        <span class="process-marker" aria-hidden="true">!</span>
        <span class="process-text"><strong>{{ flow.aborted.label }}</strong><small v-if="flow.aborted.hint">{{ flow.aborted.hint }}</small></span>
      </li>
    </ol>
  </nav>
</template>
<style scoped>
.process-compact { display: inline-flex; align-items: center; gap: 7px; }
.process-dots { display: inline-flex; gap: 3px; }
.process-dots > i { width: 7px; height: 7px; border-radius: 50%; background: var(--field-line); }
.process-dots > i.process-done { background: var(--el-color-primary); }
.process-dots > i.process-current { background: var(--el-color-primary); box-shadow: 0 0 0 2px var(--brand-ring); }
.process-dots > i.process-aborted { background: var(--risk); }
.process-compact small { font-size: 12px; color: var(--mute); white-space: nowrap; }

/* Inline chain: 执行中 › 交付中 › 已验收 › 已结项, current step filled. */
.process-inline ol { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 0; list-style: none; margin: 0; padding: 0; }
.process-inline li { display: inline-flex; align-items: center; font-size: 13px; line-height: 20px; color: var(--ink-6); white-space: nowrap; cursor: default; }
.process-inline li + li::before { content: '›'; margin: 0 5px; color: var(--ink-6); }
.process-pill { display: inline-flex; align-items: center; gap: 3px; padding: 2px 9px; border-radius: 999px; }
.process-inline li.process-done { color: var(--ink-3); }
.process-check { color: var(--el-color-primary); font-size: 12px; }
.process-inline li.process-current .process-pill { background: var(--el-color-primary); color: #fff; font-weight: 600; }
.process-inline li.process-skipped { opacity: 0.55; }
.process-inline li.process-aborted .process-pill { background: var(--risk); color: #fff; font-weight: 600; }

/* The node row measures itself: a narrow host (detail pane, phone) switches to the vertical rail
   below, so a wrapped row never leaves a connector pointing into empty space. */
.process-steps { container-type: inline-size; }
.process-steps ol { display: flex; list-style: none; margin: 0; padding: 0; }
.process-steps li { position: relative; flex: 1 1 0; min-width: 92px; display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 0 4px; text-align: center; }
/* The connector sits behind the markers and stops at the row edges. */
.process-steps li::before { content: ''; position: absolute; top: 12px; left: -50%; width: 100%; height: 2px; background: var(--field-line); }
.process-steps li:first-child::before { display: none; }
.process-steps li.process-done::before, .process-steps li.process-current::before { background: var(--el-color-primary); }
.process-marker { position: relative; width: 25px; height: 25px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; line-height: 1; font-weight: 600; border: 2px solid var(--field-line); background: #fff; color: var(--ink-5); }
.process-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.process-text strong { font-size: 12px; font-weight: 500; color: var(--mute); overflow-wrap: anywhere; }
.process-text small { font-size: 11px; line-height: 1.45; color: var(--ink-6); }
.process-done .process-marker { border-color: var(--el-color-primary); background: var(--el-color-primary); color: #fff; }
.process-done .process-text strong { color: var(--ink-3); }
.process-current .process-marker { border-color: var(--el-color-primary); color: var(--el-color-primary); box-shadow: 0 0 0 4px var(--brand-ring); }
.process-current .process-text strong { color: var(--el-color-primary); font-weight: 600; }
.process-skipped .process-marker, .process-skipped .process-text strong { opacity: 0.55; }
.process-aborted .process-marker { border-color: var(--risk); background: var(--risk); color: #fff; }
.process-aborted .process-text strong { color: var(--risk); font-weight: 600; }
.process-aborted::before { background: repeating-linear-gradient(90deg, var(--risk) 0 5px, transparent 5px 10px) !important; }
@container (max-width: 700px) {
  .process-steps ol { display: block; }
  .process-steps li { flex-direction: row; align-items: flex-start; gap: 10px; text-align: left; padding: 0 0 12px; min-width: 0; }
  .process-steps li:last-child { padding-bottom: 0; }
  /* Vertical rail: draw downward from each marker instead of across the row. */
  .process-steps li::before { top: 25px; left: 11px; width: 2px; height: calc(100% - 25px); background: var(--field-line); }
  .process-steps li:first-child::before { display: block; }
  .process-steps li:last-child::before { display: none; }
  .process-steps li.process-done::before { background: var(--el-color-primary); }
  .process-steps li.process-current::before { background: var(--field-line); }
  /* Vertically the aborted node's own connector is hidden as the last child, so mark the segment leading into it. */
  .process-steps ol:has(.process-aborted) li:nth-last-child(2)::before { background: repeating-linear-gradient(180deg, var(--risk) 0 5px, transparent 5px 10px) !important; }
  .process-marker { flex-shrink: 0; }
  .process-text { padding-top: 3px; }
}
</style>
