<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
// 已有里程碑节点后（普通任务不算），生成不再是这里的主要动作：降为次要按钮并改叫「补充」。
const planned = computed(() => Number(summary.value.milestones) > 0)
// 旧接口没有 missing 时按「仍可补充」处理，由对话框自己说明。
const missing = computed(() => summary.value.missing == null ? null : Number(summary.value.missing))
const complete = computed(() => planned.value && missing.value === 0)
const note = '六阶段可交叉推进，点击阶段筛选下方任务。客户终验收阶段包含各批次的安装、验收任务；“发货”“现场安装接线”“现场验收”按实际交付记录同步。'
function progress(stage: Row) {
  if (stage.shipped != null && !stage.total) return `已发货 ${stage.shipped} / ${stage.equipment} 台`
  return stage.total ? `${stage.done} / ${stage.total}` : '未安排'
}
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
    <div class="milestone-strip">
      <h2>里程碑<el-tooltip :content="note" placement="bottom-start"><button type="button" class="milestone-help" :aria-label="`里程碑说明：${note}`">?</button></el-tooltip></h2>
      <div class="phase-grid">
        <!-- 「全部」常驻在阶段前面，选中阶段后布局不跳动；读屏名称沿用「查看全部阶段」。 -->
        <button type="button" class="phase-all" :class="{ selected: !phase }" :aria-pressed="!phase" aria-label="查看全部阶段" @click="emit('phase', '')">全部</button>
        <button v-for="stage in summary.stages" :key="stage.key" type="button" class="phase-card" :class="{ selected: phase === stage.key, late: stage.overdue }" :aria-pressed="phase === stage.key" @click="emit('phase', phase === stage.key ? '' : stage.key)">
          <strong>{{ stage.label }}</strong>
          <span>{{ progress(stage) }}</span>
          <small v-if="stage.overdue" class="overdue">{{ stage.overdue }} 项逾期</small>
          <small v-if="stage.shipped != null && stage.total" class="shipped">已发货 {{ stage.shipped }} / {{ stage.equipment }} 台</small>
        </button>
      </div>
      <div class="milestone-actions">
        <template v-if="summary.can_generate">
          <span v-if="complete" class="milestone-complete muted" title="六阶段节点已全部生成，新增其他任务请用「新建任务」">节点已全部生成</span>
          <el-button v-else :type="planned ? undefined : 'primary'" size="small" :loading="busy" @click="generate">{{ planned ? (missing ? `补充里程碑节点（缺 ${missing} 个）` : '补充里程碑节点') : '一键生成里程碑' }}</el-button>
        </template>
      </div>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <ActionDialog :command="command" @close="command = null" @replace="command = $event" @saved="emit('changed')" />
  </section>
</template>
<style scoped>
/* 一行筛选条：阶段卡紧凑排在标题右侧，任务表尽量留在首屏。 */
.milestones { margin-bottom: 8px; padding: 6px 12px; }
.milestone-strip { display: flex; align-items: center; gap: 10px 14px; flex-wrap: wrap; }
.milestone-strip h2 { display: inline-flex; align-items: center; gap: 6px; margin: 0; font-size: 14px; white-space: nowrap; }
.milestone-help { width: 18px; height: 18px; padding: 0; border: 1px solid var(--field-line); border-radius: 50%; background: #fff; color: var(--mute); font-size: 12px; line-height: 16px; cursor: help; }
.milestone-help:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.phase-grid { display: flex; flex-wrap: wrap; gap: 6px; flex: 1 1 640px; min-width: 0; }
.phase-card { flex: 1 1 auto; display: flex; flex-wrap: wrap; align-items: baseline; gap: 0 6px; padding: 4px 9px; border: 1px solid var(--surface-border); border-radius: 6px; background: #fff; color: inherit; text-align: left; cursor: pointer; font: inherit; min-width: 0; }
.phase-card strong { font-size: 13px; font-weight: 600; white-space: nowrap; }
.phase-card span, .phase-card small { font-size: 12px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.phase-card span { color: var(--text-secondary, #546583); }
.phase-card.selected { border-color: #2563eb; background: #eff6ff; }
.phase-card.late { border-left: 3px solid var(--risk); }
.phase-all { flex: none; padding: 4px 10px; border: 1px solid var(--surface-border); border-radius: 6px; background: #fff; color: var(--mute); font: inherit; font-size: 12px; cursor: pointer; }
.phase-all.selected { border-color: #2563eb; background: #eff6ff; color: #1d4ed8; }
.phase-all:focus-visible, .phase-card:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.overdue { color: var(--risk); font-weight: 600; }
.shipped { color: var(--mute); }
.milestone-actions { display: inline-flex; align-items: center; gap: 10px; margin-left: auto; }
.milestone-complete { font-size: 12px; white-space: nowrap; }
@media (max-width: 1100px) { .phase-grid { flex-basis: 100%; } }
@media (max-width: 600px) { .phase-card { flex-basis: calc(50% - 3px); } }
</style>
