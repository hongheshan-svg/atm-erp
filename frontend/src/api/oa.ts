import request from '@/utils/request'

// ========== 考勤记录 ==========
export function getAttendanceRecords(params?: Record<string, any>) {
  return request({ url: '/oa/attendance-records/', method: 'get', params })
}
export function getAttendanceRecord(id: number) {
  return request({ url: `/oa/attendance-records/${id}/`, method: 'get' })
}
export function getTodayAttendance() {
  return request({ url: '/auth/attendance-records/today/', method: 'get' })
}
export function getAttendanceToday() {
  return request({ url: '/oa/attendance-records/today/', method: 'get' })
}
export function getAttendanceMonthlySummary(params?: Record<string, any>) {
  return request({ url: '/oa/attendance-records/monthly_summary/', method: 'get', params })
}
export function checkIn(data: any) {
  return request({ url: '/oa/attendance-records/check_in/', method: 'post', data })
}
export function checkOut(data: any) {
  return request({ url: '/oa/attendance-records/check_out/', method: 'post', data })
}
export function batchImportAttendance(data: any) {
  return request({ url: '/oa/attendance-records/batch_import/', method: 'post', data })
}
export function recalculateMonthAttendance(data: any) {
  return request({ url: '/oa/attendance-records/recalculate_month/', method: 'post', data })
}
export function exportAttendanceReport(params?: Record<string, any>, config = {}) {
  return request({ url: '/oa/attendance-records/export_report/', method: 'get', params, ...config })
}
export function getAttendanceMonthStats(params?: Record<string, any>) {
  return request({ url: '/oa/attendance-records/month_stats/', method: 'get', params })
}
export function getAttendanceImportHistory() {
  return request({ url: '/oa/attendance-records/import_history/', method: 'get' })
}

// ========== 请假 ==========
export function getLeaveRequests(params?: Record<string, any>) {
  return request({ url: '/oa/leave-requests/', method: 'get', params })
}
export function getLeaveRequest(id: number) {
  return request({ url: `/oa/leave-requests/${id}/`, method: 'get' })
}
export function createLeaveRequest(data: any) {
  return request({ url: '/oa/leave-requests/', method: 'post', data })
}
export function updateLeaveRequest(id: number, data: any) {
  return request({ url: `/oa/leave-requests/${id}/`, method: 'put', data })
}
export function getLeaveTypes() {
  return request({ url: '/oa/leave-requests/leave_types/', method: 'get' })
}
export function submitLeaveRequest(id: number) {
  return request({ url: `/oa/leave-requests/${id}/submit/`, method: 'post' })
}
export function deleteLeaveRequest(id: number) {
  return request({ url: `/oa/leave-requests/${id}/`, method: 'delete' })
}

// ========== 加班 ==========
export function getOvertimeRequests(params?: Record<string, any>) {
  return request({ url: '/oa/overtime-requests/', method: 'get', params })
}
export function createOvertimeRequest(data: any) {
  return request({ url: '/oa/overtime-requests/', method: 'post', data })
}
export function submitOvertimeRequest(id: number) {
  return request({ url: `/oa/overtime-requests/${id}/submit/`, method: 'post' })
}
export function deleteOvertimeRequest(id: number) {
  return request({ url: `/oa/overtime-requests/${id}/`, method: 'delete' })
}

// ========== 车辆管理 ==========
export function getVehicles(params?: Record<string, any>) {
  return request({ url: '/oa/vehicles/', method: 'get', params })
}
export function getVehicle(id: number) {
  return request({ url: `/oa/vehicles/${id}/`, method: 'get' })
}
export function createVehicle(data: any) {
  return request({ url: '/oa/vehicles/', method: 'post', data })
}
export function updateVehicle(id: number, data: any) {
  return request({ url: `/oa/vehicles/${id}/`, method: 'put', data })
}
export function deleteVehicle(id: number) {
  return request({ url: `/oa/vehicles/${id}/`, method: 'delete' })
}
export function getVehicleMaintenanceRecords(id: number) {
  return request({ url: `/oa/vehicles/${id}/maintenance-records/`, method: 'get' })
}
export function getAvailableVehicles() {
  return request({ url: '/oa/vehicles/available/', method: 'get' })
}

// ========== 用车申请 ==========
export function getVehicleRequests(params?: Record<string, any>) {
  return request({ url: '/oa/vehicle-requests/', method: 'get', params })
}
export function createVehicleRequest(data: any) {
  return request({ url: '/oa/vehicle-requests/', method: 'post', data })
}
export function updateVehicleRequest(id: number, data: any) {
  return request({ url: `/oa/vehicle-requests/${id}/`, method: 'put', data })
}
export function getVehicleRequest(id: number) {
  return request({ url: `/oa/vehicle-requests/${id}/`, method: 'get' })
}
export function submitVehicleRequest(id: number) {
  return request({ url: `/oa/vehicle-requests/${id}/submit/`, method: 'post' })
}
export function pickupVehicle(id: number) {
  return request({ url: `/oa/vehicle-requests/${id}/pickup/`, method: 'post' })
}
export function returnVehicle(id: number, data: any) {
  return request({ url: `/oa/vehicle-requests/${id}/return_vehicle/`, method: 'post', data })
}
export function deleteVehicleRequest(id: number) {
  return request({ url: `/oa/vehicle-requests/${id}/`, method: 'delete' })
}

// ========== 档案管理 ==========
export function getArchiveCategories(params?: Record<string, any>) {
  return request({ url: '/oa/archive-categories/', method: 'get', params })
}
export function getArchives(params?: Record<string, any>) {
  return request({ url: '/oa/archives/', method: 'get', params })
}
export function getArchive(id: number) {
  return request({ url: `/oa/archives/${id}/`, method: 'get' })
}
export function createArchive(data: any) {
  return request({ url: '/oa/archives/', method: 'post', data })
}
export function updateArchive(id: number, data: any) {
  return request({ url: `/oa/archives/${id}/`, method: 'put', data })
}
export function deleteArchive(id: number) {
  return request({ url: `/oa/archives/${id}/`, method: 'delete' })
}

// ========== 档案借阅 ==========
export function getArchiveBorrows(params?: Record<string, any>) {
  return request({ url: '/oa/archive-borrows/', method: 'get', params })
}
export function createArchiveBorrow(data: any) {
  return request({ url: '/oa/archive-borrows/', method: 'post', data })
}

// ========== 资产管理 ==========
export function getAssetCategories(params?: Record<string, any>) {
  return request({ url: '/oa/asset-categories/', method: 'get', params })
}
export function getAssets(params?: Record<string, any>) {
  return request({ url: '/oa/assets/', method: 'get', params })
}
export function getAsset(id: number) {
  return request({ url: `/oa/assets/${id}/`, method: 'get' })
}
export function createAsset(data: any) {
  return request({ url: '/oa/assets/', method: 'post', data })
}
export function updateAsset(id: number, data: any) {
  return request({ url: `/oa/assets/${id}/`, method: 'put', data })
}
export function deleteAsset(id: number) {
  return request({ url: `/oa/assets/${id}/`, method: 'delete' })
}
export function getAssetStatistics() {
  return request({ url: '/oa/assets/statistics/', method: 'get' })
}
export function assignAsset(id: number, data: any) {
  return request({ url: `/oa/assets/${id}/assign/`, method: 'post', data })
}
export function reclaimAsset(id: number) {
  return request({ url: `/oa/assets/${id}/reclaim/`, method: 'post' })
}

// ========== 资产借用 ==========
export function getAssetBorrows(params?: Record<string, any>) {
  return request({ url: '/oa/asset-borrows/', method: 'get', params })
}
export function getAssetBorrow(id: number) {
  return request({ url: `/oa/asset-borrows/${id}/`, method: 'get' })
}
export function createAssetBorrow(data: any) {
  return request({ url: '/oa/asset-borrows/', method: 'post', data })
}
export function submitAssetBorrow(id: number) {
  return request({ url: `/oa/asset-borrows/${id}/submit/`, method: 'post' })
}
export function approveAssetBorrow(id: number, data?: any) {
  return request({ url: `/oa/asset-borrows/${id}/approve/`, method: 'post', data })
}
export function rejectAssetBorrow(id: number, data?: any) {
  return request({ url: `/oa/asset-borrows/${id}/reject/`, method: 'post', data })
}
export function borrowAsset(id: number) {
  return request({ url: `/oa/asset-borrows/${id}/borrow/`, method: 'post' })
}
export function returnAssetBorrow(id: number, data?: any) {
  return request({ url: `/oa/asset-borrows/${id}/return_asset/`, method: 'post', data })
}
export function deleteAssetBorrow(id: number) {
  return request({ url: `/oa/asset-borrows/${id}/`, method: 'delete' })
}

// ========== 会议管理 ==========
export function getMeetings(params?: Record<string, any>) {
  return request({ url: '/oa/meetings/', method: 'get', params })
}
export function getMeeting(id: number) {
  return request({ url: `/oa/meetings/${id}/`, method: 'get' })
}
export function createMeeting(data: any) {
  return request({ url: '/oa/meetings/', method: 'post', data })
}

// ========== 公告 ==========
export function getAnnouncements(params?: Record<string, any>) {
  return request({ url: '/oa/announcements/', method: 'get', params })
}
export function getAnnouncement(id: number) {
  return request({ url: `/oa/announcements/${id}/`, method: 'get' })
}
export function createAnnouncement(data: any) {
  return request({ url: '/oa/announcements/', method: 'post', data })
}
export function getPublishedAnnouncements(params?: Record<string, any>) {
  return request({ url: '/oa/announcements/published/', method: 'get', params })
}
export function updateAnnouncement(id: number, data: any) {
  return request({ url: `/oa/announcements/${id}/`, method: 'put', data })
}
export function publishAnnouncement(id: number) {
  return request({ url: `/oa/announcements/${id}/publish/`, method: 'post' })
}
export function readAnnouncement(id: number) {
  return request({ url: `/oa/announcements/${id}/read/`, method: 'post' })
}
export function markAllAnnouncementsRead() {
  return request({ url: '/oa/announcements/mark_all_read/', method: 'post' })
}

// ========== 日程 ==========
export function getSchedules(params?: Record<string, any>) {
  return request({ url: '/oa/schedules/', method: 'get', params })
}
export function createSchedule(data: any) {
  return request({ url: '/oa/schedules/', method: 'post', data })
}
export function updateSchedule(id: number, data: any) {
  return request({ url: `/oa/schedules/${id}/`, method: 'put', data })
}

// ========== 考勤设备 ==========
export function getAttendanceDevices(params?: Record<string, any>) {
  return request({ url: '/oa/attendance-devices/', method: 'get', params })
}
export function syncAttendanceDevice(id: number) {
  return request({ url: `/oa/attendance-devices/${id}/sync/`, method: 'post' })
}

// ========== 会议管理 (core) ==========
export function getCoreMeetings(params?: Record<string, any>) {
  return request({ url: '/core/meetings/', method: 'get', params })
}
export function getCoreMeeting(id: number) {
  return request({ url: `/core/meetings/${id}/`, method: 'get' })
}
export function getTodayMeetings() {
  return request({ url: '/core/meetings/today/', method: 'get' })
}
export function getMeetingRooms() {
  return request({ url: '/core/meeting-rooms/', method: 'get' })
}
export function getMeetingRoomAvailability(roomId: number, date: string) {
  return request({ url: `/core/meeting-rooms/${roomId}/availability/`, method: 'get', params: { date } })
}
export function startMeeting(id: number) {
  return request({ url: `/core/meetings/${id}/start/`, method: 'post' })
}
export function completeMeeting(id: number, data: any) {
  return request({ url: `/core/meetings/${id}/complete/`, method: 'post', data })
}
export function cancelMeeting(id: number) {
  return request({ url: `/core/meetings/${id}/cancel/`, method: 'post' })
}
export function updateCoreMeeting(id: number, data: any) {
  return request({ url: `/core/meetings/${id}/`, method: 'patch', data })
}
export function createCoreMeeting(data: any) {
  return request({ url: '/core/meetings/', method: 'post', data })
}

// ========== 日程管理 (core) ==========
export function getCalendarSchedules(params?: Record<string, any>) {
  return request({ url: '/core/schedules/calendar/', method: 'get', params })
}
export function getTodaySchedules() {
  return request({ url: '/core/schedules/today/', method: 'get' })
}
export function getUpcomingSchedules() {
  return request({ url: '/core/schedules/upcoming/', method: 'get' })
}
export function getCoreSchedule(id: number) {
  return request({ url: `/core/schedules/${id}/`, method: 'get' })
}
export function updateCoreSchedule(id: number, data: any) {
  return request({ url: `/core/schedules/${id}/`, method: 'patch', data })
}
export function createCoreSchedule(data: any) {
  return request({ url: '/core/schedules/', method: 'post', data })
}
