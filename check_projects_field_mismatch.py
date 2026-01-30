#!/usr/bin/env python3
"""
检查前端Vue组件与后端API字段不匹配问题
"""
import re
import os
from pathlib import Path
from collections import defaultdict

# 后端序列化器字段映射
SERIALIZER_FIELDS = {
    'ProjectSerializer': [
        'id', 'code', 'name', 'customer', 'customer_name', 
        'sales_order', 'sales_order_no',
        'manager', 'manager_name',
        'start_date', 'end_date', 'status', 'status_display', 'budget_total',
        'budget_material', 'budget_labor', 'budget_expense', 'description', 'notes',
        'actual_material_cost', 'actual_labor_cost', 'actual_expense_cost',
        'total_actual_cost', 'actual_cost', 'material_cost', 'labor_cost',
        'revenue', 'profit',
        'is_deleted', 'created_by', 'created_by_name', 'created_at', 'updated_at'
    ],
    'ProjectMemberSerializer': [
        'id', 'project', 'project_name', 'user', 'user_name', 'user_email', 
        'user_department', 'role', 'hourly_rate', 'allocated_hours', 'actual_hours',
        'total_hours', 'labor_cost', 'join_date', 'can_view_salary',
        'is_active', 'is_deleted', 'created_at', 'updated_at'
    ],
    'ProjectTaskSerializer': [
        'id', 'project', 'project_name', 'parent', 'code', 'name',
        'assignee', 'assignee_name', 'planned_hours', 'actual_hours',
        'progress_percent', 'status', 'status_display', 'start_date', 'end_date',
        'description', 'sort_order', 'is_deleted', 'created_at', 'updated_at',
        'time_log_count'
    ],
    'ProjectBOMSerializer': [
        'id', 'project', 'project_code', 'project_name', 
        'item', 'item_sku', 'item_code', 'item_name',
        'item_specification', 'specification', 'item_unit', 'unit', 
        'item_type', 'item_brand', 'item_model', 'item_material',
        'item_lead_time', 'item_standard_cost',
        'item_property', 'item_property_display', 'effective_item_property',
        'status', 'status_display', 'priority', 'priority_display',
        'planned_qty', 'actual_qty', 'unit_qty', 'scrap_rate',
        'estimated_cost', 'target_cost', 'actual_cost', 'total_cost',
        'version_brand', 'version_brand_display', 'has_drawing', 'has_drawing_display',
        'drawing', 'drawing_name', 'drawing_no', 'drawing_version',
        'material_spec', 'surface_treatment', 'technical_requirement',
        'work_center', 'work_center_name', 'process', 'process_name',
        'assembly_sequence', 'assembly_instruction',
        'requirement_id_ref', 'function_module',
        'required_date', 'latest_order_date', 'requester', 'requester_name',
        'description', 'notes',
        'order_status', 'order_status_display',
        'supplier', 'supplier_name', 'supplier_code',
        'delivery_date', 'actual_delivery_date',
        'purchase_request', 'purchase_request_no', 'pr_qty',
        'ordered_qty', 'shipped_qty', 'received_qty', 'returned_qty',
        'issued_qty', 'reserved_qty',
        'purchase_order', 'purchase_order_no',
        'shortage_qty', 'is_overdue',
        'inspection_required', 'inspection_passed', 'inspection_notes',
        'parent', 'parent_name', 'level', 'sort_order',
        'children_count', 'has_children', 'children',
        'is_critical', 'is_long_lead',
        'quote_status', 'quote_status_display',
        'quote_supplier', 'quote_supplier_name', 'quote_supplier_code',
        'price_with_tax', 'price_without_tax', 'tax_rate',
        'quote_delivery_days', 'quote_date', 'quote_notes',
        'extra_fields',
        'is_deleted', 'created_at', 'updated_at'
    ],
    'TimeLogSerializer': [
        'id', 'project', 'project_name', 'task', 'task_name', 'user', 'user_name',
        'date', 'hours', 'description', 'status', 'status_display',
        'is_deleted', 'created_at', 'updated_at'
    ],
    'ECNSerializer': [
        'id', 'ecn_no', 'project', 'project_name', 'project_code',
        'title', 'change_type', 'change_type_display',
        'priority', 'priority_display', 'status', 'status_display',
        'reason', 'description', 'impact_analysis',
        'cost_impact', 'schedule_impact',
        'requested_by', 'requested_by_name', 'requested_date',
        'approved_by', 'approved_by_name', 'approved_date',
        'implemented_by', 'implemented_by_name', 'implemented_date',
        'implementation_notes', 'items', 'approvals', 'items_count',
        'is_deleted', 'created_at', 'updated_at'
    ],
    'AfterSalesOrderSerializer': [
        'id', 'order_no', 'project', 'project_name', 'project_code',
        'customer', 'customer_name', 'order_type', 'order_type_display',
        'priority', 'priority_display', 'status', 'status_display',
        'title', 'description', 'equipment_info', 'fault_code',
        'contact_person', 'contact_phone', 'site_address',
        'reported_at', 'expected_date', 'resolved_at', 'closed_at',
        'assigned_to', 'assigned_to_name',
        'is_warranty', 'labor_cost', 'travel_cost', 'parts_cost', 'other_cost', 'total_cost',
        'solution', 'root_cause', 'preventive_action',
        'satisfaction_score', 'customer_feedback',
        'service_records', 'spare_parts',
        'service_count', 'total_work_hours',
        'created_at', 'updated_at'
    ],
    'DrawingSerializer': [
        'id', 'drawing_no', 'name', 'version', 'revision',
        'project', 'project_name', 'project_code',
        'item', 'item_name', 'item_sku', 'bom_item',
        'file_type', 'file_type_display', 'file_path', 'file_size',
        'public_share_path', 'status', 'status_display',
        'designer', 'designer_name', 'reviewer', 'reviewer_name',
        'approver', 'approver_name', 'approved_at', 'released_at',
        'change_description', 'notes',
        'is_deleted', 'created_at', 'updated_at'
    ]
}

# 文件到序列化器的映射
FILE_TO_SERIALIZER = {
    'ProjectList.vue': 'ProjectSerializer',
    'ProjectDetail.vue': 'ProjectSerializer',
    'ProjectDashboard.vue': 'ProjectSerializer',
    'MemberList.vue': 'ProjectMemberSerializer',
    'TaskList.vue': 'ProjectTaskSerializer',
    'BOMList.vue': 'ProjectBOMSerializer',
    'TimeLogList.vue': 'TimeLogSerializer',
    'ECNList.vue': 'ECNSerializer',
    'ServiceOrder.vue': 'AfterSalesOrderSerializer',
    'ServiceOrderDetail.vue': 'AfterSalesOrderSerializer',
    'WorkOrderList.vue': 'AfterSalesOrderSerializer',
    'DrawingList.vue': 'DrawingSerializer',
}

def extract_fields_from_vue(file_path):
    """从Vue文件中提取字段（仅提取API返回数据中使用的字段）"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    fields = set()
    
    # 1. 提取 el-table-column 的 prop 属性（这些是显示API返回数据的字段）
    prop_pattern = r'prop=["\']([^"\']+)["\']'
    props = re.findall(prop_pattern, content)
    fields.update(props)
    
    # 2. 提取数据展示字段（如 row.field, project.field, item.field 等）
    # 排除 form.xxx, searchForm.xxx 等表单字段
    data_object_pattern = r'(?:row|project|item|task|member|bom|timeLog|ecn|order|drawing|selectedOrder|currentProject|currentTask)\.([a-zA-Z_][a-zA-Z0-9_]*)'
    data_fields = re.findall(data_object_pattern, content)
    fields.update(data_fields)
    
    # 3. 提取 el-descriptions-item 中使用的字段
    desc_pattern = r'{{[^}]*\.([a-zA-Z_][a-zA-Z0-9_]*)'
    desc_matches = re.findall(desc_pattern, content)
    # 只保留在 el-descriptions-item 标签内的字段
    desc_sections = re.findall(r'<el-descriptions-item[^>]*>.*?</el-descriptions-item>', content, re.DOTALL)
    for section in desc_sections:
        section_fields = re.findall(desc_pattern, section)
        fields.update(section_fields)
    
    # 4. 提取 el-statistic 中使用的字段
    stat_pattern = r':value=["\']([^"\']+)["\']|:value="([^"]+)"'
    stat_matches = re.findall(stat_pattern, content)
    for match in stat_matches:
        value = match[0] or match[1]
        # 提取字段名（排除表达式）
        field_match = re.search(r'\.([a-zA-Z_][a-zA-Z0-9_]*)', value)
        if field_match:
            fields.add(field_match.group(1))
    
    # 过滤掉明显不是API字段的内容
    filtered_fields = set()
    exclude_prefixes = ['form', 'searchForm', 'timeLogForm', 'dispatchForm', 'importOptions', 'queryParams']
    exclude_fields = {
        # 前端状态变量
        'dialogVisible', 'detailVisible', 'attachmentDialogVisible', 'importDialogVisible',
        'copyDialogVisible', 'quoteImportDialogVisible', 'materialCheckDialogVisible',
        'approvalDialogVisible', 'timeLogVisible', 'dispatchDialogVisible',
        'selectedProject', 'selectedProjectId', 'copySourceProject', 'currentProject',
        'currentTask', 'selectedOrder', 'selectedRows', 'selectedUserInfo',
        'filterHasDrawing', 'filterItemType', 'filterBrand', 'searchKeyword',
        'approvalComment', 'implementationNotes',
        # 单字母变量（通常是临时变量）
        's', 'n', 'l', 'y', 'i', 'j', 'k', 'm', 'x', 'z',
        # 方法名
        'toLocaleString', 'getStatusType', 'getStatusLabel', 'getRoleType', 'getRoleLabel',
        # HTML/Vue属性
        'ref', 'model', 'visible', 'title', 'width', 'height', 'style', 'class',
        'id', 'key', 'value', 'label', 'type', 'size', 'disabled', 'loading',
        # 其他前端变量
        'created', 'updated', 'items_created', 'net_demand', 'shortage', 'stock_qty',
        'shortage_value', 'progress', 'is_overdue', 'planned_start', 'planned_end',
        'dispatches', 'location', 'requirements', 'estimated_hours', 'service_address',
        'contact_name', 'code', 'name', 'sku', 'brand', 'unit_display', 'item_type_display',
        'standard_cost', 'notes', 'parent_id', 'level', 'children', 'user', 'user_name',
        'username', 'last_name', 'first_name', 'planned_days', 'total_items', 'estimated_cost'
    }
    
    for field in fields:
        # 排除带前缀的字段
        if any(field.startswith(prefix + '.') for prefix in exclude_prefixes):
            continue
        # 排除单字母或排除列表中的字段
        if len(field) <= 1 or field in exclude_fields:
            continue
        # 只保留看起来像API字段的（字母数字下划线，不以数字开头）
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', field):
            filtered_fields.add(field)
    
    return filtered_fields

def find_mismatches(frontend_fields, serializer_fields, file_name):
    """找出前端字段与后端字段的不匹配"""
    mismatches = []
    
    # 创建后端字段集合（包含别名）
    backend_fields = set(serializer_fields)
    
    # 检查前端字段是否在后端存在
    for field in frontend_fields:
        if field not in backend_fields:
            # 检查是否有类似的字段（忽略大小写）
            similar = [f for f in backend_fields if f.lower() == field.lower()]
            if similar:
                mismatches.append({
                    'type': 'case_mismatch',
                    'frontend': field,
                    'backend': similar[0],
                    'suggestion': f'将前端字段 "{field}" 改为 "{similar[0]}"'
                })
            else:
                mismatches.append({
                    'type': 'missing',
                    'frontend': field,
                    'backend': None,
                    'suggestion': f'后端序列化器中未找到字段 "{field}"，请检查是否需要添加或使用其他字段名'
                })
    
    return mismatches

def analyze_vue_file(file_path):
    """分析单个Vue文件"""
    file_name = os.path.basename(file_path)
    
    # 确定对应的序列化器
    serializer_name = FILE_TO_SERIALIZER.get(file_name)
    if not serializer_name:
        # 尝试通过文件名推断
        if 'project' in file_name.lower() and 'list' in file_name.lower():
            serializer_name = 'ProjectSerializer'
        elif 'member' in file_name.lower():
            serializer_name = 'ProjectMemberSerializer'
        elif 'task' in file_name.lower():
            serializer_name = 'ProjectTaskSerializer'
        elif 'bom' in file_name.lower():
            serializer_name = 'ProjectBOMSerializer'
        elif 'time' in file_name.lower() or 'log' in file_name.lower():
            serializer_name = 'TimeLogSerializer'
        elif 'ecn' in file_name.lower():
            serializer_name = 'ECNSerializer'
        elif 'service' in file_name.lower() or 'order' in file_name.lower():
            serializer_name = 'AfterSalesOrderSerializer'
        elif 'drawing' in file_name.lower():
            serializer_name = 'DrawingSerializer'
        else:
            return None
    
    serializer_fields = SERIALIZER_FIELDS.get(serializer_name, [])
    if not serializer_fields:
        return None
    
    # 提取前端字段
    frontend_fields = extract_fields_from_vue(file_path)
    
    # 找出不匹配
    mismatches = find_mismatches(frontend_fields, serializer_fields, file_name)
    
    return {
        'file': file_name,
        'serializer': serializer_name,
        'frontend_fields': sorted(frontend_fields),
        'mismatches': mismatches
    }

def main():
    """主函数"""
    frontend_dir = Path('/home/administrator/erp/frontend/src/views/projects')
    
    results = []
    
    # 遍历所有Vue文件
    for vue_file in frontend_dir.glob('*.vue'):
        # 跳过备份文件
        if '.bak' in vue_file.name or '.safe_bak' in vue_file.name:
            continue
        
        print(f'分析文件: {vue_file.name}...')
        result = analyze_vue_file(vue_file)
        if result:
            results.append(result)
    
    # 生成报告
    report_lines = []
    report_lines.append('# 前端Vue组件与后端API字段不匹配检查报告\n')
    report_lines.append(f'检查时间: {__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
    report_lines.append('---\n\n')
    
    total_mismatches = 0
    
    for result in results:
        if not result['mismatches']:
            continue
        
        total_mismatches += len(result['mismatches'])
        report_lines.append(f'## {result["file"]}\n')
        report_lines.append(f'**对应序列化器**: `{result["serializer"]}`\n\n')
        
        # 按类型分组显示
        missing_fields = [m for m in result['mismatches'] if m['type'] == 'missing']
        case_mismatches = [m for m in result['mismatches'] if m['type'] == 'case_mismatch']
        
        if missing_fields:
            report_lines.append('### ❌ 后端未提供的字段\n')
            for m in missing_fields:
                report_lines.append(f'- **前端字段**: `{m["frontend"]}`\n')
                report_lines.append(f'  - 建议: {m["suggestion"]}\n')
            report_lines.append('\n')
        
        if case_mismatches:
            report_lines.append('### ⚠️ 字段名不一致（大小写问题）\n')
            for m in case_mismatches:
                report_lines.append(f'- **前端**: `{m["frontend"]}` → **后端**: `{m["backend"]}`\n')
                report_lines.append(f'  - 建议: {m["suggestion"]}\n')
            report_lines.append('\n')
        
        # 显示前端使用的所有字段（用于参考）
        report_lines.append('### 📋 前端使用的字段列表\n')
        report_lines.append('```\n')
        report_lines.append(', '.join(result['frontend_fields']))
        report_lines.append('\n```\n\n')
        report_lines.append('---\n\n')
    
    if total_mismatches == 0:
        report_lines.append('✅ **未发现字段不匹配问题！**\n')
    else:
        report_lines.insert(2, f'**总计发现 {total_mismatches} 个字段不匹配问题**\n\n')
    
    # 保存报告
    report_path = Path('/home/administrator/erp/PROJECTS_FIELD_MISMATCH_REPORT.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.writelines(report_lines)
    
    print(f'\n检查完成！发现 {total_mismatches} 个字段不匹配问题')
    print(f'报告已保存到: {report_path}')
    
    # 同时输出到控制台
    print('\n' + '='*80)
    print(''.join(report_lines))
    print('='*80)

if __name__ == '__main__':
    main()
