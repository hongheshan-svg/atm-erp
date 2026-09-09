<script setup lang="ts">
import { ref, watch } from 'vue'
import { read } from '../api'
import type { Row } from '../types'
import { message } from '../utils/request'
import ListPagination from './ListPagination.vue'
import { pageSize } from '../pagination'
const props = defineProps<{ projectId: number }>()
const category = ref('materials')
const page = ref(1)
const data = ref<Row>({ results: [], count: 0 })
const error = ref('')
let generation = 0
async function load() {
  const current = ++generation
  error.value = ''
  try {
    const result = await read(`/business/projects/${props.projectId}/cost-sources/`, { category: category.value, page: page.value, page_size: pageSize.value })
    if (current === generation) data.value = result
  } catch (e) { if (current === generation) error.value = message(e) }
}
watch([category, pageSize, () => props.projectId], () => { page.value = 1; void load() }, { immediate: true })
</script>
<template>
  <label>成本类别<select v-model="category"><option value="materials">材料领退料</option><option value="labor">任务人工</option><option value="expenses">费用</option><option value="purchase_return_variance">采购退货价差</option></select></label>
  <p class="muted">按成本贡献从高到低排列，负数为退回或冲销；复用原流水，不生成新台账。</p>
  <el-alert v-if="error" :title="error" type="error" />
  <el-table :data="data.results" max-height="420"><el-table-column prop="id" label="原记录" width="90" /><el-table-column prop="description" label="来源说明" min-width="230" /><el-table-column prop="amount" label="成本贡献（元）" align="right" width="150" /><el-table-column prop="date" label="登记时间" min-width="180" /></el-table>
  <ListPagination :page="page" :total="data.count" @change="page = $event; load()" />
</template>
