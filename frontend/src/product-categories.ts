export const productCategories: Record<string, string> = {
  '11': '有图·机加', '12': '有图·钣金', '13': '有图·特殊工艺', '19': '有图·其它',
  '21': '无图·标准件', '22': '无图·耗材辅料', '23': '无图·办公用品', '29': '无图·其它',
}
// 物料类别（part_type）：标准件为外购选型件，非标件为按图加工件；未填写显示「未分类」。
export const partTypes: Record<string, string> = { standard: '标准件', custom: '非标件' }
export const partTypeLabel = (value: unknown) => partTypes[String(value)] || '未分类'
