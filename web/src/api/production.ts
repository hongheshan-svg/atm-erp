import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import request from '@/utils/request'
import type {
  PageResult,
  WorkOrder,
  WorkOrderCreateInput,
  WorkOrderListQuery,
  WorkOrderUpdateInput
} from '@/types'

const WORK_ORDERS_BASE = '/production/work-orders'

// ===== 原子 API(纯 HTTP 调用,可独立复用)=====

export function fetchWorkOrders(query: WorkOrderListQuery): Promise<PageResult<WorkOrder>> {
  return request.get<PageResult<WorkOrder>>(WORK_ORDERS_BASE, { params: query })
}

export function fetchWorkOrder(id: number): Promise<WorkOrder> {
  return request.get<WorkOrder>(`${WORK_ORDERS_BASE}/${id}`)
}

export function createWorkOrder(input: WorkOrderCreateInput): Promise<WorkOrder> {
  return request.post<WorkOrder>(WORK_ORDERS_BASE, input)
}

export function updateWorkOrder(id: number, input: WorkOrderUpdateInput): Promise<WorkOrder> {
  return request.put<WorkOrder>(`${WORK_ORDERS_BASE}/${id}`, input)
}

export function deleteWorkOrder(id: number): Promise<void> {
  return request.delete<void>(`${WORK_ORDERS_BASE}/${id}`)
}

// ===== TanStack Query 封装 =====

export const workOrderKeys = {
  all: ['work-orders'] as const,
  list: (query: WorkOrderListQuery) => ['work-orders', 'list', query] as const
}

// 工单列表查询。
export function useWorkOrdersQuery(query: MaybeRefOrGetter<WorkOrderListQuery>) {
  const queryKey = computed(() => workOrderKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchWorkOrders(toValue(query))
  })
}

// 工单新建。
export function useCreateWorkOrderMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: WorkOrderCreateInput) => createWorkOrder(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workOrderKeys.all })
    }
  })
}

// 工单更新。
export function useUpdateWorkOrderMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; input: WorkOrderUpdateInput }) => updateWorkOrder(vars.id, vars.input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workOrderKeys.all })
    }
  })
}

// 工单删除。
export function useDeleteWorkOrderMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteWorkOrder(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workOrderKeys.all })
    }
  })
}
