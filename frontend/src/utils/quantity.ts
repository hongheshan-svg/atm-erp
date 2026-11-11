// 数量显示的唯一实现：后端数量是三位小数字符串（2.000），显示时去掉尾随 0，最多保留 3 位；
// 只改显示，输入与提交仍用原字符串。空值显示占位符，非数字原样返回。
export function quantityText(value: unknown, placeholder = '—'): string {
  if (value == null || value === '') return placeholder
  const text = String(value).trim()
  if (!/^-?\d+(\.\d+)?$/.test(text)) return String(value)
  const [whole = '0', fraction = ''] = text.split('.')
  const trimmed = fraction.slice(0, 3).replace(/0+$/, '')
  const sign = text.startsWith('-') && (Number(whole.replace('-', '')) > 0 || trimmed) ? '-' : ''
  return `${sign}${whole.replace('-', '')}${trimmed ? `.${trimmed}` : ''}`
}
