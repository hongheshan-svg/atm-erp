/**
 * 主数据管理 API
 */
import request from '@/utils/request'

// ========== 物料管理 ==========
export function getItemList(params) {
  return request({ url: '/masterdata/items/', method: 'get', params })
}
export function getItem(id) {
  return request({ url: `/masterdata/items/${id}/`, method: 'get' })
}
export function createItem(data) {
  return request({ url: '/masterdata/items/', method: 'post', data })
}
export function updateItem(id, data) {
  return request({ url: `/masterdata/items/${id}/`, method: 'put', data })
}
export function deleteItem(id) {
  return request({ url: `/masterdata/items/${id}/`, method: 'delete' })
}
export function generateItemCode(data) {
  return request({ url: '/masterdata/items/generate_code/', method: 'post', data })
}
export function importItems(data) {
  return request({ url: '/masterdata/items/import_excel/', method: 'post', data })
}
export function exportItems(params) {
  return request({ url: '/masterdata/items/export_excel/', method: 'get', params, responseType: 'blob' })
}
export function exportItemTemplate() {
  return request({ url: '/masterdata/items/export_template/', method: 'get', responseType: 'blob' })
}
export function bulkDeleteItems(data) {
  return request({ url: '/masterdata/items/bulk_delete/', method: 'post', data })
}
export function getItemCategoryTree() {
  return request({ url: '/masterdata/categories/tree/', method: 'get' })
}

// ========== 客户管理 (re-export from customer.js for convenience) ==========
export { getCustomerList, getCustomer, createCustomer, updateCustomer, deleteCustomer } from './masterdata/customer'

// ========== 供应商管理 ==========
export function getSupplierList(params) {
  return request({ url: '/masterdata/suppliers/', method: 'get', params })
}
export function getSupplier(id) {
  return request({ url: `/masterdata/suppliers/${id}/`, method: 'get' })
}
export function createSupplier(data) {
  return request({ url: '/masterdata/suppliers/', method: 'post', data })
}
export function updateSupplier(id, data) {
  return request({ url: `/masterdata/suppliers/${id}/`, method: 'put', data })
}
export function deleteSupplier(id) {
  return request({ url: `/masterdata/suppliers/${id}/`, method: 'delete' })
}
export function importSuppliers(data) {
  return request({ url: '/masterdata/suppliers/import_excel/', method: 'post', data })
}
export function exportSuppliers(params) {
  return request({ url: '/masterdata/suppliers/export_excel/', method: 'get', params, responseType: 'blob' })
}
export function bulkDeleteSuppliers(data) {
  return request({ url: '/masterdata/suppliers/bulk_delete/', method: 'post', data })
}

// ========== 仓库管理 ==========
export function getWarehouseList(params) {
  return request({ url: '/masterdata/warehouses/', method: 'get', params })
}
export function getWarehouse(id) {
  return request({ url: `/masterdata/warehouses/${id}/`, method: 'get' })
}
export function createWarehouse(data) {
  return request({ url: '/masterdata/warehouses/', method: 'post', data })
}
export function updateWarehouse(id, data) {
  return request({ url: `/masterdata/warehouses/${id}/`, method: 'put', data })
}
export function deleteWarehouse(id) {
  return request({ url: `/masterdata/warehouses/${id}/`, method: 'delete' })
}
export function getWarehouseLocations(id) {
  return request({ url: `/masterdata/warehouses/${id}/locations/`, method: 'get' })
}
export function getLocationTree(id) {
  return request({ url: `/masterdata/warehouses/${id}/location_tree/`, method: 'get' })
}

// ========== 库位管理 ==========
export function getLocationList(params) {
  return request({ url: '/masterdata/locations/', method: 'get', params })
}
export function getLocation(id) {
  return request({ url: `/masterdata/locations/${id}/`, method: 'get' })
}
export function createLocation(data) {
  return request({ url: '/masterdata/locations/', method: 'post', data })
}
export function updateLocation(id, data) {
  return request({ url: `/masterdata/locations/${id}/`, method: 'put', data })
}
export function deleteLocation(id) {
  return request({ url: `/masterdata/locations/${id}/`, method: 'delete' })
}
export function getLocationTreeAll() {
  return request({ url: '/masterdata/locations/tree/', method: 'get' })
}

// ========== 客户跟进 ==========
export function getCustomerFollowUpList(params) {
  return request({ url: '/masterdata/customer-followups/', method: 'get', params })
}
export function createCustomerFollowUp(data) {
  return request({ url: '/masterdata/customer-followups/', method: 'post', data })
}
export function updateCustomerFollowUp(id, data) {
  return request({ url: `/masterdata/customer-followups/${id}/`, method: 'put', data })
}
export function deleteCustomerFollowUp(id) {
  return request({ url: `/masterdata/customer-followups/${id}/`, method: 'delete' })
}
export function getFollowUpStatistics(params) {
  return request({ url: '/masterdata/customer-followups/statistics/', method: 'get', params })
}
export function getFollowUpsByCustomer(params) {
  return request({ url: '/masterdata/customer-followups/by_customer/', method: 'get', params })
}

// ========== 客户联系人 ==========
export function getCustomerContactList(params) {
  return request({ url: '/masterdata/customer-contacts/', method: 'get', params })
}
export function createCustomerContact(data) {
  return request({ url: '/masterdata/customer-contacts/', method: 'post', data })
}
export function updateCustomerContact(id, data) {
  return request({ url: `/masterdata/customer-contacts/${id}/`, method: 'put', data })
}
export function deleteCustomerContact(id) {
  return request({ url: `/masterdata/customer-contacts/${id}/`, method: 'delete' })
}
export function setPrimaryContact(id) {
  return request({ url: `/masterdata/customer-contacts/${id}/set_primary/`, method: 'post' })
}

// ========== 客户信用 ==========
export function getCreditLevelList(params) {
  return request({ url: '/masterdata/credit-levels/', method: 'get', params })
}
export function getCustomerCreditList(params) {
  return request({ url: '/masterdata/customer-credits/', method: 'get', params })
}
export function getCustomerCredit(id) {
  return request({ url: `/masterdata/customer-credits/${id}/`, method: 'get' })
}
export function adjustCredit(id, data) {
  return request({ url: `/masterdata/customer-credits/${id}/adjust_credit/`, method: 'post', data })
}
export function changeCreditStatus(id, data) {
  return request({ url: `/masterdata/customer-credits/${id}/change_status/`, method: 'post', data })
}
export function getCreditWarningList(params) {
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
export function exportCustomers(params) {
  return request({ url: '/masterdata/customers/export_excel/', method: 'get', params, responseType: 'blob' })
}
export function downloadCustomerTemplate() {
  return request({ url: '/masterdata/customers/download_template/', method: 'get', responseType: 'blob' })
}
export function downloadSupplierTemplate() {
  return request({ url: '/masterdata/suppliers/download_template/', method: 'get', responseType: 'blob' })
}
export function getLocationChildren(id) {
  return request({ url: `/masterdata/locations/${id}/children/`, method: 'get' })
}
export function patchLocation(id, data) {
  return request({ url: `/masterdata/locations/${id}/`, method: 'patch', data })
}

// ========== 客户列表 ==========