<script setup lang="ts">
import { computed, inject, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import type { Row, Command } from '../types'
import { read, download } from '../api'
import {
  columns,
  endpoint,
  display,
  createLabel,
  createCommand,
  actionNames,
  actionCommand,
} from '../business'
import { message } from '../utils/request'
import ActionDialog from './ActionDialog.vue'
import ListPagination from './ListPagination.vue'
import TransferTools from './TransferTools.vue'
import BOMPurchasePicker from './BOMPurchasePicker.vue'
import AttachmentDialog from './AttachmentDialog.vue'
import { pageSize } from '../pagination'
import { useRoute, useRouter } from 'vue-router'
import { user, operations } from '../session'
import StatusBadge from './StatusBadge.vue'
import RecordContext from './RecordContext.vue'
import { resourceFilters, searchableResources, sidePanelResources } from '../resource-ui'
import { labels } from '../modules/shared'
const route = useRoute()
const router = useRouter()
const props = withDefaults(defineProps<{
  resource: string
  title: string
  params?: Row
  projectId?: number
  revision?: number
  allowCreate?: boolean
}>(), { allowCreate: true })
const emit = defineEmits<{ changed: [] }>()
const records = ref<Row[]>([])
const count = ref(0)
const page = ref(1)
const searchKey = () => `resource-search-${user.value?.id}-${props.resource}-${JSON.stringify(props.params || {})}`
const search = ref((props.resource === 'sales' && typeof route.query.search === 'string' ? route.query.search : '') || sessionStorage.getItem(searchKey()) || '')
const appliedSearch = ref(search.value)
const loading = ref(false)
const error = ref('')
const command = ref<Command | null>(null)
const actionBusy = ref(false)
const filterValue = ref('')
const enabledFilter = ref(''), locationFilter = ref(''), brandFilter = ref('')
const appliedExtra = ref<Row>({})
const unsettled = ref(false)
const filterConfig = computed(() => resourceFilters[props.resource])
const filterParams = computed(() => ({
  ...(filterConfig.value && filterValue.value ? { [filterConfig.value.key]: filterValue.value } : {}),
  ...appliedExtra.value,
}))
const sidePanel = computed(() => sidePanelResources.includes(props.resource))
const selectedId = ref<number | null>(null)
const selectedRow = ref<Row | null>(null)
const active = inject<Ref<boolean>>('panelActive', computed(() => true))
const toolbarTarget = inject<Ref<HTMLElement | null>>('moduleToolbar', ref(null))
const preparing = ref(false)
let commandGeneration = 0
let dirty = true
onBeforeUnmount(() => { generation++; commandGeneration++ })
const attachmentRow = ref<Row | null>(null)
let generation = 0
let focused = ''
const combinedKey = computed(() => ({ sales: 'code', projects: 'name', users: 'display_name', entries: 'title' }[props.resource]))
const secondaryKey = computed(() => ({ sales: 'name', projects: 'code', users: 'username', entries: 'project_name' }[props.resource]))
const shownColumns = computed(() => columns[props.resource]?.filter(col => (!props.projectId || col.key !== 'project_name') && col.key !== secondaryKey.value))
function primaryAction(row: Row) {
  const actions = actionNames(props.resource, row)
  return ['批准采购', '收货', '提交采购', '登记收付款', '完成任务', '查看明细', '查看收付流水'].find(name => actions.includes(name))
}
const moneyKeys = new Set(['amount', 'credit_amount', 'paid_amount', 'balance', 'value', 'unit_price', 'contract_amount', 'quote_amount', 'fee', 'hourly_cost', 'supplier_credit'])
function cell(row: Row, key: string) {
  if (!moneyKeys.has(key) || row[key] == null) return display(row[key])
  const value = String(row[key])
  const refund = key === 'balance' && value.startsWith('-')
  const [integer, fraction = ''] = (refund ? value.slice(1) : value).split('.')
  return `${refund ? '待退款 ' : ''}${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`
}
function mobileSummary(row: Row) {
  if (props.resource === 'entries') return `待结算 ${cell(row, 'balance')} · ${display(row.kind)}`
  if (props.resource === 'payments') return `${cell(row, 'amount')} 元 · ${row.date}`
  return [row.status ? display(row.status) : '', row.quantity ? `数量 ${row.quantity}` : ''].filter(Boolean).join(' · ')
}
async function load() {
  if (!active.value) { dirty = true; return }
  dirty = false
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = await read(endpoint(props.resource), {
      ...props.params,
      ...filterParams.value,
      page: page.value,
      page_size: pageSize.value,
      search: appliedSearch.value,
    })
    if (current !== generation) return
    records.value = result.results
    count.value = result.count
    const focus = String(route.query.focus || '')
    if (route.query.resource === props.resource && /^\d+$/.test(focus) && focused !== focus) {
      const row = await read(`${endpoint(props.resource)}${focus}/`)
      if (current !== generation) return
      if (props.projectId && Number(row.project) !== props.projectId) return
      focused = focus
      if (props.resource === 'purchases') await action(row, '查看明细')
      else if (props.resource === 'entries') await action(row, '查看收付流水')
      else if (props.resource === 'reconciliations') await action(row, '查看对账明细')
      else if (props.resource === 'bank-records') await action(row, '查看银行明细')
      else { command.value = { title: '待办详情', path: '', readonly: true, initial: row, fields: [{ key: 'title', label: '任务' }, { key: 'description', label: '说明', type: 'textarea' }, { key: 'due_date', label: '期限' }], actions: actionNames(props.resource, row).map(label => ({ label, run: () => action(row, label) })) } }
    }
  } catch (e) {
    if (current === generation) error.value = message(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
watch(
  [() => props.resource, () => JSON.stringify(props.params || {}), () => pageSize.value],
  () => {
    page.value = 1
    search.value = sessionStorage.getItem(searchKey()) || ''
    appliedSearch.value = search.value
    focused = ''
    void load()
  },
  { immediate: true },
)
watch(() => props.revision, () => { void load() })
watch(active, value => { if (value && dirty) void load() })
watch([() => route.query.focus, () => route.query.resource], () => {
  if (route.query.resource === props.resource && route.query.focus) void load()
})
async function create() {
  if (actionBusy.value) return
  selectedId.value = null
  selectedRow.value = null
  const current = ++commandGeneration
  preparing.value = true
  try {
    const next = await createCommand(props.resource, props.projectId)
    if (current === commandGeneration) command.value = next
  } catch (e) {
    if (current === commandGeneration) error.value = message(e)
  } finally { if (current === commandGeneration) preparing.value = false }
}
async function action(row: Row, name: string) {
  if (actionBusy.value) return
  selectedId.value = row.id
  selectedRow.value = row
  const current = ++commandGeneration
  preparing.value = true
  try {
    if (props.resource === 'purchases' && name === '预览采购合同') {
      await router.push(`/purchases/${row.id}/contract`)
      return
    }
    if (name === '附件' && ['sales', 'purchases'].includes(props.resource)) {
      command.value = null
      attachmentRow.value = row
      return
    }
    if (name === '下载') await download(row.download_url, row.original_name)
    else if (name === '下载凭证') {
      const doc = await read(`/business/documents/${row.document}/`)
      await download(doc.download_url, doc.original_name)
    }
    else {
      const next = await actionCommand(props.resource, row, name)
      if (current !== commandGeneration) return
      if (next.readonly) next.actions = [...(next.actions || []), ...actionNames(props.resource, row).filter(label => label !== name).map(label => ({ label, run: () => action(row, label) }))]
      next.subject = row.code || row.title || row.reference || `#${row.id}`
      command.value = next
    }
  } catch (e) {
    if (current === commandGeneration) error.value = message(e)
  } finally { if (current === commandGeneration) preparing.value = false }
}
function saved() {
  if (props.revision === undefined) void load()
  emit('changed')
}
function searchRecords() {
  appliedExtra.value = {
    ...(enabledFilter.value && ['users', 'items', 'partners'].includes(props.resource) ? { is_active: enabledFilter.value } : {}),
    ...(locationFilter.value && props.resource === 'stocks' ? { location: locationFilter.value } : {}),
    ...(brandFilter.value && ['stocks', 'items'].includes(props.resource) ? { [props.resource === 'stocks' ? 'item__brand' : 'brand']: brandFilter.value } : {}),
    ...(unsettled.value && props.resource === 'entries' ? { unsettled: 'true' } : {}),
  }
  appliedSearch.value = search.value
  sessionStorage.setItem(searchKey(), appliedSearch.value)
  page.value = 1
  void load()
}
function closeCommand() {
  commandGeneration++
  preparing.value = false
  command.value = null
  selectedId.value = null
  selectedRow.value = null
  focused = ''
  if (route.query.resource === props.resource && route.query.focus) {
    const { focus: _focus, resource: _resource, ...query } = route.query
    void router.replace({ query })
  }
}
function changeFilter(value: string) {
  if (actionBusy.value) return
  filterValue.value = value
  page.value = 1
  void load()
}
function inspect(row: Row) {
  if (actionBusy.value) return
  const names = actionNames(props.resource, row)
  const view = names.find(name => ['查看明细', '查看收付流水', '查看对账明细', '查看银行明细'].includes(name))
  if (view && props.resource !== 'entries') return action(row, view)
  if (['users', 'items', 'partners', 'company', 'codes'].includes(props.resource) && names.includes('编辑')) return action(row, '编辑')
  selectedId.value = row.id
  selectedRow.value = row
  command.value = { title: `${props.title}详情`, path: '', readonly: true, subject: row.code || row.name || row.title,
    initial: Object.fromEntries((columns[props.resource] || []).map(col => [col.key, col.format ? col.format(row) : cell(row, col.key)])),
    fields: (columns[props.resource] || []).map(col => ({ key: col.key, label: col.label, wide: props.resource === 'audit' && col.key === 'detail' })),
    actions: names.map(label => ({ label, run: () => action(row, label) })),
  }
}
</script>
<template>
  <div class="resource-workspace" :class="{ 'with-detail': sidePanel && command }">
  <section class="panel resource-list" :aria-label="title">
    <header class="panel-heading">
      <h2>
        {{ title }} <span class="record-count">{{ count }}</span>
      </h2>
      <Teleport :to="toolbarTarget || 'body'" :disabled="!toolbarTarget || !active"><div class="toolbar">
        <BOMPurchasePicker v-if="resource === 'purchases'" :project-id="projectId" @saved="saved" />
        <TransferTools v-if="!['users', 'company', 'codes', 'audit'].includes(resource)" :resource="resource" :path="endpoint(resource)" :params="{ ...params, ...filterParams, search: appliedSearch }" :table-columns="columns[resource]" @changed="saved" />
        <el-button @click="load">刷新</el-button
        ><el-button v-if="createLabel(resource) && allowCreate !== false" type="primary" @click="create">{{
          createLabel(resource)
        }}</el-button>
      </div></Teleport>
    </header>
    <div v-if="filterConfig && resource !== 'users'" class="resource-status-tabs" :aria-label="filterConfig.label">
      <button :aria-pressed="!filterValue" :disabled="actionBusy" @click="changeFilter('')">全部 <span v-if="!filterValue" class="record-count">{{ count }}</span></button>
      <button v-for="(label, value) in filterConfig.options" :key="value" :aria-pressed="filterValue === value" :disabled="actionBusy" @click="changeFilter(value)">{{ label }}</button>
    </div>
    <form v-if="searchableResources.includes(resource)" class="resource-search" @submit.prevent="searchRecords">
      <input v-model="search" type="search" :aria-label="`搜索${title}`" placeholder="输入名称、编号或关键词" />
      <select v-if="resource === 'users' && filterConfig" v-model="filterValue" aria-label="筛选用户角色" @change="searchRecords"><option value="">全部角色</option><option v-for="(label, value) in filterConfig.options" :key="value" :value="value">{{ label }}</option></select>
      <select v-if="['users', 'items', 'partners'].includes(resource)" v-model="enabledFilter" aria-label="筛选启用状态" @change="searchRecords"><option value="">全部状态</option><option value="true">启用</option><option value="false">停用</option></select>
      <input v-if="resource === 'stocks'" v-model="locationFilter" aria-label="筛选库位" placeholder="库位" />
      <input v-if="['stocks', 'items'].includes(resource)" v-model="brandFilter" aria-label="筛选品牌名称" placeholder="品牌（完整名称）" />
      <label v-if="resource === 'entries'" class="inline-check"><input v-model="unsettled" type="checkbox" @change="searchRecords" />仅看未结</label>
      <el-button native-type="submit" :loading="loading">搜索</el-button>
      <el-button v-if="search || filterValue || enabledFilter || locationFilter || brandFilter || unsettled" text @click="search = ''; filterValue = ''; enabledFilter = ''; locationFilter = ''; brandFilter = ''; unsettled = false; searchRecords()">重置</el-button>
    </form>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
    <p v-if="preparing" role="status">正在准备操作…</p>
    <el-table
      v-loading="loading"
      :data="records"
      :max-height="560"
      stripe
      row-key="id"
      :row-class-name="({ row }: { row: Row }) => row.id === selectedId ? 'selected-record' : ''"
      empty-text="暂无记录"
      style="width: 100%"
    >
      <el-table-column
        v-for="col in shownColumns"
        :key="col.key"
        :label="col.key === combinedKey ? `${col.label} / ${columns[resource]?.find(c => c.key === secondaryKey)?.label}` : col.label"
        :align="moneyKeys.has(col.key) ? 'right' : 'left'"
        :min-width="col.key === combinedKey || col.key === 'title' || col.key === 'name' ? 190 : ['status', 'is_active'].includes(col.key) ? 100 : 125"
        show-overflow-tooltip
      >
        <template #default="{ row }"
          ><router-link v-if="resource === 'projects' && col.key === 'name'" :to="`/projects/${row.id}`">{{
            row.name
          }}</router-link
          ><router-link v-else-if="resource === 'sales' && col.key === 'project_code' && row.project && operations()" :to="`/projects/${row.project}`">{{ row.project_code }}</router-link
          ><StatusBadge v-else-if="['status', 'is_active', 'kind'].includes(col.key)" :value="row[col.key]" :text="col.format?.(row)" />
          <span v-else-if="col.key === 'roles'" class="role-tags"><StatusBadge v-for="role in row.roles || [row.role]" :key="role" :value="role" :text="labels[role] || role" /></span>
          <StatusBadge v-else-if="col.key === 'management_reports'" :value="row[col.key] || row.is_superuser || (row.roles || [row.role]).includes('admin')" :text="row.is_superuser || (row.roles || [row.role]).includes('admin') ? '管理员默认' : row[col.key] ? '已授权' : '未授权'" />
          <button v-else-if="sidePanel && col.key === shownColumns?.[0]?.key" class="record-link" :disabled="actionBusy" @click="inspect(row)">{{ col.format ? col.format(row) : cell(row, col.key) }}</button>
          <span v-else>{{ col.format ? col.format(row) : cell(row, col.key) }}</span><small v-if="col.key === combinedKey && secondaryKey" class="record-secondary">{{ row[secondaryKey] }}</small><small v-if="col.key === shownColumns?.[0]?.key" class="mobile-row-summary">{{ mobileSummary(row) }}</small></template
        >
      </el-table-column>
      <el-table-column label="操作" fixed="right" width="150"
        ><template #default="{ row }"
          ><el-button v-if="primaryAction(row)" link type="primary" size="small" @click="action(row, primaryAction(row)!)">{{ primaryAction(row) }}</el-button
          ><el-dropdown
            v-if="actionNames(resource, row).length"
            trigger="click"
            :persistent="false"
            @command="(name: string) => action(row, String(name))"
            ><el-button size="small">操作 ▾</el-button
            ><template #dropdown
              ><el-dropdown-menu
                ><el-dropdown-item v-for="name in actionNames(resource, row)" :key="name" :command="name">{{
                  name
                }}</el-dropdown-item></el-dropdown-menu
              ></template
            ></el-dropdown
          ><span v-else class="muted">—</span></template
        ></el-table-column
      >
    </el-table>
    <ListPagination :page="page" :total="count" @change="page = $event; load()" />
    <AttachmentDialog v-if="attachmentRow" :owner="resource === 'sales' ? 'sale' : 'purchase'" :record="attachmentRow" @close="attachmentRow = null" />
  </section>
  <ActionDialog :command="command" :inline="sidePanel" @busy="actionBusy = $event" @close="closeCommand" @saved="saved"><template #context><RecordContext v-if="selectedRow && (['stocks', 'entries'].includes(resource) || (['sales', 'purchases'].includes(resource) && actionNames(resource, selectedRow).includes('附件')))" :resource="resource" :record="selectedRow" @attachments="action(selectedRow!, '附件')" /></template></ActionDialog>
  </div>
</template>
