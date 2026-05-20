/**
 * BOM对比/快照 API
 */
import request from '@/utils/request'

export function getBOMSnapshotList(params?: Record<string, any>) {
  return request({ url: '/projects/bom-snapshots/', method: 'get', params })
}

export function createBOMSnapshot(data: any) {
  return request({ url: '/projects/bom-snapshots/create_snapshot/', method: 'post', data })
}

export function compareBOMWithCurrent(id: number) {
  return request({ url: `/projects/bom-snapshots/${id}/compare_with_current/`, method: 'post' })
}

export function compareBOM(data: any) {
  return request({ url: '/projects/bom-compare/compare/', method: 'post', data })
}

export function exportBOMCompare(data: any, config: any) {
  return request({ url: '/projects/bom-compare/compare/', method: 'post', data, ...config })
}
