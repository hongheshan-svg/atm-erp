import { ref } from 'vue'
import { localStore } from './utils/storage'

// 批量删除是管理员偶尔做的整理动作。默认收起选择列、选择条和行内删除，
// 让列表首屏留给业务数据；开启后在各列表间保持，直到手动退出。
const key = 'erp.batch-mode'
export const batchMode = ref(localStore.get(key) === '1')
export function setBatchMode(value: boolean) {
  batchMode.value = value
  if (value) localStore.set(key, '1')
  else localStore.remove(key)
}
