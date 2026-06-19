import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import request from '@/utils/request'
import type {
  PageResult,
  Quotation,
  QuotationCreateInput,
  QuotationListQuery,
  QuotationUpdateInput
} from '@/types'

const QUOTATIONS_BASE = '/sales/quotations'

// ===== 原子 API(纯 HTTP 调用,可独立复用)=====

export function fetchQuotations(query: QuotationListQuery): Promise<PageResult<Quotation>> {
  return request.get<PageResult<Quotation>>(QUOTATIONS_BASE, { params: query })
}

export function fetchQuotation(id: number): Promise<Quotation> {
  return request.get<Quotation>(`${QUOTATIONS_BASE}/${id}`)
}

export function createQuotation(input: QuotationCreateInput): Promise<Quotation> {
  return request.post<Quotation>(QUOTATIONS_BASE, input)
}

export function updateQuotation(id: number, input: QuotationUpdateInput): Promise<Quotation> {
  return request.put<Quotation>(`${QUOTATIONS_BASE}/${id}`, input)
}

export function deleteQuotation(id: number): Promise<void> {
  return request.delete<void>(`${QUOTATIONS_BASE}/${id}`)
}

// ===== TanStack Query 封装 =====

export const quotationKeys = {
  all: ['quotations'] as const,
  list: (query: QuotationListQuery) => ['quotations', 'list', query] as const
}

// 报价列表查询。query 支持 ref/getter,变化时自动重新拉取。
export function useQuotationsQuery(query: MaybeRefOrGetter<QuotationListQuery>) {
  const queryKey = computed(() => quotationKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchQuotations(toValue(query))
  })
}

// 报价新建。成功后失效列表缓存。
export function useCreateQuotationMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: QuotationCreateInput) => createQuotation(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: quotationKeys.all })
    }
  })
}

// 报价更新。成功后失效列表缓存。
export function useUpdateQuotationMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; input: QuotationUpdateInput }) => updateQuotation(vars.id, vars.input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: quotationKeys.all })
    }
  })
}

// 报价删除。成功后失效列表缓存。
export function useDeleteQuotationMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteQuotation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: quotationKeys.all })
    }
  })
}
