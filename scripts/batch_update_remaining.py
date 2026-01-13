#!/usr/bin/env python3
"""
批量更新所有剩余页面的删除功能
Batch update remaining pages with delete functionality
"""
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# 剩余需要更新的页面配置
REMAINING_PAGES = [
    # 库存管理 - 剩余
    {'file': 'frontend/src/views/inventory/ReturnList.vue', 'api': '/inventory/returns/', 'name': '退货'},
    {'file': 'frontend/src/views/inventory/RequisitionList.vue', 'api': '/inventory/requisitions/', 'name': '领料'},
    {'file': 'frontend/src/views/inventory/BatchList.vue', 'api': '/inventory/batches/', 'name': '批次'},
    
    # 销售管理 - 剩余
    {'file': 'frontend/src/views/sales/DeliveryOrderList.vue', 'api': '/sales/deliveries/', 'name': '发货单'},
    
    # 设备管理
    {'file': 'frontend/src/views/equipment/FixtureList.vue', 'api': '/equipment/fixtures/', 'name': '夹具'},
    {'file': 'frontend/src/views/equipment/EquipmentList.vue', 'api': '/equipment/equipments/', 'name': '设备'},
    {'file': 'frontend/src/views/equipment/InspectionList.vue', 'api': '/equipment/inspections/', 'name': '设备检验'},
    
    # MES
    {'file': 'frontend/src/views/mes/TraceabilityList.vue', 'api': '/mes/traceability/', 'name': '追溯'},
    
    # OA
    {'file': 'frontend/src/views/oa/MeetingList.vue', 'api': '/oa/meetings/', 'name': '会议'},
    {'file': 'frontend/src/views/oa/ScheduleList.vue', 'api': '/oa/schedules/', 'name': '日程'},
    
    # 基础数据 - 剩余
    {'file': 'frontend/src/views/masterdata/LocationList.vue', 'api': '/masterdata/locations/', 'name': '货位'},
    {'file': 'frontend/src/views/masterdata/WarehouseList.vue', 'api': '/masterdata/warehouses/', 'name': '仓库'},
    
    # 项目管理 - 剩余
    {'file': 'frontend/src/views/projects/AlertList.vue', 'api': '/projects/alerts/', 'name': '预警'},
    {'file': 'frontend/src/views/projects/ECNList.vue', 'api': '/projects/ecns/', 'name': '变更'},
    {'file': 'frontend/src/views/projects/MemberList.vue', 'api': '/projects/members/', 'name': '成员'},
    {'file': 'frontend/src/views/projects/WorkOrderList.vue', 'api': '/projects/work-orders/', 'name': '工单'},
    {'file': 'frontend/src/views/projects/ArchiveList.vue', 'api': '/projects/archives/', 'name': '归档'},
    {'file': 'frontend/src/views/projects/MilestoneList.vue', 'api': '/projects/milestones/', 'name': '里程碑'},
    {'file': 'frontend/src/views/projects/BugList.vue', 'api': '/projects/bugs/', 'name': 'Bug'},
    
    # 工作流
    {'file': 'frontend/src/views/workflow/TaskList.vue', 'api': '/workflow/tasks/', 'name': '工作流任务'},
    
    # 财务管理 - 剩余
    {'file': 'frontend/src/views/finance/APList.vue', 'api': '/finance/payables/', 'name': '应付账款'},
    {'file': 'frontend/src/views/finance/ARList.vue', 'api': '/finance/receivables/', 'name': '应收账款'},
    {'file': 'frontend/src/views/finance/CollectionPlanList.vue', 'api': '/finance/collection-plans/', 'name': '回款计划'},
    {'file': 'frontend/src/views/finance/ProjectCostList.vue', 'api': '/finance/project-costs/', 'name': '项目成本'},
    {'file': 'frontend/src/views/finance/SharedExpenseList.vue', 'api': '/finance/shared-expenses/', 'name': '公摊费用'},
    
    # 生产管理 - 剩余
    {'file': 'frontend/src/views/production/QualityInspectionList.vue', 'api': '/production/quality-inspections/', 'name': '质检'},
    {'file': 'frontend/src/views/production/DebugRecordList.vue', 'api': '/production/debug-records/', 'name': '调试记录'},
    {'file': 'frontend/src/views/production/ProcessList.vue', 'api': '/production/processes/', 'name': '工序'},
]


def add_imports(content: str) -> Tuple[str, bool]:
    """添加composable导入"""
    if 'useBatchDelete' in content:
        return content, False
    
    # 查找script setup开始位置
    script_match = re.search(r'<script\s+setup[^>]*>', content)
    if not script_match:
        return content, False
    
    # 找到第一个import语句
    first_import = re.search(r'import\s+', content[script_match.end():])
    if first_import:
        insert_pos = script_match.end() + first_import.start()
        imports = """import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'
"""
        content = content[:insert_pos] + imports + content[insert_pos:]
        return content, True
    
    return content, False


def find_refresh_function(content: str) -> str:
    """查找数据刷新函数名"""
    # 常见的刷新函数名
    patterns = [
        r'const\s+(fetchData|loadData|getData|fetchList|loadList|getList)\s*=',
        r'const\s+(fetch\w+|load\w+|get\w+)\s*=\s*async',
        r'function\s+(fetchData|loadData|getData)\s*\(',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)
    
    return 'fetchData'  # 默认


def add_composable_usage(content: str, config: Dict) -> Tuple[str, bool]:
    """添加composable使用代码"""
    if 'const { canDelete }' in content:
        return content, False
    
    api = config['api']
    name = config['name']
    refresh = find_refresh_function(content)
    
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
    
    # 在第一个const声明后插入（跳过imports后的第一个const）
    # 找到imports结束后的第一个const
    pattern = r"(import[^;]+;\s*\n)(\s*\n*)(const\s+)"
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        insert_pos = match.start(2) + len(match.group(2))
        content = content[:insert_pos] + composable_code + '\n' + content[insert_pos:]
        return content, True
    
    # 备选方案：在script setup标签后添加
    script_match = re.search(r'(<script\s+setup[^>]*>\s*\n)', content)
    if script_match:
        insert_pos = script_match.end()
        # 跳过现有的imports
        remaining = content[insert_pos:]
        last_import = 0
        for m in re.finditer(r"import[^;]+;\s*\n", remaining):
            last_import = m.end()
        if last_import > 0:
            insert_pos += last_import
        content = content[:insert_pos] + composable_code + content[insert_pos:]
        return content, True
    
    return content, False


def add_selection_column(content: str) -> Tuple[str, bool]:
    """添加选择列"""
    if 'type="selection"' in content:
        # 已有选择列，添加v-if控制
        if 'v-if="canDelete"' not in content.split('type="selection"')[0][-100:]:
            content = re.sub(
                r'<el-table-column\s+type="selection"',
                '<el-table-column v-if="canDelete" type="selection"',
                content
            )
            return content, True
        return content, False
    
    # 没有选择列，在第一个el-table-column前添加
    pattern = r'(<el-table[^>]*>\s*\n)(\s*)(<el-table-column)'
    match = re.search(pattern, content)
    if match:
        selection_col = f'{match.group(2)}<el-table-column v-if="canDelete" type="selection" width="55" fixed />\n'
        content = content.replace(
            match.group(0),
            match.group(1) + selection_col + match.group(2) + match.group(3)
        )
        return content, True
    
    return content, False


def add_selection_change_handler(content: str) -> Tuple[str, bool]:
    """添加@selection-change处理"""
    if '@selection-change' in content:
        return content, False
    
    # 找到el-table标签并添加事件
    pattern = r'(<el-table\s+[^>]*)(>)'
    match = re.search(pattern, content)
    if match:
        if '@selection-change' not in match.group(1):
            new_tag = match.group(1) + '\n      @selection-change="handleSelectionChange"\n    ' + match.group(2)
            content = content.replace(match.group(0), new_tag)
            return content, True
    
    return content, False


def add_toolbar(content: str) -> Tuple[str, bool]:
    """添加批量操作工具栏"""
    if 'table-toolbar' in content:
        return content, False
    
    toolbar_html = '''
    <!-- 批量操作工具栏 -->
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
        content = content.replace(match.group(0), toolbar_html + match.group(0))
        return content, True
    
    return content, False


def update_delete_button(content: str) -> Tuple[str, bool]:
    """更新删除按钮"""
    updated = False
    
    # 模式1: handleDelete(row)
    if 'handleDelete(row)' in content and 'deleteRow(row)' not in content:
        content = content.replace('handleDelete(row)', 'deleteRow(row)')
        updated = True
    
    # 模式2: 添加v-if="canDelete"到删除按钮
    delete_button_pattern = r'(<el-button[^>]*?)(@click="deleteRow\(row\)"[^>]*>删除</el-button>)'
    matches = list(re.finditer(delete_button_pattern, content))
    for match in reversed(matches):  # 从后往前替换
        if 'v-if="canDelete"' not in match.group(0):
            new_button = match.group(1) + 'v-if="canDelete" :loading="deleteLoading" ' + match.group(2)
            content = content[:match.start()] + new_button + content[match.end():]
            updated = True
    
    # 模式3: 原始的删除按钮
    delete_button_pattern2 = r'(<el-button[^>]*?)(@click="handleDelete\(row\)"[^>]*>删除</el-button>)'
    matches = list(re.finditer(delete_button_pattern2, content))
    for match in reversed(matches):
        if 'v-if="canDelete"' not in match.group(0):
            new_button = match.group(1) + 'v-if="canDelete" :loading="deleteLoading" ' + match.group(2).replace('handleDelete', 'deleteRow')
            content = content[:match.start()] + new_button + content[match.end():]
            updated = True
    
    return content, updated


def add_styles(content: str) -> Tuple[str, bool]:
    """添加样式"""
    if '.table-toolbar' in content:
        return content, False
    
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
    
    # 查找style标签
    style_match = re.search(r'</style>', content)
    if style_match:
        content = content[:style_match.start()] + style_code + '\n' + content[style_match.start():]
        return content, True
    
    # 如果没有style标签，在文件末尾添加
    if '<style' not in content:
        content += f'\n<style scoped>{style_code}</style>\n'
        return content, True
    
    return content, False


def update_vue_file(file_path: Path, config: Dict) -> bool:
    """更新单个Vue文件"""
    if not file_path.exists():
        print(f"  ❌ 文件不存在")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"  ❌ 读取失败: {e}")
        return False
    
    original_content = content
    changes = []
    
    # 1. 添加imports
    content, updated = add_imports(content)
    if updated:
        changes.append("imports")
    
    # 2. 添加composable使用
    content, updated = add_composable_usage(content, config)
    if updated:
        changes.append("composable")
    
    # 3. 添加选择列
    content, updated = add_selection_column(content)
    if updated:
        changes.append("选择列")
    
    # 4. 添加selection-change处理
    content, updated = add_selection_change_handler(content)
    if updated:
        changes.append("事件处理")
    
    # 5. 添加工具栏
    content, updated = add_toolbar(content)
    if updated:
        changes.append("工具栏")
    
    # 6. 更新删除按钮
    content, updated = update_delete_button(content)
    if updated:
        changes.append("删除按钮")
    
    # 7. 添加样式
    content, updated = add_styles(content)
    if updated:
        changes.append("样式")
    
    if not changes:
        print(f"  ⚪ 已是最新或无需更新")
        return False
    
    # 备份
    backup_path = file_path.with_suffix('.vue.bak3')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(original_content)
    
    # 保存
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  ✅ 已更新: {', '.join(changes)}")
    return True


def main():
    """主函数"""
    print("=" * 70)
    print("批量删除功能 - 更新剩余页面")
    print("=" * 70)
    
    base_path = Path('/home/administrator/erp')
    success = 0
    skip = 0
    fail = 0
    
    for i, config in enumerate(REMAINING_PAGES, 1):
        file_path = base_path / config['file']
        name = config['name']
        
        print(f"\n[{i}/{len(REMAINING_PAGES)}] {name} ({file_path.name})")
        
        try:
            if update_vue_file(file_path, config):
                success += 1
            else:
                skip += 1
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            fail += 1
    
    print("\n" + "=" * 70)
    print(f"更新完成!")
    print(f"  ✅ 成功: {success}")
    print(f"  ⚪ 跳过: {skip}")
    print(f"  ❌ 失败: {fail}")
    print("=" * 70)


if __name__ == '__main__':
    main()
