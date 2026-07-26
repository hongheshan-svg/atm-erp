export type ReceiptTagType = 'info' | 'warning' | 'success'

const receiptStatusLabels: Record<string, string> = {
  DRAFT: '草稿',
  CONFIRMED: '已确认',
  COMPLETED: '已完成',
}

const receiptStatusTypes: Record<string, ReceiptTagType> = {
  DRAFT: 'info',
  CONFIRMED: 'warning',
  COMPLETED: 'success',
}

export const getGoodsReceiptStatusLabel = (status: string) => receiptStatusLabels[status] || status

export const getGoodsReceiptStatusType = (status: string): ReceiptTagType => receiptStatusTypes[status] || 'info'
