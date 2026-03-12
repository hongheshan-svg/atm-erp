import { usePermissionStore } from '@/stores/permission'

export default {
  mounted(el, binding) {
    const permissionStore = usePermissionStore()
    const requiredPermission = binding.value

    if (!permissionStore.hasPermission(requiredPermission)) {
      el.parentNode?.removeChild(el)
    }
  }
}
