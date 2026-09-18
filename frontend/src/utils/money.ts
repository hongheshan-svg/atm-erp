// 金额展示的唯一实现。金额一律以字符串从后端传来，这里只做千分位和补零，不经过 Number，
// 免得大额被浮点改写；在此之前工作台、报表、项目页、预算面板各写一遍，连 ¥ 后有没有空格都不一致。
export type MoneyOptions = {
  // 前缀「¥ 」。金额列已经靠右且用等宽数字，正文里的单个金额才需要符号。
  currency?: boolean
  // 空值的占位文本，预算和合同金额用「未设置」区分「没填」和「零」。
  placeholder?: string
  // 负余额显示为「待退款 x」而不是负号：应收应付页把方向写成字，比符号好认。
  refund?: boolean
}

export function money(value: unknown, options: MoneyOptions = {}): string {
  const { currency = false, placeholder = '—', refund = false } = options
  if (value == null || value === '') return placeholder
  const text = String(value)
  const negative = text.startsWith('-')
  const [whole = '0', fraction = ''] = (negative ? text.slice(1) : text).split('.')
  const grouped = `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`
  const prefix = negative ? (refund ? '待退款 ' : '-') : ''
  return `${prefix}${currency ? '¥ ' : ''}${grouped}`
}
