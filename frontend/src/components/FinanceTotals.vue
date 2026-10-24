<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { read } from '../api'
import { message } from '../utils/request'
import { money } from '../utils/money'
import type { Row } from '../types'
const props = defineProps<{ projectId?: number; revision?: number }>()
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
const cards = computed(() => {
  const row = data.value
  if (!row) return []
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
    const result = await read('/business/entries/summary/', { project: props.projectId })
    if (current === generation) data.value = result
  } catch (e) {
    if (current === generation) error.value = message(e)
  }
}
watch(() => [props.projectId, props.revision], load, { immediate: true })
</script>
<template>
  <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
  <div v-else-if="cards.length" class="finance-totals" aria-label="往来款项余额">
    <section v-for="card in cards" :key="card.key" class="panel finance-total" :class="{ 'finance-muted': card.muted }" :aria-label="card.label">
      <span>{{ card.label }}</span>
      <strong :class="{ 'finance-risk': card.risk && Number(card.value) }">{{ money(card.value, { currency: true }) }}</strong>
      <small>{{ card.note }}</small>
    </section>
  </div>
</template>
<style scoped>
.finance-totals { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-bottom: 12px; padding: 12px; background: white; border: 1px solid var(--surface-border); border-radius: 8px; }
.finance-total { display: grid; gap: 6px; margin: 0; padding: 14px 16px; }
.finance-total span { color: var(--ink-4); font-size: 13px; }
.finance-total strong { color: var(--brand); font-size: 27px; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
.finance-total small { color: var(--ink-6); font-size: 12px; line-height: 1.6; font-variant-numeric: tabular-nums; }
.finance-risk { color: var(--risk); }
.finance-muted { opacity: 0.55; }
@media (max-width: 560px) { .finance-total { padding: 16px; } .finance-total strong { font-size: 21px; } }
</style>
