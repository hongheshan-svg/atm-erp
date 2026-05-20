import { ref } from 'vue'
import request from '@/utils/request'

const companyName = ref('')
const companyShortName = ref('')
const loaded = ref(false)

export const loadCompanyConfig = async (): Promise<void> => {
  if (loaded.value) return

  try {
    const response: any = await request.get('/core/system-config/')
    companyName.value = response.company_name || ''
    companyShortName.value = response.company_short_name || ''
    loaded.value = true

    updateDocumentTitle()
  } catch (error) {
    console.error('Failed to load company config:', error)
  }
}

export const updateDocumentTitle = (): void => {
  const name = companyName.value || companyShortName.value
  if (name) {
    document.title = `${name} - ERP管理系统`
  }
}

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
