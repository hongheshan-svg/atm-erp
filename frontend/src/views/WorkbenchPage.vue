<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { CircleCheck, List, Document, Box, Wallet, ArrowRight } from '@element-plus/icons-vue'
import { read } from '../api'
import { today } from '../forms'
import { user } from '../session'
import { message } from '../utils/request'
import type { Row } from '../types'
const work = ref<Row>({})
const pages = ref<Row>({})
function changePage(key: string, page: number) { pages.value[`${key}_page`] = page; void load() }
const error = ref('')
const loading = ref(false)
const bucketIcons = { sales: Document, tasks: List, approvals: CircleCheck, receipts: Box, drafts: Document, settlements: Wallet, overdue_purchases: Box, prepayments: CircleCheck, reconciliations: Document, bank_records: Wallet }
const bucketNotes: Record<string, string> = {
  prepayments: '按合同条款核准未收货预付款', reconciliations: '核对差异，确认可结算额度', bank_records: '实际到账先记录，再认领或匹配原收付款',
  sales: '跟进负责的报价、签约、交付和回款',
  overdue_purchases: '按明细承诺交期跟进未到货或待处理物料',
  tasks: '按计划推进项目任务', approvals: '确认采购，衔接后续执行', receipts: '核对到货，及时更新库存',
  drafts: '完善采购明细后提交', settlements: '跟进到期款项与退款',
}
const bucketEmpty: Record<string, string> = {
  prepayments: '暂无待核准预付款', reconciliations: '暂无待确认对账', bank_records: '暂无未匹配银行款项',
  sales: '新建或分配给你的销售单会显示在这里',
  overdue_purchases: '暂无逾期采购',
  tasks: '新分配的任务会显示在这里', approvals: '提交后的采购单会显示在这里', receipts: '待入库的采购单会显示在这里',
  drafts: '尚未提交的采购单会显示在这里', settlements: '到期未结清款项会显示在这里',
}
const bucketLabels: Record<string, string> = {
  prepayments: '待核准预付款', reconciliations: '待确认业务对账', bank_records: '银行待认领 / 匹配',
  sales: '我的销售订单',
  overdue_purchases: '采购明细逾期',
  tasks: '我的待办',
  approvals: '待批准采购',
  receipts: '待收货',
  drafts: '采购草稿',
  settlements: '到期收付 / 待退款',
}
function target(key: string, row: Row) {
  if (key === 'bank_records') return { path: '/finance', query: { section: 'bank', resource: 'bank-records', focus: row.id } }
  if (['prepayments', 'reconciliations'].includes(key)) return { path: '/finance', query: { section: 'reconciliations', resource: 'reconciliations', focus: row.id } }
  if (key === 'sales') return { path: '/sales', query: { search: row.code } }
  const resource = key === 'tasks' ? 'tasks' : key === 'settlements' ? 'entries' : 'purchases'
  return { path: `/projects/${row.project}`, query: { tab: resource === 'tasks' ? 'tasks' : resource === 'entries' ? 'finance' : 'purchases', resource, focus: row.id } }
}
async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    work.value = await read('/business/workbench/', pages.value)
  } catch (e) {
    error.value = message(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
<template>
  <header class="page-heading">
    <div>
      <p class="eyebrow">今日协作 / {{ today() }}</p>
      <h1>工作台</h1>
      <p class="muted">{{ user?.display_name }}，从待办开始今天的协作。</p>
    </div>
    <el-button :loading="loading" @click="load">刷新</el-button>
  </header>
  <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
  <div class="workbench-grid" :aria-busy="loading">
    <section v-for="(bucket, key) in work" :key="key" class="panel work-card" :class="`work-card-${key}`">
      <header class="work-card-heading">
        <span class="work-card-icon" aria-hidden="true"><el-icon><component :is="bucketIcons[key as keyof typeof bucketIcons]" /></el-icon></span>
        <div><h2>{{ bucketLabels[key] }}</h2><p>{{ bucketNotes[key] }}</p></div>
        <span class="work-card-count" :aria-label="`${bucket.count} 项待处理`">{{ bucket.count }}</span>
      </header>
      <div v-if="!bucket.results.length" class="work-empty">
        <el-icon aria-hidden="true"><CircleCheck /></el-icon>
        <strong>暂无待办</strong><span>{{ bucketEmpty[key] }}</span>
      </div>
      <router-link
        v-for="row in bucket.results"
        :key="row.id"
        :to="target(String(key), row)"
        class="work-item"
        ><strong>{{ row.title || row.code || row.reference }}</strong
        ><span
          >{{ row.project_name || row.assignee_name }} · {{ row.next_delivery_date || row.due_date || '未设期限' }}</span
        ></router-link
      ><el-pagination v-if="bucket.count > 20" :current-page="bucket.page" :page-size="20" :total="bucket.count" layout="prev, pager, next, total" @current-change="changePage(String(key), $event)" />
      <footer class="work-card-footer">
        <span>{{ bucket.count ? '按业务进度及时处理' : '暂无需要处理的事项' }}</span>
        <router-link :to="key === 'sales' ? '/sales' : key === 'tasks' ? '/projects' : key === 'settlements' ? '/finance' : '/purchases'">
          {{ key === 'sales' ? '查看销售' : key === 'tasks' ? '查看项目' : key === 'settlements' ? '查看收付款' : '查看采购' }}<el-icon aria-hidden="true"><ArrowRight /></el-icon>
        </router-link>
      </footer>
    </section>
  </div>
</template>
