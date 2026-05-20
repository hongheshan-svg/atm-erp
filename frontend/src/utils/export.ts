interface ExportColumn {
  field: string
  title: string
  width?: number
  formatter?: (value: any, row: any) => string
}

export function exportToExcel(data: any[], columns: ExportColumn[], filename = 'export'): void {
  let csvContent = '﻿'

  const headers = columns.map(col => col.title)
  csvContent += headers.join(',') + '\n'

  data.forEach(row => {
    const values = columns.map(col => {
      let value: any = row[col.field]

      if (col.field.includes('.')) {
        const parts = col.field.split('.')
        value = parts.reduce((obj: any, key: string) => obj?.[key], row)
      }

      if (col.formatter) {
        value = col.formatter(value, row)
      }

      if (value === null || value === undefined) {
        value = ''
      } else {
        value = String(value)
        if (value.includes(',') || value.includes('"') || value.includes('\n')) {
          value = '"' + value.replace(/"/g, '""') + '"'
        }
      }

      return value
    })
    csvContent += values.join(',') + '\n'
  })

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)

  link.setAttribute('href', url)
  link.setAttribute('download', `${filename}_${formatDate(new Date())}.csv`)
  link.style.visibility = 'hidden'

  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

  URL.revokeObjectURL(url)
}

function formatDate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
}

export function exportTableData(data: any[], fieldMap: Record<string, string>, filename = 'export'): void {
  const columns: ExportColumn[] = Object.entries(fieldMap).map(([field, title]) => ({
    field,
    title
  }))
  exportToExcel(data, columns, filename)
}

export function formatMoney(value: any): string {
  if (value === null || value === undefined) return '0.00'
  return parseFloat(value).toFixed(2)
}

export function formatDateStr(dateStr: string | null | undefined): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return date.toLocaleDateString('zh-CN')
}
