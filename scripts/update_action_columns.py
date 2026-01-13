#!/usr/bin/env python3
"""
批量更新操作列的删除按钮权限控制
Update action columns to add permission control for delete buttons
"""
import re
from pathlib import Path

# 需要更新的页面列表（脚本已自动更新过的）
PAGES = [
    'frontend/src/views/projects/TaskList.vue',
    'frontend/src/views/projects/BOMList.vue',
    'frontend/src/views/projects/DrawingList.vue',
    'frontend/src/views/projects/TimeLogList.vue',
    'frontend/src/views/sales/OrderList.vue',
    'frontend/src/views/sales/ContractList.vue',
    'frontend/src/views/purchase/RequestList.vue',
    'frontend/src/views/purchase/OrderList.vue',
    'frontend/src/views/purchase/GoodsReceiptList.vue',
    'frontend/src/views/inventory/StockList.vue',
    'frontend/src/views/inventory/StockMoveList.vue',
    'frontend/src/views/inventory/StockAdjustmentList.vue',
    'frontend/src/views/finance/ExpenseList.vue',
    'frontend/src/views/finance/InvoiceList.vue',
    'frontend/src/views/finance/AssetList.vue',
    'frontend/src/views/system/RoleList.vue',
    'frontend/src/views/system/DepartmentList.vue',
    'frontend/src/views/production/PlanList.vue',
]


def update_action_column(content: str) -> tuple[str, bool]:
    """更新操作列"""
    updated = False
    
    # 模式1: 简单的删除按钮
    # <el-button ... @click="handleDelete(row)">删除</el-button>
    pattern1 = r'(<el-button[^>]*?)(@click="handleDelete\(row\)">删除</el-button>)'
    if re.search(pattern1, content):
        # 检查是否已经有v-if
        if 'v-if="canDelete"' not in content or content.count('v-if="canDelete"') < content.count('handleDelete'):
            replacement = r'\1v-if="canDelete"\n              \2'
            content = re.sub(pattern1, replacement, content)
            updated = True
    
    # 模式2: link类型的删除按钮
    # <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
    pattern2 = r'(<el-button[^>]*?type="danger"[^>]*?)(@click="(?:handleDelete|deleteRow)\([^)]*\)">删除</el-button>)'
    matches = re.finditer(pattern2, content)
    for match in matches:
        button_tag = match.group(0)
        if 'v-if="canDelete"' not in button_tag:
            new_button = button_tag.replace(
                match.group(1),
                match.group(1) + '\n              v-if="canDelete"\n              :loading="deleteLoading"\n              '
            )
            content = content.replace(button_tag, new_button, 1)
            updated = True
    
    # 更新操作列宽度 - 根据canDelete动态调整
    # <el-table-column label="操作" width="280"
    pattern3 = r'<el-table-column label="操作" width="(\d+)"'
    matches = list(re.finditer(pattern3, content))
    if matches:
        for match in matches:
            original_width = int(match.group(1))
            # 如果删除按钮占用70px，则减去这个宽度
            new_width_with = original_width
            new_width_without = max(100, original_width - 80)  # 删除按钮约占80px
            
            new_tag = f'<el-table-column label="操作" :width="canDelete ? {new_width_with} : {new_width_without}"'
            content = content.replace(match.group(0), new_tag, 1)
            updated = True
    
    return content, updated


def main():
    """主函数"""
    print("=" * 70)
    print("批量更新操作列 - 添加删除按钮权限控制")
    print("=" * 70)
    
    base_path = Path('/home/administrator/erp')
    success_count = 0
    skip_count = 0
    
    for i, page in enumerate(PAGES, 1):
        file_path = base_path / page
        page_name = file_path.stem
        
        print(f"\n[{i}/{len(PAGES)}] {page_name}")
        
        if not file_path.exists():
            print(f"  ⚪ 文件不存在，跳过")
            skip_count += 1
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            content, updated = update_action_column(content)
            
            if updated:
                # 备份
                backup_path = file_path.with_suffix('.vue.bak2')
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                
                # 保存更新
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"  ✅ 已更新操作列")
                success_count += 1
            else:
                print(f"  ⚪ 无需更新或已更新")
                skip_count += 1
                
        except Exception as e:
            print(f"  ❌ 更新失败: {e}")
    
    print("\n" + "=" * 70)
    print(f"操作列更新完成!")
    print(f"  ✅ 成功: {success_count} 个")
    print(f"  ⚪ 跳过: {skip_count} 个")
    print("=" * 70)
    
    print("\n✅ 所有自动化更新完成！")
    print("📝 请手动检查以下页面的特殊情况:")
    print("   • RequestList.vue - 有多个操作按钮，需要调整宽度")
    print("   • OrderList.vue (多个) - 有工作流按钮")
    print("\n🧪 建议进行完整测试:")
    print("   • 普通用户登录 - 确认删除功能不可见")
    print("   • 管理员登录 - 测试批量删除和单行删除")
    print("\n📊 当前进度: 约 85-90% (自动化完成)")
    print("📝 详细文档: /docs/BATCH_DELETE_PROGRESS.md")


if __name__ == '__main__':
    main()
