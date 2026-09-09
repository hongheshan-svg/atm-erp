import { catalog } from '../catalog'
import { options } from '../catalog'
import { manager } from '../session'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { select } from './shared'
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
    C('size', '字节'),
    C('created_at', '上传时间'),
  ],
}
export function createLabel(resource: string) {
  return ({ documents: '上传附件' } as Record<string, string | boolean>)[resource] || ''
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  const c = await catalog(['projects'])
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'documents')
    fields = [
      select('project', '项目', options(c.projects)),
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
export function actionNames(resource: string, _r: Row): string[] {
  const a: string[] = []
  if (resource === 'documents') a.push('下载')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  let path = endpoint(resource) + r.id + '/'
  let fields: Field[] = [reason]
  let initial: Row = {}
  let method: 'post' | 'patch' = 'post'
  let readonly = false
  const routes: Record<string, string> = {}
  if (routes[name]) path += routes[name] + '/'

  return { title: name, path, fields, initial, method, readonly }
}
