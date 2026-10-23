import type { Field, Row } from '../types'
import { productCategories } from '../product-categories'
import { rows } from './shared'

const detail = (key: string, label: string): Field => ({ key, label, readonly: true, displayOnly: true })
export function materialDetails(item: Row): Row {
  return {
    ...item,
    drawing_model: [item.drawing_number && `图号：${item.drawing_number}`, item.specification && `型号：${item.specification}`].filter(Boolean).join('\n'),
    revision_brand: [item.drawing_revision && `版本：${item.drawing_revision}`, item.brand && `品牌：${item.brand}`].filter(Boolean).join('\n'),
    part_label: [productCategories[item.product_category], ({ standard: '标准件', custom: '非标件' } as Record<string, string>)[item.part_type]].filter(Boolean).join(' / '),
  }
}
export function warehouseLines(kind: 'receipt' | 'issue', initial: Row[]): Field {
  return {
    ...rows('lines', kind === 'receipt' ? '本次收货' : '本次出库', [
      { key: kind === 'receipt' ? 'line' : 'stock', label: '明细标识', hidden: true },
      detail('project_code', '项目号'), detail('item_code', '产品编号'), detail('item_name', '零件名称'),
      ...(kind === 'receipt' ? [detail('assembly_unit', '单元')] : []),
      detail('drawing_model', '图号 / 型号'), detail('revision_brand', '版本 / 品牌'), detail('unit', '单位'),
      detail('required_quantity', '需求数量'), detail('part_label', '零件类型'),
      detail('remaining', kind === 'receipt' ? '待收数量' : '可用库存'),
      { key: 'quantity', label: '数量', numeric: { scale: 3, min: kind === 'receipt' ? 0 : 0.001 }, hint: kind === 'receipt' ? '本次合格入库数量；未到货填0。' : '本次实际领料出库数量。' },
      ...(kind === 'receipt' ? [{ key: 'pending_quantity', label: '不合格隔离数量', initial: '0', numeric: { scale: 3, min: 0 }, hint: '待检或不合格数量，不进入可用库存。' } satisfies Field] : []),
      { key: 'remark', label: '备注', optional: true, placeholder: '选填，如外观异常、使用工位；最多500字' },
    ]),
    warehouse: kind, readonly: true, initial,
    hint: kind === 'receipt'
      ? '核对产品编号、图号和版本后填写本次数量；需求数量取该BOM单元总需求，无BOM时显示采购数量。备注按本次明细保存。'
      : '需求数量按所选项目同物料的BOM需求汇总；售后领料按任务处理。库存为共享库存，保存时再次校验可领数量。',
  }
}

// BOM quantities are non-negative decimals with at most three fractional digits.
export function sumQuantities(values: string[]): string {
  const total = values.reduce((sum, value) => {
    const [whole = '0', fraction = ''] = value.split('.')
    return sum + BigInt(whole) * 1000n + BigInt(fraction.padEnd(3, '0'))
  }, 0n)
  return `${total / 1000n}.${String(total % 1000n).padStart(3, '0')}`
}
