import type { Directive } from 'vue'
import { ref, watchEffect } from 'vue'
import { usePermissionStore } from '@/stores/permission'

const permissionDirective: Directive<HTMLElement, string> = {
  mounted(el, binding) {
    const permissionStore = usePermissionStore()
    ;(el as any).__permOriginalDisplay = el.style.display

    const stop = watchEffect(() => {
      const hasAccess = permissionStore.hasPermission(binding.value)
      el.style.display = hasAccess ? (el as any).__permOriginalDisplay : 'none'
    })
    ;(el as any).__permStop = stop
  },
  updated(el, binding) {
    const permissionStore = usePermissionStore()
    const hasAccess = permissionStore.hasPermission(binding.value)
    el.style.display = hasAccess ? ((el as any).__permOriginalDisplay ?? '') : 'none'
  },
  beforeUnmount(el) {
    const stop = (el as any).__permStop
    if (stop) stop()
  }
}

export default permissionDirective
