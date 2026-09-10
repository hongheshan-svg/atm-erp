<script setup lang="ts">
import { ref, watch } from 'vue'
import { read } from '../api'
import { manager } from '../session'
import { message } from '../utils/request'
import type { Command, Row } from '../types'
import ActionDialog from './ActionDialog.vue'
import CostSources from './CostSources.vue'
const showSources = ref(false)
const amount = (value: unknown) => { if (value == null) return '未设置'; const [integer, fraction = ''] = String(value).split('.'); return `${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}` }
const props = defineProps<{ projectId: number; revision: number; status: string; canManage?: boolean }>()
const report = ref<Row | null>(null)
const error = ref('')
const command = ref<Command | null>(null)
let generation = 0
async function load() {
  const current = ++generation
  error.value = ''
  try {
    const value = await read(`/business/projects/${props.projectId}/cost-analysis/`)
    if (current === generation) report.value = value
  } catch (e) {
    if (current === generation) error.value = message(e)
  }
}
watch(() => [props.projectId, props.revision], load, { immediate: true })
function edit() {
  if (!report.value) return
  const version = report.value.budget_revision
  command.value = {
    title: '设置项目预算', path: `/business/projects/${props.projectId}/budget/`,
    fields: [
      { key: 'materials', label: '材料预算（元）', initial: '0.00' },
      { key: 'labor', label: '人工预算（元）', initial: '0.00' },
      { key: 'expenses', label: '费用预算（元）', initial: '0.00' },
      { key: 'reason', label: '原因 / 说明', type: 'textarea' },
    ],
    initial: Object.fromEntries(report.value.rows.map((row: Row) => [row.key, row.budget ?? '0.00'])),
    notice: { type: 'info', text: '预算为 CNY 含税经营口径。0 表示零额度；保存后启用预算检查，所有修改保留审计。' },
    prepare: data => ({ ...data, expected_revision: version }),
  }
}
function estimate() {
  if (!report.value) return
  const version = report.value.forecast_revision
  command.value = { title: '更新完工估算', path: `/business/projects/${props.projectId}/forecast/`, fields: [
    { key: 'remaining_materials', label: '预计剩余材料成本（元）', hint: '包含未来领用共享库存和未下单材料；排除已计入实际成本、在途采购的部分。' }, { key: 'remaining_labor', label: '预计剩余人工成本（元）' }, { key: 'remaining_expenses', label: '预计剩余费用（元）' }, { key: 'reason', label: '估算依据', type: 'textarea' },
  ], initial: { remaining_materials: report.value.remaining_materials ?? '', remaining_labor: report.value.remaining_labor ?? '0.00', remaining_expenses: report.value.remaining_expenses ?? '0.00' }, notice: { type: 'info', text: '估算不生成成本或付款流水。预测包含实际、在途及剩余材料、人工和费用。材料估算需扣除已计入实际和在途部分，避免重复。' }, prepare: data => ({ ...data, expected_revision: version }) }
}
</script>
<template>
  <section class="panel" aria-label="项目预算与成本管控">
    <header class="panel-heading">
      <h2>预算与成本管控</h2>
      <el-button @click="showSources = true">追溯成本明细</el-button>
      <div class="toolbar"><el-button @click="load">刷新</el-button><el-button v-if="manager() && canManage !== false && ['active', 'delivering', 'warranty'].includes(status)" @click="edit" :disabled="!report || Boolean(error)">设置预算</el-button></div>
    </header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <template v-if="report">
      <el-alert v-if="!report.configured" title="尚未设置预算，当前仅展示成本，不拦截采购审批。" type="info" :closable="false" />
      <el-alert v-else-if="report.over_budget" :title="report.warnings.join('；')" type="warning" :closable="false" show-icon role="alert" />
      <el-table :data="report.rows" style="width:100%">
        <el-table-column prop="label" label="类别" min-width="95" />
        <el-table-column label="预算（元）" min-width="135" align="right"><template #default="{row}">{{ amount(row.budget) }}</template></el-table-column>
        <el-table-column prop="actual" :formatter="(row: Row) => amount(row.actual)" label="实际成本" min-width="135" align="right" />
        <el-table-column prop="committed" :formatter="(row: Row) => amount(row.committed)" label="已承诺（在途）" min-width="145" align="right" />
        <el-table-column prop="occupied" :formatter="(row: Row) => amount(row.occupied)" label="实际＋在途" min-width="140" align="right" />
        <el-table-column label="预算余量" min-width="135" align="right"><template #default="{row}"><span :class="{ 'budget-overrun': Number(row.remaining) < 0 }">{{ amount(row.remaining) }}</span></template></el-table-column>
      </el-table>
      <div class="budget-totals"><span>预算合计 <strong>{{ report.budget_total ?? '未设置' }}</strong></span><span>实际＋在途合计 <strong>¥ {{ report.occupied_total }}</strong></span><span>累计采购净额 <strong>¥ {{ report.purchase_net }}</strong></span></div>
      <p class="muted budget-basis">已承诺仅含已批准未收货采购；实际材料含退货价差。人工、费用仅计已有实际记录，未付款费用不重复计入承诺。累计采购净额另与材料预算比较，收货不会释放采购额度；以上不代表完工成本预测。</p>
      <div class="budget-totals"><span>预计剩余材料 {{ report.remaining_materials ?? '未估算' }}</span><span>预计剩余人工 {{ report.remaining_labor ?? '未估算' }}</span><span>预计剩余费用 {{ report.remaining_expenses ?? '未估算' }}</span><strong :class="{ 'budget-overrun': report.configured && report.forecast_total != null && Number(report.forecast_total) > Number(report.budget_total) }">预计完工成本 {{ report.forecast_total ?? '未完整估算' }}</strong><el-button v-if="manager() && canManage !== false && ['active', 'delivering', 'warranty'].includes(status)" @click="estimate" :disabled="Boolean(error)">更新完工估算</el-button></div>
      <p class="muted">完工估算包含实际、在途及剩余材料、人工和费用，不记入实际成本。估算人：{{ report.forecast_by || '—' }} · 更新于 {{ report.forecast_at ? new Date(report.forecast_at).toLocaleString() : '—' }}。{{ report.forecast_stale ? '估算待复核：项目已变更、尚未估算或超过30天。' : '' }}</p>
    </template>
    <ActionDialog :command="command" @close="command = null" @saved="load" />
    <el-dialog v-model="showSources" title="成本来源与主要贡献" width="min(960px, 94vw)" destroy-on-close><CostSources v-if="showSources" :project-id="projectId" /></el-dialog>
  </section>
</template>
<style scoped>
.budget-totals { display: flex; flex-wrap: wrap; gap: 16px 28px; margin-top: 20px; font-size: 13px; }
.budget-totals strong { margin-left: 8px; font-variant-numeric: tabular-nums; }
.budget-basis { font-size: 12px; line-height: 1.8; margin-bottom: 0; }
.budget-overrun { color: #b74333; font-weight: 600; }
</style>
