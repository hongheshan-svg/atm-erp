<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { download, read, write } from '../api'
import { message, requestKey } from '../utils/request'
import { openDocumentPreview, closeDocumentPreview, documentPreview } from '../document-preview'
import type { Field, Option } from '../types'
const props = defineProps<{ field: Field; disabled?: boolean; id?: string; invalid?: boolean; describedBy?: string }>()
const emit = defineEmits<{ busy: [value: boolean] }>()
const model = defineModel<string | number | undefined>()
const uploaded = ref<Option[]>([]), busy = ref(false), error = ref('')
let openedPreview: number | undefined
const choices = computed(() => [...(props.field.options || []), ...uploaded.value].filter((item, i, all) => all.findIndex(other => String(other.value) === String(item.value)) === i))
let generation = 0
// 只保留当前上下文最后一次未确认上传；逐字节核对，兼容局域网 HTTP 无 SubtleCrypto 的部署。
let attempt: { signature: string; bytes: Uint8Array; key: string } | undefined
function readFile(file: File): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer))
    reader.onerror = reader.onabort = () => reject(new Error('无法读取附件，请重新选择文件。'))
    reader.readAsArrayBuffer(file)
  })
}
function closePreview() { if (openedPreview === documentPreview.value?.id) closeDocumentPreview(); openedPreview = undefined }
watch(() => JSON.stringify(props.field.upload), () => { generation++; attempt = undefined; busy.value = false; emit('busy', false); uploaded.value = []; error.value = ''; closePreview() }, { flush: 'sync' })
onBeforeUnmount(() => { generation++; attempt = undefined; closePreview(); emit('busy', false) })
async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || busy.value || props.disabled || !props.field.upload) return
  if (file.size > 20 * 1024 * 1024) { error.value = '单个附件不能超过20 MB，请压缩后重新选择。'; return }
  const current = generation
  busy.value = true; emit('busy', true); error.value = ''
  try {
    const body = new FormData()
    body.append('file', file); body.append('category', props.field.upload.category)
    for (const [key, value] of Object.entries(props.field.upload.context)) if (value != null) body.append(key, String(value))
    const signature = JSON.stringify([file.name, file.size, file.lastModified, props.field.upload.category, props.field.upload.context])
    const bytes = await readFile(file)
    if (current !== generation) return
    const previous = attempt
    const pending = previous && signature === previous.signature && bytes.length === previous.bytes.length && bytes.every((byte, i) => byte === previous.bytes[i])
      ? previous
      : { signature, bytes, key: requestKey() }
    attempt = pending
    const result = await write('/business/documents/', body, pending.key)
    if (current !== generation) return
    if (attempt === pending) attempt = undefined
    uploaded.value.push({ value: result.id, label: result.original_name || file.name })
    model.value = result.id
  } catch (e) { if (current === generation) error.value = message(e) }
  finally { if (current === generation) { busy.value = false; emit('busy', false) } }
}
function view() {
  if (!model.value || busy.value) return
  openedPreview = Number(model.value)
  openDocumentPreview(model.value, choices.value.find(option => String(option.value) === String(model.value))?.label)
}
async function downloadSelected() {
  try { const doc = await read(`/business/documents/${model.value}/`); await download(doc.download_url, doc.original_name) }
  catch (e) { error.value = message(e) }
}
</script>
<template>
  <div class="inline-document">
    <select :id="id" :aria-invalid="invalid" :aria-describedby="describedBy" v-model="model" :aria-label="field.label" :disabled="disabled || busy" :required="!field.optional"><option value="">请选择已上传附件，或在下面上传</option><option v-for="option in choices" :key="option.value" :value="option.value">{{ option.label }}</option></select>
    <div class="document-actions"><label class="file-button">上传并选中<input type="file" :aria-label="`上传${field.label}`" :disabled="disabled || busy" @change="upload" /></label><el-button v-if="model" :disabled="busy" @click="view">预览附件</el-button><el-button v-if="model" :disabled="busy" @click="downloadSelected">下载附件</el-button></div>
    <small>附件上传后保留在当前项目或单据中；上传附件不会自动提交当前业务。</small>
    <span v-if="busy" role="status">正在处理附件…</span><span v-if="error" role="alert">{{ error }}</span>
  </div>
</template>
<style scoped>
.inline-document { display: grid; gap: 8px; min-width: 0; }
.document-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.inline-document small { color: var(--ink-4); font-size: 13px; }
</style>
