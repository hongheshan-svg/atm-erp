<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { all, read } from '../api'
import { message } from '../utils/request'
import { termLabel } from '../modules/payment-terms'
import type { Command, Row } from '../types'
import ActionDialog from '../components/ActionDialog.vue'
import { buyer } from '../modules/shared'
const route = useRoute()
const data = ref<Row | null>(null), error = ref(''), loading = ref(false)
const appendix = ref(false)
const packagePrint = ref(false), selectedVersion = ref(''), command = ref<Command | null>(null)
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
  try { data.value = await read(`/business/purchases/${route.params.id}/contract-preview/`, selectedVersion.value ? { version: selectedVersion.value } : {}) }
  catch (e) { error.value = message(e) }
  finally { loading.value = false }
}
watch(() => route.params.id, () => { selectedVersion.value = ''; packagePrint.value = false; void load() }, { immediate: true })
function print() { window.print() }
async function archive() {
  if (!data.value || data.value.archived_version) return
  const docs = await all('/business/documents/', { purchase: route.params.id, category: 'contract' })
  command.value = {
    title: '归档已签署合同版本', path: `/business/purchases/${route.params.id}/archive-contract/`,
    fields: [
      { key: 'document', label: '已签署合同附件', type: 'select', options: docs.map(d => ({ value: d.id, label: d.original_name })) },
      { key: 'delivery_address', label: '双方确认的收货地址' },
      { key: 'reason', label: '归档或修订原因', type: 'textarea' },
      { key: 'confirmed', label: '已核对签署文件与本版正文、明细及收货地址一致', type: 'boolean', initial: false },
    ],
    prepare: values => ({ ...values, expected_snapshot: data.value!.snapshot_hash }),
    notice: { type: 'warning', text: '先在采购附件中上传双方签署的完整合同。归档后本版资料不可覆盖；后续修订创建新版本，金额仍以原采购业务为准。' },
  }
}
</script>
<template>
  <section class="purchase-contract-page" v-loading="loading">
    <div class="contract-toolbar">
      <router-link :to="{ path: '/purchases', query: { resource: 'purchases', focus: String(route.params.id) } }">返回采购单</router-link>
      <div><el-button :disabled="loading" @click="load">刷新预览</el-button><el-button :disabled="!data || loading" @click="appendix = !appendix">{{ appendix ? '查看合同正文' : '查看完整附件' }}</el-button><el-button type="primary" :disabled="!data || loading" @click="print">打印 / 另存为 PDF</el-button></div>
    </div>
    <el-alert v-if="error" type="error" :title="error" :closable="false" />
    <div v-if="data" class="contract-toolbar">
      <label>合同版本 <select v-model="selectedVersion" aria-label="合同版本" @change="load"><option value="">最新归档（无归档时当前资料）</option><option value="current">当前采购资料 · 待确认</option><option v-for="v in data.versions" :key="v.version" :value="String(v.version)">已归档第 {{ v.version }} 版</option></select></label>
      <label><input v-model="packagePrint" type="checkbox"> 正文与完整附件一起打印</label>
      <el-button v-if="buyer() && !data.draft && !data.archived_version && data.status !== 'cancelled'" @click="archive().catch(e => error = message(e))">归档签署版本</el-button>
      <span>{{ data.archived_version ? `当前为已归档第 ${data.archived_version} 版，资料保持不变` : '当前采购资料预览，尚未归档签署版本' }}</span>
    </div>
    <p class="contract-help">正文按单页 A4 排版，完整附件允许分页；勾选整套打印可一次输出正文与附件。签署文件请从采购附件查看，归档前需补齐双方资料并核对收货地址。</p>
    <template v-if="data"><article v-for="sheet in (packagePrint ? [false, true] : [appendix])" :key="String(sheet)" class="contract-paper" :class="{ 'contract-appendix': sheet }" aria-label="采购合同预览">
      <h1>采购合同<span v-if="data.draft">（草稿 · 未批准）</span><span v-else-if="data.status === 'cancelled'">（已取消）</span></h1>
      <p v-if="sheet" class="contract-state">附件：完整采购明细、主体资料及补充约定</p>
      <div class="contract-meta"><span>合同编号：{{ data.code }}</span><span>制单日期：{{ data.date }}</span></div>
      <p v-if="Number(data.cancelled_amount) > 0" class="contract-state">已有取消余量，请结合原合同及变更记录核对。</p>
      <div class="contract-parties">
        <section><h2>甲方（采购方）</h2><p>名称：{{ sheet ? data.buyer.name : brief(data.buyer.name, 45) }}</p><p>地址：{{ sheet ? data.buyer.address : brief(data.buyer.address) }}</p><p>电话：{{ data.buyer.phone || '________________' }}</p></section>
        <section><h2>乙方（供货方）</h2><p>名称：{{ sheet ? data.supplier.name : brief(data.supplier.name, 45) }}</p><p>地址：{{ sheet ? data.supplier.address : brief(data.supplier.address) }}</p><p>联系人：{{ sheet ? data.supplier.contact : brief(data.supplier.contact, 30) }}；电话：{{ data.supplier.phone || '________________' }}</p></section>
      </div>
      <p>项目：{{ sheet ? data.project : brief(data.project, 60) }}</p>
      <p v-if="data.delivery_address">收货地址：{{ sheet ? data.delivery_address : brief(data.delivery_address, 60) }}</p>
      <h2>一、采购明细（CNY 人民币，含税）</h2>
      <p v-if="summarized && !sheet">共 {{ data.lines.length }} 项物料，编码、名称、规格、品牌、数量、单价及逐项交期详见同编号合同附件。</p>
      <div v-else class="contract-table-wrap"><table><thead><tr><th>序号</th><th>物料编码 / 名称</th><th>规格 / 品牌</th><th>单位</th><th>数量</th><th>含税单价</th><th>含税金额</th><th>交期</th></tr></thead><tbody><tr v-for="line in data.lines" :key="line.number"><td>{{ line.number }}</td><td>{{ line.code }}<br>{{ line.name }}</td><td>{{ line.specification || '—' }}<br>{{ line.brand }}</td><td>{{ line.unit }}</td><td>{{ line.quantity }}<small v-if="Number(line.cancelled_quantity) > 0">已取消 {{ line.cancelled_quantity }}</small></td><td>{{ line.unit_price }}</td><td>{{ line.amount }}</td><td>{{ line.due_date }}</td></tr></tbody></table></div>
      <p class="contract-total">订单原含税合计：人民币 ¥ {{ data.total }}</p>
      <template v-if="!sheet">
        <h2>二、交付与结算</h2><p>订单交期：{{ data.due_date }}；逐项交期以明细为准。乙方负责适运包装并交至甲方书面指定地点，运输及包装费用含于合同价，另有书面约定除外。</p><p>{{ payment }} 乙方按约提供合法有效发票；甲方按约支付无争议到期款项。</p>
        <h2>三、质量、验收与一年质保</h2>
        <p v-for="clause in data.clauses.quality" :key="clause">{{ clause }}</p>
        <h2>四、违约责任与其他约定</h2>
        <p v-for="clause in data.clauses.liability" :key="clause">{{ clause }}</p>
      </template>
      <h2>{{ sheet ? '二' : '五' }}、补充约定</h2><p class="contract-note">{{ data.note ? (sheet ? data.note : brief(data.note, 90)) : '无；其他事项由双方另行书面确认。' }}</p>
      <div class="contract-signatures"><section><p>甲方签字 / 盖章：________________</p><p>签署日期：________________</p></section><section><p>乙方签字 / 盖章：________________</p><p>签署日期：________________</p></section></div>
    </article></template>
    <ActionDialog :command="command" @close="command = null" @saved="selectedVersion = ''; load()" />
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
  body:has(.purchase-contract-page) .el-message,
  body:has(.purchase-contract-page) .el-notification,
  body:has(.purchase-contract-page) .el-overlay,
  body:has(.purchase-contract-page) .el-loading-mask { display:none !important; }
  html:has(.purchase-contract-page),body:has(.purchase-contract-page) { background:white; }
  body:has(.purchase-contract-page) .sidebar,body:has(.purchase-contract-page) .topbar,.contract-toolbar,.contract-help { display:none !important; }
  body:has(.purchase-contract-page) .shell { display:block; min-height:0; background:white; }body:has(.purchase-contract-page) main,body:has(.purchase-contract-page) .content { margin:0; padding:0; width:auto; min-height:0; background:white; }
  .contract-paper { width:100%; max-width:none; margin:0; padding:0; box-shadow:none; font-size:9pt; line-height:1.5; }
  .contract-paper + .contract-paper { break-before:page; }
  .contract-table-wrap { overflow:visible; }.contract-paper table { min-width:0; table-layout:fixed; font-size:9pt; }.contract-paper th,.contract-paper td { overflow-wrap:anywhere; white-space:normal; }.contract-paper th:nth-child(1) { width:4%; }.contract-paper th:nth-child(2) { width:25%; }.contract-paper th:nth-child(3) { width:20%; }.contract-paper th:nth-child(4) { width:5%; }.contract-paper th:nth-child(5) { width:8%; }.contract-paper th:nth-child(6),.contract-paper th:nth-child(7) { width:11%; }.contract-paper th:nth-child(8) { width:16%; }.contract-paper thead { display:table-header-group; }.contract-paper tr,.contract-signatures { break-inside:avoid; }
}
</style>
