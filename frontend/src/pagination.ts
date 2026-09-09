import { ref } from 'vue'

export const pageSizes = [10, 20, 50, 100]
const key = 'erp.page-size'
function initialSize() {
  try {
    const saved = Number(window.localStorage.getItem(key))
    return pageSizes.includes(saved) ? saved : 10
  } catch { return 10 }
}
export const pageSize = ref(initialSize())
export function setPageSize(value: number) {
  if (!pageSizes.includes(value)) return
  pageSize.value = value
  try { window.localStorage.setItem(key, String(value)) } catch { /* This preference also works without browser storage. */ }
}
