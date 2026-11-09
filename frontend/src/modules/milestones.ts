import { read } from '../api'
import { catalog } from '../catalog'
import { date, person, select, t } from './shared'
import type { Catalog } from '../catalog'
import type { Command, Field, Row } from '../types'

export const disciplines = [{ value: 'mechanical', label: '机械' }, { value: 'electrical', label: '电气' }, { value: 'purchasing', label: '采购' }, { value: 'production', label: '生产' }, { value: 'delivery', label: '交付与验收' }]
export const disciplineField = (): Field => ({ key: 'discipline', label: '负责专业', type: 'select', optional: true, options: disciplines, hint: '选择后通知该专业主管；留空按阶段及里程碑自动归属，未设置主管时由项目经理负责。' })

export const taskAssignees = (row: Row): number[] => row.assignees ?? (row.assignee ? [row.assignee] : [])
export function taskElapsedLabel(row: Row): string {
  if (row.status === 'cancelled' || row.system_managed || row.kind === 'acceptance') return '—'
  if (row.elapsed_days != null) return `${row.elapsed_days} 天${row.status === 'open' ? '（进行中）' : ''}`
  if (!row.started_date) return row.status === 'done' ? '待补开始日期' : '未记录开始'
  return '待补完成日期'
}
export function taskVarianceLabel(row: Row): string {
  const days = row.schedule_variance_days
  if (days == null) return '—'
  if (row.status === 'open') return days > 0 ? `已逾期 ${days} 天` : '未逾期'
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
export async function milestoneTemplateCommand(projectId: number): Promise<Command> {
  const [metadata, scope, c] = await Promise.all([
    read('/business/tasks/milestone-template/', { project: projectId }),
    read('/business/projects/' + projectId + '/'),
    catalog(['users']),
  ])
  const nodes: Row[] = metadata.nodes.filter((node: Row) => !metadata.existing.includes(node.milestone))
  return {
    title: '生成六阶段里程碑', submitLabel: '确认生成里程碑',
    path: '/business/tasks/apply-milestones/', draftScope: String(projectId),
    notice: { type: 'info', text: '六阶段可交叉推进。默认20个节点，可移除不需要的行、添加自定义任务，再安排执行人和日期。已存在的节点会跳过；发货、现场安装接线、现场验收由实际业务同步。' },
    blocked: !metadata.can_generate ? '仅项目经理或管理员可为执行中、交付中的项目生成模板。' : undefined,
    fields: [{ key: 'lines', label: '项目里程碑', type: 'rows', compact: true, fields: milestoneFields(c, metadata, scope).map(field => ({ ...field, hint: '', ...(field.key === 'description' ? { type: 'text' as const, wide: false } : {}) })) }],
    initial: { lines: nodes.map(node => ({
      kind: node.kind, milestone: node.milestone, discipline: node.discipline, title: node.title, description: node.description,
      assignees: [metadata.assignee], due_date: '',
    })) },
    prepare: data => {
      if (!data.lines?.length) throw new Error('请至少保留一个节点，或添加自定义任务。')
      return { project: projectId, lines: data.lines }
    },
  }
}
