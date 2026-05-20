import { toFixedSafe } from '@/utils/number'

export function printHtml(content: string, title = '打印'): void {
  const printWindow = window.open('', '_blank')
  if (!printWindow) return

  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>${title}</title>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: "Microsoft YaHei", "SimSun", Arial, sans-serif; font-size: 12px; line-height: 1.5; padding: 20px; }
        .print-header { text-align: center; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #333; }
        .print-header h1 { font-size: 18px; margin-bottom: 5px; }
        .print-header .sub-title { font-size: 14px; color: #666; }
        .print-info { display: flex; justify-content: space-between; margin-bottom: 15px; font-size: 12px; }
        .print-info-item { margin-right: 20px; }
        .print-info-label { color: #666; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 15px; }
        th, td { border: 1px solid #333; padding: 6px 8px; text-align: left; }
        th { background-color: #f0f0f0; font-weight: bold; }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        .total-row { font-weight: bold; background-color: #f9f9f9; }
        .print-footer { margin-top: 30px; display: flex; justify-content: space-between; }
        .signature-box { width: 200px; }
        .signature-line { border-bottom: 1px solid #333; height: 30px; margin-top: 5px; }
        @media print { body { padding: 0; } .no-print { display: none; } }
      </style>
    </head>
    <body>
      ${content}
      <script>window.onload = function() { window.print(); window.close(); }</script>
    </body>
    </html>
  `)

  printWindow.document.close()
}

export function generateQuotationPrintContent(quotation: any): string {
  const lines = quotation.lines || []
  let linesHtml = ''
  let total = 0

  lines.forEach((line: any, index: number) => {
    const amount = (line.qty || 0) * (line.unit_price || 0)
    total += amount
    linesHtml += `
      <tr>
        <td class="text-center">${index + 1}</td>
        <td>${line.item_name || line.item_code || ''}</td>
        <td>${line.specification || '-'}</td>
        <td>${line.unit || '-'}</td>
        <td class="text-right">${line.qty || 0}</td>
        <td class="text-right">¥${toFixedSafe(line.unit_price)}</td>
        <td class="text-right">¥${toFixedSafe(amount)}</td>
        <td>${line.notes || '-'}</td>
      </tr>
    `
  })

  return `
    <div class="print-header">
      <h1>销售报价单</h1>
      <div class="sub-title">SALES QUOTATION</div>
    </div>
    <div class="print-info">
      <div>
        <span class="print-info-item"><span class="print-info-label">报价单号：</span>${quotation.quote_no || ''}</span>
        <span class="print-info-item"><span class="print-info-label">版本：</span>V${quotation.version || 1}</span>
      </div>
      <div>
        <span class="print-info-item"><span class="print-info-label">日期：</span>${quotation.quote_date || ''}</span>
        <span class="print-info-item"><span class="print-info-label">有效期至：</span>${quotation.valid_until || ''}</span>
      </div>
    </div>
    <div class="print-info">
      <div><span class="print-info-item"><span class="print-info-label">客户：</span>${quotation.customer_name || ''}</span></div>
      <div>
        <span class="print-info-item"><span class="print-info-label">联系人：</span>${quotation.contact || ''}</span>
        <span class="print-info-item"><span class="print-info-label">电话：</span>${quotation.phone || ''}</span>
      </div>
    </div>
    <table>
      <thead>
        <tr>
          <th class="text-center" width="40">序号</th>
          <th>物料名称</th>
          <th width="100">规格</th>
          <th width="60">单位</th>
          <th class="text-right" width="60">数量</th>
          <th class="text-right" width="80">单价</th>
          <th class="text-right" width="100">金额</th>
          <th width="100">备注</th>
        </tr>
      </thead>
      <tbody>
        ${linesHtml}
        <tr class="total-row">
          <td colspan="6" class="text-right">合计金额：</td>
          <td class="text-right">¥${total.toFixed(2)}</td>
          <td></td>
        </tr>
      </tbody>
    </table>
    <div style="margin-bottom: 15px;"><p><strong>备注：</strong>${quotation.notes || '无'}</p></div>
    <div class="print-footer">
      <div class="signature-box"><p>报价人：</p><div class="signature-line"></div></div>
      <div class="signature-box"><p>审核人：</p><div class="signature-line"></div></div>
      <div class="signature-box"><p>客户确认：</p><div class="signature-line"></div></div>
    </div>
  `
}

export function generateDeliveryOrderPrintContent(delivery: any): string {
  const lines = delivery.lines || []
  let linesHtml = ''

  lines.forEach((line: any, index: number) => {
    linesHtml += `
      <tr>
        <td class="text-center">${index + 1}</td>
        <td>${line.item_name || line.item_code || ''}</td>
        <td>${line.specification || '-'}</td>
        <td>${line.unit || '-'}</td>
        <td class="text-right">${line.qty || 0}</td>
        <td>${line.notes || '-'}</td>
      </tr>
    `
  })

  return `
    <div class="print-header">
      <h1>发货单</h1>
      <div class="sub-title">DELIVERY ORDER</div>
    </div>
    <div class="print-info">
      <div>
        <span class="print-info-item"><span class="print-info-label">发货单号：</span>${delivery.delivery_no || ''}</span>
        <span class="print-info-item"><span class="print-info-label">销售订单：</span>${delivery.sales_order_no || ''}</span>
      </div>
      <div><span class="print-info-item"><span class="print-info-label">发货日期：</span>${delivery.delivery_date || ''}</span></div>
    </div>
    <div class="print-info">
      <div>
        <span class="print-info-item"><span class="print-info-label">客户：</span>${delivery.customer_name || ''}</span>
        <span class="print-info-item"><span class="print-info-label">收货地址：</span>${delivery.shipping_address || ''}</span>
      </div>
    </div>
    <div class="print-info">
      <div><span class="print-info-item"><span class="print-info-label">发货仓库：</span>${delivery.warehouse_name || ''}</span></div>
    </div>
    <table>
      <thead>
        <tr>
          <th class="text-center" width="40">序号</th>
          <th>物料名称</th>
          <th width="100">规格</th>
          <th width="60">单位</th>
          <th class="text-right" width="80">数量</th>
          <th width="150">备注</th>
        </tr>
      </thead>
      <tbody>${linesHtml}</tbody>
    </table>
    <div style="margin-bottom: 15px;"><p><strong>备注：</strong>${delivery.notes || '无'}</p></div>
    <div class="print-footer">
      <div class="signature-box"><p>发货人：</p><div class="signature-line"></div></div>
      <div class="signature-box"><p>运输人：</p><div class="signature-line"></div></div>
      <div class="signature-box"><p>收货人签收：</p><div class="signature-line"></div></div>
    </div>
  `
}
