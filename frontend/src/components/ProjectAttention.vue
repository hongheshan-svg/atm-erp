<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { read } from '../api'
import { can, purchaseReader } from '../session'
import { message } from '../utils/request'
import type { Row } from '../types'

const props = defineProps<{ project: Row; revision: number }>()
const summary = ref<Record<string, number>>({})
const error = ref(''), loading = ref(false)
const compact = ref(window.innerWidth <= 600), mobileExpanded = ref(false)
const expanded = computed(() => !compact.value || mobileExpanded.value)
const detailsId = useId()
function resize() { compact.value = window.innerWidth <= 600 }
onMounted(() => window.addEventListener('resize', resize))
let generation = 0
const cards = computed(() => [
  { key: 'tasks', label: '未完成任务', unit: '项', tab: 'tasks', section: 'tasks', attention: 'open-tasks' },
  { key: 'shortage', label: '缺料明细', unit: '行', tab: 'bom', section: 'demand', attention: '' },
  // 从 BOM 生成的采购草稿还没提交，缺口看起来已被覆盖，其实还没下单。
  ...(purchaseReader() ? [{ key: 'drafts', label: '采购草稿', unit: '单', tab: 'purchases', section: '', attention: 'draft' }] : []),
  ...(can(['admin', 'purchase_manager']) || (can(['manager']) && props.project.can_manage !== false)
    ? [{ key: 'approvals', label: '待批准采购', unit: '单', tab: 'purchases', section: '', attention: 'submitted' }] : []),
  ...(purchaseReader() ? [
    { key: 'receipts', label: '待收货采购', unit: '单', tab: 'purchases', section: '', attention: 'approved' },
    { key: 'partial', label: '部分收货采购', unit: '单', tab: 'purchases', section: '', attention: 'partial' },
  ] : []),
  { key: 'acceptance', label: '待验收任务', unit: '项', tab: 'tasks', section: 'tasks', attention: 'acceptance' },
])
const note = '缺料按 BOM 明细行统计，共享库存不代表项目预留；采购草稿尚未提交审批；待验收任务由项目经理登记验收。'
async function load() {
  const current = ++generation
  summary.value = {}; error.value = ''; loading.value = true
  const project = props.project.id
  const count = async (resource: string, params: Row) => (await read(`/business/${resource}/`, { project, ...params, page_size: 1 })).count
  const requests: Record<string, () => Promise<number>> = {
    tasks: () => count('tasks', { status: 'open' }),
    shortage: async () => (await read(`/business/projects/${project}/demand/`)).lines.filter((line: Row) => Number(line.shortage) > 0).length,
    drafts: () => count('purchases', { status: 'draft' }),
    approvals: () => count('purchases', { status: 'submitted' }),
    receipts: () => count('purchases', { status: 'approved' }),
    partial: () => count('purchases', { status: 'partial' }),
    acceptance: () => count('tasks', { kind: 'acceptance', status: 'open' }),
  }
  const selected = cards.value
  const results = await Promise.allSettled(selected.map(card => requests[card.key]!()))
  if (current !== generation) return
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') summary.value[selected[index]!.key] = result.value
    else error.value = `部分项目摘要未能加载：${message(result.reason)}`
  })
  loading.value = false
}
watch(() => [props.project.id, props.revision, cards.value.map(card => card.key).join(',')], load, { immediate: true })
onBeforeUnmount(() => { generation++; window.removeEventListener('resize', resize) })
</script>

<template>
  <section class="panel project-attention" aria-label="项目待办摘要" :aria-busy="loading">
    <!-- 手机收起时压成一行：标题、三项计数、展开按钮；按钮显示短字，读屏名称保留「展开项目待办」。 -->
    <header><h2>项目待办</h2><el-tooltip v-if="expanded" :content="note" placement="bottom"><button type="button" class="attention-help" :aria-label="`项目待办说明：${note}`">?</button></el-tooltip
      ><span v-if="!expanded" class="compact-summary">任务 {{ summary.tasks ?? '—' }} 项 · 缺料 {{ summary.shortage ?? '—' }} 行 · 验收 {{ summary.acceptance ?? '—' }} 项</span
      ><button v-if="compact" type="button" class="attention-toggle" :aria-expanded="expanded" :aria-controls="detailsId" :aria-label="expanded ? '收起项目待办' : '展开项目待办'" :title="expanded ? undefined : `展开查看 ${cards.length} 类事项及入口`" @click="mobileExpanded = !mobileExpanded">{{ expanded ? '收起' : '展开' }} <span aria-hidden="true">{{ expanded ? '▴' : '▾' }}</span></button><span v-else class="muted">点击查看当前项目的对应事项</span></header>
    <p v-if="!expanded && error" role="alert" class="compact-error">部分摘要未加载，展开查看详情。</p>
    <div :id="detailsId" v-show="expanded" class="attention-details">
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <div class="attention-grid">
      <router-link v-for="card in cards" :key="card.key" :to="{ path: `/projects/${project.id}`, query: { tab: card.tab, section: card.section || undefined, attention: card.attention || undefined } }">
        <span>{{ card.label }}</span><strong>{{ summary[card.key] ?? '—' }} <small>{{ card.unit }}</small></strong>
      </router-link>
    </div>
    </div>
  </section>
</template>

<style scoped>
/* 一行摘要条：项目页的首屏要留给标签页里的业务内容。 */
.project-attention { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 16px; padding: 10px 16px; margin-bottom: 12px; }
.project-attention header { display: flex; gap: 12px; align-items: center; margin: 0; }
.project-attention header > .muted { display: none; }
.project-attention h2 { margin: 0; font-size: 14px; white-space: nowrap; }
.attention-details { flex: 1 1 0; min-width: 0; }
.attention-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.attention-grid a { display: inline-flex; align-items: baseline; gap: 8px; padding: 5px 12px; border: 1px solid var(--surface-border); border-radius: 999px; font-size: 13px; white-space: nowrap; }
.attention-grid a:hover { background: var(--brand-wash-2); border-color: var(--brand-line); }
.attention-grid strong { font-size: 15px; font-variant-numeric: tabular-nums; }
.attention-grid small { font-size: 12px; font-weight: normal; }
.project-attention p { margin: 6px 0 0; font-size: 12px; line-height: 1.5; }
.attention-help { width: 18px; height: 18px; padding: 0; border: 1px solid var(--field-line); border-radius: 50%; background: #fff; color: var(--mute); font-size: 12px; line-height: 16px; cursor: help; flex-shrink: 0; }
.attention-help:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.attention-toggle { border: 0; background: transparent; color: var(--brand); cursor: pointer; font: inherit; font-size: 13px; padding: 5px 0; flex-shrink: 0; }
.attention-toggle:focus-visible { outline: 2px solid var(--brand); outline-offset: 3px; border-radius: 3px; }
.compact-error { color: var(--risk); }
@media (max-width: 600px) {
  .project-attention { display: block; padding: 10px 12px; }
  .project-attention header { flex-wrap: nowrap; gap: 8px; margin-bottom: 0; }
  .project-attention h2 { font-size: 13px; }
  .project-attention .compact-summary { flex: 1 1 auto; min-width: 0; font-size: 12px; line-height: 1.5; font-variant-numeric: tabular-nums; }
  .attention-toggle { margin-left: auto; padding: 2px 0; font-size: 12px; white-space: nowrap; }
  .attention-details { margin-top: 8px; }
}
</style>
