import type { Field, Row } from './types'
export function defaults(fields: Field[], initial: Row = {}): Row {
  return Object.fromEntries(
    fields.map((f) => [
      f.key,
      initial[f.key] ??
        f.initial ??
        (f.type === 'rows'
          ? [defaults(f.fields!)]
          : f.type === 'multi'
            ? []
            : f.type === 'boolean'
              ? true
              : ''),
    ]),
  )
}
export function payload(fields: Field[], data: Row): Row {
  return Object.fromEntries(
    fields
      .filter((f) => !(f.optional && (data[f.key] === '' || data[f.key] == null)))
      .map((f) => [
        f.key,
        f.type === 'rows' ? data[f.key].map((r: Row) => payload(f.fields!, r)) : data[f.key],
      ]),
  )
}
export const today = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
export function decimalDifference(...values: string[]): string {
  const scaled = (v: string) => {
    const [a, b = ''] = v.split('.')
    return BigInt(a || '0') * 1000n + BigInt((b + '000').slice(0, 3))
  }
  const n = values.slice(1).reduce((n, v) => n - scaled(v), scaled(values[0] || '0'))
  return `${n / 1000n}.${String(n % 1000n).padStart(3, '0')}`
}
