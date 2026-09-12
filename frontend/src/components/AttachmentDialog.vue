<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { read, download } from '../api'
import { can, purchasing } from '../session'
import { display } from '../business'
import { message } from '../utils/request'
import { pageSize } from '../pagination'
import type { Row, Command } from '../types'
import ActionDialog from './ActionDialog.vue'
import ListPagination from './ListPagination.vue'

const props = defineProps<{ owner: 'sale' | 'purchase'; record: Row }>()
const emit = defineEmits<{ close: [] }>()
const title = computed(() => `${props.owner === 'sale' ? '销售' : '采购'}附件 · ${props.record.code}`)
const writable = computed(() => props.record.status !== 'cancelled' && (props.owner === 'sale' ? can(['admin', 'manager', 'sales_manager']) : purchasing()))
const records = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const command = ref<Command | null>(null)
let generation = 0
async function load() {
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = await read('/business/documents/', { [props.owner]: props.record.id, page: page.value, page_size: pageSize.value })
    if (current === generation) { records.value = result.results; total.value = result.count }
  } catch (e) { if (current === generation) { records.value = []; total.value = 0; error.value = message(e) } }
  finally { if (current === generation) loading.value = false }
}
function upload() {
  command.value = {
    title: props.owner === 'sale' ? '上传销售附件' : '上传采购附件', path: '/business/documents/',
    fields: [
      { key: 'category', label: '分类', type: 'select', options: [{ value: 'contract', label: '合同' }, { value: 'other', label: '其他（报价及技术资料）' }] },
      { key: 'file', label: '文件', type: 'file', hint: '单个文件不超过 20 MB；重新上传会保留原文件。' },
    ], initial: { category: 'contract' }, prepare: data => ({ ...data, [props.owner]: props.record.id }),
  }
}
async function downloadFile(row: Row) {
  try { await download(row.download_url, row.original_name) }
  catch (e) { error.value = message(e) }
}
watch([() => props.owner, () => props.record.id, pageSize], () => { page.value = 1; void load() }, { immediate: true })
</script>
<template>
  <el-dialog class="transfer-dialog" :model-value="true" :title="title" width="min(800px, 94vw)" append-to-body @close="emit('close')">
    <p class="muted">附件关联当前单据，项目中自动汇总。仅有权限的人员可查看和下载。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <div class="toolbar"><el-button :loading="loading" @click="load">刷新</el-button><el-button v-if="writable" type="primary" @click="upload">上传附件</el-button></div>
    <el-table :data="records" :aria-busy="loading" max-height="420">
      <el-table-column prop="original_name" label="文件" min-width="220" />
      <el-table-column label="分类" min-width="80"><template #default="{ row }">{{ display(row.category) }}</template></el-table-column>
      <el-table-column label="大小" width="100"><template #default="{ row }">{{ Math.max(1, Math.ceil(row.size / 1024)) }} KB</template></el-table-column>
      <el-table-column label="上传时间" min-width="170"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN', { hour12: false }) }}</template></el-table-column>
      <el-table-column label="操作" width="80" fixed="right"><template #default="{ row }"><el-button size="small" @click="downloadFile(row)">下载</el-button></template></el-table-column>
    </el-table>
    <ListPagination :page="page" :total="total" @change="page = $event; load()" />
    <template #footer><el-button @click="emit('close')">关闭</el-button></template>
  </el-dialog>
  <ActionDialog :command="command" @close="command = null" @saved="load" />
</template>
<style scoped>
.toolbar { margin-bottom: 12px; }
</style>
