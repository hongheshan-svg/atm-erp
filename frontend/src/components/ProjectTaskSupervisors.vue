<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { catalog, options } from '../catalog'
import { participants } from '../modules/shared'
import { disciplines } from '../modules/milestones'
import { manager } from '../session'
import { message } from '../utils/request'
import type { Command, Row } from '../types'
import ActionDialog from './ActionDialog.vue'
const props = defineProps<{ project: Row }>()
const emit = defineEmits<{ changed: [] }>()
const people = ref<Row[]>([]), error = ref('')
const command = ref<Command | null>(null)
const editable = computed(() => manager() && props.project.can_manage && ['active', 'delivering', 'warranty'].includes(props.project.status))
watch(() => props.project.id, async (_, __, onCleanup) => {
  let current = true
  onCleanup(() => { current = false })
  try { const result = await catalog(['users']); if (current) people.value = result.users }
  catch (e) { if (current) error.value = message(e) }
}, { immediate: true })
function label(key: string) {
  const id = props.project.task_supervisors?.[key]
  if (!id) return `${props.project.manager_name}（项目经理代管）`
  return options(people.value.filter(person => person.id === id))[0]?.label || '人员不可用，请调整主管'
}
async function edit() {
  try {
    people.value = (await catalog(['users'])).users
    const ids = [...(props.project.members || []), props.project.manager]
    const choices = options(participants(people.value, props.project).filter(person => ids.includes(person.id) && person.is_active !== false))
    const revision = props.project.supervisor_revision
    command.value = {
      title: '设置专业主管', path: `/business/projects/${props.project.id}/task-supervisors/`,
      notice: { type: 'info', text: '主管需先加入项目成员。未选择的专业由项目经理负责；调整后向新主管发送待办提醒。设置不会增加其他业务权限。' },
      fields: [...disciplines.map(item => ({ key: item.value, label: `${item.label}主管`, type: 'select' as const, optional: true, options: choices })), { key: 'reason', label: '设置说明', type: 'textarea', optional: true }],
      initial: { ...props.project.task_supervisors },
      prepare: data => ({ supervisors: Object.fromEntries(disciplines.map(item => [item.value, data[item.value] || null])), expected_revision: revision, ...(data.reason ? { reason: data.reason } : {}) }),
    }
    error.value = ''
  } catch (e) { error.value = message(e) }
}
</script>
<template>
  <section class="panel task-supervisors" aria-label="项目专业主管">
    <header><h2>专业主管</h2><dl><div v-for="item in disciplines" :key="item.value"><dt>{{ item.label }}</dt><dd>{{ label(item.value) }}</dd></div></dl><el-button v-if="editable" size="small" @click="edit">设置专业主管</el-button></header>
    <p class="muted">主管统一确认任务完成，按人员和日期登记实际小时数；员工查看进度。任务历时不自动计入人工成本。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <ActionDialog :command="command" @close="command = null" @saved="emit('changed')" />
  </section>
</template>
<style scoped>
/* 主管是偶尔调整的配置，放在任务列表之后。 */
.task-supervisors { padding-top: 10px; padding-bottom: 10px; margin-top: 12px; }
header { display: flex; align-items: center; gap: 8px 16px; flex-wrap: wrap; }
h2 { font-size: 16px; margin: 0; flex: none; }
p { margin: 4px 0 0; line-height: 1.5; font-size: 12px; }
dl { display: flex; flex-wrap: wrap; gap: 4px 20px; margin: 0; flex: 1 1 400px; font-size: 13px; }
dl div { display: flex; gap: 6px; align-items: baseline; }
dt { color: var(--ink-4); }
dd { margin: 0; overflow-wrap: anywhere; }
@media (max-width: 640px) { header { align-items: stretch; flex-direction: column; } }
</style>
