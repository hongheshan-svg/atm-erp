import { ref } from 'vue'
import { localStore } from './utils/storage'

export const pageSizes = [10, 20, 50, 100]
const key = 'erp.page-size'
function initialSize() {
  const saved = Number(localStore.get(key))
  return pageSizes.includes(saved) ? saved : 10
}
export const pageSize = ref(initialSize())
export function setPageSize(value: number) {
  if (!pageSizes.includes(value)) return
  pageSize.value = value
  localStore.set(key, String(value))
}
