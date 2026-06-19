import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import request from '@/utils/request'
import type {
  Customer,
  CustomerCreateInput,
  CustomerListQuery,
  CustomerUpdateInput,
  Item,
  ItemCreateInput,
  ItemListQuery,
  ItemUpdateInput,
  PageResult,
  Supplier,
  SupplierCreateInput,
  SupplierListQuery,
  SupplierUpdateInput,
  Warehouse,
  WarehouseCreateInput,
  WarehouseListQuery,
  WarehouseUpdateInput
} from '@/types'

const ITEMS_BASE = '/masterdata/items'
const CUSTOMERS_BASE = '/masterdata/customers'
const SUPPLIERS_BASE = '/masterdata/suppliers'
const WAREHOUSES_BASE = '/masterdata/warehouses'

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

// ===========================================================================
// 客户 Customer
// ===========================================================================

export function fetchCustomers(query: CustomerListQuery): Promise<PageResult<Customer>> {
  return request.get<PageResult<Customer>>(CUSTOMERS_BASE, { params: query })
}

export function fetchCustomer(id: number): Promise<Customer> {
  return request.get<Customer>(`${CUSTOMERS_BASE}/${id}`)
}

export function createCustomer(input: CustomerCreateInput): Promise<Customer> {
  return request.post<Customer>(CUSTOMERS_BASE, input)
}

export function updateCustomer(id: number, input: CustomerUpdateInput): Promise<Customer> {
  return request.put<Customer>(`${CUSTOMERS_BASE}/${id}`, input)
}

export function deleteCustomer(id: number): Promise<void> {
  return request.delete<void>(`${CUSTOMERS_BASE}/${id}`)
}

export const customerKeys = {
  all: ['customers'] as const,
  list: (query: CustomerListQuery) => ['customers', 'list', query] as const
}

export function useCustomersQuery(query: MaybeRefOrGetter<CustomerListQuery>) {
  const queryKey = computed(() => customerKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchCustomers(toValue(query))
  })
}

export function useCreateCustomerMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CustomerCreateInput) => createCustomer(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: customerKeys.all })
    }
  })
}

export function useUpdateCustomerMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; input: CustomerUpdateInput }) => updateCustomer(vars.id, vars.input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: customerKeys.all })
    }
  })
}

export function useDeleteCustomerMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteCustomer(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: customerKeys.all })
    }
  })
}

// ===========================================================================
// 供应商 Supplier
// ===========================================================================

export function fetchSuppliers(query: SupplierListQuery): Promise<PageResult<Supplier>> {
  return request.get<PageResult<Supplier>>(SUPPLIERS_BASE, { params: query })
}

export function fetchSupplier(id: number): Promise<Supplier> {
  return request.get<Supplier>(`${SUPPLIERS_BASE}/${id}`)
}

export function createSupplier(input: SupplierCreateInput): Promise<Supplier> {
  return request.post<Supplier>(SUPPLIERS_BASE, input)
}

export function updateSupplier(id: number, input: SupplierUpdateInput): Promise<Supplier> {
  return request.put<Supplier>(`${SUPPLIERS_BASE}/${id}`, input)
}

export function deleteSupplier(id: number): Promise<void> {
  return request.delete<void>(`${SUPPLIERS_BASE}/${id}`)
}

export const supplierKeys = {
  all: ['suppliers'] as const,
  list: (query: SupplierListQuery) => ['suppliers', 'list', query] as const
}

export function useSuppliersQuery(query: MaybeRefOrGetter<SupplierListQuery>) {
  const queryKey = computed(() => supplierKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchSuppliers(toValue(query))
  })
}

export function useCreateSupplierMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: SupplierCreateInput) => createSupplier(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: supplierKeys.all })
    }
  })
}

export function useUpdateSupplierMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; input: SupplierUpdateInput }) => updateSupplier(vars.id, vars.input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: supplierKeys.all })
    }
  })
}

export function useDeleteSupplierMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteSupplier(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: supplierKeys.all })
    }
  })
}

// ===========================================================================
// 仓库 Warehouse
// ===========================================================================

export function fetchWarehouses(query: WarehouseListQuery): Promise<PageResult<Warehouse>> {
  return request.get<PageResult<Warehouse>>(WAREHOUSES_BASE, { params: query })
}

export function fetchWarehouse(id: number): Promise<Warehouse> {
  return request.get<Warehouse>(`${WAREHOUSES_BASE}/${id}`)
}

export function createWarehouse(input: WarehouseCreateInput): Promise<Warehouse> {
  return request.post<Warehouse>(WAREHOUSES_BASE, input)
}

export function updateWarehouse(id: number, input: WarehouseUpdateInput): Promise<Warehouse> {
  return request.put<Warehouse>(`${WAREHOUSES_BASE}/${id}`, input)
}

export function deleteWarehouse(id: number): Promise<void> {
  return request.delete<void>(`${WAREHOUSES_BASE}/${id}`)
}

export const warehouseKeys = {
  all: ['warehouses'] as const,
  list: (query: WarehouseListQuery) => ['warehouses', 'list', query] as const
}

export function useWarehousesQuery(query: MaybeRefOrGetter<WarehouseListQuery>) {
  const queryKey = computed(() => warehouseKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchWarehouses(toValue(query))
  })
}

export function useCreateWarehouseMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: WarehouseCreateInput) => createWarehouse(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: warehouseKeys.all })
    }
  })
}

export function useUpdateWarehouseMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; input: WarehouseUpdateInput }) => updateWarehouse(vars.id, vars.input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: warehouseKeys.all })
    }
  })
}

export function useDeleteWarehouseMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteWarehouse(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: warehouseKeys.all })
    }
  })
}
