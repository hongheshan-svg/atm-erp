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
export async function download(path: string, name: string) {
  const response = await request.get(path.replace(/^\/api\//, '/'), { responseType: 'blob' })
  const url = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
