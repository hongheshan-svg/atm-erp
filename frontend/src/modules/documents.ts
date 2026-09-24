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
export const columns: Record<string, Column[]> = {
  documents: [
    C('original_name', '文件'),
    C('source', '来源'),
    C('category', '分类'),
    { key: 'size', label: '大小', format: row => fileSize(row.size) },
    C('created_at', '上传时间'),
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
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'documents')
    fields = [
      remote('project', '项目', '/business/projects/', { remoteFilter: row => row.status !== 'closed' }),
      select(
        'category',
        '分类',
        choices({
          drawing: '图纸',
          ...(manager() ? { contract: '合同' } : {}),
          ...(finance() ? { receipt: '收付款凭据' } : {}),
          delivery: '交付',
          other: '其他',
        }),
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
  if (resource === 'documents') a.push('下载')
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
