import { request } from '../utils/request'

// Send all stable BOM row IDs in the body so cross-page selections do not hit URL length limits.
export async function downloadBOM(project: number, ids: number[], fileFormat: 'xlsx' | 'csv', name: string) {
  let response
  try {
    response = await request.post('/business/bom/export/', { project, ids, file_format: fileFormat }, { responseType: 'blob' })
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
