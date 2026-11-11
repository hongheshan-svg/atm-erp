// 时间显示统一为「YYYY-MM-DD HH:mm」（取服务端 ISO 串的本地时间部分，不做时区换算）。
export function dateTimeText(value: unknown, placeholder = '—'): string {
  if (value == null || value === '') return placeholder
  return String(value).slice(0, 16).replace('T', ' ')
}
