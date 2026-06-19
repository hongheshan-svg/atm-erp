import type { Directive, DirectiveBinding } from 'vue'
import { watchEffect, type WatchStopHandle } from 'vue'
import { usePermissionStore } from '@/stores/permission'

// 在元素上挂载内部状态(原始 display 与 watch 停止句柄)。
interface PermEl extends HTMLElement {
  __permOriginalDisplay?: string
  __permStop?: WatchStopHandle
}

// v-permission="'masterdata:item:create'":无权限则隐藏元素,权限变更响应式更新。
const permissionDirective: Directive<PermEl, string> = {
  mounted(el, binding: DirectiveBinding<string>) {
    const permissionStore = usePermissionStore()
    el.__permOriginalDisplay = el.style.display

    el.__permStop = watchEffect(() => {
      const hasAccess = permissionStore.hasPermission(binding.value)
      el.style.display = hasAccess ? (el.__permOriginalDisplay ?? '') : 'none'
    })
  },
  updated(el, binding: DirectiveBinding<string>) {
    const permissionStore = usePermissionStore()
    const hasAccess = permissionStore.hasPermission(binding.value)
    el.style.display = hasAccess ? (el.__permOriginalDisplay ?? '') : 'none'
  },
  beforeUnmount(el) {
    el.__permStop?.()
  }
}

export default permissionDirective
