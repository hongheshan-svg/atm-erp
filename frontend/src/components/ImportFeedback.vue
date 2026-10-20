<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { Row } from '../types'
import { pageSize } from '../pagination'
import { message } from '../utils/request'
import ListPagination from './ListPagination.vue'

const props = defineProps<{
  rows: Row[]; columns: { key: string; label: string }[]; errors: Row[]
  errorFile?: { name: string; content: string }; busy?: boolean
}>()
const onlyErrors = ref(false)
const page = ref(1)
const table = ref<{ $el: HTMLElement }>()
const focusedRow = ref<number>()
const issues = (row: number) => props.errors.filter(issue => issue.row === row)
const errorRows = computed(() => new Set(props.errors.filter(issue => Number.isInteger(issue.row)).map(issue => issue.row)))
const filtered = computed(() => onlyErrors.value ? props.rows.filter(row => errorRows.value.has(row.row)) : props.rows)
const visible = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
watch(() => props.rows, () => { onlyErrors.value = false })
watch([() => props.rows, onlyErrors, pageSize], () => { page.value = 1; focusedRow.value = undefined })
const cellIssues = (row: number, key: string) => issues(row).filter(issue => !issue.fields?.length || issue.fields.includes(key))
async function locate(issue: Row) {
  const index = filtered.value.findIndex(row => row.row === issue.row)
  if (index < 0) return
  page.value = Math.floor(index / pageSize.value) + 1
  focusedRow.value = issue.row
  await nextTick()
  const field = props.columns.find(column => issue.fields?.includes(column.key)) || props.columns[0]
  const cell = table.value?.$el.querySelector<HTMLElement>(`[data-import-row="${issue.row}"][data-import-field="${field?.key}"]`)
  cell?.focus({ preventScroll: true })
  cell?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' })
}
function downloadErrors() {
  if (!props.errorFile) return
  const bytes = Uint8Array.from(atob(props.errorFile.content), character => character.charCodeAt(0))
  const url = URL.createObjectURL(new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = props.errorFile.name
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>
<template>
  <div class="import-feedback">
    <div class="feedback-toolbar">
      <p aria-live="polite">共 {{ rows.length }} 行，{{ errorRows.size }} 行有问题<span v-if="errors.some(issue => !issue.row)">，另有整批校验问题</span>。</p>
      <label v-if="errorRows.size"><input v-model="onlyErrors" type="checkbox" />只看错误行</label>
      <el-button v-if="errorFile" :disabled="busy" @click="downloadErrors">下载标注错误的 Excel</el-button>
    </div>
    <p v-if="errorFile" class="muted">红色单元格的批注说明填写问题。修改后保存并重新上传，整批重新校验；保留原表头和全部数据行。</p>
    <div v-if="errors.length" class="import-errors" role="alert">
      <p v-for="(issue, index) in errors" :key="index">{{ message(issue.message ? { row: issue.row, message: issue.message } : issue) }}
        <el-button v-if="rows.some(row => row.row === issue.row)" text @click="locate(issue)">定位第 {{ issue.row }} 行</el-button>
      </p>
    </div>
    <el-table ref="table" :data="visible" :max-height="360" row-key="row" empty-text="没有符合条件的预览行">
      <el-table-column prop="row" label="文件行号" width="100" fixed="left" />
      <el-table-column v-if="errors.length" label="填写问题" min-width="230"><template #default="{ row }">{{ issues(row.row).map(issue => issue.message).join('；') || '—' }}</template></el-table-column>
      <el-table-column v-for="column in columns" :key="column.key" :label="column.label" min-width="150">
        <template #default="{ row }"><span tabindex="-1" :data-import-row="row.row" :data-import-field="column.key" :class="{ 'error-cell': cellIssues(row.row, column.key).length, 'located-cell': focusedRow === row.row }" :title="cellIssues(row.row, column.key).map(issue => issue.message).join('；')">{{ row.data[column.key] ?? '—' }}<small v-if="row.matches?.[column.key]" class="matched-reference">已对应：{{ row.matches[column.key] }}</small></span></template>
      </el-table-column>
    </el-table>
    <ListPagination :page="page" :total="filtered.length" @change="page = $event" />
  </div>
</template>
<style scoped>
.feedback-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 16px; }
.feedback-toolbar label { display: flex; align-items: center; gap: 6px; }
.import-errors { max-height: 160px; overflow: auto; }
.import-errors p { margin: 4px 0; }
.matched-reference { display: block; color: var(--mute); }
.error-cell { display: block; background: #fff0f0; color: #a12622; border-bottom: 2px solid #ce4640; padding: 4px; }
.located-cell:focus { outline: 2px solid var(--el-color-primary); outline-offset: -2px; }
</style>
