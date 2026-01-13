#!/usr/bin/env python3
"""
自动为Vue页面添加批量删除功能
Auto-update Vue pages with batch delete functionality
"""
import re
import sys
from pathlib import Path

def update_vue_file(file_path, config):
    """更新单个Vue文件"""
    print(f"\n正在更新: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    original_content = content
    updated = False
    
    # 1. 添加import语句
    if 'useBatchDelete' not in content:
        # 查找 <script setup> 后的import区域
        script_pattern = r'(<script setup>.*?)(import .*? from .*?\n)'
        match = re.search(script_pattern, content, re.DOTALL)
        if match:
            # 在最后一个import后添加
            import_section = match.group(2)
            new_imports = f"{import_section}import {{ useBatchDelete }} from '@/composables/useBatchDelete'\nimport {{ usePermission }} from '@/composables/usePermission'\n"
            content = content.replace(import_section, new_imports, 1)
            updated = True
            print("  ✓ 添加了composable导入")
    
    # 2. 添加权限检查和批量删除功能
    if 'const { canDelete }' not in content:
        # 在第一个const声明前添加
        api_endpoint = config['api_endpoint']
        refresh_method = config['refresh_method']
        confirm_title = config['confirm_title']
        confirm_message = config['confirm_message']
        
        permission_code = f"""
// 权限检查
const {{ canDelete }} = usePermission()

// 批量删除功能
const {{ selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow }} = useBatchDelete(
  '{api_endpoint}',
  {{
    confirmTitle: '{confirm_title}',
    confirmMessage: '{confirm_message}',
    successMessage: '删除成功',
    errorMessage: '删除失败',
    onSuccess: () => {refresh_method}()
  }}
)
"""
        
        # 在第一个const ref/reactive声明前插入
        first_const_pattern = r'(import .*?\n\n)(const \w+ = ref\(|const \w+ = reactive\()'
        match = re.search(first_const_pattern, content, re.DOTALL)
        if match:
            content = content.replace(match.group(0), match.group(1) + permission_code + '\n' + match.group(2))
            updated = True
            print("  ✓ 添加了权限检查和批量删除功能")
    
    # 3. 更新模板 - 添加批量工具栏
    if 'class="table-toolbar"' in content and 'canDelete && selectedRows' not in content:
        # 替换现有的工具栏
        old_toolbar = r'<div class="table-toolbar" v-if="selectedItems\.length > 0">'
        new_toolbar = '<div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">'
        if old_toolbar in content or 'selectedItems.length' in content:
            content = re.sub(r'selectedItems\.length', 'selectedRows.length', content)
            content = re.sub(r'v-if="selectedRows\.length > 0"', 'v-if="canDelete && selectedRows.length > 0"', content)
            updated = True
            print("  ✓ 更新了批量工具栏")
    
    # 4. 添加选择列
    if 'type="selection"' in content and 'v-if="canDelete"' not in content:
        content = re.sub(
            r'<el-table-column type="selection" width="(\d+)"',
            r'<el-table-column v-if="canDelete" type="selection" width="55" fixed',
            content
        )
        updated = True
        print("  ✓ 添加了权限控制到选择列")
    
    # 5. 更新操作列
    # 这部分比较复杂，需要手动更新
    
    # 6. 删除旧函数
    patterns_to_remove = [
        r'const selectedItems = ref\(\[\]\)\n',
        r'const handleDelete = async \(row\) => \{[\s\S]*?\}\n',
        r'const handleBatchDelete = async \(\) => \{[\s\S]*?\}\n',
        r'const handleSelectionChange = \(selection\) => \{[\s\S]*?\}\n'
    ]
    
    for pattern in patterns_to_remove:
        if re.search(pattern, content):
            content = re.sub(pattern, '// 删除功能已迁移到 useBatchDelete composable\n', content, count=1)
            updated = True
    
    # 7. 添加样式
    if '.table-toolbar' not in content and '<style' in content:
        style_to_add = """
.table-toolbar {
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
        content = content.replace('</style>', style_to_add + '\n</style>')
        updated = True
        print("  ✓ 添加了table-toolbar样式")
    
    if updated:
        # 备份原文件
        backup_path = Path(file_path).with_suffix('.vue.backup')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        
        # 写入更新后的内容
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 更新完成")
        print(f"   备份已保存: {backup_path}")
        return True
    else:
        print(f"⚠️  无需更新（可能已经更新过）")
        return False


def main():
    """主函数"""
    # 配置需要更新的页面
    pages_config = [
        {
            'file': 'frontend/src/views/sales/LeadList.vue',
            'api_endpoint': '/sales/leads/',
            'refresh_method': 'fetchData',
            'confirm_title': '确认删除销售线索',
            'confirm_message': '此操作将永久删除选中的线索记录，是否继续？'
        },
        {
            'file': 'frontend/src/views/sales/OpportunityList.vue',
            'api_endpoint': '/sales/opportunities/',
            'refresh_method': 'fetchData',
            'confirm_title': '确认删除销售商机',
            'confirm_message': '此操作将永久删除选中的商机记录，是否继续？'
        },
        {
            'file': 'frontend/src/views/sales/QuotationList.vue',
            'api_endpoint': '/sales/quotations/',
            'refresh_method': 'fetchData',
            'confirm_title': '确认删除报价单',
            'confirm_message': '此操作将永久删除选中的报价单，是否继续？'
        },
    ]
    
    print("=" * 60)
    print("批量删除功能自动更新脚本")
    print("=" * 60)
    
    base_path = Path('/home/administrator/erp')
    success_count = 0
    failed_count = 0
    
    for config in pages_config:
        file_path = base_path / config['file']
        if update_vue_file(file_path, config):
            success_count += 1
        else:
            failed_count += 1
    
    print("\n" + "=" * 60)
    print(f"更新完成: 成功 {success_count} 个, 失败/跳过 {failed_count} 个")
    print("=" * 60)
    print("\n⚠️  注意: 脚本只能完成部分自动化")
    print("请手动检查并完成以下操作:")
    print("1. 更新操作列的删除按钮（添加v-if='canDelete')")
    print("2. 调整操作列宽度（:width='canDelete ? xxx : yyy')")
    print("3. 测试功能是否正常")
    print("\n参考文档: /docs/BATCH_DELETE_GUIDE.md")


if __name__ == '__main__':
    main()
