#!/usr/bin/env python3
"""
安全批量更新脚本 - 修复之前脚本的问题
Safe batch update script
"""
import re
import os
from pathlib import Path
from typing import Tuple

def get_all_vue_files(base_path: Path) -> list:
    """获取所有需要更新的Vue文件"""
    views_path = base_path / 'frontend' / 'src' / 'views'
    vue_files = []
    
    for root, dirs, files in os.walk(views_path):
        for file in files:
            if file.endswith('.vue') and not file.endswith('.bak') and not file.endswith('.bak2') and not file.endswith('.bak3') and not file.endswith('.backup'):
                if 'List' in file:
                    vue_files.append(Path(root) / file)
    
    return sorted(vue_files)


def restore_from_backup(file_path: Path) -> bool:
    """从备份恢复文件"""
    # 尝试找到最早的备份
    for suffix in ['.vue.bak', '.vue.backup']:
        backup = file_path.with_suffix(suffix)
        if backup.exists():
            with open(backup, 'r', encoding='utf-8') as f:
                content = f.read()
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
    return False


def has_syntax_error(content: str) -> bool:
    """检查是否有语法错误"""
    # 检查常见的错误模式
    patterns = [
        r'@selection-change="handleSelectionChange">',  # selection-change在非el-table标签上
        r'/ @',  # 自闭合标签后有事件
        r'width="\d+"[^/]*/ @',  # 错误格式
    ]
    
    for pattern in patterns:
        if re.search(pattern, content):
            return True
    return False


def safe_add_delete_feature(content: str, api_path: str, name: str) -> Tuple[str, bool, list]:
    """安全地添加删除功能"""
    changes = []
    
    # 检查是否已经正确配置
    if 'useBatchDelete' in content and 'const { canDelete }' in content:
        if not has_syntax_error(content):
            return content, False, ['已是最新']
    
    # 1. 添加imports（如果没有）
    if 'useBatchDelete' not in content:
        # 找到script setup标签
        script_match = re.search(r'<script\s+setup[^>]*>\s*\n', content)
        if script_match:
            imports = """import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'
"""
            insert_pos = script_match.end()
            content = content[:insert_pos] + imports + content[insert_pos:]
            changes.append('imports')
    
    # 2. 添加composable使用（如果没有）
    if 'const { canDelete }' not in content:
        # 找到刷新函数名
        refresh_match = re.search(r'const\s+(fetch\w+|load\w+|get\w+)\s*=', content)
        refresh_func = refresh_match.group(1) if refresh_match else 'fetchData'
        
        composable_code = f"""
// 权限检查
const {{ canDelete }} = usePermission()

// 批量删除功能
const {{ selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow }} = useBatchDelete(
  '{api_path}',
  {{
    confirmTitle: '确认删除{name}',
    confirmMessage: '此操作将永久删除选中的{name}记录，是否继续？',
    successMessage: '删除{name}成功',
    errorMessage: '删除{name}失败',
    onSuccess: () => {refresh_func}()
  }}
)
"""
        # 找到所有import语句的末尾
        import_matches = list(re.finditer(r"import\s+[^;]+;\s*\n", content))
        if import_matches:
            last_import_end = import_matches[-1].end()
            content = content[:last_import_end] + composable_code + content[last_import_end:]
            changes.append('composable')
    
    # 3. 在el-table上添加@selection-change（如果没有）
    if '@selection-change=' not in content:
        # 只在el-table标签上添加
        pattern = r'(<el-table\s+[^>]*)(>)'
        match = re.search(pattern, content)
        if match:
            tag_content = match.group(1)
            if '@selection-change' not in tag_content:
                new_tag = tag_content + ' @selection-change="handleSelectionChange"' + match.group(2)
                content = content.replace(match.group(0), new_tag)
                changes.append('selection事件')
    
    # 4. 添加选择列（如果没有）
    if 'type="selection"' not in content:
        # 在第一个数据列前添加选择列
        pattern = r'(<el-table[^>]*>\s*\n)(\s*)(<el-table-column\s)'
        match = re.search(pattern, content)
        if match:
            selection_col = f'{match.group(2)}<el-table-column v-if="canDelete" type="selection" width="55" />\n'
            content = content.replace(
                match.group(0),
                match.group(1) + selection_col + match.group(2) + match.group(3)
            )
            changes.append('选择列')
    else:
        # 已有选择列，确保有v-if控制
        if 'v-if="canDelete" type="selection"' not in content and 'type="selection"' in content:
            content = re.sub(
                r'<el-table-column\s+type="selection"',
                '<el-table-column v-if="canDelete" type="selection"',
                content
            )
            changes.append('选择列权限')
    
    # 5. 添加工具栏（如果没有）
    if 'table-toolbar' not in content:
        toolbar_html = '''    <!-- 批量操作工具栏 -->
    <div v-if="canDelete && selectedRows.length > 0" class="table-toolbar">
      <span>已选择 {{ selectedRows.length }} 项</span>
      <el-button type="danger" size="small" @click="batchDelete" :loading="deleteLoading">
        批量删除
      </el-button>
    </div>

'''
        # 在el-table前插入
        pattern = r'(\s*)(<el-table\s)'
        match = re.search(pattern, content)
        if match:
            content = content.replace(match.group(0), '\n' + toolbar_html + match.group(0))
            changes.append('工具栏')
    
    # 6. 更新删除按钮（handleDelete -> deleteRow）
    if '@click="handleDelete(row)"' in content:
        content = content.replace('@click="handleDelete(row)"', '@click="deleteRow(row)"')
        changes.append('删除按钮')
    
    # 7. 添加删除按钮权限控制
    if '@click="deleteRow(row)"' in content:
        # 检查是否已有v-if="canDelete"
        delete_btn_pattern = r'<el-button[^>]*@click="deleteRow\(row\)"[^>]*>'
        matches = list(re.finditer(delete_btn_pattern, content))
        for match in reversed(matches):
            btn_tag = match.group(0)
            if 'v-if="canDelete"' not in btn_tag:
                # 在type=前添加v-if
                if 'type="danger"' in btn_tag:
                    new_btn = btn_tag.replace('type="danger"', 'v-if="canDelete" type="danger"')
                    content = content[:match.start()] + new_btn + content[match.end():]
                    changes.append('按钮权限')
    
    # 8. 添加样式（如果没有）
    if '.table-toolbar' not in content:
        style_code = """
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
        if '</style>' in content:
            content = content.replace('</style>', style_code + '</style>')
            changes.append('样式')
        elif '<style' not in content:
            content += f'\n<style scoped>{style_code}</style>\n'
            changes.append('样式')
    
    return content, bool(changes), changes


def get_api_path_and_name(file_path: Path) -> Tuple[str, str]:
    """根据文件路径推断API路径和名称"""
    file_name = file_path.stem
    parent_dir = file_path.parent.name
    
    # 移除List后缀获取实体名
    entity = file_name.replace('List', '')
    
    # 构建API路径
    api_path = f'/{parent_dir}/{entity.lower()}s/'
    
    # 中文名映射
    name_map = {
        'Role': '角色',
        'Department': '部门',
        'User': '用户',
        'Item': '物料',
        'Customer': '客户',
        'Supplier': '供应商',
        'Warehouse': '仓库',
        'Location': '货位',
        'Project': '项目',
        'Task': '任务',
        'BOM': 'BOM',
        'Drawing': '图纸',
        'TimeLog': '工时',
        'Lead': '线索',
        'Opportunity': '商机',
        'Quotation': '报价',
        'Order': '订单',
        'Contract': '合同',
        'Delivery': '发货',
        'Request': '申请',
        'GoodsReceipt': '收货',
        'Stock': '库存',
        'StockMove': '库存流水',
        'StockAdjustment': '盘点',
        'Return': '退货',
        'Requisition': '领料',
        'Batch': '批次',
        'Equipment': '设备',
        'Fixture': '夹具',
        'Inspection': '检验',
        'Expense': '费用',
        'Invoice': '发票',
        'Asset': '资产',
        'AP': '应付',
        'AR': '应收',
        'Meeting': '会议',
        'Schedule': '日程',
        'Plan': '计划',
        'Process': '工序',
        'Alert': '预警',
        'ECN': '变更',
        'Member': '成员',
        'WorkOrder': '工单',
        'Archive': '归档',
        'Milestone': '里程碑',
        'Bug': 'Bug',
        'QualityInspection': '质检',
        'DebugRecord': '调试',
        'Traceability': '追溯',
        'CollectionPlan': '回款',
        'ProjectCost': '成本',
        'SharedExpense': '公摊',
        'DeliveryOrder': '发货单',
    }
    
    name = name_map.get(entity, entity)
    
    return api_path, name


def main():
    """主函数"""
    print("=" * 70)
    print("安全批量更新脚本 - 批量删除功能")
    print("=" * 70)
    
    base_path = Path('/home/administrator/erp')
    vue_files = get_all_vue_files(base_path)
    
    print(f"\n找到 {len(vue_files)} 个列表页面\n")
    
    success = 0
    skip = 0
    restore = 0
    fail = 0
    
    for i, file_path in enumerate(vue_files, 1):
        rel_path = file_path.relative_to(base_path / 'frontend' / 'src' / 'views')
        print(f"[{i}/{len(vue_files)}] {rel_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查是否有语法错误
            if has_syntax_error(content):
                print(f"  ⚠️  检测到语法错误，正在恢复...")
                if restore_from_backup(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    restore += 1
                    print(f"  🔄 已从备份恢复")
                else:
                    print(f"  ❌ 无法恢复，跳过")
                    fail += 1
                    continue
            
            api_path, name = get_api_path_and_name(file_path)
            new_content, updated, changes = safe_add_delete_feature(content, api_path, name)
            
            if updated:
                # 创建备份
                backup_path = file_path.with_suffix('.vue.safe_bak')
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # 保存更新
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print(f"  ✅ 更新: {', '.join(changes)}")
                success += 1
            else:
                print(f"  ⚪ {changes[0] if changes else '跳过'}")
                skip += 1
                
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            fail += 1
    
    print("\n" + "=" * 70)
    print(f"更新完成!")
    print(f"  ✅ 成功: {success}")
    print(f"  🔄 恢复: {restore}")
    print(f"  ⚪ 跳过: {skip}")
    print(f"  ❌ 失败: {fail}")
    print("=" * 70)


if __name__ == '__main__':
    main()
