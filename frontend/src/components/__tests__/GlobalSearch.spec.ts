import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import GlobalSearch from '../GlobalSearch.vue'

const { requestGet, routerPush } = vi.hoisted(() => ({
  requestGet: vi.fn(),
  routerPush: vi.fn()
}))

vi.mock('@/utils/request', () => ({
  default: {
    get: (...args: any[]) => requestGet(...args)
  }
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: routerPush
  })
}))

const mountGlobalSearch = () => mount(GlobalSearch, {
  global: {
    directives: {
      loading: () => undefined
    },
    stubs: {
      ElAutocomplete: true,
      ElAvatar: true,
      ElDialog: true,
      ElEmpty: true,
      ElIcon: true,
      ElTabPane: true,
      ElTabs: true,
      ElTable: true,
      ElTableColumn: true
    }
  }
})

describe('GlobalSearch suggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('passes suggestions from the unwrapped request payload to the autocomplete callback', async () => {
    const suggestions = [
      {
        id: 'item-1',
        text: '测试物料',
        type: 'items',
        meta: 'ITEM-001'
      }
    ]
    requestGet.mockResolvedValue({ suggestions })
    const callback = vi.fn()
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const wrapper = mountGlobalSearch()

    await (wrapper.vm as any).fetchSuggestions('测试', callback)

    expect(callback).toHaveBeenCalledWith(suggestions)
    expect(consoleError).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('returns an empty suggestion list without logging when the response is empty', async () => {
    requestGet.mockResolvedValue(undefined)
    const callback = vi.fn()
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const wrapper = mountGlobalSearch()

    await (wrapper.vm as any).fetchSuggestions('测试', callback)

    expect(callback).toHaveBeenCalledWith([])
    expect(consoleError).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('uses the unwrapped search payload for full search results', async () => {
    const results = {
      items: {
        total: 1,
        hits: [{ id: 'item-1', name: '测试物料' }]
      }
    }
    requestGet.mockResolvedValue({ results })
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const wrapper = mountGlobalSearch()

    ;(wrapper.vm as any).searchQuery = '测试'
    await (wrapper.vm as any).performSearch()

    expect((wrapper.vm as any).results).toEqual(results)
    expect((wrapper.vm as any).resultsVisible).toBe(true)
    expect(consoleError).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('handles an empty full search response without logging', async () => {
    requestGet.mockResolvedValue(undefined)
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const wrapper = mountGlobalSearch()

    ;(wrapper.vm as any).searchQuery = '测试'
    await (wrapper.vm as any).performSearch()

    expect((wrapper.vm as any).results).toEqual({})
    expect((wrapper.vm as any).resultsVisible).toBe(true)
    expect(consoleError).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('navigates when selecting a suggestion with the plural API type', () => {
    const wrapper = mountGlobalSearch()

    ;(wrapper.vm as any).handleSelect({
      id: 'item-1',
      text: '测试物料',
      type: 'items'
    })

    expect(routerPush).toHaveBeenCalledWith('/masterdata/items')
    wrapper.unmount()
  })
})
