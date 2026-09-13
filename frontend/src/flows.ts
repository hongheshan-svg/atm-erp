// The single place that says which nodes each business flow has and where a record currently sits.
import { today } from './forms'
import type { Flow, FlowNode, Row } from './types'
const node = (key: string, label: string, hint?: string): FlowNode => ({ key, label, hint })
type Definition = {
  label: string
  nodes: FlowNode[]
  // Terminal states that leave the main chain, keyed by the value `locate` reports.
  aborted?: Record<string, FlowNode>
  // Returns the reached node key; an aborted key ends the flow off the chain.
  locate?: (row: Row) => string
}
const byStatus = (row: Row) => String(row.status ?? '')
const number = (value: unknown) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}
const settled = (value: unknown) => Math.abs(number(value)) < 0.005

function deliveryStage(row: Row) {
  if (!row.accepted_date) return 'shipped'
  if (!row.warranty_until) return 'accepted'
  return String(row.warranty_until) < today() ? 'expired' : 'warranty'
}

function entryStage(row: Row) {
  if (row.cancelled) return 'cancelled'
  if (settled(row.balance)) return 'settled'
  if (number(row.balance) < 0) return 'refund'
  return settled(row.paid_amount) && settled(row.credit_amount) ? 'pending' : 'partial'
}

function bankStage(row: Row) {
  if (row.void_reason) return 'void'
  if (row.needs_review) return 'registered'
  if (settled(row.remaining_amount)) return 'cleared'
  // A payment row carries a negative amount but a positive unmatched remainder.
  return Math.abs(number(row.remaining_amount)) === Math.abs(number(row.amount)) ? 'registered' : 'matching'
}

function paymentStage(row: Row) {
  if (row.reversal_of) return 'reversal'
  if (row.reversed_by) return 'reversed'
  return row.bank_matched ? 'matched' : 'recorded'
}

const definitions: Record<string, Definition> = {
  sales: {
    label: '销售流程',
    nodes: [
      node('draft', '需求中', '登记客户需求'),
      node('quoted', '已报价', '报价金额已确认'),
      node('signed', '已签约', '生成执行项目'),
    ],
    aborted: { cancelled: node('cancelled', '已取消', '销售终止，保留原记录') },
  },
  projects: {
    label: '项目流程',
    nodes: [
      node('draft', '需求中', '需求登记'),
      node('quoted', '已报价', '等待客户确认'),
      node('active', '执行中', '设计、采购与装配'),
      node('delivering', '交付中', '发货与现场安装'),
      node('warranty', '已验收', '进入质保期'),
      node('closed', '已结项', '成本与账款关闭'),
    ],
    aborted: { cancelled: node('cancelled', '已取消', '项目终止') },
  },
  purchases: {
    label: '采购流程',
    nodes: [
      node('draft', '草稿', '按缺料勾选生成'),
      node('submitted', '待批准', '等待采购审批'),
      node('approved', '待收货', '已下单给供应商'),
      node('partial', '部分收货', '部分批次已入库'),
      node('received', '已收货', '全部入库完成'),
    ],
    aborted: { cancelled: node('cancelled', '已取消', '采购终止') },
  },
  deliveries: {
    label: '交付流程',
    nodes: [
      node('shipped', '已发货', '设备出库发运'),
      node('accepted', '已验收', '客户签署验收'),
      node('warranty', '质保中', '质保期内响应售后'),
      node('expired', '质保期满', '质保责任结束'),
    ],
    locate: deliveryStage,
  },
  entries: {
    label: '收付款流程',
    nodes: [
      node('pending', '待结算', '尚未收付或抵减'),
      node('partial', '部分结算', '已部分收付或抵减'),
      node('settled', '已结清', '余额为零'),
    ],
    aborted: {
      cancelled: node('cancelled', '已取消', '原款项作废，保留流水'),
      refund: node('refund', '待退款', '超收超付，需退回差额'),
    },
    locate: entryStage,
  },
  reconciliations: {
    label: '对账流程',
    nodes: [
      node('draft', '待确认', '已按原业务生成快照'),
      node('confirmed', '已确认', '可据此登记收付款'),
    ],
    aborted: { void: node('void', '已作废', '对账终止，需重新生成') },
  },
  'bank-records': {
    label: '银行流水流程',
    nodes: [
      node('registered', '已登记', '按银行实际记录录入'),
      node('matching', '部分匹配', '已认领或部分匹配收付款'),
      node('cleared', '已核对', '金额全额匹配'),
    ],
    aborted: { void: node('void', '已作废', '登记有误已作废') },
    locate: bankStage,
  },
  payments: {
    label: '收付流水流程',
    nodes: [
      node('recorded', '已登记', '收付款已入账'),
      node('matched', '银行已核对', '与银行流水匹配'),
    ],
    aborted: {
      reversed: node('reversed', '已冲销', '原记录已被冲销'),
      reversal: node('reversal', '冲销记录', '用于纠正原记录'),
    },
    locate: paymentStage,
  },
  tasks: {
    label: '任务流程',
    nodes: [node('open', '待完成', '已派工给执行人'), node('done', '已完成', '执行人确认完成')],
    aborted: { cancelled: node('cancelled', '已取消', '任务撤销') },
  },
}

export function flowFor(resource: string, row: Row | null | undefined): Flow | null {
  const definition = definitions[resource]
  if (!definition || !row) return null
  const stage = (definition.locate || byStatus)(row)
  const aborted = definition.aborted?.[stage]
  if (aborted) return { label: definition.label, nodes: definition.nodes, current: -1, aborted }
  const current = definition.nodes.findIndex(item => item.key === stage)
  return current < 0 ? null : { label: definition.label, nodes: definition.nodes, current }
}
