import { createApp, type Plugin } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin } from '@tanstack/vue-query'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// vxe-table 作为蓝图既定表格库全局注册;v4 默认导出即可作为 Vue 插件。
import VxeTable from 'vxe-table'
import 'vxe-table/lib/style.css'

import App from './App.vue'
import router from './router'
import permission from './directives/permission'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.use(VxeTable as unknown as Plugin)
app.use(VueQueryPlugin)

// 注册 v-permission 指令(无权限隐藏元素)。
app.directive('permission', permission)

app.mount('#app')
