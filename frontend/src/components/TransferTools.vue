<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { download, read, write } from '../api'
import { canImportResource } from '../session'
import { message, requestKey } from '../utils/request'
import type { Column, Row } from '../types'
import ImportFeedback from './ImportFeedback.vue'
import { importDestination, importTitles, templateMismatch } from '../utils/import-context'

const props = withDefaults(defineProps<{ resource: string; path: string; params?: Row; exportPath?: string; tableColumns?: Column[]; allowImport?: boolean }>(), { allowImport: true })
const emit = defineEmits<{ changed: [] }>()
const busy = ref(false)
const error = ref('')
const opened = ref(false)
const preview = ref<Row | null>(null)
const result = ref('')
const project = ref<Row | null>(null)
const mismatch = ref<ReturnType<typeof templateMismatch>>(null)
const destination = computed(() => mismatch.value ? importDestination(mismatch.value.resource, Number(props.params?.project) || undefined) : null)
const title = computed(() => `导入${layout.value?.title || importTitles[props.resource] || '资料'}`)
let generation = 0
onBeforeUnmount(() => { generation++ })
const layout = ref<Row | null>(null)
const mappings = computed(() => (layout.value?.columns || []).map((column: Row) => ({
  ...column,
  table: (props.tableColumns || []).filter(c => column.table_keys.includes(c.key)).map(c => c.label).join('、') || '单据明细 / 新增时填写',
})))
const generatedColumns = computed(() => (props.tableColumns || []).filter(c => !(layout.value?.columns || []).some((field: Row) => field.table_keys.includes(c.key))).map(c => c.label).join('、'))
const importable = computed(() => props.allowImport && canImportResource(props.resource))
const bankImport = computed(() => props.resource === 'bank-records')
watch([() => props.resource, () => props.params?.project], () => { generation++; layout.value = null; preview.value = null; project.value = null; opened.value = false; busy.value = false; error.value = ''; result.value = ''; mismatch.value = null })
watch(opened, value => { if (!value) { generation++; preview.value = null; mismatch.value = null; busy.value = false } })
watch(importable, value => { if (!value) opened.value = false })
async function openImport() {
  if (!importable.value) return
  opened.value = true
  preview.value = null
  mismatch.value = null
  error.value = ''
  result.value = ''
  layout.value = null
  if (bankImport.value) return
  busy.value = true
  const id = ++generation
  try {
    const data = await read(`${props.path}import-schema/`)
    if (id !== generation) return
    layout.value = data
    if (props.params?.project) {
      const context = await read(`/business/projects/${props.params.project}/`)
      if (id === generation) project.value = context
    }
  } catch (e) { if (id === generation) error.value = message(e) } finally { if (id === generation) busy.value = false }
}
async function file(template = false, chosen = 'xlsx') {
  busy.value = true
  error.value = ''
  try {
    await download(template ? `${props.path}import-template/` : (props.exportPath || `${props.path}export/`),
      `${template ? `${layout.value?.title || props.resource}导入模板` : props.resource}.${chosen}`, { ...(template ? {} : props.params), file_format: chosen })
  } catch (e) { error.value = message(e) } finally { busy.value = false }
}
async function guide() {
  busy.value = true
  error.value = ''
  try {
    await download(`${props.path}import-template/`, `${layout.value?.title || props.resource}导入填写说明.html`, { file_format: 'html' })
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
  const id = ++generation
  mismatch.value = null
  try {
    const data = new FormData()
    data.append('file', selected)
    const response = await write(`${props.path}import-file/`, data, requestKey())
    if (id === generation) preview.value = response
  } catch (e) {
    if (id === generation) { mismatch.value = templateMismatch(e); error.value = mismatch.value?.message || message(e) }
  } finally { if (id === generation) busy.value = false; input.value = '' }
}
async function confirm() {
  if (busy.value || !preview.value?.can_import || !importable.value) return
  const id = ++generation
  busy.value = true
  error.value = ''
  try {
    const data = await write(`${props.path}import-confirm/`, { token: preview.value.token }, requestKey())
    if (id !== generation) return
    result.value = `成功导入 ${data.count} 条记录${bankImport.value ? `，跳过已导入 ${data.skipped} 条` : ''}`
    preview.value = null
    emit('changed')
  } catch (e) { if (id === generation) error.value = message(e) } finally { if (id === generation) busy.value = false }
}
</script>
<template>
  <div class="transfer-tools">
    <!-- Collapsed into one menu so the toolbar leads with the entries that create work. -->
    <el-dropdown trigger="click" :persistent="false" @command="(name: string) => name === 'import' ? openImport() : file(false, name)">
      <el-button :loading="busy">{{ importable ? '导入导出 ▾' : '导出 ▾' }}</el-button>
      <template #dropdown
        ><el-dropdown-menu
          ><el-dropdown-item command="xlsx">导出 Excel</el-dropdown-item
          ><el-dropdown-item command="csv">导出 CSV</el-dropdown-item
          ><el-dropdown-item v-if="importable" command="import" divided>导入</el-dropdown-item
        ></el-dropdown-menu></template
      >
    </el-dropdown>
    <span v-if="error && !opened" role="alert">{{ error }}</span>
    <el-dialog v-model="opened" class="transfer-dialog" :title="title" width="min(1100px, 94vw)" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" destroy-on-close>
      <p v-if="params?.project" class="import-context"><strong>当前项目：{{ project ? `${project.name}（${project.code}）` : '当前页面所选项目' }}</strong>。文件中的项目编号仍会逐行校验，请核对是否与本次用途一致。</p>
      <p v-if="bankImport">上传工行 XLSX 或华夏 XLS 原始流水（含表头及汇总），单文件最多 1000 行、5 MB。完整保留个人往来和手续费，不自动核销或指定项目；缺失户名进入待核实，相同交易重复上传会跳过。没有唯一银行编号时生成导入标识，原始编号保留在明细中。预览按银行流水页面列展示；项目和未匹配金额由后续认领、匹配操作维护。</p>
      <p v-else>下载模板后填写，支持 CSV / XLSX，最多 1000 行、5 MB。人员可填姓名或账号，重名请填姓名（用户名）；其他引用使用编号，标明 ID 的列可从对应列表导出获取。日期填写 YYYY-MM-DD。</p>
      <template v-if="layout">
        <p><strong>{{ layout.title }}导入</strong> · {{ layout.entry }}</p>
        <div v-if="layout.quick_start" class="import-quick-start">
          <p><strong>① 先准备：</strong>{{ layout.quick_start.prepare }}</p>
          <p><strong>② 最少填什么：</strong>{{ layout.quick_start.minimum }}</p>
          <p><strong>③ 保存并上传：</strong>先核对预览中的项目、行数、数量和金额；有错误按文件行号修改后重新上传，通过后再确认导入。</p>
        </div>
        <p>{{ layout.note }}</p>
        <p>Excel 模板自带“填写说明”页和表头提示，打开先看操作指引，点击“开始填写”进入数据页。固定取值可下拉选择：单击第2行起的空白格，再点右侧▼；也可从说明页点“▼点此选择”跳过去。缺少必填内容会标红，CSV 不保留下拉选项。</p>
        <details class="import-field-guide"><summary>模板字段与页面列对应说明</summary>
          <el-table :data="mappings" max-height="260"><el-table-column prop="label" label="模板字段" min-width="160" /><el-table-column prop="required" label="是否必填" min-width="160" /><el-table-column prop="source" label="去哪找 / 怎么选" min-width="280" /><el-table-column prop="hint" label="填写说明" min-width="320" /><el-table-column prop="example" label="格式示例（请替换）" min-width="180" /><el-table-column prop="table" label="对应页面列" min-width="150" /></el-table>
          <p v-if="generatedColumns">页面中的 {{ generatedColumns }} 由系统生成或业务操作维护，无需填写到新增模板中。</p>
        </details>
      </template>
      <el-button v-else-if="!bankImport" :loading="busy" @click="openImport">加载字段说明</el-button>
      <div class="toolbar"><el-button v-if="!bankImport" :disabled="busy || !layout" @click="file(true)">下载模板</el-button><el-button v-if="!bankImport" :disabled="busy || !layout" @click="guide">下载填写说明</el-button><label class="file-button">{{ preview ? '重新选择文件并预览' : '选择文件并预览' }}<input type="file" :accept="bankImport ? '.xls,.xlsx' : '.csv,.xlsx'" :disabled="busy || (!bankImport && !layout)" @change="upload" /></label><details v-if="!bankImport"><summary>更多格式</summary><el-button :disabled="busy || !layout" @click="file(true, 'csv')">下载 CSV 模板</el-button></details></div>
      <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
      <p v-if="mismatch"><router-link v-if="destination" :to="destination" @click="opened = false">前往{{ mismatch.title }}导入入口</router-link><span v-else>请联系具备相应权限的同事，在{{ mismatch.entry }}操作。</span> 切换入口后请核对导入对象，并重新选择文件。</p>
      <el-alert v-if="result" :title="result" type="success" :closable="false" role="status" />
      <template v-if="preview">
        <p>共 {{ preview.count }} 条，确认时再次校验；任一行失败，整批不保存。预览有效期 30 分钟。<span v-if="resource === 'purchases'">文件 {{ preview.row_count }} 行明细合并为 {{ preview.count }} 张采购草稿，下方按原文件逐行显示。</span></p>
        <p v-if="preview.summary">收入 {{ preview.summary.income_count }} 笔 / {{ preview.summary.income }} 元；支出 {{ preview.summary.expense_count }} 笔 / {{ preview.summary.expense }} 元。{{ preview.summary.check }}</p>
        <ImportFeedback :rows="(preview.rows || []).map((row: Row) => ({ ...row, data: { ...row.data, status: row.status } }))" :columns="bankImport ? [{ key: 'status', label: '导入状态' }, ...(preview.columns || [])] : (preview.columns || [])" :errors="preview.errors || []" :error-file="preview.error_file" :busy="busy" />
      </template>
      <template #footer><el-button :disabled="busy" @click="opened = false">关闭</el-button><el-button type="primary" :disabled="busy || !preview?.can_import" :loading="busy" @click="confirm">确认导入</el-button></template>
    </el-dialog>
  </div>
</template>
<style scoped>
.import-quick-start { padding: 4px 16px; border: 1px solid #c6dbf5; border-radius: 8px; background: #f2f7ff; }
</style>
