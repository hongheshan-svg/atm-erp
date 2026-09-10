<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { read } from '../api'
import { message } from '../utils/request'
import { labels } from '../modules/shared'
import type { Row } from '../types'
import ListPagination from '../components/ListPagination.vue'
import TransferTools from '../components/TransferTools.vue'
import { pageSize } from '../pagination'
import ReportAttention from '../components/ReportAttention.vue'

const data = ref<Row | null>(null)
const loading = ref(false)
const error = ref('')
const search = ref('')
const status = ref('')
const risk = ref('')
let applied = { search: '', status: '', risk: '' }
const exportFilters = ref(applied)
let generation = 0
const money = (value: string) => {
  const [integer, fraction = ''] = String(value).split('.')
  return `${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`
}
const metrics = [
  { key: 'contract_amount', label: '已签约合同额', note: '筛选项目累计合同金额' },
  { key: 'actual_cost', label: '实际成本', note: '材料、人工、费用及退货价差' },
  { key: 'committed_cost', label: '已承诺采购', note: '已批准、尚未收货金额' },
  { key: 'receivable', label: '待收款', note: '应收余额，不含待退客户款' },
  { key: 'payable', label: '待付款', note: '采购与费用余额，不含待收退款' },
  { key: 'overdue_receivable', label: '逾期待收款', note: '期限早于今天的未收余额' },
  { key: 'overdue_payable', label: '逾期待付款', note: '期限早于今天的未付余额' },
]
async function load(page = 1) {
  const current = ++generation
  loading.value = true
  error.value = ''
  data.value = null
  try {
    const result = await read('/business/reports/', { ...applied, page, page_size: pageSize.value })
    if (current === generation) data.value = result
  } catch (e) {
    if (current === generation) error.value = message(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
function focusRisk(value: string) { risk.value = value; filter() }
function filter() {
  applied = { search: search.value, status: status.value, risk: risk.value }
  exportFilters.value = applied
  void load()
}
onMounted(() => load())
watch(pageSize, () => load())
</script>
<template>
  <header class="page-heading">
    <div><p class="eyebrow">经营全景 / 项目累计</p><h1>经营报表</h1><p class="muted">从合同、成本和收付款看经营进度，定位需要跟进的项目。</p></div>
    <div class="toolbar"><TransferTools resource="reports" path="/business/reports/" export-path="/business/reports/" :params="exportFilters" /><el-button :loading="loading" @click="load(data?.page || 1)">刷新</el-button></div>
  </header>
  <ReportAttention />
  <section class="panel report-filters">
    <form @submit.prevent="filter">
      <label>项目<input v-model="search" aria-label="搜索项目" placeholder="项目名称或编号" maxlength="150" /></label>
      <label>项目状态<select v-model="status" aria-label="项目状态"><option value="">全部状态</option><option v-for="key in ['draft', 'quoted', 'active', 'delivering', 'warranty', 'closed', 'cancelled']" :key="key" :value="key">{{ labels[key] }}</option></select></label>
      <label>关注事项<select v-model="risk" aria-label="关注事项"><option value="">全部项目</option><option value="over_budget">超预算</option><option value="overdue">交付逾期</option><option value="unbudgeted">未设置预算</option></select></label>
      <el-button type="primary" native-type="submit" :loading="loading">查询</el-button>
    </form>
    <p class="muted">CNY 含税经营口径；全部指标按当前筛选项目累计，不是期间收入或会计利润。合同额不等于已收款，未完成项目的实际成本不代表完工成本。</p>
  </section>
  <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
  <p v-if="loading" role="status">正在汇总经营数据…</p>
  <template v-if="data">
    <div class="report-metrics">
      <section v-for="metric in metrics" :key="metric.key" class="panel report-metric" :aria-label="metric.label"><span>{{ metric.label }}</span><strong>¥ {{ money(data.summary[metric.key]) }}</strong><small>{{ metric.note }}</small></section>
    </div>
    <section class="panel report-watch" aria-label="经营关注">
      <span>项目 <strong>{{ data.summary.projects }}</strong></span><span>执行 / 交付 / 质保 <strong>{{ data.summary.active_projects }}</strong></span>
      <el-button text @click="focusRisk('over_budget')">超预算 {{ data.summary.over_budget }}</el-button><el-button text @click="focusRisk('overdue')">交付逾期 {{ data.summary.overdue }}</el-button><el-button text @click="focusRisk('unbudgeted')">未设置预算 {{ data.summary.unbudgeted }}</el-button>
      <span>待退客户款 ¥ {{ money(data.summary.refund_out) }}</span><span>待收退款 ¥ {{ money(data.summary.refund_in) }}</span>
    </section>
    <section class="panel" aria-label="项目经营明细">
      <header class="panel-heading"><h2>项目经营明细 <span class="record-count">{{ data.count }}</span></h2><small class="muted">更新于 {{ new Date(data.generated_at).toLocaleString('zh-CN') }}</small></header>
      <el-table :data="data.results" :max-height="560" stripe empty-text="没有符合筛选条件的项目">
        <el-table-column label="项目" min-width="190" fixed><template #default="{ row }"><component :is="row.can_open === false ? 'span' : 'router-link'" :to="`/projects/${row.id}`">{{ row.name }}</component><small class="report-code">{{ row.code }} · {{ row.manager }}</small></template></el-table-column>
        <el-table-column label="状态" min-width="85"><template #default="{ row }">{{ labels[row.status] }}</template></el-table-column>
        <el-table-column label="合同额" min-width="115" align="right"><template #default="{ row }">{{ money(row.contract_amount) }}</template></el-table-column>
        <el-table-column label="预算" min-width="110" align="right"><template #default="{ row }">{{ row.budget === null ? '未设置' : money(row.budget) }}</template></el-table-column>
        <el-table-column label="实际成本" min-width="115" align="right"><template #default="{ row }"><component :is="row.can_open === false ? 'span' : 'router-link'" :to="{ path: `/projects/${row.id}`, query: { tab: 'cost', section: 'actual' } }">{{ money(row.actual_cost) }}</component></template></el-table-column>
        <el-table-column label="在途采购" min-width="115" align="right"><template #default="{ row }"><component :is="row.can_open === false ? 'span' : 'router-link'" :to="{ path: `/projects/${row.id}`, query: { tab: 'purchases' } }">{{ money(row.committed_cost) }}</component></template></el-table-column>

        <el-table-column label="待收 / 待付" min-width="165" align="right"><template #default="{ row }"><component :is="row.can_open === false ? 'span' : 'router-link'" :to="{ path: `/projects/${row.id}`, query: { tab: 'finance', section: 'entries' } }">{{ money(row.receivable) }} / {{ money(row.payable) }}</component></template></el-table-column>
        <el-table-column label="关注" width="85"><template #default="{ row }">{{ row.over_budget ? '超预算' : row.overdue ? '逾期' : row.unbudgeted ? '未设预算' : '—' }}</template></el-table-column>
        <el-table-column type="expand" width="42"><template #default="{ row }"><div class="report-detail"><p>实际＋在途：{{ money(row.occupied_cost) }}</p><span v-if="row.overdue" class="report-warning">交付逾期 · {{ row.due_date }}</span><span v-for="warning in row.warnings" :key="warning" class="report-warning">{{ warning }}</span><span v-if="!row.overdue && !row.over_budget">{{ row.unbudgeted ? '尚未设置项目预算' : '当前无预算或交期预警' }}</span></div></template></el-table-column>
      </el-table>
      <ListPagination :page="data.page" :total="data.count" @change="load" />
      <p class="muted">已承诺仅含未收货采购；人工和费用使用实际记录。采购净额超材料预算同样计入超预算项目。取消项目的待退款仍保留，退款与正向待收待付分别展示。</p>
    </section>
  </template>
</template>
<style scoped>
.report-detail { padding: 12px 24px; line-height: 1.8; }
.report-filters form { display: flex; flex-wrap: wrap; gap: 16px; align-items: end; }
.report-filters label { display: grid; gap: 8px; min-width: 180px; color: var(--muted); font-size: 13px; }
.report-filters input, .report-filters select { padding: 10px 12px; border: 1px solid #d9e1ed; border-radius: 8px; background: white; color: #243b5a; }
.report-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin: 20px 0; }
.report-metric { display: grid; gap: 12px; margin: 0; }
.report-metric strong { color: #285ec1; font-size: 24px; overflow-wrap: anywhere; }
.report-metric small, .report-code { color: #7b8ba3; font-size: 12px; }
.report-watch { display: flex; flex-wrap: wrap; gap: 20px; }
.report-watch strong { color: #285ec1; margin-left: 4px; }
.report-code, .report-warning { display: block; margin-top: 5px; }
.report-warning { color: #b45309; }
@media (max-width: 1000px) { .report-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .report-filters label { min-width: 0; width: 100%; } .report-metric { padding: 16px; } .report-metric strong { font-size: 19px; } }
</style>
