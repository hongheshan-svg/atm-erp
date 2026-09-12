import { can, reports, operations, purchaseReader } from './session'
import {
  House,
  Folder,
  Files,
  ShoppingCart,
  Box,
  Wallet,
  Collection,
  Setting,
} from '@element-plus/icons-vue'
export function navigation() {
  return [
    { key: 'workbench', label: '工作台', icon: House },
    ...(reports() ? [{ key: 'reports', label: '经营报表', icon: Files }] : []),
    ...(can(['admin', 'manager', 'finance', 'sales_manager']) ? [{ key: 'sales', label: '销售', icon: Files }] : []),
    ...(operations() ? [{ key: 'projects', label: '项目', icon: Folder }, { key: 'bom', label: 'BOM', icon: Files }] : []),
    ...(purchaseReader()
      ? [
          { key: 'purchases', label: '采购', icon: ShoppingCart },
          { key: 'inventory', label: '库存', icon: Box },
        ]
      : []),
    ...(can(['admin', 'manager', 'finance'])
      ? [{ key: 'finance', label: '收付款', icon: Wallet }]
      : []),
    { key: 'masterdata', label: '基础资料', icon: Collection },
    { key: 'settings', label: '设置', icon: Setting },
  ]
}
