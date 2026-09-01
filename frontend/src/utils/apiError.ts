/**
 * 后端错误消息提取。
 *
 * 后端返回的错误位置并不统一：
 * - 业务校验（视图自己 return）        → { error: '...' }
 * - DRF 异常（PermissionDenied 等）    → { detail: '...' }
 * - 序列化器字段校验                    → { quantity: ['数量必须大于 0'] }
 * - 未捕获异常（真 500）                → 无 JSON body，Django 返回 HTML
 *
 * 调用点只读某一个 key 时，其余情况会被兜底文案糊掉，用户看不到真实原因。
 */
export function extractApiError(err: any, fallback = '请求失败'): string {
  const data = err?.response?.data

  if (!data) {
    // 真 500 / 网络错误：没有可读的响应体，只能用兜底文案。
    return fallback
  }

  if (typeof data === 'string') {
    // Django 的 HTML 错误页对用户没有意义，别直接抛给他们。
    return data.trim().startsWith('<') ? fallback : data.trim() || fallback
  }

  const direct = data.error ?? data.detail
  if (typeof direct === 'string' && direct.trim()) {
    return direct.trim()
  }

  const flat = flattenFieldErrors(data)
  return flat || fallback
}

/**
 * 序列化器字段校验错误，取首条可读消息。覆盖三种形状：
 * - { field: ['msg', ...] } / { non_field_errors: [...] }
 * - { field: 'msg' }
 * - 嵌套列表序列化器 { lines: [{}, { quantity: ['msg'] }] }
 */
function flattenFieldErrors(value: any, depth = 0): string {
  if (depth > 4) {
    return ''
  }

  if (typeof value === 'string') {
    return value.trim()
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const found = flattenFieldErrors(item, depth + 1)
      if (found) {
        return found
      }
    }
    return ''
  }

  if (value && typeof value === 'object') {
    for (const inner of Object.values(value)) {
      const found = flattenFieldErrors(inner, depth + 1)
      if (found) {
        return found
      }
    }
  }

  return ''
}
