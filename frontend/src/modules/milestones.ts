import { read } from '../api'
import { catalog } from '../catalog'
import { today } from '../forms'
import { date, person, select, t } from './shared'
import type { Catalog } from '../catalog'
import type { Command, Field, Row } from '../types'

export const disciplines = [{ value: 'mechanical', label: '机械' }, { value: 'electrical', label: '电气' }, { value: 'purchasing', label: '采购' }, { value: 'production', label: '生产' }, { value: 'delivery', label: '交付与验收' }]
export const disciplineField = (): Field => ({ key: 'discipline', label: '负责专业', type: 'select', optional: true, options: disciplines, hint: '选择后通知该专业主管；留空按阶段及里程碑自动归属，未设置主管时由项目经理负责。' })

export const taskAssignees = (row: Row): number[] => row.assignees ?? (row.assignee ? [row.assignee] : [])
const dayNumber = (value: unknown) => {
  const [year, month, day] = String(value || '').slice(0, 10).split('-').map(Number)
  return year && month && day ? Date.UTC(year, month - 1, day) / 86400000 : null
}
// 距某日还有几天（负数为已过），按业务日历日计算；没有日期时返回 null。
export function daysUntil(value: unknown, from: string = today()): number | null {
  const target = dayNumber(value), start = dayNumber(from)
  return target == null || start == null ? null : Math.round(target - start)
}
export function addDays(value: string, days: number): string {
  return new Date((dayNumber(value)! + days) * 86400000).toISOString().slice(0, 10)
}
export function taskElapsedLabel(row: Row): string {
  if (row.status === 'cancelled' || row.system_managed || row.kind === 'acceptance') return '—'
  if (row.elapsed_days != null) return `${row.elapsed_days} 天${row.status === 'open' ? '（进行中）' : ''}`
  if (!row.started_date) return row.status === 'done' ? '待补开始日期' : '未记录开始'
  return '待补完成日期'
}
export function taskVarianceLabel(row: Row): string {
  const days = row.schedule_variance_days
  if (days == null) return '—'
  if (row.status === 'open') {
    if (days > 0) return `已逾期 ${days} 天`
    // 未逾期的待完成任务给出剩余天数，而不是每行重复「未逾期」。
    const left = daysUntil(row.due_date)
    return left == null ? '—' : left > 0 ? `剩 ${left} 天` : '今天到期'
  }
  return days > 0 ? `延期 ${days} 天` : days < 0 ? `提前 ${-days} 天` : '按期完成'
}
export function executorField(c: Catalog, scope?: Row | null): Field {
  return { ...person(c, 'assignees', '执行人', scope), type: 'multi', searchableMulti: true,
    hint: '可选择多人共同执行。由对应专业主管确认完成并按人员、工作日期登记工时；执行人可查看进度。' }
}
export function taskSyncHint(row: Row): string {
  if (row.kind === 'acceptance') return '按批次验收记录完成'
  if (!row.system_managed) return ''
  return ({ shipping_dispatch: '按实际发货记录同步', site_install: '按批次安装任务同步', site_acceptance: '按实际验收记录同步' } as Record<string, string>)[row.milestone] || '按实际业务记录同步'
}

export function milestoneFields(c: Catalog, metadata: Row, scope?: Row | null, canDesign = true): Field[] {
  const stages = metadata.stages.filter((stage: Row) => canDesign || ['assembly', 'test'].includes(stage.value))
  const nodes: Row[] = metadata.nodes
  return [
    select('kind', '阶段', stages),
    {
      key: 'milestone', label: '里程碑节点', type: 'select', optional: true,
      optionsFor: data => nodes.filter(node => node.kind === data.kind).map(node => ({
        value: node.milestone, label: node.title + (node.system_managed ? '（业务自动同步）' : ''),
      })),
      hint: '先选阶段，再选节点；留空可新增自定义任务。',
    },
    { ...t('title', '任务名称', true), hint: '选定节点后可留空，自动使用节点名称；自定义任务请填写名称。' },
    disciplineField(),
    executorField(c, scope),
    date('due_date', '计划完成日期', true),
    { ...t('description', '完成要求', true), hint: '写明图档版本、交付物或验收标准。发货、现场安装接线、现场验收按实际业务记录同步。' },
  ]
}
// 「按计划交期倒排」：从今天到项目计划交期，按各阶段常见工期占比累计排出每个阶段的完成日期。
const scheduleShare: Record<string, number> = { design: 0.25, purchase: 0.5, assembly: 0.7, test: 0.85, shipping: 0.92, site: 1 }
export function backSchedule(dueDate: string, stages: string[], from: string = today()): Row {
  const span = daysUntil(dueDate, from)
  if (span == null || span < 0) return {}
  return Object.fromEntries(stages.filter(stage => stage in scheduleShare).map(stage => [`stage_due_${stage}`, addDays(from, Math.round(span * scheduleShare[stage]!))]))
}
// 里程碑行在表格式明细里的列宽；「完成要求」不设宽度，占用剩余空间。
const rowWidths: Record<string, number> = { kind: 110, milestone: 130, title: 150, discipline: 100, assignees: 200, due_date: 150 }
export async function milestoneTemplateCommand(projectId: number): Promise<Command> {
  const [metadata, scope, c] = await Promise.all([
    read('/business/tasks/milestone-template/', { project: projectId }),
    read('/business/projects/' + projectId + '/'),
    catalog(['users']),
  ])
  const nodes: Row[] = metadata.nodes.filter((node: Row) => !metadata.existing.includes(node.milestone))
  const stages: Row[] = metadata.stages.filter((stage: Row) => nodes.some(node => node.kind === stage.value))
  const rowFields = milestoneFields(c, metadata, scope).map(field => ({
    ...field, hint: '', ...(rowWidths[field.key] ? { width: rowWidths[field.key] } : {}),
    ...(field.key === 'description' ? { type: 'text' as const, wide: false } : {}),
  }))
  const defaultAssignees = (row: Row) => (row.assignees || []).length === 1 && row.assignees[0] === metadata.assignee
  // 已有节点时这是「补充」：标题写明缺几个，避免看起来像重新生成整套模板。
  const supplement = metadata.existing.length > 0
  const dueDate = String(scope.due_date || '')
  const command: Command = {
    title: supplement ? `补充里程碑节点（缺 ${nodes.length} 个）` : '生成六阶段里程碑',
    submitLabel: supplement ? '确认补充节点' : '确认生成里程碑',
    path: '/business/tasks/apply-milestones/', draftScope: String(projectId),
    notice: { type: 'info', text: '可移除不需要的行或添加自定义任务；行内日期留空时用所属阶段日期。发货、现场安装接线、现场验收按实际业务同步。' },
    blocked: !metadata.can_generate
      ? '仅项目经理或管理员可为执行中、交付中的项目生成模板。'
      : !nodes.length ? '六阶段节点已全部生成，新增其他任务请用「新建任务」。' : undefined,
    fields: [
      // 批量工具：二十个节点不必逐行填日期和执行人；行内已单独填写的值优先。
      ...stages.map((stage: Row): Field => ({ key: `stage_due_${stage.value}`, label: `${stage.label}计划完成`, type: 'date', optional: true })),
      { ...executorField(c, scope), key: 'batch_assignees', label: '统一执行人', optional: true, hint: '只替换仍为默认执行人（项目经理）的行。' },
      { key: 'lines', label: '项目里程碑', type: 'rows', dense: true, fields: rowFields },
    ],
    initial: { lines: nodes.map(node => ({
      kind: node.kind, milestone: node.milestone, discipline: node.discipline, title: node.title, description: node.description,
      assignees: [metadata.assignee], due_date: '',
    })) },
    prepare: data => {
      if (!data.lines?.length) throw new Error('请至少保留一个节点，或添加自定义任务。')
      return {
        project: projectId,
        lines: data.lines.map((row: Row) => ({
          ...row,
          due_date: row.due_date || data[`stage_due_${row.kind}`] || '',
          assignees: data.batch_assignees?.length && defaultAssignees(row) ? data.batch_assignees : row.assignees,
        })),
      }
    },
  }
  // 交期在今天之后才能倒排；排出的日期只是初值，仍可逐项修改。
  const left = daysUntil(dueDate)
  if (nodes.length && stages.length && left != null && left > 0) {
    command.alternatives = [{
      label: '按计划交期倒排',
      open: async () => ({
        ...command,
        initial: { ...command.initial, ...backSchedule(dueDate, stages.map(stage => String(stage.value))) },
        notice: { type: 'info', text: `已按计划交期 ${dueDate} 倒排各阶段完成日期（设计约占 25%、采购 25%、组装 20%、调试 15%、发货 7%、现场 8%），可逐项修改。` },
      }),
    }]
  }
  return command
}
