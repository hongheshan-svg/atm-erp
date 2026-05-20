/**
 * BOM对比/快照 API
 */
import request from '@/utils/request'

export function getBOMSnapshotList(params) {
  return request({ url: '/projects/bom-snapshots/', method: 'get', params })
}

export function createBOMSnapshot(data) {
  return request({ url: '/projects/bom-snapshots/create_snapshot/', method: 'post', data })
}

export function compareBOMWithCurrent(id) {
  return request({ url: `/projects/bom-snapshots/${id}/compare_with_current/`, method: 'post' })
}

export function compareBOM(data) {
  return request({ url: '/projects/bom-compare/compare/', method: 'post', data })
}

export function exportBOMCompare(data, config) {
  return request({ url: '/projects/bom-compare/compare/', method: 'post', data, ...config })
}
