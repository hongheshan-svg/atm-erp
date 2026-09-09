<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { download, write } from '../api'
import { can } from '../session'
import { message } from '../utils/request'
import type { Row } from '../types'
import ListPagination from './ListPagination.vue'
import { pageSize } from '../pagination'

const props = defineProps<{ resource: string; path: string; params?: Row; exportPath?: string }>()
const emit = defineEmits<{ changed: [] }>()
const format = ref('xlsx')
const busy = ref(false)
const error = ref('')
const opened = ref(false)
const preview = ref<Row | null>(null)
const result = ref('')
const page = ref(1)
const roles: Record<string, string[]> = {
  items: ['admin', 'manager', 'purchaser'], partners: ['admin', 'manager', 'purchaser', 'sales_manager'],
  sales: ['admin', 'manager', 'sales_manager'], projects: ['admin', 'manager'], purchases: ['admin', 'manager', 'purchaser'],
  tasks: ['admin', 'manager'], stocks: ['admin'], entries: ['admin', 'finance'], payments: ['admin', 'finance'],
  time: ['admin', 'manager', 'purchaser', 'warehouse', 'finance', 'member'],
  moves: ['admin', 'warehouse'], deliveries: ['admin', 'manager'],
}
const importable = computed(() => !!roles[props.resource] && can(roles[props.resource]!))
const visibleRows = computed(() => preview.value?.rows.slice((page.value - 1) * pageSize.value, page.value * pageSize.value) || [])
watch(pageSize, () => { page.value = 1 })
watch(() => props.resource, () => { preview.value = null; opened.value = false; error.value = ''; result.value = '' })
async function file(template = false) {
  busy.value = true
  error.value = ''
  try {
    await download(template ? `${props.path}import-template/` : (props.exportPath || `${props.path}export/`),
      `${props.resource}${template ? '-template' : ''}.${format.value}`, { ...(template ? {} : props.params), file_format: format.value })
  } catch (e) { error.value = message(e) } finally { busy.value = false }
}
async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const selected = input.files?.[0]
  if (!selected) return
  busy.value = true
  error.value = ''
  preview.value = null
  result.value = ''
  try {
    const data = new FormData()
    data.append('file', selected)
    preview.value = await write(`${props.path}import-file/`, data, crypto.randomUUID())
    page.value = 1
  } catch (e) { error.value = message(e) } finally { busy.value = false; input.value = '' }
}
async function confirm() {
  if (!preview.value?.can_import) return
  busy.value = true
  error.value = ''
  try {
    const data = await write(`${props.path}import-confirm/`, { token: preview.value.token }, crypto.randomUUID())
    result.value = `成功导入 ${data.count} 条记录`
    preview.value = null
    emit('changed')
  } catch (e) { error.value = message(e) } finally { busy.value = false }
}
</script>
<template>
  <div class="transfer-tools">
    <select v-model="format" aria-label="导入导出格式" :disabled="busy"><option value="xlsx">Excel</option><option value="csv">CSV</option></select>
    <el-button :loading="busy" @click="file()">导出</el-button>
    <el-button v-if="importable" :disabled="busy" @click="opened = true; error = ''; result = ''">导入</el-button>
    <span v-if="error && !opened" role="alert">{{ error }}</span>
    <el-dialog v-model="opened" class="transfer-dialog" title="批量导入" width="min(780px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" destroy-on-close>
      <p>下载模板后填写，支持 CSV / XLSX，最多 1000 行、5 MB。引用使用编号或账号；标明 ID 的列可从对应列表导出获取。日期填写 YYYY-MM-DD。</p>
      <p>仅新增记录，按文件中的项目编号归属。销售与采购生成草稿，期初库存、费用、收付款、工时及发货仍执行原业务校验；不会覆盖或自动审批已有单据。</p>
      <div class="toolbar"><el-button :disabled="busy" @click="file(true)">下载模板</el-button><label class="file-button">选择文件并预览<input type="file" accept=".csv,.xlsx" :disabled="busy" @change="upload" /></label></div>
      <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
      <el-alert v-if="result" :title="result" type="success" :closable="false" role="status" />
      <template v-if="preview">
        <p>{{ preview.note }} 共 {{ preview.count }} 条，确认时再次校验；任一行失败，整批不保存。预览有效期 30 分钟。</p>
        <el-table :data="visibleRows" :max-height="360"><el-table-column prop="row" label="文件行号" width="100" /><el-table-column label="内容"><template #default="{ row }">{{ Object.values(row.data).map(v => typeof v === 'object' ? JSON.stringify(v) : v).join(' · ') }}</template></el-table-column></el-table>
        <ListPagination :page="page" :total="preview.rows.length" @change="page = $event" />
        <div v-if="preview.errors.length" class="import-errors" role="alert"><p v-for="e in preview.errors" :key="e.row">第 {{ e.row }} 行：{{ e.message }}</p></div>
      </template>
      <template #footer><el-button :disabled="busy" @click="opened = false">关闭</el-button><el-button type="primary" :disabled="!preview?.can_import" :loading="busy" @click="confirm">确认导入</el-button></template>
    </el-dialog>
  </div>
</template>
