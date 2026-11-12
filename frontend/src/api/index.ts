import { request } from '../utils/request'
import type { Row } from '../types'
export const business = (path: string) => `/business/${path}`
export async function read(path: string, params: Row = {}) {
  return (await request.get(path, { params })).data
}
export async function all(path: string, params: Row = {}) {
  const result: Row[] = []
  for (let page = 1; ; page++) {
    const data = await read(path, { ...params, page, page_size: 200 })
    if (Array.isArray(data)) return data as Row[]
    result.push(...data.results)
    if (!data.next) return result
  }
}
export async function write(path: string, data: Row | FormData, key: string, method = 'post') {
  return (await request({ url: path, method, data, headers: { 'Idempotency-Key': key } })).data
}
// 文件按 blob 读取；出错时服务端返回的 JSON 也成了 blob，转回对象后错误提示才能取到 detail。
export async function blobResponse(send: () => Promise<{ data: Blob }>): Promise<Blob> {
  try { return (await send()).data }
  catch (error: any) {
    if (error.response?.data instanceof Blob) {
      try { error.response.data = JSON.parse(await error.response.data.text()) } catch { /* retain original error */ }
    }
    throw error
  }
}
export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export async function download(path: string, name: string, params: Row = {}) {
  saveBlob(await blobResponse(() => request.get(path.replace(/^\/api\//, '/'), { responseType: 'blob', params })), name)
}
export function readBlob(path: string): Promise<Blob> {
  return blobResponse(() => request.get(path.replace(/^\/api\//, '/'), { responseType: 'blob' }))
}
