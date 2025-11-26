/**
 * 导出Excel工具函数
 */

/**
 * 将数据导出为Excel文件
 * @param {Array} data - 要导出的数据数组
 * @param {Array} columns - 列配置 [{field: 'name', title: '名称', width: 20}]
 * @param {String} filename - 文件名（不含扩展名）
 */
export function exportToExcel(data, columns, filename = 'export') {
  // 创建工作表内容
  let csvContent = '\uFEFF' // BOM for UTF-8
  
  // 添加表头
  const headers = columns.map(col => col.title)
  csvContent += headers.join(',') + '\n'
  
  // 添加数据行
  data.forEach(row => {
    const values = columns.map(col => {
      let value = row[col.field]
      
      // 处理嵌套属性 (如 'customer.name')
      if (col.field.includes('.')) {
        const parts = col.field.split('.')
        value = parts.reduce((obj, key) => obj?.[key], row)
      }
      
      // 格式化值
      if (col.formatter) {
        value = col.formatter(value, row)
      }
      
      // 处理特殊字符
      if (value === null || value === undefined) {
        value = ''
      } else {
        value = String(value)
        // 如果包含逗号、引号或换行，需要用引号包裹
        if (value.includes(',') || value.includes('"') || value.includes('\n')) {
          value = '"' + value.replace(/"/g, '""') + '"'
        }
      }
      
      return value
    })
    csvContent += values.join(',') + '\n'
  })
  
  // 创建Blob并下载
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

/**
 * 格式化日期为 YYYYMMDD_HHmmss
 */
function formatDate(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
}

/**
 * 导出表格数据（简化版本）
 * @param {Array} data - 数据数组
 * @param {Object} fieldMap - 字段映射 {field: title}
 * @param {String} filename - 文件名
 */
export function exportTableData(data, fieldMap, filename = 'export') {
  const columns = Object.entries(fieldMap).map(([field, title]) => ({
    field,
    title
  }))
  exportToExcel(data, columns, filename)
}

/**
 * 格式化金额
 */
export function formatMoney(value) {
  if (value === null || value === undefined) return '0.00'
  return parseFloat(value).toFixed(2)
}

/**
 * 格式化日期
 */
export function formatDateStr(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return dateStr
  return date.toLocaleDateString('zh-CN')
}

