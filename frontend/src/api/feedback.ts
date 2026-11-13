import { read, write } from './index'

export type FeedbackCategory = 'bug' | 'feature' | 'question'
export type FeedbackState = 'open' | 'completed' | 'not_planned'
export type FeedbackImpact = '' | 'blocked' | 'workaround' | 'minor'
export type FeedbackFrequency = '' | 'always' | 'sometimes' | 'once'
export interface FeedbackAttachment { name: string; url: string; image: boolean }
export interface FeedbackItem {
  id: number
  category: FeedbackCategory
  title: string
  issue_number: number
  issue_url: string
  state: FeedbackState
  attachments: FeedbackAttachment[]
  submitter: string
  mine: boolean
  created_at: string
}
export interface FeedbackLimits { files: number; file_mb: number; total_mb: number }
export interface FeedbackList {
  enabled: boolean
  limits: FeedbackLimits
  issues_url: string
  results: FeedbackItem[]
}
export interface FeedbackDraft {
  category: FeedbackCategory
  title: string
  description: string
  steps: string
  expected: string
  impact: FeedbackImpact
  frequency: FeedbackFrequency
  page: string
  request_id: string
  client: string
}
export interface FeedbackSettings { configured: boolean; repository: string }

export const CATEGORY_LABELS: Record<FeedbackCategory, string> = { bug: '错误', feature: '功能建议', question: '使用问题' }
export const STATE_LABELS: Record<FeedbackState, string> = { open: '处理中', completed: '已解决', not_planned: '不处理' }
export const IMPACT_LABELS: Record<Exclude<FeedbackImpact, ''>, string> = { blocked: '无法继续工作', workaround: '有替代办法', minor: '轻微不便' }
export const FREQUENCY_LABELS: Record<Exclude<FeedbackFrequency, ''>, string> = { always: '每次都出现', sometimes: '偶尔出现', once: '只出现过一次' }
export const DEFAULT_LIMITS: FeedbackLimits = { files: 6, file_mb: 10, total_mb: 20 }
// 与后端同一白名单；文件头由服务端核对。
export const IMAGE_TYPES = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
export const FILE_TYPES = [...IMAGE_TYPES, '.pdf', '.xlsx', '.xls', '.docx', '.csv', '.txt', '.log', '.json', '.mp4', '.mov']

export function extension(name: string): string {
  const match = /\.[^.]+$/.exec(name)
  return match ? match[0].toLowerCase() : ''
}

// 本地预检，提示与服务端一致；返回错误文字，通过时返回空字符串。
export function checkFiles(files: File[], limits: FeedbackLimits = DEFAULT_LIMITS): string {
  if (files.length > limits.files) return `一次最多上传 ${limits.files} 个附件。`
  const unsupported = files.find(file => !FILE_TYPES.includes(extension(file.name)))
  if (unsupported) return `「${unsupported.name}」的格式不支持。支持图片 png/jpg/gif/webp，文件 pdf/xlsx/xls/docx/csv/txt/log/json，录屏 mp4/mov。`
  const total = files.reduce((sum, file) => sum + file.size, 0)
  if (files.some(file => file.size > limits.file_mb * 1024 * 1024) || total > limits.total_mb * 1024 * 1024)
    return `单个附件不能超过 ${limits.file_mb} MB，合计不能超过 ${limits.total_mb} MB。`
  if (files.some(file => file.size === 0)) return '附件不能是空文件。'
  return ''
}

// 与后端同一规则：只留路径和定位用的 resource/section；搜索词、筛选条件可能含客户名称，不写进 issue。
export function feedbackPage(fullPath: string): string {
  const [path = '', query = ''] = (fullPath.split('#', 1)[0] ?? '').split('?', 2)
  if (!/^\/[A-Za-z0-9/_-]{0,100}$/.test(path) || path.startsWith('/feedback')) return ''
  const params = new URLSearchParams(query)
  const kept = new URLSearchParams()
  for (const key of ['resource', 'section']) {
    const value = params.get(key)
    if (value && /^[a-z0-9-]{1,40}$/.test(value)) kept.set(key, value)
  }
  const text = kept.toString()
  return text ? `${path}?${text}` : path
}

export function listFeedback(): Promise<FeedbackList> {
  return read('/core/feedback/')
}
// 有附件时走 multipart（上传类请求自动用较长超时），否则提交 JSON。
export function submitFeedback(draft: FeedbackDraft, files: File[], key: string): Promise<FeedbackItem> {
  if (!files.length) return write('/core/feedback/', { ...draft }, key)
  const form = new FormData()
  for (const [name, value] of Object.entries(draft)) form.append(name, value)
  for (const file of files) form.append('files', file, file.name)
  return write('/core/feedback/', form, key)
}
export function getFeedbackSettings(): Promise<FeedbackSettings> {
  return read('/core/feedback/settings/')
}
export function saveFeedbackToken(token: string, key: string): Promise<FeedbackSettings> {
  return write('/core/feedback/settings/', { token }, key)
}
