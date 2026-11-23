import { codeField } from './shared'
import { rows } from './shared'
import { read } from '../api'
import { dateTimeText } from '../utils/datetime'
import { quantityText } from '../utils/quantity'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
import { select } from './shared'
import { choices } from './shared'
import { buyer } from './shared'
import { C } from './shared'
import { endpoint } from './shared'
import { materialEditor, partnerEditor, customerOnly } from '../session'
import { termFields, termLabel } from './payment-terms'
import { partTypeLabel, partTypes, productCategories } from '../product-categories'
import { linkLabel, purchaseLink } from '../utils/links'
function partnerPayload(data: Row): Row {
  // 转为纯客户时同步清除已保存的供应商条款，避免后端沿用原账期后拒绝保存。
  return data.kind === 'customer' ? { ...data, payment_term: 'manual', payment_days: 0 } : data
}
export const columns: Record<string, Column[]> = {
  items: [
    C('code', '物料编码'),
    C('name', '物料名称'),
    C('specification', '规格'),
    C('drawing_number', '图号'),
    // 同图号已换成新版的旧版在版本旁注明，免得继续选用旧图。
    { key: 'drawing_revision', label: '图档版本', format: r => [r.drawing_revision, r.newer_revision ? `已有新版 ${r.newer_revision.drawing_revision || r.newer_revision.code}` : ''].filter(Boolean).join(' · ') },
    { key: 'product_category', label: '产品编码类别', format: r => productCategories[r.product_category] || '未分类' },
    C('brand', '品牌'),
    { key: 'part_type', label: '物料类别', format: r => partTypeLabel(r.part_type) },
    C('unit', '单位'),
    // 网购件的商品页：点开直接下单，按网店写「淘宝 ↗」「京东 ↗」。
    { key: 'purchase_url', label: '购买链接', format: r => purchaseLink(r.purchase_url) ? `${linkLabel(purchaseLink(r.purchase_url))} ↗` : '—', href: r => purchaseLink(r.purchase_url) },
    C('is_active', '启用'),
  ],
  partners: [
    C('code', '编码'),
    C('name', '往来单位'),
    C('kind', '类型'),
    C('contact', '联系人'),
    C('phone', '电话'),
    { key: 'payment_term', label: '采购账期', format: r => r.kind === 'customer' ? '—' : termLabel(r) },
    C('address', '地址'),
    C('is_active', '启用'),
  ],
}
export function createLabel(resource: string) {
  return (
    (
      { items: materialEditor() && '新增物料', partners: partnerEditor() && '新增往来单位' } as Record<
        string,
        string | boolean
      >
    )[resource] || ''
  )
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'items')
    fields = [
      codeField('物料编码（留空自动生成）'),
      t('name', '物料名称'),
      { ...t('specification', '规格', true), hint: '标准件填写经厂家或供应商确认的完整型号；原文保存，不自动补全或修改。' },
      { ...t('drawing_number', '图号', true), hint: '有图产品必填；工程图示例 A26-E-05-P-000001，模具子图 ATM-T1-P-000001。历史图号可保留。' },
      t('drawing_revision', '图档版本', true),
      { ...select('product_category', '产品编码类别', choices(productCategories), true), hint: '编码留空时按类别自动生成10位编码：有图使用当年年份，无图固定99，流水六位。未分类沿用普通编号规则；版本升级须新增物料。' },
      t('brand', '品牌', true),
      select('part_type', '物料类别', choices(partTypes), true),
      { key: 'unit', label: '单位', initial: '件' },
      { ...t('purchase_url', '购买链接', true), placeholder: 'https://…', hint: '网购件填写商品页链接；可直接粘贴淘宝、京东 App 里“分享 → 复制链接”得到的整段文字，系统只保存其中的链接。' },
      { ...t('duplicate_reason', '相同物料独立编码原因', true), hint: '名称或型号疑似重复时，先核对厂家完整型号；确认是不同物料后填写独立建码原因。' },
    ]
  if (resource === 'partners')
    fields = [
      codeField('往来单位编码'),
      t('name', '单位名称'),
      select(
        'kind',
        '类型',
        choices(customerOnly() ? { customer: '客户' } : { customer: '客户', supplier: '供应商', both: '客户及供应商' }),
      ),
      t('contact', '联系人', true),
      t('phone', '电话', true),
      t('address', '地址', true),
      ...(!customerOnly() ? termFields().map(field => ({
        ...field,
        visibleWhen: (data: Row) => data.kind === 'supplier' || data.kind === 'both',
      })) : []),
    ]
  return {
    title: String(createLabel(resource)),
    path,
    fields,
    initial: projectId ? { project: projectId } : {},
    prepare: resource === 'partners' ? partnerPayload : undefined,
  }
}
export function actionNames(resource: string, _r: Row): string[] {
  const a: string[] = []
  if (resource === 'items' && materialEditor()) a.push('编辑')
  if (resource === 'items' && _r.drawing_number) a.push('版本记录')
  if (resource === 'partners' && buyer()) a.push('编辑')
  if (resource === 'partners' && customerOnly() && _r.kind === 'customer') a.push('编辑')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (resource === 'items' && name === '版本记录') return versionHistory(r)
  if (name !== '编辑' || !['items', 'partners'].includes(resource)) throw new Error('不支持的基础资料操作。')
  return {
    title: name, path: endpoint(resource) + r.id + '/', method: 'patch', initial: r,
    fields: [...(await createCommand(resource)).fields.filter(f => f.key !== 'code').map(f => resource === 'items' && r.product_category && ['product_category', 'specification', 'drawing_number', 'drawing_revision'].includes(f.key) ? { ...f, readonly: true, displayOnly: true } : f), { key: 'is_active', label: '启用', type: 'boolean' }],
    // 选填文本清空后也提交空串，否则服务端按「未提交」保留原值；已编码物料的规格、图号、图档版本只读，不提交。
    prepare: data => resource === 'items'
      ? { ...data, brand: data.brand ?? '', part_type: data.part_type ?? '', purchase_url: data.purchase_url ?? '', ...(r.product_category ? {} : { specification: data.specification ?? '', drawing_number: data.drawing_number ?? '', drawing_revision: data.drawing_revision ?? '' }) }
      : partnerPayload({ ...data, contact: data.contact ?? '', phone: data.phone ?? '', address: data.address ?? '' }),
    // 前后端口径一致：已按产品编码类别编码的物料，类别、规格、图号、图档版本不可覆盖；另外被 BOM、采购、库存引用后，已有的单位、规格、图档也不能改写（由服务端校验）。
    ...(resource === 'items' && r.product_category ? { notice: { type: 'info' as const, text: '该物料已按产品编码类别编码：产品编码类别、规格、图号、图档版本不能在此修改；版本升级请新增物料编码并修订 BOM。物料一旦被 BOM、采购或库存引用，已有的单位、规格、图档也不能改写。' } } : {}),
  }
}

// 同图号的全部版本和各项目的换版记录：反复改图时查清每一版由谁、因为哪张 ECN、在哪个项目换上来的。
async function versionHistory(r: Row): Promise<Command> {
  const data = await read(`/business/items/${r.id}/revisions/`)
  const versions = (data.versions || []) as Row[]
  const latest = versions.find(row => row.latest)
  return {
    title: `版本记录 · 图号 ${data.drawing_number || r.drawing_number}`,
    path: '',
    readonly: true,
    notice: { type: 'info', text: latest ? `当前最新为 ${latest.drawing_revision || latest.code} 版（${latest.code}）。旧版仍可用于售后或备件；项目 BOM 要换成新版，在该行「升版」。` : '这张图还没有通过 BOM 换版记录过新版本。' },
    initial: {
      versions: versions.map(row => ({ ...row, state: row.latest ? '最新' : row.superseded_by ? `已由 ${row.superseded_by} 取代` : row.is_active ? '在用' : '已停用' })),
      changes: (data.changes || []).map((row: Row) => ({
        ...row,
        time: dateTimeText(row.created_at, ''),
        project: `${row.project_code} ${row.project_name}`,
        change: `${row.old_item_code}${row.old_revision ? `（${row.old_revision}）` : ''} → ${row.new_item_code}${row.new_revision ? `（${row.new_revision}）` : ''}`,
        amount: `${quantityText(row.old_quantity)} → ${quantityText(row.new_quantity)}${Number(row.converted_quantity) > 0 ? `，在途 ${quantityText(row.converted_quantity)} 改单` : ''}`,
      })),
    },
    fields: [
      rows('versions', '同图号的全部版本', [t('drawing_revision', '版本'), t('code', '物料编码'), t('name', '名称'), t('specification', '规格'), t('state', '状态')]),
      rows('changes', '换版记录（只列你参与的项目）', [t('time', '时间'), t('project', '项目'), t('assembly_unit', '单元'), t('change', '换版'), t('amount', '数量'), t('reason', '原因'), t('created_by', '经办人')]),
    ],
  }
}
