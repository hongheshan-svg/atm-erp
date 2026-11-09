<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElScrollbar } from 'element-plus'

withDefaults(defineProps<{ label?: string }>(), { label: '表格' })
const root = ref<HTMLElement>()
const native = ref(false)
const horizontal = ref<{ setScrollLeft: (left: number) => void }>()
const controlWidth = ref(0)
const position = ref({ left: 0, maximum: 0, width: 0 })
const narrow = computed(() => position.value.width < 640)
let viewport: HTMLElement | null = null, content: HTMLElement | null = null
let resize: ResizeObserver | undefined, mutation: MutationObserver | undefined
function sync() {
  const next = viewport ? { left: viewport.scrollLeft, maximum: Math.max(0, viewport.scrollWidth - viewport.clientWidth), width: viewport.clientWidth } : { left: 0, maximum: 0, width: 0 }
  if (next.left !== position.value.left || next.maximum !== position.value.maximum || next.width !== position.value.width) position.value = next
  controlWidth.value = root.value?.clientWidth || next.width
  horizontal.value?.setScrollLeft(next.left)
}
function bind() {
  const next = root.value?.querySelector<HTMLElement>('[data-table-scroll], .el-table__body-wrapper .el-scrollbar__wrap') || null
  const table = next?.querySelector<HTMLElement>('table') || null
  if (next !== viewport || table !== content) {
    viewport?.removeEventListener('scroll', sync)
    resize?.disconnect()
    viewport = next; content = table
    native.value = Boolean(viewport?.hasAttribute('data-table-scroll'))
    viewport?.addEventListener('scroll', sync, { passive: true })
    for (const element of [root.value, viewport, content]) if (element) resize?.observe(element)
  }
  sync()
}
function drag({ scrollLeft }: { scrollLeft: number }) {
  if (viewport && Math.abs(viewport.scrollLeft - scrollLeft) > 1) viewport.scrollLeft = scrollLeft
}
watch(horizontal, sync)
function move(direction: number) {
  if (!viewport) return
  viewport.scrollLeft = Math.max(0, Math.min(position.value.maximum, viewport.scrollLeft + direction * Math.max(160, viewport.clientWidth * 0.7)))
  sync()
}
onMounted(() => {
  if (typeof ResizeObserver !== 'undefined') resize = new ResizeObserver(sync)
  if (typeof MutationObserver !== 'undefined') {
    mutation = new MutationObserver(bind)
    if (root.value) mutation.observe(root.value, { childList: true, subtree: true })
  }
  bind()
})
onBeforeUnmount(() => { resize?.disconnect(); mutation?.disconnect(); viewport?.removeEventListener('scroll', sync) })
</script>
<template>
  <div ref="root" class="table-scroll" :class="{ 'table-scroll-narrow': narrow }">
    <slot :narrow="narrow" />
    <!-- 原生滚动条在部分电脑上自动隐藏，明细表共用常显滑条并与正文同步。 -->
    <el-scrollbar v-if="native && position.maximum > 1" ref="horizontal" class="table-scroll-native" height="16px" always :aria-label="`${label}横向滚动条`" @scroll="drag">
      <div :style="{ width: `${position.maximum + controlWidth}px`, height: '1px' }" />
    </el-scrollbar>
    <div v-if="position.maximum > 1 || $slots.tools" class="table-scroll-tools" role="group" :aria-label="`${label}左右查看`">
      <template v-if="position.maximum > 1">
        <el-button :disabled="position.left <= 1" @click="move(-1)">← 向左查看</el-button>
        <el-button :disabled="position.left >= position.maximum - 1" @click="move(1)">向右查看 →</el-button>
        <span class="muted">拖动表格底部横向滚动条，或点击左右查看。</span>
      </template>
      <slot name="tools" />
    </div>
  </div>
</template>
<style scoped>
.table-scroll { min-width: 0; max-width: 100%; }
.table-scroll-tools { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 12px 0; }
.table-scroll-tools .el-button + .el-button { margin-left: 0; }
.table-scroll :deep(.el-scrollbar__bar.is-horizontal) { height: 12px; bottom: 2px; }
.table-scroll :deep(.el-scrollbar__bar.is-horizontal .el-scrollbar__thumb) { background: #64748b; opacity: .8; }
.table-scroll :deep([data-table-scroll]) { max-width: 100%; overflow-x: auto; }
.table-scroll :deep([data-table-scroll]::-webkit-scrollbar) { height: 0; width: 12px; }
.table-scroll :deep([data-table-scroll]::-webkit-scrollbar-track) { background: #eef2f7; }
.table-scroll :deep([data-table-scroll]::-webkit-scrollbar-thumb) { background: #64748b; border-radius: 6px; border: 2px solid #eef2f7; }
/* 窄屏固定列会遮住数据；保留整张表的横向查看空间。 */
.table-scroll-narrow :deep(.el-table-fixed-column--left),
.table-scroll-narrow :deep(.el-table-fixed-column--right) { position: static !important; box-shadow: none !important; }
.table-scroll-narrow :deep(.el-table-fixed-column--left::before),
.table-scroll-narrow :deep(.el-table-fixed-column--right::before) { display: none; }
@media print {
  .table-scroll-tools, .table-scroll-native { display: none; }
  .table-scroll :deep([data-table-scroll]) { overflow: visible; max-height: none; }
}
</style>
