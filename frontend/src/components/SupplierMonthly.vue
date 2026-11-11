<script setup lang="ts">
import BusinessTable from './BusinessTable.vue'
import { onBeforeUnmount, ref, watch } from 'vue'
import { ElDatePicker } from 'element-plus'
import { read } from '../api'
import { message } from '../utils/request'
import type { Command, Row } from '../types'
import ActionDialog from './ActionDialog.vue'
import RemoteSelect from './RemoteSelect.vue'
import { can } from '../session'
import { today } from '../forms'
// 往来单位统一走 RemoteSelect（见 modules/shared）：按输入分页搜索非客户单位，不再每次打开都整表下载。
// 不限在用：已停用的供应商仍可能有待月结的收货和付款。
const notCustomer = (partner: Row) => partner.kind !== 'customer'
const supplier = ref<string | number>(), month = ref(today().slice(0, 7))
// 报告抬头用的供应商名称：报告本身只带 ID，查询时一并读取所选供应商资料（读不到只显示编号，不影响报告）。
const supplierName = ref('')
const data = ref<Row | null>(null), error = ref(''), busy = ref(false), command = ref<Command | null>(null)
const feedback = ref('')
let generation = 0
// 手机宽度：月份用中文月份选择器并让标签在输入框上方，明细改为逐行卡片，免得表格横滚。
const narrow = ref(typeof window !== 'undefined' && !!window.matchMedia?.('(max-width: 600px)').matches)
if (typeof window !== 'undefined' && window.matchMedia) {
  const query = window.matchMedia('(max-width: 600px)')
  const sync = () => { narrow.value = query.matches }
  query.addEventListener?.('change', sync)
  onBeforeUnmount(() => query.removeEventListener?.('change', sync))
}
watch([supplier, month], () => { generation++; data.value = null; command.value = null; busy.value = false; feedback.value = '' }, { flush: 'sync' })
onBeforeUnmount(() => { generation++ })
async function load() {
  if (supplier.value == null || supplier.value === '') { error.value = '请选择供应商。'; return }
  const current = ++generation
  busy.value = true; error.value = ''; data.value = null
  try {
    const [report, partner] = await Promise.all([
      read('/business/reconciliations/supplier-monthly/', { supplier: supplier.value, month: month.value }),
      read(`/business/partners/${encodeURIComponent(String(supplier.value))}/`).catch(() => null),
    ])
    if (current === generation) { data.value = report; supplierName.value = String(partner?.name || '') }
  }
  catch (e) { if (current === generation) error.value = message(e) } finally { if (current === generation) busy.value = false }
}
function confirm() {
  const report = data.value!
  if (!report || String(report.supplier) !== String(supplier.value) || report.month !== month.value) return
  command.value = { title: '确认供应商月度对账', draftScope: `supplier:${report.supplier}:${report.month}`, path: '/business/reconciliations/supplier-monthly/',
    subject: `${supplierName.value || report.supplier} · ${report.month}`,
    fields: [{ key: 'counterparty_balance', label: '供应商确认的期末余额' }, { key: 'reason', label: '核对依据与说明', type: 'textarea', optional: true, placeholder: '选填；不填按「月结确认」记录' }],
    prepare: values => ({ ...values, supplier: report.supplier, month: report.month, expected_snapshot: report.snapshot_hash }),
    notice: { type: 'info', text: '按原收退货与付款核对。差异为零时，按各原应付当前可结算金额生成已确认对账单；不新增款项或付款。负余额和未收货预付继续从原应付处理。' },
  }
}
function saved(result: Row) {
  feedback.value = result.requires_advance_review ? '月度核对已记录；存在预付负余额，请先按原单确认退款或抵扣处理。本次未新增付款授权，不自动跨采购单抵扣。' : `月度核对已记录，生成 ${result.reconciliations.length} 笔原应付对账授权。`
  void load()
}
</script>
<template>
  <section class="panel" aria-label="供应商月度对账">
    <h2>供应商月度对账</h2>
    <form class="toolbar" @submit.prevent="load"><label class="supplier-picker">供应商 <RemoteSelect v-model="supplier" path="/business/partners/" label="对账供应商" :accept="notCustomer" required commit-on-select /></label><label>月份 <input v-if="!narrow" v-model="month" required type="month" aria-label="对账月份"><ElDatePicker v-else v-model="month" type="month" value-format="YYYY-MM" format="YYYY年MM月" :clearable="false" aria-label="对账月份" placeholder="选择月份" /></label><el-button native-type="submit" :loading="busy">查询月度对账</el-button></form>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="feedback" :title="feedback" type="info" :closable="false" />
    <template v-if="data">
      <p>当前报告：{{ supplierName || `供应商 #${data.supplier}` }} · {{ data.month }}</p>
      <p>截至 {{ data.through }}；期初 {{ data.totals.opening }} ＋ 收货 {{ data.totals.received }} － 退货 {{ data.totals.returned }} － 净付款 {{ data.totals.paid }} ＝ 期末 {{ data.totals.closing }} 元。</p>
      <p class="muted">按该供应商跨项目汇总，不受外层项目筛选影响；经理仅查看负责或参与项目。以合格收货及退货供应商贷项计账，隔离品、未收货合同额不计入；负余额表示预付净额。历史无收货日期的记录沿用创建日。</p>
      <BusinessTable v-if="!narrow" label="供应商月结" :data="data.rows" max-height="450" stripe><el-table-column prop="project_name" label="项目" /><el-table-column prop="code" label="采购单" /><el-table-column v-for="(label, key) in { opening: '期初', received: '收货', returned: '退货', paid: '净付款', closing: '期末' }" :key="key" :prop="key" :label="label" /><el-table-column label="原单"><template #default="{ row }"><router-link :to="{ path: '/finance', query: { section: 'entries', resource: 'entries', focus: row.entry } }">核对应付</router-link></template></el-table-column></BusinessTable>
      <ul v-else class="monthly-cards" aria-label="供应商月结明细"><li v-for="row in data.rows" :key="row.code"><strong>{{ row.code }} · {{ row.project_name }}</strong><dl><template v-for="(label, key) in { opening: '期初', received: '收货', returned: '退货', paid: '净付款', closing: '期末' }" :key="key"><dt>{{ label }}</dt><dd>{{ row[key] }}</dd></template></dl><router-link :to="{ path: '/finance', query: { section: 'entries', resource: 'entries', focus: row.entry } }">核对应付</router-link></li></ul>
      <el-button v-if="can(['admin', 'finance']) && data.rows.length" type="primary" @click="confirm">确认月度对账</el-button>
    </template>
    <ActionDialog :command="command" @close="command = null" @saved="saved" />
  </section>
</template>
<style scoped>
.supplier-picker { display: flex; align-items: flex-start; gap: 8px; }
.supplier-picker :deep(.remote-select) { width: min(360px, 70vw); }
.monthly-cards { list-style: none; margin: 0 0 12px; padding: 0; display: grid; gap: 10px; }
.monthly-cards li { border: 1px solid var(--surface-border); border-radius: 8px; padding: 10px 12px; }
.monthly-cards strong { display: block; overflow-wrap: anywhere; }
.monthly-cards dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px 10px; margin: 8px 0; }
.monthly-cards dt { font-size: 11px; color: var(--ink-4); }
.monthly-cards dd { margin: 0; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.monthly-cards a { display: inline-flex; align-items: center; min-height: 40px; }
@media (max-width: 600px) {
  .toolbar { flex-direction: column; align-items: stretch; gap: 12px; }
  .toolbar label { display: flex; flex-direction: column; gap: 6px; }
  .toolbar .supplier-picker :deep(.remote-select) { width: 100%; }
  .toolbar .supplier-picker :deep(.remote-input input) { min-height: 40px; }
  .toolbar :deep(.el-date-editor) { width: 100%; }
  .toolbar :deep(.el-date-editor .el-input__wrapper) { min-height: 40px; }
  .toolbar :deep(.el-date-editor input) { border: 0; box-shadow: none; padding: 0; min-height: 0; background: transparent; }
  .toolbar .el-button { min-height: 40px; }
}
</style>
