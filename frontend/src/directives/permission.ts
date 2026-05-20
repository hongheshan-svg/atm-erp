import type { Directive } from 'vue'
import { usePermissionStore } from '@/stores/permission'

const permissionDirective: Directive<HTMLElement, string> = {
  mounted(el, binding) {
    const permissionStore = usePermissionStore()
    const requiredPermission = binding.value

    if (!permissionStore.hasPermission(requiredPermission)) {
      el.parentNode?.removeChild(el)
    }
  }
}

export default permissionDirective
