import type { Field, Row } from './types'
export function applicableFields(fields: Field[], data: Row): Field[] {
  return fields.filter(field => !field.visibleWhen || field.visibleWhen(data))
}
export function defaults(fields: Field[], initial: Row = {}): Row {
  return Object.fromEntries(
    fields.map((f) => [
      f.key,
      initial[f.key] ??
        f.initial ??
        (f.type === 'rows'
          ? [defaults(f.fields!)]
          : f.type === 'multi' || f.type === 'checks'
            ? []
            : f.type === 'boolean'
              ? true
              : ''),
    ]),
  )
}
export function payload(fields: Field[], data: Row): Row {
  return Object.fromEntries(
    applicableFields(fields, data)
      .filter((f) => !f.displayOnly && !(f.optional && (data[f.key] === '' || data[f.key] == null)))
      .map((f) => [
        f.key,
        f.type === 'rows' ? data[f.key].map((r: Row) => payload(f.fields!, r)) : data[f.key],
      ]),
  )
}
export type FieldIssue = { path: string; label: string; message: string }
export function fieldIssues(fields: Field[], data: Row, prefix = '', path = ''): FieldIssue[] {
  const issues: FieldIssue[] = []
  for (const field of applicableFields(fields, data)) {
    if (field.hidden || field.displayOnly || (field.readonly && field.type !== 'rows')) continue
    const value = data[field.key]
    const label = `${prefix}${field.label}`
    const key = path ? `${path}.${field.key}` : field.key
    const add = (message: string) => issues.push({ path: key, label, message })
    if (field.type === 'rows') {
      if (!Array.isArray(value)) add(`${label}明细格式无效。`)
      else value.forEach((row, i) => issues.push(...fieldIssues(field.fields || [], row, `${label}第 ${i + 1} 行 · `, `${key}.${i}`)))
      continue
    }
    if (value === '' || value == null || (typeof value === 'string' && !value.trim()) || (Array.isArray(value) && !value.length)) {
      if (!field.optional) add(`请填写${label}。`)
      continue
    }
    if (field.type === 'date' && !/^\d{4}-\d{2}-\d{2}$/.test(String(value))) { add(`${label}请按年-月-日填写，例如2026-10-21。`); continue }
    if (!field.numeric) continue
    const { scale, signed, min, max } = field.numeric
    const text = String(value).trim()
    const pattern = new RegExp(`^${signed ? '-?' : ''}\\d+${scale ? `(\\.\\d{1,${scale}})?` : ''}$`)
    if (!pattern.test(text)) { add(`${label}请填写${signed ? '' : '非负'}${scale ? `数字，最多 ${scale} 位小数` : '整数'}，不要带单位、千分位或科学计数法。`); continue }
    const [whole, fraction = ''] = text.replace(/^-/, '').split('.')
    const factor = 10n ** BigInt(scale)
    const number = (BigInt(whole!) * factor + BigInt(fraction.padEnd(scale, '0') || '0')) * (text.startsWith('-') ? -1n : 1n)
    const bound = (limit: number) => {
      const [whole = '0', fraction = ''] = String(Math.abs(limit)).split('.')
      return (BigInt(whole) * factor + BigInt(fraction.padEnd(scale, '0') || '0')) * (limit < 0 ? -1n : 1n)
    }
    if (min != null && number < bound(min)) add(`${label}不能小于 ${min}。`)
    if (max != null && number > bound(max)) add(`${label}不能大于 ${max}。`)
  }
  return issues
}
export function validateFields(fields: Field[], data: Row, prefix = ''): void {
  const first = fieldIssues(fields, data, prefix)[0]
  if (first) throw new Error(first.message)
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
