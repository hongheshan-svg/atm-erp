import { request } from '../utils/request'
import { blobResponse, saveBlob } from '.'

export type BOMExportLayout = 'standard' | 'purchase' | 'import'
// Send all stable BOM row IDs in the body so cross-page selections do not hit URL length limits.
// purchase：缺料清单（追加已领、在途、待批、库存、缺料）；import：按导入模板列顺序，可直接回导。
export async function downloadBOM(project: number, ids: number[], fileFormat: 'xlsx' | 'csv', name: string, layout: BOMExportLayout = 'standard') {
  saveBlob(await blobResponse(() => request.post('/business/bom/export/', { project, ids, file_format: fileFormat, ...(layout === 'standard' ? {} : { layout }) }, { responseType: 'blob' })), name)
}
