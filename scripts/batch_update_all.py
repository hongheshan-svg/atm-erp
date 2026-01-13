#!/usr/bin/env python3
"""
批量为所有列表页面添加删除功能
Batch update all list pages with delete functionality
"""
import re
import sys
from pathlib import Path
from typing import Dict, List

# 页面配置清单
PAGES_CONFIG = [
    # 项目管理
    {'file': 'frontend/src/views/projects/TaskList.vue', 'api': '/projects/tasks/', 'refresh': 'fetchData', 'name': '任务'},
    {'file': 'frontend/src/views/projects/BOMList.vue', 'api': '/projects/bom/', 'refresh': 'fetchData', 'name': 'BOM'},
    {'file': 'frontend/src/views/projects/DrawingList.vue', 'api': '/projects/drawings/', 'refresh': 'fetchData', 'name': '图纸'},
    {'file': 'frontend/src/views/projects/TimeLogList.vue', 'api': '/projects/time-logs/', 'refresh': 'fetchData', 'name': '工时记录'},
    
    # 销售管理
    {'file': 'frontend/src/views/sales/OrderList.vue', 'api': '/sales/orders/', 'refresh': 'fetchData', 'name': '销售订单'},
    {'file': 'frontend/src/views/sales/ContractList.vue', 'api': '/sales/contracts/', 'refresh': 'fetchData', 'name': '销售合同'},
    
    # 采购管理
    {'file': 'frontend/src/views/purchase/RequestList.vue', 'api': '/purchase/requests/', 'refresh': 'fetchData', 'name': '采购申请'},
    {'file': 'frontend/src/views/purchase/OrderList.vue', 'api': '/purchase/orders/', 'refresh': 'fetchData', 'name': '采购订单'},
    {'file': 'frontend/src/views/purchase/GoodsReceiptList.vue', 'api': '/purchase/receipts/', 'refresh': 'fetchData', 'name': '收货单'},
    
    # 库存管理
    {'file': 'frontend/src/views/inventory/StockList.vue', 'api': '/inventory/stocks/', 'refresh': 'fetchData', 'name': '库存'},
    {'file': 'frontend/src/views/inventory/StockMoveList.vue', 'api': '/inventory/moves/', 'refresh': 'fetchData', 'name': '库存流水'},
    {'file': 'frontend/src/views/inventory/StockAdjustmentList.vue', 'api': '/inventory/adjustments/', 'refresh': 'fetchData', 'name': '库存盘点'},
    {'file': 'frontend/src/views/inventory/WarehouseList.vue', 'api': '/inventory/warehouses/', 'refresh': 'fetchData', 'name': '仓库'},
    
    # 财务管理
    {'file': 'frontend/src/views/finance/ExpenseList.vue', 'api': '/finance/expenses/', 'refresh': 'fetchData', 'name': '费用报销'},
    {'file': 'frontend/src/views/finance/InvoiceList.vue', 'api': '/finance/invoices/', 'refresh': 'fetchData', 'name': '发票'},
    {'file': 'frontend/src/views/finance/AssetList.vue', 'api': '/finance/assets/', 'refresh': 'fetchData', 'name': '固定资产'},
    
    # 系统管理
    {'file': 'frontend/src/views/system/RoleList.vue', 'api': '/accounts/roles/', 'refresh': 'fetchData', 'name': '角色'},
    {'file': 'frontend/src/views/system/DepartmentList.vue', 'api': '/accounts/departments/', 'refresh': 'fetchData', 'name': '部门'},
    
    # 生产管理
    {'file': 'frontend/src/views/production/PlanList.vue', 'api': '/production/plans/', 'refresh': 'fetchData', 'name': '生产计划'},
    {'file': 'frontend/src/views/production/WorkOrderList.vue', 'api': '/production/work-orders/', 'refresh': 'fetchData', 'name': '工单'},
    {'file': 'frontend/src/views/production/EquipmentList.vue', 'api': '/production/equipments/', 'refresh': 'fetchData', 'name': '设备'},
]


def add_imports(content: str) -> tuple[str, bool]:
    """添加composable导入"""
    if 'useBatchDelete' in content:
        return content, False
    
    # 查找script setup后的第一个import
    pattern = r'(<script setup>\n)(import )'
    match = re.search(pattern, content)
    if match:
        imports = """import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

"""
        content = content.replace(match.group(0), match.group(1) + imports + match.group(2))
        return content, True
    
    return content, False


def add_composable_usage(content: str, config: Dict) -> tuple[str, bool]:
    """添加composable使用代码"""
    if 'const { canDelete }' in content:
        return content, False
    
    api = config['api']
    refresh = config['refresh']
    name = config['name']
    
    composable_code = f"""
// 权限检查
const {{ canDelete }} = usePermission()

// 批量删除功能
const {{ selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow }} = useBatchDelete(
  '{api}',
  {{
    confirmTitle: '确认删除{name}',
    confirmMessage: '此操作将永久删除选中的{name}记录，是否继续？',
    successMessage: '删除{name}成功',
    errorMessage: '删除{name}失败',
    onSuccess: () => {refresh}()
  }}
)

"""
    
    # 在第一个const声明前插入
    pattern = r'(\nimport .*?\n)(\nconst )'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        # 找到最后一个import
        last_import_pos = content.rfind('import ', 0, match.end())
        if last_import_pos != -1:
            # 找到这个import语句的结束位置
            newline_pos = content.find('\n', last_import_pos)
            if newline_pos != -1:
                content = content[:newline_pos+1] + composable_code + content[newline_pos+1:]
                return content, True
    
    return content, False


def remove_old_code(content: str) -> tuple[str, bool]:
    """删除旧的删除相关代码"""
    updated = False
    
    # 删除 selectedItems
    if 'const selectedItems = ref([])' in content:
        content = re.sub(r'const selectedItems = ref\(\[\]\)\n', '', content)
        updated = True
    
    # 删除旧的handleDelete函数（更精确的匹配）
    pattern = r'const handleDelete = async \(row\) => \{[^}]*\}(?:\s*catch[^}]*\})*\s*\}\s*\n'
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, '// 删除功能已迁移到 useBatchDelete composable\n\n', content, flags=re.DOTALL)
        updated = True
    
    # 删除handleSelectionChange
    if 'selectedItems.value = selection' in content:
        pattern = r'const handleSelectionChange = \(selection\) => \{[^}]*\}\n'
        content = re.sub(pattern, '', content)
        updated = True
    
    # 删除handleBatchDelete
    pattern = r'const handleBatchDelete = async \(\) => \{[^}]*\}(?:\s*catch[^}]*\})*\s*\}\s*\n'
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, '', content, flags=re.DOTALL)
        updated = True
    
    return content, updated


def update_template(content: str) -> tuple[str, bool]:
    """更新模板部分"""
    updated = False
    
    # 更新批量工具栏
    if 'selectedItems.length' in content:
        content = content.replace('selectedItems.length', 'selectedRows.length')
        updated = True
    
    if 'table-toolbar' in content and 'canDelete &&' not in content:
        content = re.sub(
            r'v-if="selectedRows\.length > 0"',
            'v-if="canDelete && selectedRows.length > 0"',
            content
        )
        updated = True
    
    # 添加选择列的权限控制
    if 'type="selection"' in content and not re.search(r'v-if="canDelete".*type="selection"', content):
        content = re.sub(
            r'<el-table-column type="selection" width="\d+"',
            '<el-table-column v-if="canDelete" type="selection" width="55" fixed',
            content
        )
        updated = True
    
    # 添加@selection-change事件（如果没有）
    if '<el-table ' in content and '@selection-change' not in content:
        content = re.sub(
            r'(<el-table[^>]*?)>',
            r'\1 @selection-change="handleSelectionChange">',
            content
        )
        updated = True
    
    return content, updated


def add_toolbar_style(content: str) -> tuple[str, bool]:
    """添加table-toolbar样式"""
    if '.table-toolbar' in content:
        return content, False
    
    if '</style>' not in content:
        return content, False
    
    style_code = """.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 10px;
  border: 1px solid #e4e7ed;
}

.table-toolbar span {
  font-size: 14px;
  color: #606266;
}

"""
    
    content = content.replace('</style>', style_code + '</style>')
    return content, True


def update_vue_file(file_path: Path, config: Dict) -> bool:
    """更新单个Vue文件"""
    if not file_path.exists():
        print(f"  ❌ 文件不存在: {file_path}")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"  ❌ 读取文件失败: {e}")
        return False
    
    original_content = content
    changes = []
    
    # 1. 添加imports
    content, updated = add_imports(content)
    if updated:
        changes.append("添加imports")
    
    # 2. 添加composable使用
    content, updated = add_composable_usage(content, config)
    if updated:
        changes.append("添加composable配置")
    
    # 3. 删除旧代码
    content, updated = remove_old_code(content)
    if updated:
        changes.append("删除旧代码")
    
    # 4. 更新模板
    content, updated = update_template(content)
    if updated:
        changes.append("更新模板")
    
    # 5. 添加样式
    content, updated = add_toolbar_style(content)
    if updated:
        changes.append("添加样式")
    
    if not changes:
        print(f"  ⚪ 无需更新")
        return False
    
    # 备份原文件
    backup_path = file_path.with_suffix('.vue.bak')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(original_content)
    
    # 写入更新后的内容
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  ✅ 已更新: {', '.join(changes)}")
    return True


def main():
    """主函数"""
    print("=" * 70)
    print("批量删除功能 - 批量更新脚本")
    print("=" * 70)
    
    base_path = Path('/home/administrator/erp')
    success_count = 0
    skip_count = 0
    failed_count = 0
    
    for i, config in enumerate(PAGES_CONFIG, 1):
        file_path = base_path / config['file']
        page_name = config['name']
        
        print(f"\n[{i}/{len(PAGES_CONFIG)}] {page_name} ({file_path.name})")
        
        try:
            if update_vue_file(file_path, config):
                success_count += 1
            else:
                skip_count += 1
        except Exception as e:
            print(f"  ❌ 更新失败: {e}")
            failed_count += 1
    
    print("\n" + "=" * 70)
    print(f"批量更新完成!")
    print(f"  ✅ 成功: {success_count} 个")
    print(f"  ⚪ 跳过: {skip_count} 个")
    print(f"  ❌ 失败: {failed_count} 个")
    print("=" * 70)
    
    if success_count > 0:
        print("\n⚠️  重要提示:")
        print("1. 脚本已完成大部分自动化工作")
        print("2. 请手动检查并完成以下操作:")
        print("   • 更新操作列的删除按钮（添加 v-if='canDelete'）")
        print("   • 调整操作列宽度（:width='canDelete ? xxx : yyy'）")
        print("   • 测试功能是否正常")
        print("\n3. 备份文件位置: *.vue.bak")
        print("4. 如有问题可从备份恢复")
        print("\n参考文档: /docs/BATCH_DELETE_GUIDE.md")
        print("参考示例: ItemList.vue, UserList.vue, CustomerList.vue")


if __name__ == '__main__':
    main()
