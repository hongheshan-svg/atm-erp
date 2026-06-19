import { useQuery } from '@tanstack/vue-query'
import request from '@/utils/request'
import type { AppNotification, PageResult } from '@/types'

const NOTIFY_BASE = '/notifications'

// ===== 原子 API =====

export function fetchNotifications(onlyUnread = false): Promise<PageResult<AppNotification>> {
  return request.get<PageResult<AppNotification>>(NOTIFY_BASE, {
    params: { unread: onlyUnread ? 'true' : undefined, page_size: 20 }
  })
}

export function fetchUnreadCount(): Promise<{ unread: number }> {
  return request.get<{ unread: number }>(`${NOTIFY_BASE}/unread_count`)
}

export function markNotificationRead(id: number): Promise<void> {
  return request.post<void>(`${NOTIFY_BASE}/${id}/read`)
}

export function markAllNotificationsRead(): Promise<void> {
  return request.post<void>(`${NOTIFY_BASE}/read_all`)
}

// ===== TanStack Query 封装 =====

export const notifyKeys = {
  unread: ['notify', 'unread'] as const,
  list: ['notify', 'list'] as const
}

// 未读角标:30s 轮询(无 WebSocket 实时推送时的兜底)。
export function useUnreadCountQuery() {
  return useQuery({
    queryKey: notifyKeys.unread,
    queryFn: fetchUnreadCount,
    refetchInterval: 30_000
  })
}

export function useNotificationsQuery() {
  return useQuery({
    queryKey: notifyKeys.list,
    queryFn: () => fetchNotifications(false)
  })
}
