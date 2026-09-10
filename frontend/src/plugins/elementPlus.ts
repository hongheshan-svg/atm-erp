import type { App } from 'vue'
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElIcon,
  ElLoading,
  ElPagination,
  ElTable,
  ElTableColumn,
  ElTabPane,
  ElTabs,
  ElTag,
} from 'element-plus'

export function installElementPlus(app: App) {
  app.use(ElLoading)
  for (const component of [
    ElAlert,
    ElButton,
    ElDialog,
    ElDropdown,
    ElDropdownItem,
    ElDropdownMenu,
    ElIcon,
    ElPagination,
    ElTable,
    ElTableColumn,
    ElTabPane,
    ElTabs,
    ElTag,
  ]) {
    app.use(component)
  }
}
