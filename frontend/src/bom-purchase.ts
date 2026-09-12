function scaledDecimal(value: unknown, scale: number, integerDigits: number): bigint | null {
  if (typeof value !== 'string' && typeof value !== 'number') return null
  // An unsafe numeric input may already have lost digits before reaching this parser.
  if (typeof value === 'number' && (!Number.isFinite(value) || Math.abs(value) > Number.MAX_SAFE_INTEGER)) return null
  const text = String(value).trim()
  if (!new RegExp(`^\\d{1,${integerDigits}}(?:\\.\\d{1,${scale}})?$`).test(text)) return null
  const [whole, fraction = ''] = text.split('.')
  return BigInt(whole!) * 10n ** BigInt(scale) + BigInt(fraction.padEnd(scale, '0'))
}

/** Quantity in thousandths, matching the server's Decimal(18, 3) input. */
export function quantityValue(value: unknown): bigint | null {
  return scaledDecimal(value, 3, 15)
}

/** Round each purchase line to cents using ROUND_HALF_UP before summing lines. */
export function purchaseLineCents(quantity: unknown, price: unknown): bigint | null {
  const thousandths = quantityValue(quantity)
  const unitCents = scaledDecimal(price, 2, 16)
  if (thousandths == null || thousandths <= 0n || unitCents == null) return null
  return (thousandths * unitCents + 500n) / 1000n
}

export function formatPurchaseAmount(cents: bigint | null): string {
  if (cents == null) return '待填写'
  const amount = cents < 0n ? -cents : cents
  const whole = (amount / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const fraction = (amount % 100n).toString().padStart(2, '0')
  return `${cents < 0n ? '-' : ''}${whole}.${fraction}`
}
