<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { read } from '../api'
import { message } from '../utils/request'
import { termLabel } from '../modules/payment-terms'
import type { Row } from '../types'
const route = useRoute()
const data = ref<Row | null>(null), error = ref(''), loading = ref(false)
const appendix = ref(false)
const summarized = computed(() => {
  const d = data.value
  if (!d) return false
  const text = [d.buyer.name, d.buyer.address, d.supplier.name, d.supplier.address, d.supplier.contact, d.project, d.note].map(value => brief(value)).join('')
  return d.lines.length > 1 || text.length > 200 || d.lines.some((line: Row) => `${line.code}${line.name}${line.specification}${line.brand}${line.unit}`.length > 85)
})
function brief(value: unknown, limit = 70) { const text = String(value || '________________').replace(/\s+/g, ' '); return text.length > limit ? '详见同编号合同附件' : text }
const payment = computed(() => {
  if (!data.value) return ''
  const d = data.value
  if (d.payment_term === 'manual') return `指定付款日期：${d.payment_due_date}`
  if (d.payment_term === 'cash') return '现付：按实际合格收货日付款。'
  return `${termLabel(d)}：每批合格收货当月月底加 ${d.payment_days} 个自然日；跨月收货分别计算。`
})
async function load() {
  loading.value = true; data.value = null; error.value = ''; appendix.value = false
  try { data.value = await read(`/business/purchases/${route.params.id}/contract-preview/`) }
  catch (e) { error.value = message(e) }
  finally { loading.value = false }
}
watch(() => route.params.id, load, { immediate: true })
function print() { window.print() }
</script>
<template>
  <section class="purchase-contract-page" v-loading="loading">
    <div class="contract-toolbar">
      <router-link :to="{ path: '/purchases', query: { resource: 'purchases', focus: String(route.params.id) } }">返回采购单</router-link>
      <div><el-button :disabled="loading" @click="load">刷新预览</el-button><el-button :disabled="!data || loading" @click="appendix = !appendix">{{ appendix ? '查看合同正文' : '查看完整附件' }}</el-button><el-button type="primary" :disabled="!data || loading" @click="print">打印 / 另存为 PDF</el-button></div>
    </div>
    <el-alert v-if="error" type="error" :title="error" :closable="false" />
    <p class="contract-help">合同正文按单页 A4 排版；明细较多或内容较长时列入同编号附件，可单独预览、打印完整附件。请将正文与附件一并确认签署，再上传采购附件保存。</p>
    <article v-if="data" class="contract-paper" :class="{ 'contract-appendix': appendix }" aria-label="采购合同预览">
      <h1>采购合同<span v-if="data.draft">（草稿 · 未批准）</span><span v-else-if="data.status === 'cancelled'">（已取消）</span></h1>
      <p v-if="appendix" class="contract-state">附件：完整采购明细、主体资料及补充约定</p>
      <div class="contract-meta"><span>合同编号：{{ data.code }}</span><span>制单日期：{{ data.date }}</span></div>
      <p v-if="Number(data.cancelled_amount) > 0" class="contract-state">已有取消余量，请结合原合同及变更记录核对。</p>
      <div class="contract-parties">
        <section><h2>甲方（采购方）</h2><p>名称：{{ appendix ? data.buyer.name : brief(data.buyer.name, 45) }}</p><p>地址：{{ appendix ? data.buyer.address : brief(data.buyer.address) }}</p><p>电话：{{ data.buyer.phone || '________________' }}</p></section>
        <section><h2>乙方（供货方）</h2><p>名称：{{ appendix ? data.supplier.name : brief(data.supplier.name, 45) }}</p><p>地址：{{ appendix ? data.supplier.address : brief(data.supplier.address) }}</p><p>联系人：{{ appendix ? data.supplier.contact : brief(data.supplier.contact, 30) }}；电话：{{ data.supplier.phone || '________________' }}</p></section>
      </div>
      <p>项目：{{ appendix ? data.project : brief(data.project, 60) }}</p>
      <h2>一、采购明细（CNY 人民币，含税）</h2>
      <p v-if="summarized && !appendix">共 {{ data.lines.length }} 项物料，编码、名称、规格、品牌、数量、单价及逐项交期详见同编号合同附件。</p>
      <div v-else class="contract-table-wrap"><table><thead><tr><th>序号</th><th>物料编码 / 名称</th><th>规格 / 品牌</th><th>单位</th><th>数量</th><th>含税单价</th><th>含税金额</th><th>交期</th></tr></thead><tbody><tr v-for="line in data.lines" :key="line.number"><td>{{ line.number }}</td><td>{{ line.code }}<br>{{ line.name }}</td><td>{{ line.specification || '—' }}<br>{{ line.brand }}</td><td>{{ line.unit }}</td><td>{{ line.quantity }}<small v-if="Number(line.cancelled_quantity) > 0">已取消 {{ line.cancelled_quantity }}</small></td><td>{{ line.unit_price }}</td><td>{{ line.amount }}</td><td>{{ line.due_date }}</td></tr></tbody></table></div>
      <p class="contract-total">订单原含税合计：人民币 ¥ {{ data.total }}</p>
      <template v-if="!appendix">
        <h2>二、交付与结算</h2><p>订单交期：{{ data.due_date }}；逐项交期以明细为准。乙方负责适运包装并交至甲方书面指定地点，运输及包装费用含于合同价，另有书面约定除外。</p><p>{{ payment }} 乙方按约提供合法有效发票；甲方按约支付无争议到期款项。</p>
        <h2>三、质量、验收与一年质保</h2>
        <p>乙方保证货物为符合约定的全新合格品，品牌、规格及性能符合明细、双方确认的图纸和技术要求，并满足适用的强制性标准；随货提供合格证明及必要资料，未经甲方书面同意不得替换。</p>
        <p>甲方到货后及时核验数量、外观及技术指标，发现不符及时书面通知乙方；签收不等于质量验收。隐蔽缺陷发现后及时提出，不因外观验收而免除乙方责任。</p>
        <p><strong>质保期为各批货物验收合格之日起一年。</strong>质保期内因产品质量问题，乙方免费维修或更换，承担必要运输、拆装费用，并在接到通知后及时响应、在双方确认期限内处理；非质量原因损坏由双方确认处理费用。法定责任或另行承诺的更长质保不受本条缩短。</p>
        <h2>四、违约责任与其他约定</h2>
        <p>迟延交货、逾期付款或质量不符的，违约方应及时纠正并依法赔偿可归责的损失；质量不符可要求修理、更换、减价，符合法定或约定条件时退货、解除合同及退还相应价款。违约金有双方书面约定的按约处理，受损方应采取合理措施防止损失扩大。</p>
        <p>不可抗力影响履约时，应及时通知、提供证明并减轻损失，依法按影响程度处理责任。双方对图纸、价格及商业资料负保密义务，依法披露除外。变更须经双方书面确认；争议先协商，协商不成向有管辖权的人民法院起诉。</p>
        <p>本合同经双方授权代表签字或盖章生效，一式两份，各执一份。同编号附件经双方确认后为合同组成部分；补充约定与正文不一致的，以双方明确确认的补充约定为准。</p>
      </template>
      <h2>{{ appendix ? '二' : '五' }}、补充约定</h2><p class="contract-note">{{ data.note ? (appendix ? data.note : brief(data.note, 90)) : '无；其他事项由双方另行书面确认。' }}</p>
      <div class="contract-signatures"><section><p>甲方签字 / 盖章：________________</p><p>签署日期：________________</p></section><section><p>乙方签字 / 盖章：________________</p><p>签署日期：________________</p></section></div>
    </article>
  </section>
</template>
<style>
.contract-toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:16px; }
.contract-help { color:#667085; line-height:1.7; }
.contract-paper { box-sizing:border-box; max-width:210mm; margin:20px auto; padding:16mm 12mm; background:white; color:#182230; box-shadow:0 4px 24px #16283a12; font-size:13px; line-height:1.7; overflow-wrap:anywhere; }
.contract-paper h1 { text-align:center; font-size:24px; margin:0 0 10px; }.contract-paper h1 span { display:block; font-size:12px; }
.contract-paper h2 { font-size:13px; margin:10px 0 4px; }.contract-paper p { margin:3px 0; }
.contract-meta,.contract-parties,.contract-signatures { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.contract-state { font-weight:600; }.contract-table-wrap { overflow-x:auto; }
.contract-paper table { width:100%; border-collapse:collapse; font-size:11px; }.contract-paper th,.contract-paper td { border:1px solid #667085; padding:6px; text-align:left; vertical-align:top; }.contract-paper th { background:#f3f5f8; }.contract-paper small { display:block; }
.contract-total { text-align:right; font-weight:700; }.contract-note { white-space:pre-wrap; }.contract-signatures { margin-top:18px; }
@media screen and (max-width:700px) { .contract-paper { padding:20px 12px; }.contract-meta,.contract-parties,.contract-signatures { grid-template-columns:1fr; gap:8px; }.contract-paper table { min-width:650px; } }
@media print {
  @page { size:A4; margin:12mm; }
  html:has(.purchase-contract-page),body:has(.purchase-contract-page) { background:white; }
  body:has(.purchase-contract-page) .sidebar,body:has(.purchase-contract-page) .topbar,.contract-toolbar,.contract-help { display:none !important; }
  body:has(.purchase-contract-page) .shell { display:block; min-height:0; background:white; }body:has(.purchase-contract-page) main,body:has(.purchase-contract-page) .content { margin:0; padding:0; width:auto; min-height:0; background:white; }
  .contract-paper { width:100%; max-width:none; margin:0; padding:0; box-shadow:none; font-size:9pt; line-height:1.5; }
  .contract-table-wrap { overflow:visible; }.contract-paper table { min-width:0; table-layout:fixed; font-size:9pt; }.contract-paper th,.contract-paper td { overflow-wrap:anywhere; white-space:normal; }.contract-paper th:nth-child(1) { width:4%; }.contract-paper th:nth-child(2) { width:25%; }.contract-paper th:nth-child(3) { width:20%; }.contract-paper th:nth-child(4) { width:5%; }.contract-paper th:nth-child(5) { width:8%; }.contract-paper th:nth-child(6),.contract-paper th:nth-child(7) { width:11%; }.contract-paper th:nth-child(8) { width:16%; }.contract-paper thead { display:table-header-group; }.contract-paper tr,.contract-signatures { break-inside:avoid; }
}
</style>
