import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import request from '@/utils/request'
import type {
  PageResult,
  Vehicle,
  VehicleCreateInput,
  VehicleListQuery,
  VehicleUpdateInput
} from '@/types'

const VEHICLES_BASE = '/oa/vehicles'

// ===== 原子 API(纯 HTTP 调用,可独立复用)=====

export function fetchVehicles(query: VehicleListQuery): Promise<PageResult<Vehicle>> {
  return request.get<PageResult<Vehicle>>(VEHICLES_BASE, { params: query })
}

export function fetchVehicle(id: number): Promise<Vehicle> {
  return request.get<Vehicle>(`${VEHICLES_BASE}/${id}`)
}

export function createVehicle(input: VehicleCreateInput): Promise<Vehicle> {
  return request.post<Vehicle>(VEHICLES_BASE, input)
}

export function updateVehicle(id: number, input: VehicleUpdateInput): Promise<Vehicle> {
  return request.put<Vehicle>(`${VEHICLES_BASE}/${id}`, input)
}

export function deleteVehicle(id: number): Promise<void> {
  return request.delete<void>(`${VEHICLES_BASE}/${id}`)
}

// ===== TanStack Query 封装 =====

export const vehicleKeys = {
  all: ['vehicles'] as const,
  list: (query: VehicleListQuery) => ['vehicles', 'list', query] as const
}

// 车辆列表查询。
export function useVehiclesQuery(query: MaybeRefOrGetter<VehicleListQuery>) {
  const queryKey = computed(() => vehicleKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchVehicles(toValue(query))
  })
}

// 车辆新建。
export function useCreateVehicleMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: VehicleCreateInput) => createVehicle(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: vehicleKeys.all })
    }
  })
}

// 车辆更新。
export function useUpdateVehicleMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; input: VehicleUpdateInput }) => updateVehicle(vars.id, vars.input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: vehicleKeys.all })
    }
  })
}

// 车辆删除。
export function useDeleteVehicleMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteVehicle(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: vehicleKeys.all })
    }
  })
}
