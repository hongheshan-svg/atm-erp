import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ProcessSteps from './ProcessSteps.vue'
import { flowFor } from '../flows'

const render = (resource: string, row: Record<string, unknown>, compact = false) =>
  mount(ProcessSteps, { props: { flow: flowFor(resource, row)!, compact } })

describe('流程节点展示', () => {
  it('已过节点打勾，当前节点标记为进行中，后续节点保持待办', () => {
    const wrapper = render('purchases', { status: 'approved' })
    const items = wrapper.findAll('li')
    expect(items.map(item => item.classes().find(name => name.startsWith('process-')))).toEqual([
      'process-done', 'process-done', 'process-current', 'process-todo', 'process-todo',
    ])
    expect(items[0]!.get('.process-marker').text()).toBe('✓')
    expect(items[2]!.get('.process-marker').text()).toBe('3')
    expect(items[2]!.attributes('aria-current')).toBe('step')
    expect(wrapper.get('nav').attributes('aria-label')).toBe('采购流程：第 3 / 5 步 待收货')
  })

  it('终止的流程把主链整体置灰，只把终止节点标为当前位置', () => {
    const wrapper = render('sales', { status: 'cancelled' })
    expect(wrapper.findAll('li.process-skipped')).toHaveLength(3)
    expect(wrapper.findAll('[aria-current="step"]')).toHaveLength(1)
    expect(wrapper.get('.process-aborted').text()).toContain('已取消')
    expect(wrapper.get('nav').attributes('aria-label')).toBe('销售流程：已取消')
  })

  it('每个节点带上业务说明，便于判断下一步做什么', () => {
    const wrapper = render('deliveries', { shipped_date: '2026-09-12' })
    expect(wrapper.text()).toContain('设备出库发运')
    expect(wrapper.text()).toContain('质保期内响应售后')
  })

  it('紧凑形态用圆点加当前节点名，适配表格单元格', () => {
    const wrapper = render('warranty', { status: '维修中' }, true)
    expect(wrapper.find('.process-compact').exists()).toBe(true)
    expect(wrapper.findAll('.process-dots > i')).toHaveLength(3)
    expect(wrapper.findAll('.process-dots > i.process-done')).toHaveLength(1)
    expect(wrapper.findAll('.process-dots > i.process-current')).toHaveLength(1)
    expect(wrapper.get('small').text()).toBe('处理中')
    expect(wrapper.get('nav').attributes('aria-label')).toBe('采购质保流程：第 2 / 3 步 处理中')
  })
})
