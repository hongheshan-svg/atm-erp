<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { read } from '../api'
import { message } from '../utils/request'
import { quantityText } from '../utils/quantity'
import { dateTimeText } from '../utils/datetime'
import type { Row } from '../types'
// 领料单：领料成功后、领料单列表和库存流水都链到这里；数据全部来自服务端领料单与其领料流水，可随时重新打开打印。
const route = useRoute()
const slip = ref<Row | null>(null), error = ref(''), loading = ref(false)
let generation = 0
onBeforeUnmount(() => { generation++ })
async function load() {
  const current = ++generation
  loading.value = true; slip.value = null; error.value = ''
  try {
    const result = await read(`/business/issue-slips/${route.params.id}/`)
    if (current === generation) slip.value = result
  } catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) loading.value = false }
}
watch(() => route.params.id, () => { void load() }, { immediate: true })
const lines = computed<Row[]>(() => slip.value?.lines || [])
const project = computed(() => [slip.value?.project_code, slip.value?.project_name].filter(Boolean).join(' · '))
const spec = (line: Row) => [line.specification, line.brand].filter(Boolean).join(' / ') || '—'
const drawing = (line: Row) => [line.drawing_number && `图号 ${line.drawing_number}`, line.drawing_revision && `版本 ${line.drawing_revision}`].filter(Boolean).join('；')
function print() { window.print() }
</script>
<template>
  <section class="issue-slip-page" v-loading="loading">
    <div class="slip-toolbar">
      <div><router-link :to="{ path: '/inventory', query: { section: 'slips', project: slip?.project ? String(slip.project) : 'all' } }">返回领料单列表</router-link><h1>领料单</h1></div>
      <div><el-button :disabled="loading" @click="load">刷新</el-button><el-button v-if="slip" type="primary" @click="print">打印 / 另存为 PDF</el-button></div>
    </div>
    <el-alert v-if="error" type="error" :title="error" :closable="false" show-icon role="alert" />
    <article v-if="slip" class="slip-paper" aria-label="领料单">
      <p v-if="slip.company_name" class="slip-company">{{ slip.company_name }}</p>
      <h1>领料单</h1>
      <dl class="slip-meta">
        <div><dt>单号</dt><dd>{{ slip.code }}</dd></div>
        <div><dt>领料时间</dt><dd>{{ dateTimeText(slip.created_at) }}</dd></div>
        <div class="slip-wide"><dt>项目</dt><dd>{{ project || '—' }}</dd></div>
        <div v-if="slip.task_title" class="slip-wide"><dt>售后任务</dt><dd>{{ slip.task_title }}</dd></div>
        <div class="slip-wide"><dt>领料说明</dt><dd>{{ slip.reason || '—' }}</dd></div>
        <div><dt>经办仓管</dt><dd>{{ slip.created_by_name || '—' }}</dd></div>
        <div><dt>明细行数</dt><dd>{{ lines.length }} 行</dd></div>
      </dl>
      <div class="slip-table-wrap" role="region" aria-label="领料明细" tabindex="0">
        <table>
          <thead><tr><th>序号</th><th>物料编码</th><th>物料名称</th><th>规格 / 品牌</th><th>库位</th><th>数量</th><th>单位</th><th>备注</th></tr></thead>
          <tbody>
            <tr v-for="(line, index) in lines" :key="line.id">
              <td data-label="序号">{{ index + 1 }}</td>
              <td data-label="物料编码">{{ line.item_code }}</td>
              <td data-label="物料名称">{{ line.item_name }}<small v-if="drawing(line)">{{ drawing(line) }}</small></td>
              <td data-label="规格 / 品牌">{{ spec(line) }}</td>
              <td data-label="库位">{{ line.location }}</td>
              <td data-label="数量" class="slip-number">{{ quantityText(line.quantity) }}</td>
              <td data-label="单位">{{ line.unit || '—' }}</td>
              <td data-label="备注">{{ line.remark || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="slip-note">数量以本单出库流水为准；退料按原领料流水另行登记，不改动本单。</p>
      <div class="slip-signatures">
        <p><span>领料人签字：________________</span><span>日期：__________</span></p>
        <p><span>仓管签字：________________</span><span>日期：__________</span></p>
      </div>
    </article>
  </section>
</template>
<style>
.issue-slip-page .slip-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.issue-slip-page .slip-toolbar > div { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.issue-slip-page .slip-toolbar h1 { margin: 0 0 0 8px; font-size: 20px; }
.issue-slip-page .slip-toolbar .el-button + .el-button { margin-left: 0; }
.slip-paper { box-sizing: border-box; max-width: 210mm; margin: 0 auto 20px; padding: 14mm 12mm; background: white; color: var(--ink); box-shadow: 0 4px 24px #16283a12; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.slip-paper .slip-company { margin: 0; text-align: center; font-size: 14px; color: var(--ink-3); }
.slip-paper h1 { margin: 2px 0 14px; text-align: center; font-size: 22px; letter-spacing: 8px; }
.slip-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 24px; margin: 0 0 14px; }
.slip-meta > div { display: flex; gap: 8px; min-width: 0; }
.slip-meta .slip-wide { grid-column: 1 / -1; }
.slip-meta dt { flex: none; color: var(--ink-3); }
.slip-meta dt::after { content: '：'; }
.slip-meta dd { margin: 0; min-width: 0; }
.slip-table-wrap { overflow-x: auto; }
.slip-paper table { width: 100%; border-collapse: collapse; font-size: 12px; }
.slip-paper th, .slip-paper td { border: 1px solid var(--ink-6); padding: 6px; text-align: left; vertical-align: top; }
.slip-paper th { background: var(--subtle); white-space: nowrap; }
.slip-paper td small { display: block; color: var(--ink-3); }
.slip-paper .slip-number { text-align: right; white-space: nowrap; }
.slip-note { margin: 10px 0 0; font-size: 12px; color: var(--ink-3); }
.slip-signatures { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 28px; }
.slip-signatures p { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 0; }
/* 手机（≤600px）：明细逐行成卡片，不出整页横向滚动；签字行上下排。 */
@media screen and (max-width: 600px) {
  .slip-paper { padding: 16px 12px; }
  .slip-meta { grid-template-columns: minmax(0, 1fr); }
  .slip-paper table { display: block; font-size: 13px; }
  .slip-paper thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
  .slip-paper tbody { display: block; }
  .slip-paper tr { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 4px 12px; padding: 10px; margin-bottom: 10px; border: 1px solid var(--ink-6); border-radius: 6px; }
  .slip-paper td { display: block; min-width: 0; border: 0; padding: 0; }
  .slip-paper td[data-label]::before { content: attr(data-label); display: block; font-size: 11px; color: var(--ink-6); }
  .slip-paper td:nth-child(3), .slip-paper td:nth-child(4), .slip-paper td:nth-child(8) { grid-column: 1 / -1; }
  .slip-paper .slip-number { text-align: left; }
  .slip-signatures { grid-template-columns: 1fr; gap: 16px; }
  .issue-slip-page .slip-toolbar a { display: inline-flex; align-items: center; min-height: 40px; }
}
@media print {
  @page { size: A4; margin: 12mm; }
  body:has(.issue-slip-page) .el-message,
  body:has(.issue-slip-page) .el-notification,
  body:has(.issue-slip-page) .el-overlay,
  body:has(.issue-slip-page) .el-loading-mask { display: none !important; }
  html:has(.issue-slip-page), body:has(.issue-slip-page) { background: white; }
  body:has(.issue-slip-page) .sidebar, body:has(.issue-slip-page) .topbar, .issue-slip-page .slip-toolbar { display: none !important; }
  body:has(.issue-slip-page) .shell { display: block; min-height: 0; background: white; }
  body:has(.issue-slip-page) main, body:has(.issue-slip-page) .content { margin: 0; padding: 0; width: auto; min-height: 0; background: white; }
  .slip-paper { width: 100%; max-width: none; margin: 0; padding: 0; box-shadow: none; font-size: 10pt; line-height: 1.5; }
  .slip-table-wrap { overflow: visible; }
  .slip-paper table { font-size: 9pt; }
  .slip-paper thead { display: table-header-group; }
  .slip-paper tr, .slip-signatures { break-inside: avoid; }
}
</style>
