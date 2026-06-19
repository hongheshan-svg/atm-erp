import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import request from '@/utils/request'
import type {
  PageResult,
  Receivable,
  ReceivableCreateInput,
  ReceivableListQuery,
  ReceivableUpdateInput
} from '@/types'

const RECEIVABLES_BASE = '/finance/receivables'

// ===== 原子 API(纯 HTTP 调用,可独立复用)=====

export function fetchReceivables(query: ReceivableListQuery): Promise<PageResult<Receivable>> {
  return request.get<PageResult<Receivable>>(RECEIVABLES_BASE, { params: query })
}

export function fetchReceivable(id: number): Promise<Receivable> {
  return request.get<Receivable>(`${RECEIVABLES_BASE}/${id}`)
}

export function createReceivable(input: ReceivableCreateInput): Promise<Receivable> {
  return request.post<Receivable>(RECEIVABLES_BASE, input)
}

export function updateReceivable(id: number, input: ReceivableUpdateInput): Promise<Receivable> {
  return request.put<Receivable>(`${RECEIVABLES_BASE}/${id}`, input)
}

export function deleteReceivable(id: number): Promise<void> {
  return request.delete<void>(`${RECEIVABLES_BASE}/${id}`)
}

// ===== TanStack Query 封装 =====

export const receivableKeys = {
  all: ['receivables'] as const,
  list: (query: ReceivableListQuery) => ['receivables', 'list', query] as const
}

// 应收账款列表查询。
export function useReceivablesQuery(query: MaybeRefOrGetter<ReceivableListQuery>) {
  const queryKey = computed(() => receivableKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchReceivables(toValue(query))
  })
}

// 应收账款新建。
export function useCreateReceivableMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ReceivableCreateInput) => createReceivable(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: receivableKeys.all })
    }
  })
}

// 应收账款更新。
export function useUpdateReceivableMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; input: ReceivableUpdateInput }) => updateReceivable(vars.id, vars.input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: receivableKeys.all })
    }
  })
}

// 应收账款删除。
export function useDeleteReceivableMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteReceivable(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: receivableKeys.all })
    }
  })
}
