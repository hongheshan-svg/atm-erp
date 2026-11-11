<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { read } from '../api'
import { message } from '../utils/request'
import { money } from '../utils/money'
import type { Row } from '../types'
// project：项目收付款页签的汇总口径（应收合计 / 已收 / 未收，应付含费用），而不是全公司余额卡。
const props = defineProps<{ projectId?: number; revision?: number; project?: boolean }>()
const data = ref<Row | null>(null)
const error = ref('')
let generation = 0
// 金额是后端返回的两位小数字符串，按「分」用 BigInt 相加，避免 Number 的浮点误差。
function toCents(value: unknown): bigint {
  if (value == null || value === '') return 0n
  const match = /^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec(String(value).trim())
  if (!match) throw new Error(`无法识别的金额：${String(value)}`)
  const [, sign, whole, fraction = ''] = match
  const cents = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))
  return sign ? -cents : cents
}
function centsToAmount(cents: bigint): string {
  const abs = cents < 0n ? -cents : cents
  const text = `${abs / 100n}.${(abs % 100n).toString().padStart(2, '0')}`
  return cents < 0n ? `-${text}` : text
}
const overdue = computed(() => {
  const row = data.value
  if (!row) return '0.00'
  return centsToAmount(toCents(row.overdue_receivable) + toCents(row.overdue_payable))
})
const sum = (...values: unknown[]) => centsToAmount(values.reduce<bigint>((total, value) => total + toCents(value), 0n))
type Card = { key: string; label: string; value: unknown; note: string; risk: boolean; muted?: boolean; alert?: boolean }
const projectCards = computed((): Card[] => {
  const row = data.value
  if (!row?.receivable) return []
  const receivable = row.receivable, payable = row.payable || {}, expense = row.expense || {}
  const payableOverdue = sum(payable.overdue, expense.overdue)
  return [
    { key: 'receivable_total', label: '应收合计', value: receivable.total, note: `${receivable.count ?? 0} 笔，已扣除合同减额`, risk: false },
    { key: 'received', label: '已收', value: receivable.settled, note: '已登记的客户收款', risk: false },
    { key: 'unreceived', label: '未收', value: receivable.outstanding, risk: false, alert: toCents(receivable.overdue) > 0n,
      note: toCents(receivable.overdue) > 0n ? `其中逾期 ${money(receivable.overdue)}` : '暂无逾期应收' },
    { key: 'payable_total', label: '应付合计（含费用）', value: sum(payable.total, expense.total), note: `采购 ${money(payable.total)} · 费用 ${money(expense.total)}`, risk: false },
    { key: 'paid', label: '已付', value: sum(payable.settled, expense.settled), note: '已登记的付款', risk: false },
    { key: 'unpaid', label: '未付', value: sum(payable.outstanding, expense.outstanding), risk: false, alert: toCents(payableOverdue) > 0n,
      note: toCents(payableOverdue) > 0n ? `其中逾期 ${money(payableOverdue)}` : '暂无逾期应付' },
  ]
})
const cards = computed((): Card[] => {
  const row = data.value
  if (!row) return []
  if (props.project) return projectCards.value
  return [
    { key: 'receivable', label: '待收款', value: row.receivable, note: '应收余额，不含待退客户款', risk: false },
    { key: 'payable', label: '待付款', value: row.payable, note: '采购与费用余额，不含待收退款', risk: false },
    // 逾期是同一批余额里的一部分，单独一张卡说明「其中」多少已经过期。
    { key: 'overdue', label: '其中已逾期', value: overdue.value, risk: true,
      note: `待收 ${money(row.overdue_receivable)} · 待付 ${money(row.overdue_payable)}` },
    // 退款是反向余额，不并入待收/待付；为 0 时淡化，避免干扰主要数字。
    { key: 'refund_out', label: '待退客户款', value: centsToAmount(toCents(row.refund_out)), risk: false, muted: toCents(row.refund_out) === 0n,
      note: '客户多付或取消后应退还的款项' },
    { key: 'refund_in', label: '待收退款', value: centsToAmount(toCents(row.refund_in)), risk: false, muted: toCents(row.refund_in) === 0n,
      note: '供应商多收或取消后应退回的款项' },
  ]
})
async function load() {
  const current = ++generation
  error.value = ''
  try {
    const result = props.project
      ? await read(`/business/projects/${props.projectId}/finance-summary/`)
      : await read('/business/entries/summary/', { project: props.projectId })
    if (current === generation) data.value = result
  } catch (e) {
    if (current === generation) error.value = message(e)
  }
}
watch(() => [props.projectId, props.revision], load, { immediate: true })
</script>
<template>
  <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
  <div v-else-if="cards.length" class="finance-totals" :aria-label="project ? '项目款项汇总' : '往来款项余额'">
    <section v-for="card in cards" :key="card.key" class="panel finance-total" :class="{ 'finance-muted': card.muted }" :aria-label="card.label">
      <span>{{ card.label }}</span>
      <strong :class="{ 'finance-risk': card.risk && Number(card.value) }">{{ money(card.value, { currency: true }) }}</strong>
      <small :class="{ 'finance-risk': card.alert }">{{ card.note }}</small>
    </section>
  </div>
</template>
<style scoped>
.finance-totals { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); margin-bottom: 12px; background: white; border: 1px solid var(--surface-border); border-radius: 8px; overflow: hidden; }
.finance-total { display: grid; gap: 2px; margin: 0; padding: 10px 16px; border: 0; border-right: 1px solid var(--line-2); border-radius: 0; box-shadow: none; }
.finance-total:last-child { border-right: 0; }
.finance-total span { color: var(--ink-4); font-size: 12px; }
.finance-total strong { color: var(--brand-ink); font-size: 20px; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
.finance-total small { color: var(--ink-6); font-size: 11px; line-height: 1.5; font-variant-numeric: tabular-nums; }
.finance-risk { color: var(--risk); }
.finance-muted { opacity: 0.55; }
@media (max-width: 560px) { .finance-total { border-right: 0; border-bottom: 1px solid var(--line-2); } }
</style>
