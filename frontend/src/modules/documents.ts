import { manager } from '../session'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { select } from './shared'
import { remote } from './shared'
import { choices } from './shared'
import { reason } from './shared'
import { finance } from './shared'
import { C } from './shared'
import { endpoint } from './shared'
import { categoryLabels } from './shared'
import { dateTimeText } from '../utils/datetime'
export const columns: Record<string, Column[]> = {
  documents: [
    C('original_name', '文件'),
    C('source', '来源'),
    C('category', '分类'),
    { key: 'size', label: '大小', format: row => fileSize(row.size) },
    { key: 'created_at', label: '上传时间', format: row => dateTimeText(row.created_at) },
  ],
}
export function fileSize(bytes: unknown) {
  const size = Number(bytes)
  if (bytes == null || bytes === '' || !Number.isFinite(size)) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}
export function createLabel(resource: string) {
  return ({ documents: '上传附件' } as Record<string, string | boolean>)[resource] || ''
}
// 与服务端 documents.upload 一致：已结项项目不能再上传；已取消项目只能补传结算凭证（退款、冲抵依据）。
const uploadableProject = (row: Row) => !['closed', 'cancelled'].includes(String(row.status))
const receiptProject = (row: Row) => row.status !== 'closed'
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'documents')
    fields = [
      remote('project', '项目', '/business/projects/', { remoteFilter: uploadableProject, remoteFilterFor: data => data.category === 'receipt' ? receiptProject : uploadableProject, hint: '已结项项目不能再上传；已取消项目只能上传结算凭证。' }),
      // 分类名称与列表、服务端取值同一份 categoryLabels；合同仅项目经理、结算凭证仅财务可上传。
      select(
        'category',
        '分类',
        choices(Object.fromEntries(Object.entries(categoryLabels).filter(([key]) => (key !== 'contract' || manager()) && (key !== 'receipt' || finance())))),
      ),
      { key: 'file', label: '文件', type: 'file' },
    ]
  return {
    title: String(createLabel(resource)),
    path,
    fields,
    initial: projectId ? { project: projectId } : {},
  }
}
export function actionNames(resource: string, r: Row): string[] {
  const a: string[] = []
  if (resource === 'documents') a.push('预览附件', '下载')
  if (resource === 'documents' && r.can_remove) a.push('删除附件')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (name === '删除附件')
    return {
      title: name,
      path: `${endpoint(resource)}${r.id}/remove/`,
      fields: [{ ...reason, label: '删除原因', hint: '用于传错文件、传错分类或传错项目。' }],
      notice: {
        type: 'warning',
        text: `将「${r.original_name}」移出附件列表。记录、文件本体和上传审计仍然保留；已作为收付款、对账或合同依据的附件不能删除。`,
      },
    }
  return { title: name, path: endpoint(resource) + r.id + '/', fields: [reason] }
}
