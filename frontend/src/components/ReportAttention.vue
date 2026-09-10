<script setup lang="ts">
import { ref, watch } from 'vue'
import { read } from '../api'
import { message } from '../utils/request'
import type { Row } from '../types'
import ListPagination from './ListPagination.vue'
import { pageSize } from '../pagination'
const opened = ref(false), view = ref('cash30'), data = ref<Row | null>(null), error = ref(''), busy = ref(false)
let generation = 0
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
  <section class="panel">
    <el-button @click="opened = !opened; opened && load()">{{ opened ? '收起' : '展开' }}资金与采购库存关注</el-button>
    <template v-if="opened"><p class="muted">全公司只读原业务明细，独立于下方项目筛选；不授予项目编辑或财务记账权限。</p><label>关注视图 <select v-model="view" aria-label="经营关注视图"><option value="cash30">未来30天到期资金</option><option value="aging">逾期账龄</option><option value="late_purchase">采购逾期</option><option value="stale_stock">90天未动库存</option></select></label><el-button :loading="busy" @click="load">刷新明细</el-button>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <template v-if="data"><p>{{ data.definition }}</p><el-table :data="data.results" stripe max-height="430"><el-table-column prop="source" label="来源单据 / 物料" min-width="220" /><el-table-column prop="project" label="项目" /><el-table-column prop="date" label="到期 / 最后移动" /><el-table-column prop="amount" :label="['cash30', 'aging'].includes(view) ? '金额（元）' : '数量'" /><el-table-column prop="status" label="跟进事项" /><el-table-column v-if="view === 'aging'" prop="age_band" label="账龄段" /></el-table><ListPagination :page="data.page" :total="data.count" @change="load" /></template>
    </template>
  </section>
</template>
