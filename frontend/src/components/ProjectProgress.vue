<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { read } from '../api'
import { flowFor } from '../flows'
import { message } from '../utils/request'
import type { Row } from '../types'
import ProcessSteps from './ProcessSteps.vue'

const props = defineProps<{ projectId: number; revision?: number }>()
const data = ref<Row | null>(null), error = ref(''), loading = ref(false), copied = ref('')
const category = ref('tasks'), state = ref('open'), page = ref(1)
const labels = { tasks: '任务执行', purchases: '采购到货', deliveries: '交付验收', entries: '收付款进度' }
const groups = computed(() => data.value?.groups || Object.entries(labels).map(([key, label]) => ({ key, label, open: '—' })))
const names = (row: Row) => (row.handlers || []).map((person: Row) => `${person.name}${person.active ? '' : '（已停用）'}`).join('、') || '待安排，请联系项目负责人'
const time = (value?: string) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
const pages = computed(() => Math.max(1, Math.ceil((data.value?.count || 0) / 20)))
function recordFlow(row: Row) {
  const flow = flowFor(row.resource, row.record)
  if (!flow || flow.current < 0) return flow
  return { ...flow, nodes: flow.nodes.map((node, index) => index === flow.current ? { ...node, label: row.status_label, hint: row.hint } : node) }
}
let generation = 0
async function load() {
  const current = ++generation
  loading.value = true; error.value = ''; copied.value = ''; data.value = null
  try {
    const result = await read(`/business/projects/${props.projectId}/progress/`, { category: category.value, state: state.value, page: page.value, page_size: 20 })
    if (current === generation) { data.value = result; page.value = result.page }
  } catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) loading.value = false }
}
function select(key: string) { category.value = key; page.value = 1; void load() }
function scope(value: string) { state.value = value; page.value = 1; void load() }
function turn(value: number) { page.value = value; void load() }
async function copy(row: Row) {
  const text = [
    `${data.value?.project.code} · ${data.value?.project.name}`,
    `${row.title}：${row.status_label}`, `${row.handler_label}：${names(row)}`,
    row.due_date ? `${row.due_label}：${row.due_date}${row.overdue ? '（已逾期）' : ''}` : '', row.hint,
  ].filter(Boolean).join('\n')
  try { await navigator.clipboard.writeText(text); copied.value = `已复制“${row.title}”的进度，可粘贴给相关人员。` }
  catch { copied.value = '浏览器不支持直接复制，请选中卡片上的进度文字复制。' }
}
watch(() => [props.projectId, props.revision], () => { page.value = 1; void load() }, { immediate: true })
onBeforeUnmount(() => { generation++ })
</script>

<template>
  <section class="project-progress" aria-label="流程进度" :aria-busy="loading">
    <header class="progress-heading"><div><h2>流程进度</h2><p class="muted">查看当前节点，找到相关人员跟进。可审批人员是岗位候选人，尚未指定某个人处理。</p></div><el-button :loading="loading" @click="load">刷新进度</el-button></header>
    <p v-if="data" class="progress-context">项目负责人：{{ data.project.manager.name }}<span>更新于 {{ time(data.checked_at) }}</span></p>
    <nav class="progress-groups" aria-label="流程分类"><button v-for="group in groups" :key="group.key" type="button" :aria-pressed="category === group.key" @click="select(group.key)"><span>{{ group.label }}</span><strong>{{ group.open }} <small>待跟进</small></strong></button></nav>
    <div class="progress-tools"><div role="group" aria-label="进度范围"><el-button :type="state === 'open' ? 'primary' : undefined" :aria-pressed="state === 'open'" @click="scope('open')">待跟进</el-button><el-button :type="state === 'all' ? 'primary' : undefined" :aria-pressed="state === 'all'" @click="scope('all')">全部记录</el-button></div><span v-if="data" class="muted">共 {{ data.count }} 项</span></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" /><el-button v-if="error" @click="load">重新加载进度</el-button>
    <p v-if="copied" role="status">{{ copied }}</p>
    <p v-if="loading" class="muted" role="status">正在读取最新流程进度…</p>
    <p v-else-if="data && !data.results.length" class="progress-empty">{{ state === 'open' ? '本类暂无待跟进事项。可切换“全部记录”查看已结束的流程。' : '本类还没有业务记录。' }}</p>
    <div v-if="data" class="progress-records">
      <article v-for="row in data.results" :key="`${row.resource}-${row.id}`" class="progress-record" :class="{ overdue: row.overdue }">
        <header><h3>{{ row.title }}</h3><span class="progress-status">{{ row.status_label }}</span></header>
        <dl><div><dt>{{ row.handler_label }}</dt><dd>{{ names({ handlers: row.handlers.slice(0, 3) }) }}<details v-if="row.handlers.length > 3" class="more-contacts"><summary>查看其余 {{ row.handlers.length - 3 }} 位人员</summary>{{ names({ handlers: row.handlers.slice(3) }) }}</details></dd></div><div><dt>{{ row.due_label }}</dt><dd>{{ row.due_date || '未设置' }} <strong v-if="row.overdue" class="overdue-label">已逾期</strong></dd></div><div v-if="row.agreed_date"><dt>约定付款日</dt><dd>{{ row.agreed_date }}（实际付款期限尚未起算）</dd></div></dl>
        <p class="progress-hint">{{ row.hint }}</p>
        <details v-if="recordFlow(row)"><summary>查看流程节点</summary><ProcessSteps :flow="recordFlow(row)!" /></details>
        <footer><el-button text @click="copy(row)">复制跟进信息</el-button><router-link v-if="row.path" :to="row.path">查看原单</router-link></footer>
      </article>
    </div>
    <nav v-if="data && pages > 1" class="progress-pagination" aria-label="流程进度分页"><el-button :disabled="page <= 1" @click="turn(page - 1)">上一页</el-button><span>{{ page }} / {{ pages }}</span><el-button :disabled="page >= pages" @click="turn(page + 1)">下一页</el-button></nav>
  </section>
</template>

<style scoped>
.project-progress { padding: 16px 0; }
.progress-heading, .progress-context, .progress-tools, .progress-record header, .progress-record footer, .progress-pagination { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.progress-heading h2 { margin: 0 0 6px; font-size: 18px; }
.progress-heading p { margin: 0; font-size: 13px; line-height: 1.6; }
.progress-context { font-size: 13px; margin: 16px 0; }
.progress-context span { color: var(--mute); font-size: 12px; }
.progress-groups { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 140px), 1fr)); gap: 10px; margin: 16px 0; }
.progress-groups button { border: 1px solid var(--surface-border); border-radius: 8px; background: #fff; padding: 12px; color: var(--ink); cursor: pointer; text-align: left; font: inherit; }
.progress-groups button[aria-pressed=true] { border-color: var(--brand); background: var(--brand-ring); }
.progress-groups button:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.progress-groups span, .progress-groups strong { display: block; }
.progress-groups span { font-size: 13px; }
.progress-groups strong { margin-top: 6px; font-size: 20px; }
.progress-groups small { font-size: 11px; font-weight: normal; color: var(--mute); }
.progress-tools { margin-bottom: 16px; }
.progress-records { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); gap: 14px; }
.progress-record { border: 1px solid var(--surface-border); border-radius: 8px; padding: 16px; min-width: 0; background: #fff; overflow-wrap: anywhere; }
.progress-record.overdue { border-left: 3px solid var(--risk); }
.progress-record header { align-items: flex-start; }
.progress-record h3 { margin: 0; font-size: 15px; flex: 1 1 180px; }
.progress-status { font-size: 12px; color: var(--brand); }
.progress-record dl { font-size: 13px; margin: 16px 0; }
.progress-record dl div { display: grid; grid-template-columns: 100px minmax(0, 1fr); gap: 8px; margin-top: 8px; }
.progress-record dt { color: var(--mute); }
.progress-record dd { margin: 0; line-height: 1.6; }
.overdue-label { color: var(--risk); font-size: 12px; }
.progress-hint, .progress-record details { font-size: 12px; line-height: 1.7; color: var(--mute); }
.progress-record details summary { cursor: pointer; color: var(--brand); padding: 4px 0 10px; }
.progress-record footer { margin-top: 14px; font-size: 13px; }
.progress-empty { padding: 24px 0; color: var(--mute); font-size: 13px; }
.progress-pagination { justify-content: flex-end; margin-top: 16px; }
@media (max-width: 760px) { .progress-groups { grid-template-columns: repeat(2, minmax(0, 1fr)); } .progress-records { grid-template-columns: 1fr; } .progress-record { padding: 12px; } }
</style>
