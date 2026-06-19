import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import request from '@/utils/request'
import type {
  PageResult,
  PurchaseOrder,
  PurchaseOrderCreateInput,
  PurchaseOrderListQuery,
  PurchaseOrderUpdateInput
} from '@/types'

const ORDERS_BASE = '/purchase/orders'

// ===== 原子 API(纯 HTTP 调用,可独立复用)=====

export function fetchPurchaseOrders(query: PurchaseOrderListQuery): Promise<PageResult<PurchaseOrder>> {
  return request.get<PageResult<PurchaseOrder>>(ORDERS_BASE, { params: query })
}

export function fetchPurchaseOrder(id: number): Promise<PurchaseOrder> {
  return request.get<PurchaseOrder>(`${ORDERS_BASE}/${id}`)
}

export function createPurchaseOrder(input: PurchaseOrderCreateInput): Promise<PurchaseOrder> {
  return request.post<PurchaseOrder>(ORDERS_BASE, input)
}

export function updatePurchaseOrder(id: number, input: PurchaseOrderUpdateInput): Promise<PurchaseOrder> {
  return request.put<PurchaseOrder>(`${ORDERS_BASE}/${id}`, input)
}

export function deletePurchaseOrder(id: number): Promise<void> {
  return request.delete<void>(`${ORDERS_BASE}/${id}`)
}

// ===== TanStack Query 封装 =====

export const purchaseOrderKeys = {
  all: ['purchase-orders'] as const,
  list: (query: PurchaseOrderListQuery) => ['purchase-orders', 'list', query] as const
}

// 采购订单列表查询。
export function usePurchaseOrdersQuery(query: MaybeRefOrGetter<PurchaseOrderListQuery>) {
  const queryKey = computed(() => purchaseOrderKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchPurchaseOrders(toValue(query))
  })
}

// 采购订单新建。
export function useCreatePurchaseOrderMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: PurchaseOrderCreateInput) => createPurchaseOrder(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: purchaseOrderKeys.all })
    }
  })
}

// 采购订单更新。
export function useUpdatePurchaseOrderMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; input: PurchaseOrderUpdateInput }) => updatePurchaseOrder(vars.id, vars.input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: purchaseOrderKeys.all })
    }
  })
}

// 采购订单删除。
export function useDeletePurchaseOrderMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deletePurchaseOrder(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: purchaseOrderKeys.all })
    }
  })
}
