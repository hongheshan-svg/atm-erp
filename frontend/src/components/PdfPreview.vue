<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { getDocument, GlobalWorkerOptions, type PDFDocumentLoadingTask, type PDFDocumentProxy, type RenderTask } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?worker&url'
GlobalWorkerOptions.workerSrc = workerUrl
const props = defineProps<{ file: Blob }>()
const holder = ref<HTMLDivElement>(), page = ref(1), pages = ref(0), zoom = ref(100)
const busy = ref(true), error = ref(''), pageText = ref(''), showText = ref(false)
let pdf: PDFDocumentProxy | undefined, task: PDFDocumentLoadingTask | undefined, rendering: RenderTask | undefined
let generation = 0, drawing = 0, timer: ReturnType<typeof setTimeout> | undefined
function clearCanvas() { holder.value?.querySelectorAll('canvas').forEach(canvas => { canvas.width = 0; canvas.height = 0 }); holder.value?.replaceChildren() }
async function render() {
  if (!pdf) return
  const current = ++drawing
  rendering?.cancel(); busy.value = true; error.value = ''; pageText.value = ''; clearCanvas()
  try {
    const source = await pdf.getPage(page.value)
    if (current !== drawing) return
    await nextTick()
    const width = Math.max(220, (holder.value?.clientWidth || 600) - 20)
    const natural = source.getViewport({ scale: 1 })
    const viewport = source.getViewport({ scale: width / natural.width * zoom.value / 100 })
    const outputScale = Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(12_000_000 / (viewport.width * viewport.height)))
    const canvas = document.createElement('canvas')
    canvas.width = Math.floor(viewport.width * outputScale); canvas.height = Math.floor(viewport.height * outputScale)
    canvas.style.width = `${viewport.width}px`; canvas.style.height = `${viewport.height}px`
    canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', `PDF第${page.value}页`)
    rendering = source.render({ canvas, viewport, transform: [outputScale, 0, 0, outputScale, 0, 0] })
    await rendering.promise
    if (current !== drawing) { canvas.width = 0; canvas.height = 0; return }
    holder.value?.replaceChildren(canvas)
    const text = await source.getTextContent()
    if (current === drawing) pageText.value = text.items.map(item => 'str' in item ? item.str + (item.hasEOL ? '\n' : ' ') : '').join('')
  } catch (e) {
    if (current === drawing && (e as Error).name !== 'RenderingCancelledException') error.value = '本页无法显示，请重试或下载原文件查看。'
  } finally { if (current === drawing) busy.value = false }
}
async function load() {
  const current = ++generation
  drawing++; rendering?.cancel(); void task?.destroy().catch(() => {})
  pdf = undefined; task = undefined; page.value = 1; pages.value = 0; busy.value = true; error.value = ''; clearCanvas()
  try {
    const bytes = new Uint8Array(await props.file.arrayBuffer())
    if (current !== generation) return
    const root = `${import.meta.env.BASE_URL}pdfjs/`
    // Match the existing production CSP without enabling eval or WebAssembly execution.
    const loadingTask = getDocument({ data: bytes, cMapUrl: root + 'cmaps/', cMapPacked: true, standardFontDataUrl: root + 'standard_fonts/', wasmUrl: root + 'wasm/', useWasm: false, enableXfa: false, stopAtErrors: true, canvasMaxAreaInBytes: 48_000_000 })
    task = loadingTask
    const loaded = await loadingTask.promise
    if (current !== generation) { void loadingTask.destroy().catch(() => {}); return }
    pdf = loaded; pages.value = loaded.numPages
    await render()
  } catch (e) {
    if (current === generation) { error.value = (e as Error).name === 'PasswordException' ? '此PDF已加密，请下载后输入密码查看，或请上传人提供未加密版本。' : 'PDF无法读取，请确认文件完整后重试或下载原文件。'; busy.value = false }
  }
}
function resize() { clearTimeout(timer); timer = setTimeout(() => { void render() }, 180) }
window.addEventListener('resize', resize)
watch(() => props.file, load, { immediate: true })
watch([page, zoom], () => { void render() })
onBeforeUnmount(() => { generation++; drawing++; rendering?.cancel(); void task?.destroy().catch(() => {}); clearCanvas(); clearTimeout(timer); window.removeEventListener('resize', resize) })
</script>
<template>
  <section class="pdf-preview" aria-label="PDF预览" :aria-busy="busy">
    <div class="pdf-toolbar"><el-button :disabled="busy || page <= 1" @click="page--">上一页PDF</el-button><label>页码 <select v-model.number="page" aria-label="PDF页码" :disabled="busy || !pages"><option v-for="n in pages" :key="n" :value="n">{{ n }}</option></select> / {{ pages }}</label><el-button :disabled="busy || page >= pages" @click="page++">下一页PDF</el-button><label>缩放 <select v-model.number="zoom" aria-label="PDF缩放" :disabled="busy"><option :value="75">75%</option><option :value="100">适合窗口</option><option :value="150">150%</option><option :value="200">200%</option></select></label><el-button :disabled="!pageText" @click="showText = !showText">{{ showText ? '隐藏本页文字' : '查看本页文字' }}</el-button></div>
    <p v-if="busy" role="status">正在显示PDF…</p><p v-if="error" role="alert">{{ error }} <el-button @click="pdf ? render() : load()">重试PDF</el-button></p>
    <div ref="holder" class="pdf-paper" tabindex="0" aria-label="PDF页面，可滚动查看" />
    <pre v-if="showText" class="pdf-text">{{ pageText || '此页没有可提取的文字。' }}</pre>
  </section>
</template>
<style scoped>
.pdf-toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 10px; }
.pdf-toolbar label { display: flex; align-items: center; gap: 6px; white-space: nowrap; }
.pdf-toolbar select { padding: 6px; border: 1px solid var(--field-line); border-radius: 5px; max-width: 120px; }
.pdf-paper { width: 100%; min-height: 80px; max-height: 60vh; overflow: auto; background: #eef0f4; border-radius: 6px; padding: 10px; box-sizing: border-box; }
.pdf-paper :deep(canvas) { display: block; margin: 0 auto; background: white; }
.pdf-text { max-height: 25vh; overflow: auto; white-space: pre-wrap; }
@media (max-width: 600px) { .pdf-toolbar { gap: 6px; }.pdf-toolbar select { font-size: 16px; } }
</style>
