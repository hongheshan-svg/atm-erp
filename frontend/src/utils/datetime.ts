// 时间显示统一为「YYYY-MM-DD HH:mm」，按业务时区 Asia/Shanghai（与服务端 TIME_ZONE 一致），不随浏览器时区变化。
// 带时区的 ISO 串（含 UTC 的 Z、+00:00）先换算；不带时区的串视为已是业务本地时间，原样截取。
const businessDateTime = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})
const zoned = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?)(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})$/i
export function dateTimeText(value: unknown, placeholder = '—'): string {
  if (value == null || value === '') return placeholder
  const text = String(value).trim()
  const match = zoned.exec(text)
  // 毫秒以下的位数各浏览器解析不一，只保留到毫秒。
  const time = match ? new Date(`${match[1]}${match[2] ? `.${match[2].slice(0, 3).padEnd(3, '0')}` : ''}${match[3]!.toUpperCase()}`) : null
  if (!time || Number.isNaN(time.getTime())) return text.slice(0, 16).replace('T', ' ')
  const parts = Object.fromEntries(businessDateTime.formatToParts(time).map(({ type, value }) => [type, value]))
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`
}
