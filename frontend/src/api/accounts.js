/**
 * 账户管理 API
 */
import request from '@/utils/request'

// ========== 用户管理 ==========
export function getUserList(params) {
  return request({ url: '/auth/users/', method: 'get', params })
}
export function getUser(id) {
  return request({ url: `/auth/users/${id}/`, method: 'get' })
}
export function createUser(data) {
  return request({ url: '/auth/users/', method: 'post', data })
}
export function updateUser(id, data) {
  return request({ url: `/auth/users/${id}/`, method: 'put', data })
}
export function deleteUser(id) {
  return request({ url: `/auth/users/${id}/`, method: 'delete' })
}
export function getUserProfile() {
  return request({ url: '/auth/users/profile/', method: 'get' })
}
export function updateUserProfile(data) {
  return request({ url: '/auth/users/update_profile/', method: 'post', data })
}
export function changePassword(data) {
  return request({ url: '/auth/users/change_password/', method: 'post', data })
}
export function resetPassword(id) {
  return request({ url: `/auth/users/${id}/reset_password/`, method: 'post' })
}

// ========== 角色管理 ==========
export function getRoleList(params) {
  return request({ url: '/auth/roles/', method: 'get', params })
}
export function getRole(id) {
  return request({ url: `/auth/roles/${id}/`, method: 'get' })
}
export function createRole(data) {
  return request({ url: '/auth/roles/', method: 'post', data })
}
export function updateRole(id, data) {
  return request({ url: `/auth/roles/${id}/`, method: 'put', data })
}
export function deleteRole(id) {
  return request({ url: `/auth/roles/${id}/`, method: 'delete' })
}

// ========== 部门管理 ==========
export function getDepartmentList(params) {
  return request({ url: '/auth/departments/', method: 'get', params })
}
export function getDepartment(id) {
  return request({ url: `/auth/departments/${id}/`, method: 'get' })
}
export function createDepartment(data) {
  return request({ url: '/auth/departments/', method: 'post', data })
}
export function updateDepartment(id, data) {
  return request({ url: `/auth/departments/${id}/`, method: 'put', data })
}
export function deleteDepartment(id) {
  return request({ url: `/auth/departments/${id}/`, method: 'delete' })
}
export function getDepartmentTree() {
  return request({ url: '/auth/departments/tree/', method: 'get' })
}

// ========== 考勤管理 ==========
export function getAttendanceConfigList(params) {
  return request({ url: '/auth/attendance-configs/', method: 'get', params })
}
export function setDefaultAttendanceConfig(id) {
  return request({ url: `/auth/attendance-configs/${id}/set_default/`, method: 'post' })
}
export function getAttendanceRecordList(params) {
  return request({ url: '/auth/attendance-records/', method: 'get', params })
}
export function checkIn() {
  return request({ url: '/auth/attendance-records/check_in/', method: 'post' })
}
export function checkOut() {
  return request({ url: '/auth/attendance-records/check_out/', method: 'post' })
}
export function getMyAttendanceRecords(params) {
  return request({ url: '/auth/attendance-records/my_records/', method: 'get', params })
}
export function getTodayAttendance() {
  return request({ url: '/auth/attendance-records/today/', method: 'get' })
}
export function getMonthlySummary(params) {
  return request({ url: '/auth/attendance-records/monthly_summary/', method: 'get', params })
}

// ========== 考勤 (别名兼容) ==========
export function getAttendanceToday() {
  return request({ url: '/auth/attendance-records/today/', method: 'get' })
}
export function getAttendanceMonthlySummary(params) {
  return request({ url: '/auth/attendance-records/monthly_summary/', method: 'get', params })
}
export function attendanceCheckIn(data) {
  return request({ url: '/auth/attendance-records/check_in/', method: 'post', data })
}
export function attendanceCheckOut(data) {
  return request({ url: '/auth/attendance-records/check_out/', method: 'post', data })
}

// ========== 请假 ==========
export function getMyLeaveRequests(params) {
  return request({ url: '/auth/leave-requests/my_requests/', method: 'get', params })
}
export function getLeaveTypes() {
  return request({ url: '/auth/leave-requests/leave_types/', method: 'get' })
}
export function createLeaveRequest(data) {
  return request({ url: '/auth/leave-requests/', method: 'post', data })
}
export function submitLeaveRequest(id) {
  return request({ url: `/auth/leave-requests/${id}/submit/`, method: 'post' })
}
export function cancelLeaveRequest(id) {
  return request({ url: `/auth/leave-requests/${id}/cancel/`, method: 'post' })
}

// ========== 加班 ==========
export function getMyOvertimeRequests(params) {
  return request({ url: '/auth/overtime-requests/my_requests/', method: 'get', params })
}
export function createOvertimeRequest(data) {
  return request({ url: '/auth/overtime-requests/', method: 'post', data })
}
export function submitOvertimeRequest(id) {
  return request({ url: `/auth/overtime-requests/${id}/submit/`, method: 'post' })
}
