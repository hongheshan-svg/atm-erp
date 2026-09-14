// How a list row presents its actions. No imports, so the e2e helpers can share this one registry
// instead of restating where an action lives.

// The row's headline button is only ever the next step that advances the document, so its meaning
// is the same on every row; read-only entries stay in the menu. First match wins.
export const primaryActions = ['批准采购', '收货', '提交采购', '登记收付款', '完成任务']

// Long menus (purchases has nine entries) are grouped by what an entry does. Classifying by shape
// rather than by a name registry lets a newly added action land somewhere sensible on its own.
export const actionGroups = [
  { key: 'advance', label: '推进单据' },
  { key: 'warranty', label: '质保' },
  { key: 'reference', label: '查看与资料' },
]
const referenceActions = new Set(['处理记录', '补充协议记录', '交付与回款', '附件', '补录凭证'])
export function actionGroup(name: string) {
  if (name.includes('质保')) return 'warranty'
  return /^(查看|下载|预览)/.test(name) || referenceActions.has(name) ? 'reference' : 'advance'
}
