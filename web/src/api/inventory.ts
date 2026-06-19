import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import request from '@/utils/request'
import type {
  PageResult,
  Stock,
  StockListQuery,
  StockMove,
  StockMoveCreateInput,
  StockMoveListQuery,
  StockMoveUpdateInput
} from '@/types'

const STOCKS_BASE = '/inventory/stocks'
const STOCK_MOVES_BASE = '/inventory/stock-moves'

// ===== Stock 原子 API(只读聚合视图)=====

export function fetchStocks(query: StockListQuery): Promise<PageResult<Stock>> {
  return request.get<PageResult<Stock>>(STOCKS_BASE, { params: query })
}

// ===== StockMove 原子 API =====

export function fetchStockMoves(query: StockMoveListQuery): Promise<PageResult<StockMove>> {
  return request.get<PageResult<StockMove>>(STOCK_MOVES_BASE, { params: query })
}

export function fetchStockMove(id: number): Promise<StockMove> {
  return request.get<StockMove>(`${STOCK_MOVES_BASE}/${id}`)
}

export function createStockMove(input: StockMoveCreateInput): Promise<StockMove> {
  return request.post<StockMove>(STOCK_MOVES_BASE, input)
}

export function updateStockMove(id: number, input: StockMoveUpdateInput): Promise<StockMove> {
  return request.put<StockMove>(`${STOCK_MOVES_BASE}/${id}`, input)
}

export function deleteStockMove(id: number): Promise<void> {
  return request.delete<void>(`${STOCK_MOVES_BASE}/${id}`)
}

// ===== TanStack Query 封装 =====

export const stockKeys = {
  all: ['stocks'] as const,
  list: (query: StockListQuery) => ['stocks', 'list', query] as const
}

export const stockMoveKeys = {
  all: ['stock-moves'] as const,
  list: (query: StockMoveListQuery) => ['stock-moves', 'list', query] as const
}

// 库存列表查询(只读)。
export function useStocksQuery(query: MaybeRefOrGetter<StockListQuery>) {
  const queryKey = computed(() => stockKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchStocks(toValue(query))
  })
}

// 库存移动列表查询。
export function useStockMovesQuery(query: MaybeRefOrGetter<StockMoveListQuery>) {
  const queryKey = computed(() => stockMoveKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchStockMoves(toValue(query))
  })
}

// 库存移动新建。
export function useCreateStockMoveMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: StockMoveCreateInput) => createStockMove(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: stockMoveKeys.all })
    }
  })
}

// 库存移动更新。
export function useUpdateStockMoveMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; input: StockMoveUpdateInput }) => updateStockMove(vars.id, vars.input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: stockMoveKeys.all })
    }
  })
}

// 库存移动删除。
export function useDeleteStockMoveMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteStockMove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: stockMoveKeys.all })
    }
  })
}
