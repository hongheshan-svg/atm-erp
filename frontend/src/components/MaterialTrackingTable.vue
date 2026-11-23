<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import BusinessTable from './BusinessTable.vue'
import ListPagination from './ListPagination.vue'
import RemoteSelect from './RemoteSelect.vue'
import { download, read } from '../api'
import { message } from '../utils/request'
import { useNarrow } from '../utils/media'
import { pageSize } from '../pagination'
import { today } from '../forms'
import { money, purchaseReader, purchasing } from '../session'
import { partTypes } from '../product-categories'
import { slipRoute } from '../modules/inventory'
import type { Row } from '../types'
import {
  bomRoute, drawingText, needText, partText, purchaseRoute, qtyText, textOr, trackingParams, trackingPath, trackingStatuses, trackingSummary, trackingTone, unitPriceText,
} from '../modules/material-tracking'

// 跨项目物料跟踪总表：每个「项目×物料」一行，需求、已采购、已收、已领、缺料并排；可按状态、类别、供应商筛选并导出 Excel。
const props = defineProps<{ projectId?: number }>()
const mobile = useNarrow()
const rows = ref<Row[]>([])
const count = ref(0)
const page = ref(1)
const loading = ref(false)
const exporting = ref(false)
const error = ref('')
const search = ref('')
const filters = ref({ search: '', status: '', partType: '', supplier: undefined as string | number | undefined, outsideBom: false, allProjects: false })
// 采购单号、供应商只给能看采购单的岗位；单价金额只给能看采购价的岗位（服务端同样不返回）。
const purchaseInfo = computed(() => purchaseReader())
const priceInfo = computed(() => money() || purchasing())
const notCustomer = (partner: Row) => partner.kind !== 'customer'
const params = computed(() => trackingParams(filters.value, props.projectId))
const filtered = computed(() => Boolean(filters.value.search || filters.value.status || filters.value.partType || filters.value.supplier || filters.value.outsideBom || filters.value.allProjects))
let generation = 0
onBeforeUnmount(() => { generation++ })
async function load() {
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    const data = await read(trackingPath, { ...params.value, page: page.value, page_size: pageSize.value })
    if (current !== generation) return
    rows.value = data.results || []
    count.value = data.count || 0
  } catch (e) {
    if (current === generation) { rows.value = []; count.value = 0; error.value = message(e) }
  } finally {
    if (current === generation) loading.value = false
  }
}
function apply() { filters.value.search = search.value.trim(); page.value = 1; void load() }
function setStatus(value: string) { filters.value.status = value; page.value = 1; void load() }
function reset() {
  search.value = ''
  filters.value = { search: '', status: '', partType: '', supplier: undefined, outsideBom: false, allProjects: false }
  page.value = 1
  void load()
}
function turn(value: number) { page.value = value; void load() }
watch(() => filters.value.supplier, (value, before) => { if (value !== before) apply() })
watch([() => props.projectId, pageSize], () => { page.value = 1; void load() }, { immediate: true })
async function exportFile() {
  exporting.value = true
  error.value = ''
  try { await download(`${trackingPath}export/`, `物料跟踪-${today()}.xlsx`, { ...params.value, file_format: 'xlsx' }) }
  catch (e) { error.value = message(e) }
  finally { exporting.value = false }
}
const tone = (row: Row) => trackingTone[String(row.status)] || 'neutral'
const shortageClass = (row: Row) => (Number(row.shortage) > 0 ? 'tracking-shortage' : '')
const emptyTitle = computed(() => (filtered.value ? '没有符合当前筛选条件的物料' : props.projectId ? '这个项目还没有 BOM 物料或采购记录' : '在推进的项目还没有 BOM 物料或采购记录'))
</script>
<template>
  <section class="panel tracking-panel" aria-label="物料跟踪表">
    <header class="panel-heading">
      <h2>物料跟踪 <span class="record-count">{{ count }}</span></h2>
      <div class="resource-status-tabs" role="group" aria-label="跟踪状态">
        <button type="button" :aria-pressed="!filters.status" @click="setStatus('')">全部</button>
        <button v-for="(label, value) in trackingStatuses" :key="value" type="button" :aria-pressed="filters.status === value" @click="setStatus(String(value))">{{ label }}</button>
      </div>
    </header>
    <form class="resource-search" @submit.prevent="apply">
      <input v-model="search" type="search" aria-label="搜索物料跟踪" placeholder="物料编码、名称、型号或项目" />
      <select v-model="filters.partType" aria-label="筛选物料类别" @change="apply"><option value="">全部类别</option><option v-for="(label, value) in partTypes" :key="value" :value="value">{{ label }}</option></select>
      <RemoteSelect v-if="purchaseInfo" v-model="filters.supplier" path="/business/partners/" label="供应商筛选" :accept="notCustomer" commit-on-select />
      <label class="inline-check"><input v-model="filters.outsideBom" type="checkbox" @change="apply" />只看不在 BOM 的物料</label>
      <label v-if="!projectId" class="inline-check"><input v-model="filters.allProjects" type="checkbox" @change="apply" />包括已验收、已结项项目</label>
      <el-button native-type="submit">搜索</el-button>
      <el-button v-if="filtered || search" text @click="reset">重置</el-button>
      <span class="tracking-tools">
        <el-button :loading="exporting" :disabled="!count" @click="exportFile">导出 Excel</el-button>
        <el-button :icon="Refresh" aria-label="刷新物料跟踪" title="刷新" @click="load" />
      </span>
    </form>
    <p class="muted tracking-hint">每个项目的每种物料一行：需求按 BOM 各单元合计，缺料与 BOM 页同一口径；项目后来另外采购、不在 BOM 里的物料也会列出。{{ projectId ? '' : '未选项目时只看需求中到交付中的项目。' }}</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
    <section v-if="!loading && !error && !rows.length" class="empty-guidance" role="status"><strong>{{ emptyTitle }}</strong><p>{{ filtered ? '可清除筛选后再查看。' : '项目维护 BOM 或下采购单后，这里会列出每种物料的采购、到货和领料情况。' }}</p><el-button v-if="filtered" @click="reset">清除筛选</el-button></section>
    <ul v-else-if="mobile" v-loading="loading" class="tracking-cards" aria-label="物料跟踪">
      <li v-for="row in rows" :key="row.id">
        <div class="tracking-card-head">
          <strong>{{ row.item_name }}</strong>
          <span class="tracking-status" :class="`status-${tone(row)}`">{{ row.status_label }}</span>
        </div>
        <small>{{ [row.item_code, row.specification, row.in_bom === false ? '不在 BOM' : ''].filter(Boolean).join(' · ') }}</small>
        <small><router-link :to="bomRoute(row)">{{ row.project_code }}</router-link> {{ row.project_name }}</small>
        <p :class="shortageClass(row)">{{ trackingSummary(row) }}</p>
        <small v-if="row.due_dates || row.purchase_codes">{{ [row.purchase_codes, row.due_dates ? `交期 ${row.due_dates}` : ''].filter(Boolean).join(' · ') }}</small>
        <small v-if="row.recipients || row.last_issued_date">{{ ['领料', row.last_issued_date, row.recipients].filter(Boolean).join(' ') }}</small>
      </li>
    </ul>
    <BusinessTable v-else v-loading="loading" label="物料跟踪表" :data="rows" :row-offset="(page - 1) * pageSize" row-key="id" border size="small" class="tracking-table">
      <el-table-column label="项目号" width="104" fixed="left"><template #default="{ row }"><router-link :to="bomRoute(row)" :title="`${row.project_name}：打开项目 BOM`">{{ row.project_code }}</router-link></template></el-table-column>
      <el-table-column prop="item_code" label="物料编码" width="124" fixed="left" />
      <el-table-column label="物料名称" min-width="140" fixed="left"><template #default="{ row }">{{ row.item_name }}<el-tag v-if="row.in_bom === false" size="small" type="info" class="tracking-tag" title="项目后来另外采购或领用、不在当前 BOM 里的物料（零星采购、改版移除）">不在 BOM</el-tag></template></el-table-column>
      <el-table-column label="状态" width="92"><template #default="{ row }"><span class="tracking-status" :class="`status-${tone(row)}`">{{ row.status_label }}</span></template></el-table-column>
      <el-table-column label="需求" width="80" align="right"><template #default="{ row }">{{ needText(row) }}</template></el-table-column>
      <el-table-column label="已采购" width="92" align="right"><template #default="{ row }">{{ qtyText(row, 'ordered') }}<small v-if="Number(row.unapproved) > 0" class="tracking-sub">待批 {{ qtyText(row, 'unapproved') }}</small></template></el-table-column>
      <el-table-column label="已收" width="80" align="right"><template #default="{ row }">{{ qtyText(row, 'received') }}</template></el-table-column>
      <el-table-column label="已领" width="80" align="right"><template #default="{ row }">{{ qtyText(row, 'issued') }}</template></el-table-column>
      <el-table-column label="缺料" width="80" align="right"><template #default="{ row }"><span :class="shortageClass(row)">{{ row.in_bom === false ? '—' : qtyText(row, 'shortage') }}</span></template></el-table-column>
      <el-table-column label="在途" width="80" align="right"><template #default="{ row }">{{ qtyText(row, 'incoming') }}</template></el-table-column>
      <el-table-column v-if="purchaseInfo" label="采购单号" min-width="150"><template #default="{ row }"><template v-if="row.purchase_refs?.length"><router-link v-for="order in row.purchase_refs" :key="order.id" class="tracking-link" :to="purchaseRoute(order, row)" :title="order.status_label">{{ order.code }}</router-link></template><span v-else>—</span></template></el-table-column>
      <el-table-column v-if="purchaseInfo" label="供应商" min-width="130"><template #default="{ row }">{{ textOr(row.suppliers) }}</template></el-table-column>
      <el-table-column v-if="priceInfo" label="单价" width="90" align="right"><template #default="{ row }"><span :title="row.unit_prices || ''">{{ unitPriceText(row) }}</span></template></el-table-column>
      <el-table-column v-if="priceInfo" label="金额" width="100" align="right"><template #default="{ row }">{{ textOr(row.amount) }}</template></el-table-column>
      <el-table-column label="采购交期" min-width="110"><template #default="{ row }">{{ textOr(row.due_dates) }}</template></el-table-column>
      <el-table-column label="最近入库" width="104"><template #default="{ row }">{{ textOr(row.last_received_date) }}</template></el-table-column>
      <el-table-column v-if="purchaseInfo" label="送货单号 / 收货说明" min-width="150"><template #default="{ row }">{{ textOr(row.delivery_notes) }}</template></el-table-column>
      <el-table-column v-if="purchaseInfo" label="采购员" width="96"><template #default="{ row }">{{ textOr(row.buyers) }}</template></el-table-column>
      <el-table-column label="最近领料" width="104"><template #default="{ row }">{{ textOr(row.last_issued_date) }}</template></el-table-column>
      <el-table-column label="领料人" min-width="110"><template #default="{ row }">{{ textOr(row.recipients) }}</template></el-table-column>
      <el-table-column label="领料单号" min-width="130"><template #default="{ row }"><template v-if="row.slip_refs?.length"><template v-if="purchaseInfo"><router-link v-for="slip in row.slip_refs" :key="slip.id" class="tracking-link" :to="slipRoute(slip.id)">{{ slip.code }}</router-link></template><span v-else>{{ row.issue_slips }}</span></template><span v-else>—</span></template></el-table-column>
      <el-table-column label="图号 / 版本" min-width="130"><template #default="{ row }">{{ drawingText(row) }}</template></el-table-column>
      <el-table-column label="型号 / 规格" min-width="130"><template #default="{ row }">{{ textOr(row.specification) }}</template></el-table-column>
      <el-table-column label="单位" width="64"><template #default="{ row }">{{ textOr(row.unit) }}</template></el-table-column>
      <el-table-column label="类别" width="76"><template #default="{ row }">{{ partText(row) }}</template></el-table-column>
      <el-table-column label="单元" min-width="100"><template #default="{ row }">{{ textOr(row.assembly_units) }}</template></el-table-column>
      <el-table-column label="需求日期" width="104"><template #default="{ row }">{{ textOr(row.required_date) }}</template></el-table-column>
      <el-table-column label="申请日期" width="104"><template #default="{ row }">{{ textOr(row.application_date) }}</template></el-table-column>
      <el-table-column label="申请人" width="96"><template #default="{ row }">{{ textOr(row.applicants) }}</template></el-table-column>
      <el-table-column label="备注" min-width="140"><template #default="{ row }">{{ [row.notes, row.issue_notes].filter(Boolean).join('；') || '—' }}</template></el-table-column>
    </BusinessTable>
    <ListPagination v-if="count > pageSize" :page="page" :total="count" @change="turn" />
  </section>
</template>
<style scoped>
.tracking-tools { display: inline-flex; gap: 8px; margin-left: auto; }
.tracking-hint { margin: -6px 0 12px; font-size: 12px; }
.tracking-status { display: inline-flex; align-items: center; padding: 1px 8px; border-radius: 5px; font-size: 12px; line-height: 20px; font-weight: 500; white-space: nowrap; }
.status-success { background: var(--ok-wash); color: var(--ok); }
.status-primary { background: var(--brand-wash); color: var(--brand); }
.status-warning { background: var(--warn-wash); color: var(--warn); }
.status-danger { background: var(--risk-wash); color: var(--risk); }
.status-neutral { background: var(--line-2); color: var(--mute); }
.tracking-shortage { color: var(--risk); font-weight: 600; }
.tracking-sub { display: block; color: var(--warn); font-size: 12px; }
.tracking-tag { margin-left: 6px; }
.tracking-link { display: block; white-space: nowrap; }
.tracking-cards { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.tracking-cards li { display: flex; flex-direction: column; gap: 4px; padding: 12px; border: 1px solid var(--surface-border); border-radius: var(--r-ctl); }
.tracking-cards p { margin: 4px 0 0; font-size: 13px; }
.tracking-cards small { color: var(--ink-4); font-size: 12px; overflow-wrap: anywhere; }
.tracking-card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
@media (max-width: 600px) {
  .tracking-tools { margin-left: 0; }
  .resource-search input[type='search'] { flex: 1 1 100%; max-width: none; }
}
</style>
