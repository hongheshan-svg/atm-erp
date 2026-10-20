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
  ...(can(['admin', 'purchase_manager']) || (can(['manager']) && props.project.can_manage !== false)
    ? [{ key: 'approvals', label: '待批准采购', unit: '单', tab: 'purchases', section: '', attention: 'submitted' }] : []),
  ...(purchaseReader() ? [
    { key: 'receipts', label: '待收货采购', unit: '单', tab: 'purchases', section: '', attention: 'approved' },
    { key: 'partial', label: '部分收货采购', unit: '单', tab: 'purchases', section: '', attention: 'partial' },
  ] : []),
  { key: 'acceptance', label: '待验收任务', unit: '项', tab: 'tasks', section: 'tasks', attention: 'acceptance' },
])
async function load() {
  const current = ++generation
  summary.value = {}; error.value = ''; loading.value = true
  const project = props.project.id
  const count = async (resource: string, params: Row) => (await read(`/business/${resource}/`, { project, ...params, page_size: 1 })).count
  const requests: Record<string, () => Promise<number>> = {
    tasks: () => count('tasks', { status: 'open' }),
    shortage: async () => (await read(`/business/projects/${project}/demand/`)).lines.filter((line: Row) => Number(line.shortage) > 0).length,
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
    <header><h2>项目待办</h2><button v-if="compact" type="button" class="attention-toggle" :aria-expanded="expanded" :aria-controls="detailsId" @click="mobileExpanded = !mobileExpanded">{{ expanded ? '收起项目待办' : '展开项目待办' }}</button><span v-else class="muted">点击查看当前项目的对应事项</span></header>
    <template v-if="!expanded">
      <p class="compact-summary">任务 {{ summary.tasks ?? '—' }} 项 · 缺料 {{ summary.shortage ?? '—' }} 行 · 验收 {{ summary.acceptance ?? '—' }} 项</p>
      <small class="compact-hint muted">点击“展开项目待办”查看 {{ cards.length }} 类事项及入口</small>
      <p v-if="error" role="alert" class="compact-error">部分摘要未加载，展开查看详情。</p>
    </template>
    <div :id="detailsId" v-show="expanded" class="attention-details">
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <div class="attention-grid">
      <router-link v-for="card in cards" :key="card.key" :to="{ path: `/projects/${project.id}`, query: { tab: card.tab, section: card.section || undefined, attention: card.attention || undefined } }">
        <span>{{ card.label }}</span><strong>{{ summary[card.key] ?? '—' }} <small>{{ card.unit }}</small></strong>
      </router-link>
    </div>
    <p class="muted">缺料按 BOM 明细行统计，共享库存不代表项目预留；待验收任务由项目经理登记验收。</p>
    </div>
  </section>
</template>

<style scoped>
.project-attention header { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }
.project-attention h2 { margin: 0; font-size: 18px; }
.attention-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.attention-grid a { display: grid; gap: 8px; padding: 14px; border: 1px solid var(--surface-border); border-radius: 8px; }
.attention-grid strong { font-size: 24px; }
.attention-grid small { font-size: 13px; font-weight: normal; }
.project-attention p { margin-bottom: 0; font-size: 13px; line-height: 1.6; }
.attention-toggle { border: 0; background: transparent; color: var(--brand); cursor: pointer; font: inherit; font-size: 13px; padding: 5px 0; flex-shrink: 0; }
.attention-toggle:focus-visible { outline: 2px solid var(--brand); outline-offset: 3px; border-radius: 3px; }
.compact-hint { display: block; margin-top: 2px; font-size: 11px; line-height: 1.5; }
.compact-error { color: var(--risk); }
@media (max-width: 600px) {
  .project-attention { padding: 12px 14px; }
  .project-attention header { justify-content: space-between; flex-wrap: nowrap; margin-bottom: 0; }
  .project-attention h2 { font-size: 16px; }
  .project-attention .compact-summary { margin: 4px 0 0; font-size: 12px; }
  .attention-details { margin-top: 10px; }
}
</style>
