<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { all, read } from '../api'
import { message } from '../utils/request'
import type { Command, Row } from '../types'
import ActionDialog from './ActionDialog.vue'
import { can } from '../session'
import { today } from '../forms'
const suppliers = ref<Row[]>([]), supplier = ref(''), month = ref(today().slice(0, 7))
const data = ref<Row | null>(null), error = ref(''), busy = ref(false), command = ref<Command | null>(null)
const feedback = ref('')
onMounted(async () => { try { suppliers.value = (await all('/business/partners/')).filter(r => r.kind !== 'customer') } catch (e) { error.value = message(e) } })
async function load() {
  busy.value = true; error.value = ''; data.value = null
  try { data.value = await read('/business/reconciliations/supplier-monthly/', { supplier: supplier.value, month: month.value }) }
  catch (e) { error.value = message(e) } finally { busy.value = false }
}
function confirm() {
  const report = data.value!
  command.value = { title: '确认供应商月度对账', path: '/business/reconciliations/supplier-monthly/',
    fields: [{ key: 'counterparty_balance', label: '供应商确认的期末余额' }, { key: 'reason', label: '核对依据与说明', type: 'textarea' }],
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
    <form class="toolbar" @submit.prevent="load"><label>供应商 <select v-model="supplier" required aria-label="对账供应商"><option value="">请选择</option><option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.code }} · {{ s.name }}</option></select></label><label>月份 <input v-model="month" required type="month" aria-label="对账月份"></label><el-button native-type="submit" :loading="busy">查询月度对账</el-button></form>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="feedback" :title="feedback" type="info" :closable="false" />
    <template v-if="data">
      <p>截至 {{ data.through }}；期初 {{ data.totals.opening }} ＋ 收货 {{ data.totals.received }} － 退货 {{ data.totals.returned }} － 净付款 {{ data.totals.paid }} ＝ 期末 {{ data.totals.closing }} 元。</p>
      <p class="muted">按该供应商跨项目汇总，不受外层项目筛选影响；经理仅查看负责或参与项目。以合格收货及退货供应商贷项计账，隔离品、未收货合同额不计入；负余额表示预付净额。历史无收货日期的记录沿用创建日。</p>
      <el-table :data="data.rows" max-height="450" stripe><el-table-column prop="project_name" label="项目" /><el-table-column prop="code" label="采购单" /><el-table-column v-for="(label, key) in { opening: '期初', received: '收货', returned: '退货', paid: '净付款', closing: '期末' }" :key="key" :prop="key" :label="label" /><el-table-column label="原单"><template #default="{ row }"><router-link :to="{ path: '/finance', query: { section: 'entries', resource: 'entries', focus: row.entry } }">核对应付</router-link></template></el-table-column></el-table>
      <el-button v-if="can(['admin', 'finance']) && data.rows.length" type="primary" @click="confirm">确认月度对账</el-button>
    </template>
    <ActionDialog :command="command" @close="command = null" @saved="saved" />
  </section>
</template>
