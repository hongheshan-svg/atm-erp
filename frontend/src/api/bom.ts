import { request } from '../utils/request'

export type BOMExportLayout = 'standard' | 'purchase' | 'import'
// Send all stable BOM row IDs in the body so cross-page selections do not hit URL length limits.
// purchase：缺料清单（追加已领、在途、待批、库存、缺料）；import：按导入模板列顺序，可直接回导。
export async function downloadBOM(project: number, ids: number[], fileFormat: 'xlsx' | 'csv', name: string, layout: BOMExportLayout = 'standard') {
  let response
  try {
    response = await request.post('/business/bom/export/', { project, ids, file_format: fileFormat, ...(layout === 'standard' ? {} : { layout }) }, { responseType: 'blob' })
  } catch (error: any) {
    if (error.response?.data instanceof Blob) {
      try { error.response.data = JSON.parse(await error.response.data.text()) } catch { /* retain original error */ }
    }
    throw error
  }
  const url = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
