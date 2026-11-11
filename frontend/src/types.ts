import type { RouteLocationRaw } from 'vue-router'
export type Row = Record<string, any>
export type Option = { value: string | number; label: string }
export type Field = {
  key: string
  label: string
  type?: 'text' | 'password' | 'date' | 'select' | 'multi' | 'checks' | 'boolean' | 'rows' | 'file' | 'textarea'
  options?: Option[]
  searchableMulti?: boolean
  // 单选下拉可输入搜索（人员较多时用）；选填字段可清空。
  searchable?: boolean
  // 依赖同一表单其他字段的选项（如按所选项目过滤任务）；选中值不在新选项内时自动清空。
  optionsFor?: (data: Row) => Option[]
  // 文本输入的候选值（datalist），仍允许输入新值。
  suggestions?: string[]
  fields?: Field[]
  optional?: boolean
  initial?: any
  readonly?: boolean
  compact?: boolean
  // 明细行按表格排布：宽屏一行一条，仅首行显示列名；窄屏退回 compact 栅格。
  dense?: boolean
  // dense 明细行里该字段的列宽：数字按 px，字符串原样作为 CSS 宽度；不设则均分剩余宽度。
  width?: number | string
  warehouse?: 'receipt' | 'issue'
  hidden?: boolean
  // 条件不满足时不展示、不校验、不提交；保留表单内输入以便切换回来。
  visibleWhen?: (data: Row) => boolean
  hint?: string
  placeholder?: string
  wide?: boolean
  numeric?: { scale: number; signed?: boolean; min?: number; max?: number }
  displayOnly?: boolean
  randomPassword?: boolean
  remotePath?: string
  remoteParams?: Row
  remoteFilter?: (row: Row) => boolean
  // 远程选项的标签；不给就用 catalog 的通用「编码 · 名称 · 规格」拼法。
  remoteLabel?: (row: Row) => string
  // Renders the row's position in this flow instead of a plain value (read-only row tables).
  flow?: string
  upload?: { context: Row; category: string }
}
export type Command = {
  title: string
  submitLabel?: string
  blocked?: string
  links?: { label: string; path: string }[]
  alternatives?: { label: string; open: () => Promise<Command> }[]
  draftScope?: string
  subject?: string
  path: string
  method?: 'post' | 'patch'
  fields: Field[]
  initial?: Row
  readonly?: boolean
  notice?: { type: 'warning' | 'info'; text: string }
  prepare?: (data: Row) => Row
  actions?: { label: string; run: () => void | Promise<void> }[]
  previewPath?: string
  flow?: Flow | null
  progressProject?: number
}
export type Column = {
  key: string
  label: string
  format?: (row: Row) => string
  tip?: (row: Row) => string | undefined
  // 单元格链接到关联单据（项目、采购单等）；返回 undefined 时按普通文本显示。
  link?: (row: Row) => RouteLocationRaw | undefined
  // 值下方的一行小字（如「3 项逾期」「剩 20 天」）；risk 时用风险色。
  flag?: (row: Row) => { text: string; risk?: boolean } | undefined
}
export type FlowNode = { key: string; label: string; hint?: string }
export type Flow = {
  label: string
  nodes: FlowNode[]
  // Index of the node the record currently sits on; -1 when the flow ended off the main chain.
  current: number
  aborted?: FlowNode
}
