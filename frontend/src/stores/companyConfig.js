import { ref } from 'vue'
import request from '@/utils/request'

// 公司配置状态
const companyName = ref('')
const companyShortName = ref('')
const loaded = ref(false)

// 获取公司配置
export const loadCompanyConfig = async () => {
  if (loaded.value) return
  
  try {
    const response = await request.get('/core/system-config/')
    companyName.value = response.company_name || ''
    companyShortName.value = response.company_short_name || ''
    loaded.value = true
    
    // 更新浏览器标题
    updateDocumentTitle()
  } catch (error) {
    console.error('Failed to load company config:', error)
  }
}

// 更新浏览器标题
export const updateDocumentTitle = () => {
  const name = companyName.value || companyShortName.value
  if (name) {
    document.title = `${name} - ERP管理系统`
  }
}

// 导出响应式引用
export const useCompanyConfig = () => {
  return {
    companyName,
    companyShortName,
    loaded,
    loadCompanyConfig,
    updateDocumentTitle
  }
}

export default {
  companyName,
  companyShortName,
  loaded,
  loadCompanyConfig,
  updateDocumentTitle
}

