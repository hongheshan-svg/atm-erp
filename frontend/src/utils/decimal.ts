// 定点小数运算的唯一实现。金额（两位）、数量（三位）都以十进制字符串从后端传来，换算成以最小单位计的 BigInt
// 再加减、比较，不经过 Number，免得浮点误差和大数丢位。显示用的千分位、去尾零仍分别交给 money / quantityText。
export const MONEY_SCALE = 2
export const QUANTITY_SCALE = 3

export type ScaledOptions = {
  // 是否接受负号；数量、单价等非负输入传 false，带负号视为格式不符。
  signed?: boolean
  // 超出 scale 的小数位：默认视为格式不符；'truncate' 直接截掉（不舍入）。
  excess?: 'reject' | 'truncate'
  // 整数部分最多几位（含前导 0），对应服务端 Decimal 的 max_digits − decimal_places。
  integerDigits?: number
}

/** 十进制字符串（或安全整数范围内的数字）→ 以 10^-scale 为单位的整数；格式不符时返回 null。 */
export function toScaled(value: unknown, scale: number, options: ScaledOptions = {}): bigint | null {
  const { signed = true, excess = 'reject', integerDigits } = options
  if (typeof value === 'number') {
    // 超出安全整数的数字在到这里之前已经丢了位。
    if (!Number.isFinite(value) || Math.abs(value) > Number.MAX_SAFE_INTEGER) return null
  } else if (typeof value !== 'string') return null
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(String(value).trim())
  if (!match) return null
  const [, sign, whole = '0', fraction = ''] = match
  if (sign && !signed) return null
  if (integerDigits != null && whole.length > integerDigits) return null
  if (fraction.length > scale && excess === 'reject') return null
  const scaled = BigInt(whole) * 10n ** BigInt(scale) + BigInt(fraction.slice(0, scale).padEnd(scale, '0') || '0')
  return sign ? -scaled : scaled
}

/** 以 10^-scale 为单位的整数 → 补足 scale 位小数的字符串。符号单独处理：BigInt 除法向零截断、余数带符号，直接拼接会得到「0.-500」。 */
export function fromScaled(value: bigint, scale: number): string {
  const negative = value < 0n, abs = negative ? -value : value
  const unit = 10n ** BigInt(scale)
  return `${negative ? '-' : ''}${abs / unit}${scale > 0 ? `.${String(abs % unit).padStart(scale, '0')}` : ''}`
}

/** 整数除法按 ROUND_HALF_UP（与服务端 Decimal 一致：恰好一半时远离零）。 */
export function divideHalfUp(value: bigint, divisor: bigint): bigint {
  const negative = (value < 0n) !== (divisor < 0n)
  const a = value < 0n ? -value : value, b = divisor < 0n ? -divisor : divisor
  const quotient = (a * 2n + b) / (b * 2n)
  return negative ? -quotient : quotient
}
