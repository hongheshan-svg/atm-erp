import { describe, it, expect } from 'vitest'
import { extractApiError } from '../apiError'

const resp = (data: any) => ({ response: { data } })

describe('extractApiError', () => {
  it('读取业务校验的 error 字段', () => {
    expect(extractApiError(resp({ error: '该采购订单已存在合同: PC202601' }))).toBe(
      '该采购订单已存在合同: PC202601'
    )
  })

  it('读取 DRF 异常的 detail 字段', () => {
    expect(extractApiError(resp({ detail: '您没有执行该操作的权限。' }))).toBe(
      '您没有执行该操作的权限。'
    )
  })

  it('读取序列化器字段校验的首条消息', () => {
    expect(extractApiError(resp({ quantity: ['数量必须大于 0'] }))).toBe('数量必须大于 0')
  })

  it('读取嵌套列表序列化器的首条消息', () => {
    // PurchaseOrderDetail 创建收货单时后端返回这种形状
    expect(extractApiError(resp({ lines: [{}, { quantity: ['收货数量超出未交数量'] }] }))).toBe(
      '收货数量超出未交数量'
    )
  })

  it('跳过嵌套里的空对象与空字符串', () => {
    expect(extractApiError(resp({ lines: [{}, { note: '' }] }), '创建收货单失败')).toBe(
      '创建收货单失败'
    )
  })

  it('读取 non_field_errors', () => {
    expect(extractApiError(resp({ non_field_errors: ['开始日期不能晚于结束日期'] }))).toBe(
      '开始日期不能晚于结束日期'
    )
  })

  it('真 500 无响应体时用兜底文案', () => {
    expect(extractApiError({ message: 'Network Error' }, '合同操作失败')).toBe('合同操作失败')
  })

  it('Django HTML 错误页不抛给用户', () => {
    const html = '<h1>Server Error (500)</h1>'
    expect(extractApiError(resp(html), '服务器错误，请稍后再试')).toBe('服务器错误，请稍后再试')
  })

  it('纯文本响应体原样返回', () => {
    expect(extractApiError(resp('订单已锁定'))).toBe('订单已锁定')
  })

  it('无可读消息时用兜底文案', () => {
    expect(extractApiError(resp({ error: '   ' }), '合同操作失败')).toBe('合同操作失败')
  })
})
