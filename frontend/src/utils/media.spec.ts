import { afterEach, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { useNarrow } from './media'

afterEach(() => vi.unstubAllGlobals())
const probe = (query?: string) => defineComponent({ setup() { const narrow = useNarrow(query); return () => h('i', narrow.value ? 'narrow' : 'wide') } })

it('跟随媒体查询变化，卸载后解除监听', async () => {
  let matches = true
  const listeners = new Set<() => void>()
  const media = vi.fn((query: string) => ({
    media: query, get matches() { return matches },
    addEventListener: (_: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
  }))
  vi.stubGlobal('matchMedia', media)
  const wrapper = mount(probe())
  expect(media).toHaveBeenCalledWith('(max-width: 600px)')
  expect(wrapper.text()).toBe('narrow')
  matches = false
  listeners.forEach(listener => listener())
  await nextTick()
  expect(wrapper.text()).toBe('wide')
  wrapper.unmount()
  expect(listeners.size).toBe(0)
  mount(probe('(max-width: 760px)')).unmount()
  expect(media).toHaveBeenLastCalledWith('(max-width: 760px)')
})

it('没有 matchMedia 时按宽屏处理', () => {
  vi.stubGlobal('matchMedia', undefined)
  expect(mount(probe()).text()).toBe('wide')
})
