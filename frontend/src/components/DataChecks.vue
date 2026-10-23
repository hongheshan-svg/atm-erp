<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { read } from '../api'
import { can } from '../session'
import { pageSize } from '../pagination'
import type { Row } from '../types'
import { money } from '../utils/money'
import { message } from '../utils/request'
import ListPagination from './ListPagination.vue'
import TransferTools from './TransferTools.vue'

// 只读清单：与后端 GET /api/business/data-checks/ 一致，仅管理员可见；处理一律回到原单上的冲销、作废、取消等动作。
const notice = '只读核查，不会修改任何数据；请用原单上的冲销、作废、取消等动作处理。'
const categories = ref<Row[]>([])
const category = ref('')
const rows = ref<Row[]>([])
const count = ref(0)
const page = ref(1)
const busy = ref(false)
const error = ref('')
let generation = 0
onBeforeUnmount(() => { generation++ })
async function load() {
  if (!can(['admin'])) return
  const current = ++generation
  busy.value = true
  error.value = ''
  try {
    const result = await read('/business/data-checks/', { ...(category.value ? { category: category.value } : {}), page: page.value, page_size: pageSize.value })
    if (current !== generation) return
    categories.value = result.categories
    category.value = result.category
    rows.value = result.results
    count.value = result.count
  } catch (e) { if (current === generation) error.value = message(e) } finally { if (current === generation) busy.value = false }
}
function choose(key: string) {
  if (key === category.value && !error.value) return
  category.value = key
  page.value = 1
  rows.value = []
  void load()
}
watch(pageSize, () => { page.value = 1; void load() })
void load()
</script>
<template>
  <section v-if="can(['admin'])" class="panel data-checks" aria-label="历史数据核查">
    <h2>历史数据核查</h2>
    <el-alert :title="notice" type="info" :closable="false" show-icon />
    <p class="muted">列出新规则上线前已经存在、按现行规则需要人工核对的记录。系统不会自动冲销、作废、合并或删除；请打开原单核对后，由财务或采购用原单上的动作处理，处理完成后刷新即从清单中消失。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <div class="data-check-categories" role="group" aria-label="核查类别">
      <el-button v-for="item in categories" :key="item.key" :type="item.key === category ? 'primary' : 'default'" :aria-pressed="item.key === category" :disabled="busy" @click="choose(item.key)">{{ item.label }}（{{ item.count }}）</el-button>
    </div>
    <div class="toolbar"><el-button :loading="busy" @click="load">刷新</el-button><TransferTools v-if="category" resource="data-checks" path="/business/data-checks/" export-path="/business/data-checks/" :params="{ category }" :allow-import="false" /></div>
    <p v-if="busy && !rows.length" role="status">正在核查…</p>
    <p v-else-if="!rows.length && !error && categories.length" role="status">该类别暂无需要核对的记录。</p>
    <table v-if="rows.length" class="data-check-table">
      <thead><tr><th scope="col">记录类型</th><th scope="col">编号/标题</th><th scope="col">项目编号</th><th scope="col">金额</th><th scope="col">问题说明</th><th scope="col">原单</th></tr></thead>
      <tbody>
        <tr v-for="row in rows" :key="`${row.record_type}-${row.record_id}`">
          <td data-label="记录类型">{{ row.record_type_label }} · ID {{ row.record_id }}</td>
          <td data-label="编号/标题">{{ row.title }}</td>
          <td data-label="项目编号">{{ row.project_code || '—' }}</td>
          <td data-label="金额" class="data-check-amount">{{ money(row.amount) }}</td>
          <td data-label="问题说明" class="data-check-problem">{{ row.problem }}</td>
          <td data-label="原单"><router-link :to="row.path">打开原单</router-link></td>
        </tr>
      </tbody>
    </table>
    <ListPagination v-if="count" :page="page" :total="count" @change="page = $event; load()" />
  </section>
</template>
<style scoped>
.data-checks > p { line-height: 1.6; }
.data-check-categories { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.data-check-categories .el-button { margin: 0; }
.data-check-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.data-check-table th, .data-check-table td { padding: 10px 8px; border-bottom: 1px solid var(--field-line); text-align: left; vertical-align: top; overflow-wrap: anywhere; }
.data-check-amount { white-space: nowrap; }
.data-check-problem { min-width: 240px; line-height: 1.6; }
@media (max-width: 760px) {
  .data-check-table thead { display: none; }
  .data-check-table, .data-check-table tbody, .data-check-table tr, .data-check-table td { display: block; width: 100%; box-sizing: border-box; }
  .data-check-table tr { padding: 8px 0; border-bottom: 1px solid var(--field-line); }
  .data-check-table td { display: grid; grid-template-columns: 6em minmax(0, 1fr); gap: 8px; padding: 4px 0; border: 0; min-width: 0; }
  .data-check-table td::before { content: attr(data-label); color: var(--el-text-color-secondary); }
  .data-check-amount { white-space: normal; }
}
</style>
