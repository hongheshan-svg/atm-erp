import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import { beforeEach, describe, expect, it } from 'vitest'

import permission from '../permission'
import { usePermissionStore } from '@/stores/permission'

const mountButton = (requiredPermission = 'purchase:order:edit') => {
  const required = ref(requiredPermission)
  const wrapper = mount(
    {
      setup: () => ({ required }),
      template: '<button v-permission="required" style="display: inline-block">受控操作</button>',
    },
    {
      global: {
        directives: { permission },
      },
    }
  )
  return { required, wrapper }
}

describe('v-permission', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('defaults to hidden and reacts when permission is granted', async () => {
    const store = usePermissionStore()
    const { wrapper } = mountButton()

    expect(wrapper.element.style.display).toBe('none')

    store.setPermissions(['purchase:order:edit'])
    await nextTick()

    expect(wrapper.element.style.display).toBe('inline-block')
  })

  it('hides immediately after permission state is cleared', async () => {
    const store = usePermissionStore()
    store.setPermissions(['purchase:order:edit'])
    const { wrapper } = mountButton()
    expect(wrapper.element.style.display).toBe('inline-block')

    store.clear()
    await nextTick()

    expect(wrapper.element.style.display).toBe('none')
  })

  it('uses the same parent-code inheritance as the permission store', () => {
    const store = usePermissionStore()
    store.setPermissions(['purchase:order'])

    const { wrapper } = mountButton('purchase:order:delete')

    expect(wrapper.element.style.display).toBe('inline-block')
  })

  it('re-evaluates when the directive binding changes', async () => {
    const store = usePermissionStore()
    store.setPermissions(['purchase:order:view'])
    const { required, wrapper } = mountButton('purchase:order:view')
    expect(wrapper.element.style.display).toBe('inline-block')

    required.value = 'purchase:order:delete'
    await nextTick()

    expect(wrapper.element.style.display).toBe('none')
  })
})
