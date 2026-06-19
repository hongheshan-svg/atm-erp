import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import request from '@/utils/request'
import type { PageResult, User, UserListQuery } from '@/types'

const USERS_BASE = '/accounts/users'

// ===== 原子 API(纯 HTTP 调用,只读)=====

export function fetchUsers(query: UserListQuery): Promise<PageResult<User>> {
  return request.get<PageResult<User>>(USERS_BASE, { params: query })
}

export function fetchUser(id: number): Promise<User> {
  return request.get<User>(`${USERS_BASE}/${id}`)
}

// ===== TanStack Query 封装 =====

export const userKeys = {
  all: ['users'] as const,
  list: (query: UserListQuery) => ['users', 'list', query] as const
}

// 用户列表查询(只读)。
export function useUsersQuery(query: MaybeRefOrGetter<UserListQuery>) {
  const queryKey = computed(() => userKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchUsers(toValue(query))
  })
}
