import { nextTick } from 'vue'
import type { TabsInstance } from 'element-plus'
const nativeBars = new WeakSet<HTMLElement>()

export async function revealActiveTab(instance: () => TabsInstance | undefined) {
  await nextTick()
  const root = instance()?.$el as HTMLElement | undefined
  const bar = root?.querySelector<HTMLElement>(':scope > .el-tabs__header .el-tabs__nav-scroll')
  if (bar && !nativeBars.has(bar)) {
    // Let the browser scroll; do not also run Element Plus's transform gestures.
    for (const name of ['touchstart', 'touchmove', 'wheel']) bar.addEventListener(name, event => event.stopPropagation(), { capture: true, passive: true })
    nativeBars.add(bar)
  }
  const active = bar?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')
  if (bar && active) bar.scrollLeft += active.getBoundingClientRect().left - bar.getBoundingClientRect().left - (bar.clientWidth - active.offsetWidth) / 2
}
