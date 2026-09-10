import type { Field, Row } from '../types'

export const termLabels: Record<string, string> = { manual: '指定付款日期', cash: '现付（合格收货日）', month30: '月结30天', month60: '月结60天', month90: '月结90天', month120: '月结120天', custom: '月结自定义天数' }
export const termLabel = (r: Row) => r.payment_term === 'custom' ? `月结${r.payment_days}天` : termLabels[r.payment_term] || '指定付款日期'
export const termFields = (inherit = false): Field[] => [
  { key: 'payment_term', label: inherit ? '采购账期（留空沿用供应商）' : '供应商默认采购账期', type: 'select', optional: inherit, initial: inherit ? '' : 'manual', options: Object.entries(termLabels).map(([value, label]) => ({ value, label })), hint: '月结＝每批合格收货当月月底＋天数；跨月收货分别到期。' },
  { key: 'payment_days', label: '自定义月结天数（0～365）', optional: true, hint: '仅选择月结自定义时使用；留空沿用原设置。' },
]
