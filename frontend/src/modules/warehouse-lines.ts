import type { Field, Row } from '../types'
import { partTypes, productCategories } from '../product-categories'
import { fromScaled, QUANTITY_SCALE, toScaled } from '../utils/decimal'
import { rows } from './shared'

const detail = (key: string, label: string): Field => ({ key, label, readonly: true, displayOnly: true })
export function materialDetails(item: Row): Row {
  const drawing_model = [item.drawing_number && `图号：${item.drawing_number}`, item.specification && `型号：${item.specification}`].filter(Boolean).join('\n')
  const revision_brand = [item.drawing_revision && `版本：${item.drawing_revision}`, item.brand && `品牌：${item.brand}`].filter(Boolean).join('\n')
  const part_label = [productCategories[item.product_category], partTypes[item.part_type]].filter(Boolean).join(' / ')
  return {
    ...item,
    drawing_model,
    revision_brand,
    part_label,
    // 1366 宽度下不横向滚动：编号与名称、图号型号版本品牌与类型各并成一列，数量输入列紧随其后。
    material_label: [item.item_code, item.item_name].filter(Boolean).join('\n'),
    spec_label: [drawing_model, revision_brand, part_label].filter(Boolean).join('\n'),
  }
}
// batch：按 BOM 批量领料，每行是一个库位，可填 0 表示本次不领；单行领料数量须大于 0。
// location：库存页勾选多行领料，逐行显示库位，数量仍须大于 0（勾选了就是要领）。
// 收货：每行前有「本次到货」勾选（selected，默认勾选，不提交）；cancel 为 true 时（有采购权限）
// 未收足的行可勾选「余量不再到货」（cancel_remainder），同一次提交里取消该行剩余未收数量。
export function warehouseLines(kind: 'receipt' | 'issue', initial: Row[], options: { batch?: boolean; location?: boolean; cancel?: boolean } = {}): Field {
  const batch = kind === 'issue' && !!options.batch
  const located = kind === 'issue' && (batch || !!options.location)
  return {
    ...rows('lines', kind === 'receipt' ? '本次收货' : '本次出库', [
      { key: kind === 'receipt' ? 'line' : 'stock', label: '明细标识', hidden: true },
      ...(kind === 'receipt' ? [{ key: 'selected', label: '本次到货', type: 'boolean', hidden: true, initial: true } satisfies Field] : []),
      ...(kind === 'receipt' && options.cancel ? [{ key: 'cancel_remainder', label: '余量不再到货', type: 'boolean', hidden: true, initial: false } satisfies Field] : []),
      detail('material_label', '产品编号 / 零件名称'),
      ...(kind === 'receipt' ? [detail('assembly_unit', '单元')] : located ? [detail('location', '库位')] : []),
      detail('spec_label', '图号 / 型号 / 版本 / 类型'), detail('unit', '单位'),
      detail('required_quantity', '需求数量'),
      ...(batch ? [detail('bom_remaining', 'BOM 未领')] : []),
      detail('remaining', kind === 'receipt' ? '待收数量' : located ? '本库位可用' : '可用库存'),
      { key: 'quantity', label: '数量', numeric: { scale: 3, min: kind === 'receipt' || batch ? 0 : 0.001 }, hint: kind === 'receipt' ? '本次实际到货的合格数量；可少于待收，余量继续待收。' : batch ? '本次领用数量；填 0 表示本行不领。' : '本次实际领料出库数量。' },
      ...(kind === 'receipt' ? [{ key: 'pending_quantity', label: '不合格隔离数量', initial: '0', numeric: { scale: 3, min: 0 }, hint: '待检或不合格数量，不进入可用库存。' } satisfies Field] : []),
      { key: 'remark', label: '备注', optional: true, placeholder: '选填，如外观异常、使用工位；最多500字' },
    ]),
    warehouse: kind, readonly: true, initial, dense: true,
    hint: kind === 'receipt'
      ? '勾选本次实际到货的行，未到货的行取消勾选；核对产品编号、图号和版本后填写本次数量。需求数量取该BOM单元总需求，无BOM时显示采购数量。备注按本次明细保存。'
      : batch
        ? '需求数量为本项目 BOM 中该物料的合计，BOM 未领 = 需求 − 已领；同一物料有多个库位时按库位依次预填。库存为共享库存，保存时再次校验。'
        : '需求数量按所选项目同物料的BOM需求汇总；售后领料按任务处理。库存为共享库存，保存时再次校验可领数量。',
  }
}

// BOM quantities are non-negative decimals with at most three fractional digits; anything else counts as 0.
export function sumQuantities(values: string[]): string {
  return fromScaled(values.reduce((sum, value) => sum + (toScaled(value, QUANTITY_SCALE) ?? 0n), 0n), QUANTITY_SCALE)
}
