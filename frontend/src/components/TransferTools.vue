<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { download, read, write } from '../api'
import { canImportResource } from '../session'
import { message } from '../utils/request'
import type { Column, Row } from '../types'
import ListPagination from './ListPagination.vue'
import { pageSize } from '../pagination'

const props = defineProps<{ resource: string; path: string; params?: Row; exportPath?: string; tableColumns?: Column[] }>()
const emit = defineEmits<{ changed: [] }>()
const format = ref('xlsx')
const busy = ref(false)
const error = ref('')
const opened = ref(false)
const preview = ref<Row | null>(null)
const result = ref('')
const page = ref(1)
const layout = ref<Row | null>(null)
const mappings = computed(() => (layout.value?.columns || []).map((column: Row) => ({
  ...column,
  table: (props.tableColumns || []).filter(c => column.table_keys.includes(c.key)).map(c => c.label).join('、') || '单据明细 / 新增时填写',
})))
const generatedColumns = computed(() => (props.tableColumns || []).filter(c => !(layout.value?.columns || []).some((field: Row) => field.table_keys.includes(c.key))).map(c => c.label).join('、'))
const importable = computed(() => canImportResource(props.resource))
const bankImport = computed(() => props.resource === 'bank-records')
const visibleRows = computed(() => preview.value?.rows.slice((page.value - 1) * pageSize.value, page.value * pageSize.value) || [])
watch(pageSize, () => { page.value = 1 })
watch(() => props.resource, () => { layout.value = null; preview.value = null; opened.value = false; error.value = ''; result.value = '' })
async function openImport() {
  opened.value = true
  preview.value = null
  page.value = 1
  error.value = ''
  result.value = ''
  layout.value = null
  if (bankImport.value) return
  busy.value = true
  const resource = props.resource
  try {
    const data = await read(`${props.path}import-schema/`)
    if (props.resource === resource) layout.value = data
  } catch (e) { error.value = message(e) } finally { busy.value = false }
}
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
  const resource = props.resource
  try {
    const data = new FormData()
    data.append('file', selected)
    const response = await write(`${props.path}import-file/`, data, crypto.randomUUID())
    if (props.resource === resource) { preview.value = response; page.value = 1 }
  } catch (e) { if (props.resource === resource) error.value = message(e) } finally { busy.value = false; input.value = '' }
}
async function confirm() {
  if (!preview.value?.can_import) return
  busy.value = true
  error.value = ''
  try {
    const data = await write(`${props.path}import-confirm/`, { token: preview.value.token }, crypto.randomUUID())
    result.value = `成功导入 ${data.count} 条记录${bankImport.value ? `，跳过已导入 ${data.skipped} 条` : ''}`
    preview.value = null
    emit('changed')
  } catch (e) { error.value = message(e) } finally { busy.value = false }
}
</script>
<template>
  <div class="transfer-tools">
    <select v-model="format" aria-label="导入导出格式" :disabled="busy"><option value="xlsx">Excel</option><option value="csv">CSV</option></select>
    <el-button :loading="busy" @click="file()">导出</el-button>
    <el-button v-if="importable" :disabled="busy" @click="openImport">导入</el-button>
    <span v-if="error && !opened" role="alert">{{ error }}</span>
    <el-dialog v-model="opened" class="transfer-dialog" title="批量导入" width="min(1100px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" destroy-on-close>
      <p v-if="bankImport">上传工行 XLSX 或华夏 XLS 原始流水（含表头及汇总），单文件最多 1000 行、5 MB。完整保留个人往来和手续费，不自动核销或指定项目；缺失户名进入待核实，相同交易重复上传会跳过。没有唯一银行编号时生成导入标识，原始编号保留在明细中。预览按银行流水页面列展示；项目和未匹配金额由后续认领、匹配操作维护。</p>
      <p v-else>下载模板后填写，支持 CSV / XLSX，最多 1000 行、5 MB。引用使用编号或账号；标明 ID 的列可从对应列表导出获取。日期填写 YYYY-MM-DD。</p>
      <template v-if="layout">
        <p>{{ layout.note }}</p>
        <details class="import-field-guide"><summary>模板字段与页面列对应说明</summary>
          <el-table :data="mappings" max-height="260"><el-table-column prop="label" label="模板字段" min-width="160" /><el-table-column prop="table" label="对应页面列" min-width="150" /><el-table-column prop="hint" label="填写说明" min-width="320" /></el-table>
          <p v-if="generatedColumns">页面中的 {{ generatedColumns }} 由系统生成或业务操作维护，无需填写到新增模板中。</p>
        </details>
      </template>
      <el-button v-else-if="!bankImport" :loading="busy" @click="openImport">加载字段说明</el-button>
      <div class="toolbar"><el-button v-if="!bankImport" :disabled="busy || !layout" @click="file(true)">下载模板</el-button><label class="file-button">选择文件并预览<input type="file" :accept="bankImport ? '.xls,.xlsx' : '.csv,.xlsx'" :disabled="busy || (!bankImport && !layout)" @change="upload" /></label></div>
      <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
      <el-alert v-if="result" :title="result" type="success" :closable="false" role="status" />
      <template v-if="preview">
        <p>共 {{ preview.count }} 条，确认时再次校验；任一行失败，整批不保存。预览有效期 30 分钟。<span v-if="resource === 'purchases'">文件 {{ preview.row_count }} 行明细合并为 {{ preview.count }} 张采购草稿，下方按原文件逐行显示。</span></p>
        <p v-if="preview.summary">收入 {{ preview.summary.income_count }} 笔 / {{ preview.summary.income }} 元；支出 {{ preview.summary.expense_count }} 笔 / {{ preview.summary.expense }} 元。{{ preview.summary.check }}</p>
        <el-table :data="visibleRows" :max-height="360" row-key="row"><el-table-column prop="row" label="文件行号" width="100" fixed="left" /><el-table-column v-if="bankImport" prop="status" label="导入状态" width="150" /><el-table-column v-for="column in preview.columns" :key="column.key" :label="column.label" min-width="150" show-overflow-tooltip><template #default="{ row }">{{ row.data[column.key] || '—' }}</template></el-table-column></el-table>
        <ListPagination :page="page" :total="preview.rows.length" @change="page = $event" />
        <div v-if="preview.errors.length" class="import-errors" role="alert"><p v-for="e in preview.errors" :key="e.row">第 {{ e.row }} 行：{{ e.message }}</p></div>
      </template>
      <template #footer><el-button :disabled="busy" @click="opened = false">关闭</el-button><el-button type="primary" :disabled="!preview?.can_import" :loading="busy" @click="confirm">确认导入</el-button></template>
    </el-dialog>
  </div>
</template>
