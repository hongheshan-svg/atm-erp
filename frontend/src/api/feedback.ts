import { read, write } from './index'

export type FeedbackCategory = 'bug' | 'feature' | 'question'
export type FeedbackState = 'open' | 'completed' | 'not_planned'
export interface FeedbackItem {
  id: number
  category: FeedbackCategory
  title: string
  issue_number: number
  issue_url: string
  state: FeedbackState
  submitter: string
  mine: boolean
  created_at: string
}
export interface FeedbackList { enabled: boolean; issues_url: string; results: FeedbackItem[] }
export interface FeedbackDraft {
  category: FeedbackCategory
  title: string
  description: string
  steps: string
  page: string
  request_id: string
  client: string
}
export interface FeedbackSettings { configured: boolean; repository: string }

export const CATEGORY_LABELS: Record<FeedbackCategory, string> = { bug: '错误', feature: '功能建议', question: '使用问题' }
export const STATE_LABELS: Record<FeedbackState, string> = { open: '处理中', completed: '已解决', not_planned: '不处理' }

// 与后端同一规则：只留路径和定位用的 resource/section；搜索词、筛选条件可能含客户名称，不进公开 issue。
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
export function submitFeedback(draft: FeedbackDraft, key: string): Promise<FeedbackItem> {
  return write('/core/feedback/', { ...draft }, key)
}
export function getFeedbackSettings(): Promise<FeedbackSettings> {
  return read('/core/feedback/settings/')
}
export function saveFeedbackToken(token: string, key: string): Promise<FeedbackSettings> {
  return write('/core/feedback/settings/', { token }, key)
}
