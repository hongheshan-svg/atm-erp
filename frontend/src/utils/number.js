export function toFixedSafe(value, digits = 2, fallback = '0.00') {
  const amount = Number.parseFloat(value ?? 0)
  if (!Number.isFinite(amount)) {
    return fallback
  }

  return amount.toFixed(digits)
}

export function subtractFixedSafe(left, right, digits = 2, fallback = '0.00') {
  const leftAmount = Number.parseFloat(left ?? 0)
  const rightAmount = Number.parseFloat(right ?? 0)

  if (!Number.isFinite(leftAmount) || !Number.isFinite(rightAmount)) {
    return fallback
  }

  return (leftAmount - rightAmount).toFixed(digits)
}
