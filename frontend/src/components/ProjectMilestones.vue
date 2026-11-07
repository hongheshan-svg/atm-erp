<script setup lang="ts">
import { ref, watch } from 'vue'
import { read } from '../api'
import { milestoneTemplateCommand } from '../modules/milestones'
import { message } from '../utils/request'
import type { Command, Row } from '../types'
import ActionDialog from './ActionDialog.vue'
const props = defineProps<{ projectId: number; revision: number; phase: string }>()
const emit = defineEmits<{ changed: []; phase: [value: string] }>()
const summary = ref<Row>({ stages: [], can_generate: false })
const command = ref<Command | null>(null)
const error = ref(''), busy = ref(false)
watch(() => [props.projectId, props.revision], async (_, __, onCleanup) => {
  let current = true
  onCleanup(() => { current = false })
  try {
    const result = await read('/business/tasks/milestone-summary/', { project: props.projectId })
    if (current) { summary.value = result; error.value = '' }
  } catch (e) { if (current) error.value = message(e) }
}, { immediate: true })
async function generate() {
  busy.value = true
  try { command.value = await milestoneTemplateCommand(props.projectId); error.value = '' }
  catch (e) { error.value = message(e) }
  finally { busy.value = false }
}
</script>
<template>
  <section class="panel milestones" aria-label="项目六阶段里程碑">
    <header class="milestone-heading">
      <div><h2>项目里程碑</h2><p class="muted">六阶段可交叉推进。点击阶段查看任务，负责人和截止日期可在任务操作中调整。</p></div>
      <el-button v-if="summary.can_generate" type="primary" :loading="busy" @click="generate">一键生成里程碑</el-button>
    </header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div class="phase-grid">
      <button v-for="stage in summary.stages" :key="stage.key" class="phase-card" :class="{ selected: phase === stage.key }" :aria-pressed="phase === stage.key" @click="emit('phase', phase === stage.key ? '' : stage.key)">
        <strong>{{ stage.label }}</strong>
        <span>{{ stage.total ? '已完成 ' + stage.done + ' / ' + stage.total : '尚未安排' }}</span>
        <small v-if="stage.overdue" class="overdue">{{ stage.overdue }} 项逾期</small>
      </button>
    </div>
    <p class="muted milestone-note">“发货”“现场安装接线”“现场验收”按实际交付记录同步；每批安装任务仍在下方列表执行。</p>
    <el-button v-if="phase" link type="primary" @click="emit('phase', '')">查看全部阶段</el-button>
    <ActionDialog :command="command" @close="command = null" @saved="emit('changed')" />
  </section>
</template>
<style scoped>
.milestones { margin-bottom: 18px; }
.milestone-heading { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-bottom: 16px; }
.milestone-heading h2 { margin: 0 0 8px; font-size: 18px; }
.milestone-heading p { margin: 0; line-height: 1.6; }
.phase-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; }
.phase-card { padding: 16px 10px; border: 1px solid var(--surface-border); border-radius: 8px; background: #fff; color: inherit; text-align: left; cursor: pointer; }
.phase-card strong, .phase-card span, .phase-card small { display: block; }
.phase-card strong { margin-bottom: 10px; }
.phase-card span { color: var(--text-secondary, #546583); }
.phase-card.selected { border-color: #2563eb; background: #eff6ff; }
.phase-card:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.overdue { color: #b45309; margin-top: 8px; }
.milestone-note { margin: 14px 0 0; line-height: 1.6; }
@media (max-width: 1100px) { .phase-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 760px) { .phase-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .milestone-heading { align-items: stretch; flex-direction: column; } }
</style>
