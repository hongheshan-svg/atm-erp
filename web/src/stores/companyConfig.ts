import { defineStore } from 'pinia'
import { ref } from 'vue'

// 公司级配置(名称、Logo、主题等),后续可由后端配置接口填充。
export const useCompanyConfigStore = defineStore('companyConfig', () => {
  const companyName = ref('ATM-ERP')
  const logo = ref('')
  const theme = ref<'light' | 'dark'>('light')

  function setCompanyName(name: string) {
    companyName.value = name
  }

  function setLogo(url: string) {
    logo.value = url
  }

  function setTheme(value: 'light' | 'dark') {
    theme.value = value
  }

  return {
    companyName,
    logo,
    theme,
    setCompanyName,
    setLogo,
    setTheme
  }
})
