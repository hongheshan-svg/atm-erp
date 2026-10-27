<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { download, read, readBlob } from '../api'
import { message } from '../utils/request'
import type { Row } from '../types'
const PdfPreview = defineAsyncComponent(() => import('./PdfPreview.vue'))
const props = defineProps<{ document: { id: number; name?: string } }>()
const emit = defineEmits<{ close: [] }>()
const data = ref<Row>(), loading = ref(false), error = ref(''), downloading = ref(false)
const binary = shallowRef<Blob>(), imageUrl = ref(''), zoom = ref(100), search = ref('')
const sheet = ref<number>(), page = ref(1)
let generation = 0
const title = computed(() => `附件预览 · ${data.value?.name || props.document.name || '正在读取'}`)
const rows = computed(() => (data.value?.rows || []).filter((row: Row) => !search.value || row.cells.some((text: string) => text.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()))))
function release() {
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  imageUrl.value = ''; binary.value = undefined
}
async function load() {
  const current = ++generation
  loading.value = true; error.value = ''; data.value = undefined; release()
  try {
    const result = await read(`/business/documents/${props.document.id}/preview/`, { page: page.value, ...(sheet.value == null ? {} : { sheet: sheet.value }) })
    if (current !== generation) return
    data.value = result; page.value = result.page || 1; sheet.value = result.sheet
    if (['image', 'pdf'].includes(result.kind)) {
      const file = await readBlob(result.file_url)
      if (current !== generation) return
      binary.value = file
      if (result.kind === 'image') imageUrl.value = URL.createObjectURL(file)
    }
  } catch (e) { if (current === generation) { data.value = undefined; error.value = message(e) } }
  finally { if (current === generation) loading.value = false }
}
function changePage(value: number) { page.value = value; search.value = ''; void load() }
async function downloadOriginal() {
  downloading.value = true
  try { await download(`/business/documents/${props.document.id}/download/`, data.value?.name || props.document.name || '附件') }
  catch (e) { error.value = message(e) }
  finally { downloading.value = false }
}
watch(() => props.document, () => { page.value = 1; sheet.value = undefined; search.value = ''; zoom.value = 100; void load() }, { immediate: true })
function sessionChanged() { emit('close') }
window.addEventListener('erp-session', sessionChanged)
onBeforeUnmount(() => { generation++; release(); window.removeEventListener('erp-session', sessionChanged) })
</script>
<template>
  <el-dialog :model-value="true" :title="title" class="document-preview-dialog" width="min(1280px, 96vw)" top="3vh" append-to-body :close-on-click-modal="false" @close="emit('close')">
    <section class="document-preview" :aria-busy="loading">
      <div class="preview-toolbar"><span>仅查看，原文件保持不变</span><el-button :loading="downloading" @click="downloadOriginal">下载原文件</el-button></div>
      <p v-if="loading" role="status">正在读取附件，请稍候…</p>
      <div v-if="error" role="alert" class="preview-error">{{ error }} <el-button :disabled="loading" @click="load">重试预览</el-button><p>也可尝试下载原文件；损坏或加密文件请联系上传人重新提供。</p></div>
      <template v-if="data && !loading">
        <p v-for="warning in data.warnings || []" :key="warning" class="preview-notice">{{ warning }}</p>
        <div v-if="data.kind === 'spreadsheet'" class="sheet-preview">
          <div class="preview-toolbar"><label>工作表 <select v-model.number="sheet" aria-label="工作表" @change="changePage(1)"><option v-for="entry in data.sheets" :key="entry.index" :value="entry.index">{{ entry.name }}</option></select></label><label>查找当前页 <input v-model="search" type="search" aria-label="查找当前页" placeholder="物料、型号或金额" /></label><span>共 {{ data.total_rows }} 行</span></div>
          <p class="preview-notice">左右滚动查看全部列，上下滚动查看本页内容。</p>
          <div class="preview-scroll" tabindex="0" aria-label="表格预览，可左右滚动"><table aria-label="附件表格"><thead><tr><th scope="col">行号</th><th v-for="col in data.columns" :key="col" scope="col">{{ col }}</th></tr></thead><tbody><tr v-for="row in rows" :key="row.number"><th scope="row">{{ row.number }}</th><td v-for="(cell, index) in row.cells" :key="index">{{ cell }}</td></tr></tbody></table></div>
          <p v-if="!rows.length">{{ search ? '本页未找到匹配内容，可清空搜索或切换页码。' : '此工作表没有可显示的内容。' }}</p>
        </div>
        <div v-else-if="data.kind === 'document'" class="word-preview preview-scroll" tabindex="0" aria-label="文档内容"><template v-for="(block, index) in data.blocks" :key="index"><p v-if="block.kind === 'paragraph'">{{ block.text }}</p><table v-else-if="block.kind === 'table'" aria-label="文档表格"><tbody><tr v-for="(row, rowIndex) in block.rows" :key="rowIndex"><td v-for="(cell, colIndex) in row" :key="colIndex">{{ cell }}</td></tr></tbody></table></template><p v-if="!data.blocks?.length">文档没有可显示的文字。</p></div>
        <pre v-else-if="data.kind === 'text'" class="text-preview preview-scroll" tabindex="0">{{ data.text }}</pre>
        <template v-else-if="data.kind === 'image' && imageUrl"><div class="preview-toolbar"><el-button :disabled="zoom <= 50" @click="zoom -= 25">缩小图片</el-button><span>{{ zoom }}%</span><el-button :disabled="zoom >= 300" @click="zoom += 25">放大图片</el-button><el-button @click="zoom = 100">适合窗口</el-button></div><div class="preview-scroll image-preview" tabindex="0"><img :src="imageUrl" :alt="data.name" :style="{ width: `${zoom}%` }" @error="error = '图片无法显示，请确认文件完整或下载原文件查看。'" /></div></template>
        <PdfPreview v-else-if="data.kind === 'pdf' && binary" :file="binary" />
        <p v-else-if="data.kind === 'unsupported'" role="status" class="unsupported-preview">{{ data.message }}</p>
        <div v-if="data.total_pages > 1" class="preview-toolbar preview-pages"><el-button :disabled="page <= 1" @click="changePage(page - 1)">上一页内容</el-button><span>第 {{ page }} / {{ data.total_pages }} 页</span><el-button :disabled="page >= data.total_pages" @click="changePage(page + 1)">下一页内容</el-button><label>跳至 <select :value="page" aria-label="内容页码" @change="changePage(Number(($event.target as HTMLSelectElement).value))"><option v-for="n in data.total_pages" :key="n" :value="n">第 {{ n }} 页</option></select></label></div>
      </template>
    </section>
    <template #footer><el-button @click="emit('close')">关闭预览</el-button></template>
  </el-dialog>
</template>
<style scoped>
.document-preview { min-width: 0; }
.preview-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 12px; }
.preview-toolbar label { display: flex; gap: 6px; align-items: center; max-width: 100%; white-space: nowrap; }
.preview-toolbar input, .preview-toolbar select { min-width: 0; max-width: 240px; padding: 8px; border: 1px solid var(--field-line); border-radius: 6px; background: var(--paper, #fff); color: inherit; }
.preview-notice { color: var(--mute); font-size: 12px; line-height: 1.6; }
.preview-scroll { position: relative; overflow: auto; max-height: 58vh; border: 1px solid var(--field-line); border-radius: 6px; }
table { border-collapse: separate; border-spacing: 0; min-width: 100%; font-size: 13px; }
th, td { padding: 8px 12px; border-right: 1px solid var(--field-line); border-bottom: 1px solid var(--field-line); text-align: left; white-space: pre-wrap; overflow-wrap: anywhere; min-width: 100px; max-width: 400px; }
thead th { position: sticky; top: 0; background: var(--subtle-2); z-index: 1; }
th { white-space: nowrap; }
.sheet-preview tbody th, .sheet-preview thead th:first-child { position: sticky; left: 0; min-width: 44px; background: var(--subtle-2); }
.preview-pages { margin-top: 12px; position: sticky; bottom: 0; background: var(--paper, #fff); padding: 8px 0; z-index: 2; }
.word-preview { padding: 16px; white-space: pre-wrap; overflow-wrap: anywhere; }
.text-preview { white-space: pre-wrap; overflow-wrap: anywhere; padding: 16px; }
.image-preview img { display: block; max-width: none; height: auto; object-fit: contain; }
.preview-error { color: var(--risk); }
.unsupported-preview { padding: 28px 16px; background: var(--subtle-2); border-radius: 8px; line-height: 1.8; }
@media (max-width: 600px) { .preview-toolbar { gap: 8px; }.preview-toolbar input, .preview-toolbar select { font-size: 16px; max-width: 180px; }.preview-scroll { max-height: 55vh; } }
</style>
<style>
.document-preview-dialog { display: flex; flex-direction: column; max-height: 94vh; max-height: 94dvh; }
.document-preview-dialog .el-dialog__header, .document-preview-dialog .el-dialog__footer { flex-shrink: 0; }
.document-preview-dialog .el-dialog__body { overflow-y: auto; min-height: 0; }
.document-preview-dialog .el-dialog__title { overflow-wrap: anywhere; }
</style>
