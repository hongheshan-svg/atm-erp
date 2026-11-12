import { money } from './utils/money'
import { divideHalfUp, fromScaled, MONEY_SCALE, QUANTITY_SCALE, toScaled } from './utils/decimal'

/** Quantity in thousandths, matching the server's Decimal(18, 3) input. */
export function quantityValue(value: unknown): bigint | null {
  return toScaled(value, QUANTITY_SCALE, { signed: false, integerDigits: 15 })
}

/** Round each purchase line to cents using ROUND_HALF_UP before summing lines. */
export function purchaseLineCents(quantity: unknown, price: unknown): bigint | null {
  const thousandths = quantityValue(quantity)
  const unitCents = toScaled(price, MONEY_SCALE, { signed: false, integerDigits: 16 })
  if (thousandths == null || thousandths <= 0n || unitCents == null) return null
  return divideHalfUp(thousandths * unitCents, 1000n)
}

export function formatPurchaseAmount(cents: bigint | null): string {
  return cents == null ? '待填写' : money(fromScaled(cents, MONEY_SCALE))
}
