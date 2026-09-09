<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
import { pageSize } from '../pagination'
import { useRoute, useRouter } from 'vue-router'
import { user } from '../session'
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
const search = ref(sessionStorage.getItem(searchKey()) || '')
const appliedSearch = ref(search.value)
const loading = ref(false)
const error = ref('')
const command = ref<Command | null>(null)
let generation = 0
let focused = ''
const shownColumns = computed(() => columns[props.resource]?.filter(col => !props.projectId || col.key !== 'project_name'))
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
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = await read(endpoint(props.resource), {
      ...props.params,
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
      else { command.value = { title: '待办详情', path: '', readonly: true, initial: row, fields: [{ key: 'title', label: '任务' }, { key: 'description', label: '说明', type: 'textarea' }, { key: 'due_date', label: '期限' }], actions: actionNames(props.resource, row).map(label => ({ label, run: () => action(row, label) })) } }
    }
  } catch (e) {
    if (current === generation) error.value = message(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
watch(
  () => [props.resource, JSON.stringify(props.params || {}), pageSize.value],
  () => {
    page.value = 1
    search.value = sessionStorage.getItem(searchKey()) || ''
    appliedSearch.value = search.value
    focused = ''
    void load()
  },
  { immediate: true, deep: true },
)
watch(() => props.revision, () => { void load() })
watch(() => [route.query.focus, route.query.resource], () => { void load() })
async function create() {
  try {
    command.value = await createCommand(props.resource, props.projectId)
  } catch (e) {
    error.value = message(e)
  }
}
async function action(row: Row, name: string) {
  try {
    if (name === '下载') await download(row.download_url, row.original_name)
    else if (name === '下载凭证') {
      const doc = await read(`/business/documents/${row.document}/`)
      await download(doc.download_url, doc.original_name)
    }
    else {
      const next = await actionCommand(props.resource, row, name)
      if (next.readonly) next.actions = [...(next.actions || []), ...actionNames(props.resource, row).filter(label => label !== name).map(label => ({ label, run: () => action(row, label) }))]
      command.value = next
    }
  } catch (e) {
    error.value = message(e)
  }
}
function saved() {
  void load()
  emit('changed')
}
function searchRecords() {
  appliedSearch.value = search.value
  sessionStorage.setItem(searchKey(), appliedSearch.value)
  page.value = 1
  void load()
}
function closeCommand() {
  command.value = null
  focused = ''
  if (route.query.resource === props.resource && route.query.focus) {
    const { focus: _focus, resource: _resource, ...query } = route.query
    void router.replace({ query })
  }
}
</script>
<template>
  <section class="panel" :aria-label="title">
    <header class="panel-heading">
      <h2>
        {{ title }} <span class="record-count">{{ count }}</span>
      </h2>
      <div class="toolbar">
        <BOMPurchasePicker v-if="resource === 'purchases'" :project-id="projectId" @saved="saved" />
        <TransferTools v-if="!['users', 'company', 'codes', 'audit'].includes(resource)" :resource="resource" :path="endpoint(resource)" :params="{ ...params, search: appliedSearch }" @changed="saved" />
        <form
          v-if="['sales', 'projects', 'purchases', 'items', 'partners'].includes(resource)"
          @submit.prevent="searchRecords"
        >
          <input
            v-model="search"
            type="search"
            :aria-label="`搜索${title}`"
            placeholder="输入名称搜索"
          /><el-button native-type="submit">搜索</el-button>
        </form>
        <el-button @click="load">刷新</el-button
        ><el-button v-if="createLabel(resource) && allowCreate !== false" type="primary" @click="create">{{
          createLabel(resource)
        }}</el-button>
      </div>
    </header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
    <el-table
      v-loading="loading"
      :data="records"
      :max-height="560"
      stripe
      row-key="id"
      empty-text="暂无记录"
      style="width: 100%"
    >
      <el-table-column
        v-for="col in shownColumns"
        :key="col.key"
        :label="col.label"
        :align="moneyKeys.has(col.key) ? 'right' : 'left'"
        :min-width="col.key === 'title' || col.key === 'name' ? 180 : 125"
        show-overflow-tooltip
      >
        <template #default="{ row }"
          ><router-link v-if="resource === 'projects' && col.key === 'name'" :to="`/projects/${row.id}`">{{
            row.name
          }}</router-link
          ><router-link v-else-if="resource === 'sales' && col.key === 'project_code' && row.project" :to="`/projects/${row.project}`">{{ row.project_code }}</router-link
          ><span v-else>{{ col.format ? col.format(row) : cell(row, col.key) }}</span><small v-if="col.key === shownColumns?.[0]?.key" class="mobile-row-summary">{{ mobileSummary(row) }}</small></template
        >
      </el-table-column>
      <el-table-column label="操作" fixed="right" width="150"
        ><template #default="{ row }"
          ><el-button v-if="primaryAction(row)" link type="primary" size="small" @click="action(row, primaryAction(row)!)">{{ primaryAction(row) }}</el-button
          ><el-dropdown
            v-if="actionNames(resource, row).length"
            trigger="click"
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
    <ActionDialog :command="command" @close="closeCommand" @saved="saved" />
  </section>
</template>
