import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import request from '@/utils/request'
import type {
  CollectionMilestone,
  CollectionMilestoneCreateInput,
  CollectionPlan,
  CollectionPlanCreateInput,
  CollectionPlanDetail,
  CollectionPlanListQuery,
  CollectionPlanUpdateInput,
  CollectionRecordCreateInput,
  PageResult
} from '@/types'

const BASE = '/finance/collection'

// ===== 原子 API =====

export function fetchPlans(query: CollectionPlanListQuery): Promise<PageResult<CollectionPlan>> {
  return request.get<PageResult<CollectionPlan>>(`${BASE}/plans`, { params: query })
}

export function fetchPlanDetail(id: number): Promise<CollectionPlanDetail> {
  return request.get<CollectionPlanDetail>(`${BASE}/plans/${id}`)
}

export function createPlan(input: CollectionPlanCreateInput): Promise<CollectionPlan> {
  return request.post<CollectionPlan>(`${BASE}/plans`, input)
}

export function updatePlan(id: number, input: CollectionPlanUpdateInput): Promise<CollectionPlan> {
  return request.put<CollectionPlan>(`${BASE}/plans/${id}`, input)
}

export function deletePlan(id: number): Promise<void> {
  return request.delete<void>(`${BASE}/plans/${id}`)
}

export function addMilestone(planId: number, input: CollectionMilestoneCreateInput): Promise<CollectionMilestone> {
  return request.post<CollectionMilestone>(`${BASE}/plans/${planId}/milestones`, input)
}

export function addRecord(milestoneId: number, input: CollectionRecordCreateInput): Promise<unknown> {
  return request.post<unknown>(`${BASE}/milestones/${milestoneId}/records`, input)
}

// ===== TanStack Query =====

export const collectionKeys = {
  all: ['collection-plans'] as const,
  list: (query: CollectionPlanListQuery) => ['collection-plans', 'list', query] as const
}

export function usePlansQuery(query: MaybeRefOrGetter<CollectionPlanListQuery>) {
  const queryKey = computed(() => collectionKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchPlans(toValue(query))
  })
}

export function useCreatePlanMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CollectionPlanCreateInput) => createPlan(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: collectionKeys.all })
    }
  })
}

export function useUpdatePlanMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; input: CollectionPlanUpdateInput }) => updatePlan(vars.id, vars.input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: collectionKeys.all })
    }
  })
}

export function useDeletePlanMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deletePlan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: collectionKeys.all })
    }
  })
}
