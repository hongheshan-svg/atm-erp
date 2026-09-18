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
  // 取消、作废、撤销、删除都是往回走的纠错动作，和「下一步做什么」混在一起最容易点错。
  { key: 'correct', label: '更正与撤销' },
  { key: 'reference', label: '查看与资料' },
]
const referenceActions = new Set(['处理记录', '补充协议记录', '交付与回款', '附件', '补录凭证'])
const correctionActions = /^(取消|作废|撤销|删除|冲销|退回修改|更正|重开)/
export function actionGroup(name: string) {
  if (name.includes('质保')) return 'warranty'
  if (/^(查看|下载|预览)/.test(name) || referenceActions.has(name)) return 'reference'
  return correctionActions.test(name) ? 'correct' : 'advance'
}
