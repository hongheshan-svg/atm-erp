<script setup lang="ts">
import BusinessTable from './BusinessTable.vue'
import { computed, ref, watch } from 'vue'
import { useNarrow } from '../utils/media'
import { read } from '../api'
import { message } from '../utils/request'
import type { Row } from '../types'
import ListPagination from './ListPagination.vue'
import { pageSize } from '../pagination'
const opened = ref(false), view = ref('cash30'), data = ref<Row | null>(null), error = ref(''), busy = ref(false)
let generation = 0
// 窄屏（≤600px）只留「来源单据 / 物料」一列，项目、日期、金额或数量、跟进事项并入下方摘要，不再横滚。
const narrow = useNarrow()
const money = computed(() => ['cash30', 'aging'].includes(view.value))
function summary(row: Row) {
  return [[row.project, row.date, row.amount != null && row.amount !== '' ? (money.value ? `${row.amount} 元` : `数量 ${row.amount}`) : ''], [row.status, view.value === 'aging' ? row.age_band : '']]
    .map(parts => parts.filter(Boolean).join(' · ')).filter(Boolean)
}
async function load(page = 1) {
  const current = ++generation
  busy.value = true; error.value = ''; data.value = null
  try { const result = await read('/business/reports/', { view: view.value, page, page_size: pageSize.value }); if (current === generation) data.value = result }
  catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) busy.value = false }
}
watch([view, pageSize], () => { if (opened.value) void load() })
</script>
<template>
  <section class="panel report-attention">
    <el-button @click="opened = !opened; opened && load()">{{ opened ? '收起' : '展开' }}资金与采购库存关注</el-button>
    <template v-if="opened"><p class="muted">全公司只读原业务明细，独立于下方项目筛选；不授予项目编辑或财务记账权限。</p><div class="attention-controls"><label>关注视图 <select v-model="view" aria-label="经营关注视图"><option value="cash30">未来30天到期资金</option><option value="aging">逾期账龄</option><option value="late_purchase">采购逾期</option><option value="stale_stock">90天未动库存</option></select></label><el-button :loading="busy" @click="load()">刷新明细</el-button></div>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <template v-if="data"><p class="attention-definition">{{ data.definition }}</p><BusinessTable label="经营关注" :row-offset="(data.page - 1) * pageSize" :numbered="!narrow" :data="data.results" stripe max-height="430"><el-table-column prop="source" label="来源单据 / 物料" min-width="220"><template #default="{ row }">{{ row.source }}<small v-if="narrow" class="attention-summary"><span v-for="(line, index) in summary(row)" :key="index">{{ line }}</span></small></template></el-table-column><template v-if="!narrow"><el-table-column prop="project" label="项目" /><el-table-column prop="date" label="到期 / 最后移动" /><el-table-column prop="amount" :label="money ? '金额（元）' : '数量'" /><el-table-column prop="status" label="跟进事项" /><el-table-column v-if="view === 'aging'" prop="age_band" label="账龄段" /></template></BusinessTable><ListPagination :page="data.page" :total="data.count" @change="load" /></template>
    </template>
  </section>
</template>
<style scoped>
.attention-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; margin-bottom: 8px; }
.attention-summary { display: none; }
@media (max-width: 600px) {
  .report-attention > .el-button { width: 100%; min-height: 40px; }
  .attention-controls label { display: grid; flex: 1 1 100%; gap: 6px; color: var(--muted); font-size: 13px; }
  .attention-controls select { min-height: 40px; width: 100%; box-sizing: border-box; padding: 0 10px; border: 1px solid var(--field-line); border-radius: 8px; background: white; color: var(--ink-2); }
  .attention-controls .el-button { min-height: 40px; }
  .attention-definition { font-size: 13px; line-height: 1.6; }
  .attention-summary { display: grid; margin-top: 4px; color: var(--ink-6); font-size: 12px; line-height: 1.6; }
}
</style>
