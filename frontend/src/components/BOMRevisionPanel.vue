<script setup lang="ts">
// 换版后的「旧版待处理」：旧版已领用、已到货中超出现 BOM 需求的数量，由仓管报废或留作备件、
// 工程师登记已装机报废、采购开返修单改制成新版；另列本项目的换版记录。
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { read } from '../api'
import { bomEditor, purchasing, can } from '../session'
import type { Command, Field, Row } from '../types'
import { message } from '../utils/request'
import { quantityText as qty } from '../utils/quantity'
import { dateTimeText } from '../utils/datetime'
import { date, remote, t } from '../modules/shared'
import { termLabel } from '../modules/payment-terms'

const props = defineProps<{ projectId: number; refresh?: number; canEditBom?: boolean; status?: string }>()
const emit = defineEmits<{ command: [Command] }>()
const parts = ref<Row[]>([])
const changes = ref<Row[]>([])
const error = ref('')
const historyOpen = ref(false)
const warehouseRole = () => can(['admin', 'warehouse'])
const editor = computed(() => bomEditor({ can_edit_bom: props.canEditBom }))
const readable = computed(() => warehouseRole() || purchasing() || editor.value)
const open = computed(() => parts.value.filter(row => row.open))
const writable = computed(() => ['draft', 'quoted', 'active', 'delivering', 'warranty'].includes(props.status || ''))

let generation = 0
onBeforeUnmount(() => { generation++ })
async function load() {
  const current = ++generation
  if (!readable.value) {
    parts.value = []
    changes.value = []
    error.value = ''
    return
  }
  error.value = ''
  try {
    const result = await read(`/business/projects/${props.projectId}/obsolete-parts/`)
    if (current !== generation) return
    parts.value = result?.parts || []
    changes.value = result?.changes || []
  } catch (e) {
    if (current === generation) error.value = message(e)
  }
}
watch(() => [props.projectId, props.refresh, readable.value], () => { void load() }, { immediate: true })

const label = (row: Row, side: 'old' | 'new') => {
  const code = row[`${side}_item_code`]
  const revision = row[`${side}_revision`]
  return revision ? `${code}（${revision} 版）` : code
}
function handled(row: Row): string {
  return [
    Number(row.scrapped_stock) > 0 ? `在库报废 ${qty(row.scrapped_stock)}` : '',
    Number(row.kept) > 0 ? `留作备件 ${qty(row.kept)}` : '',
    Number(row.rework_stock) > 0 ? `在库返修 ${qty(row.rework_stock)}` : '',
    Number(row.scrapped_issued) > 0 ? `已装机报废 ${qty(row.scrapped_issued)}` : '',
    Number(row.rework_issued) > 0 ? `已装机返修 ${qty(row.rework_issued)}` : '',
  ].filter(Boolean).join('、')
}
function actions(row: Row): string[] {
  if (!writable.value) return []
  const result: string[] = []
  if (Number(row.pending_stock) > 0 && warehouseRole()) result.push('在库报废', '留作备件')
  if (Number(row.pending_issued) > 0 && (warehouseRole() || editor.value)) result.push('已装机报废')
  if ((Number(row.pending_stock) > 0 || Number(row.pending_issued) > 0) && purchasing() && row.new_line) result.push('开返修单')
  return result
}
const reason: Field = { ...t('reason', '原因'), hint: '写明 ECN 编号或旧版不能用的原因。' }
function dispose(row: Row, source: 'stock' | 'issued', kind: 'scrap' | 'keep'): Command {
  const pending = source === 'stock' ? row.pending_stock : row.pending_issued
  const what = kind === 'keep' ? '留作公用备件' : source === 'stock' ? '报废出库' : '登记报废'
  return {
    title: `${label(row, 'old')} ${what}`,
    submitLabel: `确认${kind === 'keep' ? '留用' : '报废'}`,
    path: `/business/revision-changes/${row.change}/dispose/`,
    notice: {
      type: kind === 'scrap' ? 'warning' : 'info',
      text: kind === 'keep'
        ? `只登记、不出库：旧版仍留在库里，不再算本项目的待处理，其他项目可按需领用。本项目待处理 ${qty(pending)}。`
        : source === 'stock'
          ? `从库存出库报废，金额计入本项目材料成本。本项目在库待处理 ${qty(pending)}。`
          : `已装在设备上的旧版拆下报废，只登记数量，成本已在领料时计入项目。待处理 ${qty(pending)}。`,
    },
    fields: [{ key: 'quantity', label: '数量', numeric: { scale: 3, min: 0.001 } }, reason],
    initial: { quantity: qty(pending, ''), reason: '' },
    prepare: data => ({ source, kind, quantity: data.quantity, reason: data.reason }),
  }
}
function rework(row: Row): Command {
  const sources = [
    ...(Number(row.pending_stock) > 0 ? [{ value: 'stock', label: `在库旧版（待处理 ${qty(row.pending_stock)}）` }] : []),
    ...(Number(row.pending_issued) > 0 ? [{ value: 'issued', label: `已装机旧版（待处理 ${qty(row.pending_issued)}）` }] : []),
  ]
  return {
    title: `返修改制 ${label(row, 'old')} → ${label(row, 'new')}`,
    submitLabel: '生成返修采购草稿',
    path: `/business/revision-changes/${row.change}/rework/`,
    notice: { type: 'info', text: '生成一张新版物料的采购草稿，挂在本项目新版 BOM 行上，按正常流程提交审批和收货。在库旧版返修：收到改好的新版时同数量旧版自动出库；已装机旧版返修：拆下送修，收货只入新版。' },
    fields: [
      { key: 'source', label: '返修哪部分旧版', type: 'select', options: sources },
      { key: 'quantity', label: '返修数量', numeric: { scale: 3, min: 0.001 } },
      remote('supplier', '返修供应商', '/business/partners/', {
        remoteParams: { is_active: true },
        remoteFilter: p => p.kind !== 'customer',
        remoteLabel: p => `${p.code} · ${p.name} · ${termLabel(p)}`,
      }),
      { ...t('unit_price', '返修单价（元，含税）'), numeric: { scale: 2, min: 0 } },
      date('due_date', '交期'),
      { ...t('note', '说明', true), hint: '如改哪些孔位、是否需要重新表面处理。' },
    ],
    initial: { source: sources[0]?.value, quantity: qty(sources[0]?.value === 'issued' ? row.pending_issued : row.pending_stock, ''), note: '' },
  }
}
function act(row: Row, name: string) {
  const command = name === '在库报废' ? dispose(row, 'stock', 'scrap')
    : name === '留作备件' ? dispose(row, 'stock', 'keep')
      : name === '已装机报废' ? dispose(row, 'issued', 'scrap')
        : rework(row)
  emit('command', command)
}
defineExpose({ load })
</script>

<template>
  <section v-if="readable && (open.length || changes.length || error)" class="bom-revision-panel" aria-label="换版与旧版待处理">
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <template v-if="open.length">
      <header class="bom-revision-heading">
        <h3>旧版待处理 <el-tag size="small" type="warning">{{ open.length }}</el-tag></h3>
        <p class="muted">换版后多出来的旧版：在库的报废或留作备件，已装机的登记报废，或开返修单改制成新版。</p>
      </header>
      <ul class="bom-revision-list">
        <li v-for="row in open" :key="row.old_item">
          <div class="bom-revision-main">
            <strong>{{ row.old_item_name }}</strong>
            <span class="bom-revision-arrow">{{ label(row, 'old') }} → {{ label(row, 'new') }}</span>
            <small class="muted">{{ row.assembly_unit || '未分单元' }} · {{ row.reason }}</small>
          </div>
          <div class="bom-revision-numbers">
            <span v-if="Number(row.pending_stock) > 0">在库 <b>{{ qty(row.pending_stock) }}</b></span>
            <span v-if="Number(row.pending_issued) > 0">已装机 <b>{{ qty(row.pending_issued) }}</b></span>
            <small v-if="handled(row)" class="muted">已处理：{{ handled(row) }}</small>
          </div>
          <el-dropdown v-if="actions(row).length" trigger="click" :persistent="false" @command="(name: string) => act(row, String(name))">
            <el-button size="small">处理 ▾</el-button>
            <template #dropdown><el-dropdown-menu><el-dropdown-item v-for="name in actions(row)" :key="name" :command="name">{{ name }}</el-dropdown-item></el-dropdown-menu></template>
          </el-dropdown>
        </li>
      </ul>
    </template>
    <details v-if="changes.length" class="bom-revision-history" :open="historyOpen" @toggle="historyOpen = ($event.target as HTMLDetailsElement).open">
      <summary>换版记录（{{ changes.length }}）</summary>
      <ul>
        <li v-for="change in changes" :key="change.id">
          <span>{{ dateTimeText(change.created_at) }} · {{ change.created_by }}</span>
          <strong>{{ change.old_item_code }}{{ change.old_revision ? `（${change.old_revision} 版）` : '' }} → {{ change.new_item_code }}{{ change.new_revision ? `（${change.new_revision} 版）` : '' }}</strong>
          <span>{{ change.assembly_unit || '未分单元' }} · {{ qty(change.old_quantity) }} → {{ qty(change.new_quantity) }}<template v-if="Number(change.converted_quantity) > 0"> · 在途 {{ qty(change.converted_quantity) }} 按新图改单</template></span>
          <small class="muted">{{ change.reason }}</small>
        </li>
      </ul>
    </details>
  </section>
</template>

<style scoped>
.bom-revision-panel { display: grid; gap: 8px; margin: 8px 0 12px; padding: 10px 12px; border: 1px solid var(--el-color-warning-light-5); border-radius: 8px; background: var(--el-color-warning-light-9); }
.bom-revision-heading { display: grid; gap: 2px; }
.bom-revision-heading h3 { margin: 0; font-size: 15px; display: flex; align-items: center; gap: 6px; }
.bom-revision-heading p { margin: 0; font-size: 12px; }
.bom-revision-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.bom-revision-list li { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 12px; padding: 8px 10px; border-radius: 6px; background: var(--el-bg-color); }
.bom-revision-main, .bom-revision-numbers { display: grid; gap: 2px; min-width: 0; }
.bom-revision-main small, .bom-revision-numbers small { font-size: 12px; }
.bom-revision-arrow { font-size: 13px; overflow-wrap: anywhere; }
.bom-revision-numbers { justify-items: end; text-align: right; }
.bom-revision-numbers span { font-size: 13px; }
.bom-revision-history summary { cursor: pointer; font-size: 13px; }
.bom-revision-history ul { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 6px; }
.bom-revision-history li { display: grid; gap: 2px; padding: 6px 8px; border-radius: 6px; background: var(--el-bg-color); font-size: 13px; }
.bom-revision-history small { font-size: 12px; }
@media (max-width: 640px) {
  .bom-revision-list li { grid-template-columns: minmax(0, 1fr) auto; }
  .bom-revision-numbers { grid-column: 1; justify-items: start; text-align: left; }
  .bom-revision-list .el-dropdown { grid-column: 2; grid-row: 1 / span 2; }
}
</style>
