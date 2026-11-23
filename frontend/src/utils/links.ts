// 物料购买链接（淘宝、京东等商品页）。服务端只存 http(s) 链接；这里再守一道，别的写法一律不渲染成链接。
export function purchaseLink(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : ''
  return /^https?:\/\/[^\s]+$/i.test(text) ? text : ''
}

const SHOPS: [RegExp, string][] = [
  [/(^|\.)(taobao\.com|tb\.cn)$/, '淘宝'],
  [/(^|\.)tmall\.com$/, '天猫'],
  [/(^|\.)(jd\.com|3\.cn)$/, '京东'],
  [/(^|\.)1688\.com$/, '1688'],
  [/(^|\.)(pinduoduo\.com|yangkeduo\.com)$/, '拼多多'],
]

// 链接文字按网店写（淘宝、京东……），认不出的写「购买链接」。
export function linkLabel(url: string): string {
  let host = ''
  try { host = new URL(url).hostname.toLowerCase() } catch { return '购买链接' }
  return SHOPS.find(([pattern]) => pattern.test(host))?.[1] || '购买链接'
}
