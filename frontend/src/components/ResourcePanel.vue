<script setup lang="ts">
import { ref, watch } from 'vue'
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
const search = ref('')
const loading = ref(false)
const error = ref('')
const command = ref<Command | null>(null)
let generation = 0
async function load() {
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = await read(endpoint(props.resource), {
      ...props.params,
      page: page.value,
      search: search.value,
    })
    if (current !== generation) return
    records.value = result.results
    count.value = result.count
  } catch (e) {
    if (current === generation) error.value = message(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
watch(
  () => [props.resource, props.params, props.revision],
  () => {
    page.value = 1
    void load()
  },
  { immediate: true, deep: true },
)
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
    else command.value = await actionCommand(props.resource, row, name)
  } catch (e) {
    error.value = message(e)
  }
}
function saved() {
  void load()
  emit('changed')
}
function searchRecords() {
  page.value = 1
  void load()
}
</script>
<template>
  <section class="panel" :aria-label="title">
    <header class="panel-heading">
      <h2>
        {{ title }} <span class="muted">{{ count }}</span>
      </h2>
      <div class="toolbar">
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
      stripe
      row-key="id"
      empty-text="暂无记录"
      style="width: 100%"
    >
      <el-table-column
        v-for="col in columns[resource]"
        :key="col.key"
        :label="col.label"
        :min-width="col.key === 'title' || col.key === 'name' ? 180 : 125"
        show-overflow-tooltip
      >
        <template #default="{ row }"
          ><router-link v-if="resource === 'projects' && col.key === 'name'" :to="`/projects/${row.id}`">{{
            row.name
          }}</router-link
          ><router-link v-else-if="resource === 'sales' && col.key === 'project_code' && row.project" :to="`/projects/${row.project}`">{{ row.project_code }}</router-link
          ><span v-else>{{ col.format ? col.format(row) : display(row[col.key]) }}</span></template
        >
      </el-table-column>
      <el-table-column label="操作" fixed="right" width="150"
        ><template #default="{ row }"
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
    <el-pagination
      v-if="count > 20"
      v-model:current-page="page"
      :page-size="20"
      :total="count"
      layout="prev,pager,next,total"
      @current-change="load"
    />
    <ActionDialog :command="command" @close="command = null" @saved="saved" />
  </section>
</template>
