import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'
import ListPagination from './ListPagination.vue'

describe('分页窄屏模式', () => {
  it('渲染上一页/下一页和「第 N/M 页」，到头时禁用并按页码触发翻页', async () => {
    const wrapper = mount(ListPagination, { props: { page: 1, total: 95, minSize: 0 }, global: { plugins: [ElementPlus] } })
    const compact = wrapper.find('.pager-compact')
    expect(compact.text()).toContain('第 1/5 页')
    const [prev, next] = compact.findAll('button')
    expect(prev!.attributes('disabled')).toBeDefined()
    await next!.trigger('click')
    expect(wrapper.emitted('change')![0]).toEqual([2])
    await wrapper.setProps({ page: 5 })
    expect(wrapper.find('.pager-compact').findAll('button')[1]!.attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
})
