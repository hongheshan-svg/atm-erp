<script setup lang="ts">
import { openDocumentPreview } from '../document-preview'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { all, read } from '../api'
import { message } from '../utils/request'
import { termLabel } from '../modules/payment-terms'
import type { Command, Row } from '../types'
import ActionDialog from '../components/ActionDialog.vue'
import { buyer } from '../modules/shared'
const route = useRoute()
const data = ref<Row | null>(null), error = ref(''), loading = ref(false)
const selectedVersion = ref(''), command = ref<Command | null>(null)
let generation = 0
onBeforeUnmount(() => { generation++ })
const payment = computed(() => {
  if (!data.value) return ''
  const d = data.value
  if (d.payment_term === 'manual') return `指定付款日期：${d.payment_due_date}`
  if (d.payment_term === 'cash') return '现付：按实际合格收货日付款。'
  return `${termLabel(d)}：每批合格收货当月月底加 ${d.payment_days} 个自然日；跨月收货分别计算。`
})
const sectionNumber = (index: number) => ['一', '二', '三', '四', '五', '六', '七'][index]
const sections = computed(() => {
  const d = data.value
  if (!d) return []
  const warranty = `${d.warranty_months || 12}个月`
  // Read only this version's stored clauses: new template wording must never leak into signed history.
  return [
    ...(d.clauses?.technical?.length ? [{ key: 'technical', title: '技术要求与图纸版本', paragraphs: d.clauses.technical }] : []),
    { key: 'delivery', title: '交付与结算', paragraphs: [
      `订单交期：${d.due_date}；逐项交期以明细为准。乙方负责适运包装并交至甲方书面指定地点，运输及包装费用含于合同价，另有书面约定除外。`,
      `${payment.value} 乙方按约提供合法有效发票；甲方按约支付无争议到期款项。`,
    ] },
    { key: 'quality', title: `质量、验收与${warranty}质保`, paragraphs: d.clauses?.quality || [] },
    ...(d.clauses?.automation?.length ? [{ key: 'automation', title: '非标自动化配套与变更', paragraphs: d.clauses.automation }] : []),
    { key: 'liability', title: '违约责任与其他约定', paragraphs: d.clauses?.liability || [] },
  ]
})
async function load() {
  const current = ++generation
  loading.value = true; data.value = null; error.value = ''
  try {
    const result = await read(`/business/purchases/${route.params.id}/contract-preview/`, selectedVersion.value ? { version: selectedVersion.value } : {})
    if (current === generation) data.value = result
  }
  catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) loading.value = false }
}
watch(() => route.params.id, () => { selectedVersion.value = ''; command.value = null; void load() }, { immediate: true })
function print() { window.print() }
async function archive() {
  if (!data.value) return
  const purchaseId = route.params.id
  // 查看历史归档版本时，先切到当前采购资料再归档，快照哈希始终按当前资料计算。
  if (data.value.archived_version) {
    selectedVersion.value = 'current'
    await load()
    if (route.params.id !== purchaseId || !data.value || data.value.archived_version || data.value.draft || data.value.status === 'cancelled') return
  }
  const snapshot = data.value.snapshot_hash
  const docs = await all('/business/documents/', { purchase: purchaseId, category: 'contract' })
  if (route.params.id !== purchaseId) return
  command.value = {
    title: '归档已签署合同版本', path: `/business/purchases/${purchaseId}/archive-contract/`,
    fields: [
      { key: 'document', label: '已签署合同附件', type: 'select', upload: { context: { purchase: Number(purchaseId) }, category: 'contract' }, options: docs.map(d => ({ value: d.id, label: d.original_name })) },
      { key: 'delivery_address', label: '双方确认的收货地址' },
      { key: 'reason', label: '归档或修订原因', type: 'textarea' },
      { key: 'confirmed', label: '已核对签署文件与本版完整合同、明细、条款及收货地址一致', type: 'boolean', initial: false },
    ],
    prepare: values => ({ ...values, expected_snapshot: snapshot }),
    notice: { type: 'warning', text: '先在采购附件中上传双方签署的完整合同。归档后本版资料不可覆盖；后续修订创建新版本，金额仍以原采购业务为准。' },
  }
}
</script>
<template>
  <section class="purchase-contract-page" v-loading="loading">
    <div class="contract-toolbar">
      <div><router-link :to="{ path: '/purchases', query: { resource: 'purchases', focus: String(route.params.id) } }">返回采购单</router-link><h1>采购合同预览</h1></div>
      <el-button :disabled="loading" @click="load">刷新预览</el-button>
    </div>
    <el-alert v-if="error" type="error" :title="error" :closable="false" />
    <div class="contract-workspace">
    <aside v-if="data" class="contract-toolbar contract-actions" aria-label="合同版本与打印">
      <el-button type="primary" :disabled="loading" @click="print">打印 / 另存为 PDF</el-button>
      <el-button v-if="data.signed_document" @click="openDocumentPreview(data.signed_document, '签署合同')">预览签署文件</el-button>
      <label>合同版本 <select v-model="selectedVersion" aria-label="合同版本" @change="load"><option value="">最新归档（无归档时当前资料）</option><option value="current">当前采购资料 · 待确认</option><option v-for="v in data.versions" :key="v.version" :value="String(v.version)">已归档第 {{ v.version }} 版</option></select></label>
      <el-button v-if="buyer() && !data.draft && data.status !== 'cancelled'" @click="archive().catch(e => error = message(e))">{{ data.archived_version ? '归档新版本' : '归档签署版本' }}</el-button>
      <span>{{ data.archived_version ? `当前为已归档第 ${data.archived_version} 版，资料保持不变` : '当前采购资料预览，尚未归档签署版本' }}</span>
      <p class="contract-help">本页完整显示双方信息、全部明细、合同条款和签章区。打印 / 另存为 PDF 将输出整份合同，内容较长时自动分为多页 A4。</p>
      <p class="contract-help">签署前请核对图纸版次、技术指标、验收条件及服务时限，并在技术协议或补充约定中明确。归档前需补齐双方资料并核对收货地址；历史归档保留当时条款。</p>
    </aside>
    <div class="contract-pages">
    <article v-if="data" class="contract-paper" aria-label="采购合同预览">
      <h1>采购合同<span v-if="data.draft">（草稿 · 未批准）</span><span v-else-if="data.status === 'cancelled'">（已取消）</span></h1>
      <div class="contract-meta"><span>合同编号：{{ data.code }}</span><span>制单日期：{{ data.date }}</span></div>
      <p v-if="Number(data.cancelled_amount) > 0" class="contract-state">已有取消余量，请结合原合同及变更记录核对。</p>
      <div class="contract-parties">
        <section><h2>甲方（采购方）</h2><p>名称：{{ data.buyer.name || '________________' }}</p><p>地址：{{ data.buyer.address || '________________' }}</p><p>电话：{{ data.buyer.phone || '________________' }}</p></section>
        <section><h2>乙方（供货方）</h2><p>名称：{{ data.supplier.name || '________________' }}</p><p>地址：{{ data.supplier.address || '________________' }}</p><p>联系人：{{ data.supplier.contact || '________________' }}；电话：{{ data.supplier.phone || '________________' }}</p></section>
      </div>
      <p>项目：{{ data.project }}</p>
      <p v-if="data.delivery_address">收货地址：{{ data.delivery_address }}</p>
      <h2>一、采购明细（CNY 人民币，含税）</h2>
      <p>共 {{ data.lines.length }} 项物料，全部明细如下。</p>
      <div class="contract-table-wrap" role="region" aria-label="完整采购明细" tabindex="0"><table><thead><tr><th>序号</th><th>物料编码 / 名称</th><th>规格 / 品牌</th><th>单位</th><th>数量</th><th>含税单价</th><th>含税金额</th><th>交期</th></tr></thead><tbody><tr v-for="line in data.lines" :key="line.number"><td>{{ line.number }}</td><td>{{ line.code }}<br>{{ line.name }}</td><td>{{ line.specification || '—' }}<template v-if="line.drawing_number || line.drawing_revision"><br>图号：{{ line.drawing_number || '—' }}；版次：{{ line.drawing_revision || '—' }}</template><br>{{ line.brand }}</td><td>{{ line.unit }}</td><td>{{ line.quantity }}<small v-if="Number(line.cancelled_quantity) > 0">已取消 {{ line.cancelled_quantity }}</small></td><td>{{ line.unit_price }}</td><td>{{ line.amount }}</td><td>{{ line.due_date }}</td></tr></tbody></table></div>
      <p class="contract-total">订单原含税合计：人民币 ¥ {{ data.total }}</p>
      <section v-for="(section, index) in sections" :key="section.key" class="contract-clauses" :aria-label="section.title">
        <h2>{{ sectionNumber(index + 1) }}、{{ section.title }}</h2>
        <p v-for="(clause, clauseIndex) in section.paragraphs" :key="clauseIndex">{{ clause }}</p>
      </section>
      <h2>{{ sectionNumber(sections.length + 1) }}、补充约定</h2><p class="contract-note">{{ data.note || '无；其他事项由双方另行书面确认。' }}</p>
      <div class="contract-signatures"><section><p>甲方签字 / 盖章：________________</p><p>签署日期：________________</p></section><section><p>乙方签字 / 盖章：________________</p><p>签署日期：________________</p></section></div>
    </article>
    </div></div>
    <ActionDialog :command="command" @close="command = null" @saved="selectedVersion = ''; load()" />
  </section>
</template>
<style>
.contract-toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:16px; }
.contract-toolbar > div:last-child { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.contract-toolbar .el-button + .el-button { margin-left:0; }
.contract-toolbar label { display:flex; align-items:center; gap:8px; font-size:13px; }
.contract-toolbar label select { width:260px; max-width:100%; }
.contract-help { color:var(--ink-6); line-height:1.7; }
.contract-workspace { display:grid; grid-template-columns:minmax(0,1fr) 280px; gap:24px; align-items:start; }
.contract-pages { min-width:0; grid-column:1; grid-row:1; }
.contract-actions { grid-column:2; grid-row:1; position:sticky; top:18px; display:flex; flex-direction:column; align-items:stretch; justify-content:flex-start; padding:20px; border:1px solid var(--step-line); border-radius:8px; background:white; font-size:13px; }
.contract-actions > .el-button { width:100%; min-height:42px; }
.contract-actions label { flex-wrap:wrap; min-width:0; }
.contract-actions label select { width:100%; min-width:0; }
.contract-actions .contract-help { margin-bottom:0; font-size:12px; }
.contract-pages .contract-paper { margin-top:0; }
@media screen and (max-width:1100px) { .contract-workspace { display:flex; flex-direction:column; }.contract-actions { position:static; width:100%; }.contract-pages { width:100%; } }
.contract-paper { box-sizing:border-box; max-width:210mm; margin:20px auto; padding:16mm 12mm; background:white; color:var(--ink); box-shadow:0 4px 24px #16283a12; font-size:13px; line-height:1.7; overflow-wrap:anywhere; }
.contract-paper h1 { text-align:center; font-size:24px; margin:0 0 10px; }.contract-paper h1 span { display:block; font-size:12px; }
.contract-paper h2 { font-size:14px; margin:16px 0 6px; }.contract-paper p { margin:5px 0; white-space:pre-wrap; }
.contract-meta,.contract-parties,.contract-signatures { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.contract-state { font-weight:600; }.contract-table-wrap { overflow-x:auto; }
.contract-paper table { width:100%; border-collapse:collapse; font-size:11px; }.contract-paper th,.contract-paper td { border:1px solid var(--ink-6); padding:6px; text-align:left; vertical-align:top; }.contract-paper th { background:var(--subtle); }.contract-paper small { display:block; }
.contract-total { text-align:right; font-weight:700; }.contract-note { white-space:pre-wrap; }.contract-signatures { margin-top:18px; }
@media screen {
  .contract-paper table { table-layout:fixed; }
  .contract-paper th:nth-child(1) { width:5%; }.contract-paper th:nth-child(2) { width:20%; }.contract-paper th:nth-child(3) { width:29%; }.contract-paper th:nth-child(4) { width:5%; }.contract-paper th:nth-child(5) { width:8%; }.contract-paper th:nth-child(6) { width:10%; }.contract-paper th:nth-child(7) { width:11%; }.contract-paper th:nth-child(8) { width:12%; }
}
@media screen and (max-width:700px) { .contract-paper { padding:20px 12px; }.contract-meta,.contract-parties,.contract-signatures { grid-template-columns:1fr; gap:8px; }.contract-paper table { min-width:650px; } }
@media print {
  .contract-workspace { display:block; }.contract-actions { display:none !important; }
  @page { size:A4; margin:12mm; }
  body:has(.purchase-contract-page) .el-message,
  body:has(.purchase-contract-page) .el-notification,
  body:has(.purchase-contract-page) .el-overlay,
  body:has(.purchase-contract-page) .el-loading-mask { display:none !important; }
  html:has(.purchase-contract-page),body:has(.purchase-contract-page) { background:white; }
  body:has(.purchase-contract-page) .sidebar,body:has(.purchase-contract-page) .topbar,.contract-toolbar,.contract-help { display:none !important; }
  body:has(.purchase-contract-page) .shell { display:block; min-height:0; background:white; }body:has(.purchase-contract-page) main,body:has(.purchase-contract-page) .content { margin:0; padding:0; width:auto; min-height:0; background:white; }
  .contract-paper { width:100%; max-width:none; margin:0; padding:0; box-shadow:none; font-size:9pt; line-height:1.5; }
  .contract-paper h2 { font-size:10pt; break-after:avoid; }
  .contract-paper p { orphans:2; widows:2; }
  .contract-table-wrap { overflow:visible; }.contract-paper table { min-width:0; table-layout:fixed; font-size:9pt; }.contract-paper th,.contract-paper td { overflow-wrap:anywhere; white-space:normal; }.contract-paper th:nth-child(1) { width:4%; }.contract-paper th:nth-child(2) { width:25%; }.contract-paper th:nth-child(3) { width:20%; }.contract-paper th:nth-child(4) { width:5%; }.contract-paper th:nth-child(5) { width:8%; }.contract-paper th:nth-child(6),.contract-paper th:nth-child(7) { width:11%; }.contract-paper th:nth-child(8) { width:16%; }.contract-paper thead { display:table-header-group; }.contract-paper tr,.contract-signatures { break-inside:avoid; }
}
</style>
