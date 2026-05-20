export function toFixedSafe(value: any, digits = 2, fallback = '0.00'): string {
  const amount = Number.parseFloat(value ?? 0)
  if (!Number.isFinite(amount)) {
    return fallback
  }

  return amount.toFixed(digits)
}

export function subtractFixedSafe(left: any, right: any, digits = 2, fallback = '0.00'): string {
  const leftAmount = Number.parseFloat(left ?? 0)
  const rightAmount = Number.parseFloat(right ?? 0)

  if (!Number.isFinite(leftAmount) || !Number.isFinite(rightAmount)) {
    return fallback
  }

  return (leftAmount - rightAmount).toFixed(digits)
}
