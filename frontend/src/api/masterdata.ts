/**
 * 主数据管理 API
 */
import request from '@/utils/request'

// ========== 物料管理 ==========
export function getItemList(params?: Record<string, any>) {
  return request({ url: '/masterdata/items/', method: 'get', params })
}
export function getItem(id: number) {
  return request({ url: `/masterdata/items/${id}/`, method: 'get' })
}
export function createItem(data: any) {
  return request({ url: '/masterdata/items/', method: 'post', data })
}
export function updateItem(id: number, data: any) {
  return request({ url: `/masterdata/items/${id}/`, method: 'put', data })
}
export function deleteItem(id: number) {
  return request({ url: `/masterdata/items/${id}/`, method: 'delete' })
}
export function generateItemCode(data: any) {
  return request({ url: '/masterdata/items/generate_code/', method: 'post', data })
}
export function importItems(data: any) {
  return request({ url: '/masterdata/items/import_excel/', method: 'post', data })
}
export function exportItems(params?: Record<string, any>) {
  return request({ url: '/masterdata/items/export_excel/', method: 'get', params, responseType: 'blob' })
}
export function exportItemTemplate() {
  return request({ url: '/masterdata/items/export_template/', method: 'get', responseType: 'blob' })
}
export function bulkDeleteItems(data: any) {
  return request({ url: '/masterdata/items/bulk_delete/', method: 'post', data })
}
export function getItemCategoryTree() {
  return request({ url: '/masterdata/categories/tree/', method: 'get' })
}

// ========== 客户管理 (re-export from customer.js for convenience) ==========
export { getCustomerList, getCustomer, createCustomer, updateCustomer, deleteCustomer } from './masterdata/customer'

// ========== 供应商管理 ==========
export function getSupplierList(params?: Record<string, any>) {
  return request({ url: '/masterdata/suppliers/', method: 'get', params })
}
export function getSupplier(id: number) {
  return request({ url: `/masterdata/suppliers/${id}/`, method: 'get' })
}
export function createSupplier(data: any) {
  return request({ url: '/masterdata/suppliers/', method: 'post', data })
}
export function updateSupplier(id: number, data: any) {
  return request({ url: `/masterdata/suppliers/${id}/`, method: 'put', data })
}
export function deleteSupplier(id: number) {
  return request({ url: `/masterdata/suppliers/${id}/`, method: 'delete' })
}
export function importSuppliers(data: any) {
  return request({ url: '/masterdata/suppliers/import_excel/', method: 'post', data })
}
export function exportSuppliers(params?: Record<string, any>) {
  return request({ url: '/masterdata/suppliers/export_excel/', method: 'get', params, responseType: 'blob' })
}
export function bulkDeleteSuppliers(data: any) {
  return request({ url: '/masterdata/suppliers/bulk_delete/', method: 'post', data })
}

// ========== 仓库管理 ==========
export function getWarehouseList(params?: Record<string, any>) {
  return request({ url: '/masterdata/warehouses/', method: 'get', params })
}
export function getWarehouse(id: number) {
  return request({ url: `/masterdata/warehouses/${id}/`, method: 'get' })
}
export function createWarehouse(data: any) {
  return request({ url: '/masterdata/warehouses/', method: 'post', data })
}
export function updateWarehouse(id: number, data: any) {
  return request({ url: `/masterdata/warehouses/${id}/`, method: 'put', data })
}
export function deleteWarehouse(id: number) {
  return request({ url: `/masterdata/warehouses/${id}/`, method: 'delete' })
}
export function getWarehouseLocations(id: number) {
  return request({ url: `/masterdata/warehouses/${id}/locations/`, method: 'get' })
}
export function getLocationTree(id: number) {
  return request({ url: `/masterdata/warehouses/${id}/location_tree/`, method: 'get' })
}

// ========== 库位管理 ==========
export function getLocationList(params?: Record<string, any>) {
  return request({ url: '/masterdata/locations/', method: 'get', params })
}
export function getLocation(id: number) {
  return request({ url: `/masterdata/locations/${id}/`, method: 'get' })
}
export function createLocation(data: any) {
  return request({ url: '/masterdata/locations/', method: 'post', data })
}
export function updateLocation(id: number, data: any) {
  return request({ url: `/masterdata/locations/${id}/`, method: 'put', data })
}
export function deleteLocation(id: number) {
  return request({ url: `/masterdata/locations/${id}/`, method: 'delete' })
}
export function getLocationTreeAll() {
  return request({ url: '/masterdata/locations/tree/', method: 'get' })
}

// ========== 客户跟进 ==========
export function getCustomerFollowUpList(params?: Record<string, any>) {
  return request({ url: '/masterdata/customer-followups/', method: 'get', params })
}
export function createCustomerFollowUp(data: any) {
  return request({ url: '/masterdata/customer-followups/', method: 'post', data })
}
export function updateCustomerFollowUp(id: number, data: any) {
  return request({ url: `/masterdata/customer-followups/${id}/`, method: 'put', data })
}
export function deleteCustomerFollowUp(id: number) {
  return request({ url: `/masterdata/customer-followups/${id}/`, method: 'delete' })
}
export function getFollowUpStatistics(params?: Record<string, any>) {
  return request({ url: '/masterdata/customer-followups/statistics/', method: 'get', params })
}
export function getFollowUpsByCustomer(params?: Record<string, any>) {
  return request({ url: '/masterdata/customer-followups/by_customer/', method: 'get', params })
}

// ========== 客户联系人 ==========
export function getCustomerContactList(params?: Record<string, any>) {
  return request({ url: '/masterdata/customer-contacts/', method: 'get', params })
}
export function createCustomerContact(data: any) {
  return request({ url: '/masterdata/customer-contacts/', method: 'post', data })
}
export function updateCustomerContact(id: number, data: any) {
  return request({ url: `/masterdata/customer-contacts/${id}/`, method: 'put', data })
}
export function deleteCustomerContact(id: number) {
  return request({ url: `/masterdata/customer-contacts/${id}/`, method: 'delete' })
}
export function setPrimaryContact(id: number) {
  return request({ url: `/masterdata/customer-contacts/${id}/set_primary/`, method: 'post' })
}

// ========== 客户信用 ==========
export function getCreditLevelList(params?: Record<string, any>) {
  return request({ url: '/masterdata/credit-levels/', method: 'get', params })
}
export function getCustomerCreditList(params?: Record<string, any>) {
  return request({ url: '/masterdata/customer-credits/', method: 'get', params })
}
export function getCustomerCredit(id: number) {
  return request({ url: `/masterdata/customer-credits/${id}/`, method: 'get' })
}
export function adjustCredit(id: number, data: any) {
  return request({ url: `/masterdata/customer-credits/${id}/adjust_credit/`, method: 'post', data })
}
export function changeCreditStatus(id: number, data: any) {
  return request({ url: `/masterdata/customer-credits/${id}/change_status/`, method: 'post', data })
}
export function getCreditWarningList(params?: Record<string, any>) {
  return request({ url: '/masterdata/customer-credits/warning_list/', method: 'get', params })
}
export function getCreditStatistics() {
  return request({ url: '/masterdata/customer-credits/statistics/', method: 'get' })
}

// ========== 补充函数 ==========
export function initCreditLevels() {
  return request({ url: '/masterdata/credit-levels/init_levels/', method: 'post' })
}
export function getFollowTypes() {
  return request({ url: '/masterdata/customer-followups/follow_types/', method: 'get' })
}
export function exportCustomers(params?: Record<string, any>) {
  return request({ url: '/masterdata/customers/export_excel/', method: 'get', params, responseType: 'blob' })
}
export function downloadCustomerTemplate() {
  return request({ url: '/masterdata/customers/download_template/', method: 'get', responseType: 'blob' })
}
export function downloadSupplierTemplate() {
  return request({ url: '/masterdata/suppliers/download_template/', method: 'get', responseType: 'blob' })
}
export function getLocationChildren(id: number) {
  return request({ url: `/masterdata/locations/${id}/children/`, method: 'get' })
}
export function patchLocation(id: number, data: any) {
  return request({ url: `/masterdata/locations/${id}/`, method: 'patch', data })
}

// ========== 客户列表 ==========