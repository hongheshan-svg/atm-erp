<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { Document, Download } from '@element-plus/icons-vue'
import { read, download } from '../api'
import { display } from '../business'
import { message } from '../utils/request'
import type { Row } from '../types'
const props = defineProps<{ resource: string; record: Row }>()
const emit = defineEmits<{ attachments: [] }>()
const rows = ref<Row[]>([]), error = ref(''), loading = ref(false)
let generation = 0
async function load() {
  const current = ++generation
  rows.value = []; error.value = ''; loading.value = true
  try {
    const result = await read(props.resource === 'stocks' ? '/business/moves/' : props.resource === 'entries' ? '/business/reconciliations/' : '/business/documents/', {
      ...(props.resource === 'stocks' ? { stock: props.record.id } : props.resource === 'entries' ? { entry: props.record.id, status: 'confirmed' } : { [props.resource === 'sales' ? 'sale' : 'purchase']: props.record.id }),
      page_size: 3,
    })
    if (generation === current) rows.value = result.results
  } catch (e) { if (generation === current) error.value = message(e) }
  finally { if (generation === current) loading.value = false }
}
async function downloadFile(row: Row) {
  try { await download(row.download_url, row.original_name) }
  catch (e) { error.value = message(e) }
}
watch(() => [props.resource, props.record.id], load, { immediate: true })
onBeforeUnmount(() => { generation++ })
</script>
<template>
  <section class="record-context" :aria-label="resource === 'stocks' ? '最近库存流水' : resource === 'entries' ? '对账信息' : '合同与技术附件'" :aria-busy="loading">
    <header><h3>{{ resource === 'stocks' ? '最近库存流水' : resource === 'entries' ? '对账信息' : '合同与技术附件' }}</h3><el-button v-if="['sales', 'purchases'].includes(resource)" link type="primary" @click="emit('attachments')">查看全部附件</el-button><el-button v-else link @click="load">刷新</el-button></header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" /><el-button v-if="error" @click="load">重试</el-button>
    <p v-if="loading" class="muted">正在加载…</p><p v-else-if="!rows.length && !error" class="muted">{{ resource === 'stocks' ? '暂无库存流水' : resource === 'entries' ? '暂无已确认对账。采购付款及退款需先核对；客户到账可直接登记。' : '暂无附件，可从附件入口上传合同及技术资料。' }}</p>
    <template v-for="row in rows" :key="row.id">
      <div v-if="resource === 'stocks'" class="stock-history-row"><span>{{ display(row.kind) }}<small>{{ row.created_at?.slice(0, 10) }}</small></span><strong>{{ row.quantity }}</strong></div>
      <div v-else-if="resource === 'entries'" class="stock-history-row"><span><router-link :to="{ path: '/finance', query: { section: 'reconciliations', resource: 'reconciliations', focus: row.id } }">{{ row.code }}</router-link><small>{{ row.valid ? `剩余核准额度 ¥ ${row.remaining_amount}` : '原业务已变化，请重新核对' }}</small></span></div>
      <div v-else class="file-summary"><el-icon><Document /></el-icon><span>{{ row.original_name }}<small>{{ Math.max(1, Math.ceil(row.size / 1024)) }} KB · {{ row.created_at?.slice(0, 10) }}</small></span><el-button :icon="Download" text :aria-label="`下载 ${row.original_name}`" @click="downloadFile(row)" /></div>
    </template>
  </section>
</template>
<style scoped>
.record-context { border-top: 1px solid var(--surface-border); margin-top: 20px; padding-top: 16px; }
.record-context header, .file-summary, .stock-history-row { display: flex; align-items: center; gap: 10px; }
.record-context h3 { margin: 0; flex: 1; }
.record-context header { margin-bottom: 14px; flex-wrap: wrap; }
.file-summary, .stock-history-row { border: 1px solid #e8edf4; border-radius: 6px; padding: 10px; margin-top: 8px; font-size: 13px; }
.file-summary > span, .stock-history-row > span { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.file-summary > .el-icon { color: #2563eb; font-size: 20px; flex-shrink: 0; }
small { display: block; font-size: 11px; margin-top: 6px; }
</style>
