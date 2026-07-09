import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// Element Plus dark-mode css-vars (activated by the `dark` class on <html>)
import 'element-plus/theme-chalk/dark/css-vars.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { useWebSocketStore } from './stores/websocket'
import permissionDirective from './directives/permission'
import { initTheme } from './utils/theme'

// Apply the persisted / OS-preferred theme before mount to avoid a flash.
initTheme()

const app = createApp(App)

// Register Element Plus icons
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// Register permission directive
app.directive('permission', permissionDirective)

const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(i18n)
app.use(ElementPlus, {
  locale: zhCn,
})

app.mount('#app')

// Enable the global WebSocket connection when the user is authenticated.
// Reconnect/backoff is handled inside the store/service; a missing or
// unreachable WS endpoint is logged but never crashes the app.
try {
  const token = localStorage.getItem('access_token')
  if (token) {
    const wsStore = useWebSocketStore()
    wsStore.connect()
  }
} catch (err) {
  console.warn('Global WebSocket connect skipped:', err)
}

