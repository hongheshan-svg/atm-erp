import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import request from '@/utils/request'
import type { Item, ItemCreateInput, ItemListQuery, ItemUpdateInput, PageResult } from '@/types'

const ITEMS_BASE = '/masterdata/items'

// ===== 原子 API(纯 HTTP 调用,可独立复用)=====

export function fetchItems(query: ItemListQuery): Promise<PageResult<Item>> {
  return request.get<PageResult<Item>>(ITEMS_BASE, { params: query })
}

export function fetchItem(id: number): Promise<Item> {
  return request.get<Item>(`${ITEMS_BASE}/${id}`)
}

export function createItem(input: ItemCreateInput): Promise<Item> {
  return request.post<Item>(ITEMS_BASE, input)
}

export function updateItem(id: number, input: ItemUpdateInput): Promise<Item> {
  return request.put<Item>(`${ITEMS_BASE}/${id}`, input)
}

export function deleteItem(id: number): Promise<void> {
  return request.delete<void>(`${ITEMS_BASE}/${id}`)
}

// ===== TanStack Query 封装 =====

export const itemKeys = {
  all: ['items'] as const,
  list: (query: ItemListQuery) => ['items', 'list', query] as const
}

// 物料列表查询。query 支持 ref/getter,变化时自动重新拉取。
export function useItemsQuery(query: MaybeRefOrGetter<ItemListQuery>) {
  const queryKey = computed(() => itemKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchItems(toValue(query))
  })
}

// 物料新建。成功后失效列表缓存。
export function useCreateItemMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ItemCreateInput) => createItem(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: itemKeys.all })
    }
  })
}

// 物料更新。成功后失效列表缓存。
export function useUpdateItemMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; input: ItemUpdateInput }) => updateItem(vars.id, vars.input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: itemKeys.all })
    }
  })
}

// 物料删除。成功后失效列表缓存。
export function useDeleteItemMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: itemKeys.all })
    }
  })
}
