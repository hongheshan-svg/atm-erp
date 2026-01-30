#!/usr/bin/env python3
"""
检查OA模块前端Vue组件与后端API字段不匹配问题
"""
import re
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# 后端序列化器字段定义
BACKEND_SERIALIZERS = {
    'announcement': {
        'list': ['id', 'title', 'summary', 'announcement_type', 'announcement_type_display',
                 'priority', 'priority_display', 'status', 'status_display',
                 'is_top', 'is_popup', 'publish_time', 'expire_time',
                 'view_count', 'publisher_name', 'is_active', 'is_read', 'created_at'],
        'detail': ['id', 'title', 'content', 'summary', 'announcement_type', 'announcement_type_display',
                  'priority', 'priority_display', 'status', 'status_display',
                  'is_top', 'is_popup', 'publish_time', 'expire_time',
                  'target_all', 'target_departments', 'target_roles',
                  'view_count', 'publisher_name', 'created_by_name', 'is_active', 'is_read',
                  'created_at', 'updated_at']
    },
    'asset': {
        'list': ['id', 'asset_no', 'name', 'category', 'category_name',
                 'brand', 'model', 'status', 'status_display',
                 'current_user', 'current_user_name', 'location',
                 'purchase_price', 'current_value'],
        'detail': ['id', 'asset_no', 'name', 'category', 'category_name',
                   'brand', 'model', 'specification', 'serial_no', 'status', 'status_display',
                   'current_user', 'current_user_name', 'supplier_name', 'location',
                   'purchase_date', 'purchase_price', 'warranty_expire_date',
                   'depreciation_years', 'residual_rate', 'current_value', 'notes']
    },
    'vehicle': {
        'list': ['id', 'plate_number', 'vehicle_type', 'type_display', 'brand', 'model',
                 'color', 'seats', 'status', 'status_display', 'current_mileage'],
        'detail': ['id', 'plate_number', 'vehicle_type', 'type_display', 'brand', 'model',
                   'color', 'seats', 'engine_no', 'vin', 'status', 'status_display',
                   'insurance_company', 'insurance_expire_date', 'annual_inspection_date',
                   'next_inspection_date', 'current_mileage', 'manager_name', 'notes']
    },
    'vehicle_request': {
        'list': ['id', 'request_no', 'applicant_name', 'vehicle', 'vehicle_plate',
                 'purpose', 'purpose_display', 'start_time', 'end_time',
                 'departure', 'destination', 'status', 'status_display', 'created_at'],
        'detail': ['id', 'request_no', 'applicant_name', 'vehicle', 'vehicle_plate',
                   'purpose', 'purpose_display', 'start_time', 'end_time',
                   'departure', 'destination', 'passengers', 'purpose_detail',
                   'status', 'status_display', 'approver_name', 'total_cost',
                   'travel_distance', 'start_mileage', 'end_mileage',
                   'fuel_cost', 'toll_cost', 'parking_cost', 'created_at']
    },
    'meeting': {
        'list': ['id', 'meeting_no', 'title', 'meeting_type', 'type_display',
                 'start_time', 'end_time', 'location', 'is_online', 'status', 'status_display',
                 'organizer_name', 'room_name', 'participant_count'],
        'detail': ['id', 'meeting_no', 'title', 'meeting_type', 'type_display',
                   'start_time', 'end_time', 'location', 'meeting_room', 'room_name',
                   'meeting_link', 'is_online', 'agenda', 'status', 'status_display',
                   'organizer', 'organizer_name', 'project', 'project_name',
                   'meeting_participants', 'created_at']
    },
    'schedule': {
        'list': ['id', 'title', 'schedule_type', 'type_display',
                 'start_time', 'end_time', 'all_day', 'location', 'color', 'is_public'],
        'detail': ['id', 'title', 'schedule_type', 'type_display', 'priority',
                   'start_time', 'end_time', 'all_day', 'location', 'description',
                   'color', 'owner', 'owner_name', 'project', 'project_name',
                   'customer', 'customer_name', 'participants', 'participant_names']
    },
    'leave_request': {
        'list': ['id', 'user', 'user_name', 'leave_type', 'leave_type_display',
                 'start_date', 'end_date', 'days', 'reason', 'status', 'status_display',
                 'approver_name', 'created_at'],
        'detail': ['id', 'user', 'user_name', 'leave_type', 'leave_type_display',
                   'start_date', 'end_date', 'start_time', 'end_time', 'days',
                   'reason', 'attachments', 'status', 'status_display',
                   'approver', 'approver_name', 'approved_at', 'approval_remarks',
                   'created_at', 'updated_at']
    },
    'attendance': {
        'list': ['id', 'user', 'attendance_date', 'check_in_time', 'check_out_time',
                 'status', 'status_display', 'work_hours', 'late_minutes', 'early_minutes',
                 'remarks'],
        'detail': ['id', 'user', 'attendance_date', 'check_in_time', 'check_out_time',
                   'check_in_location', 'check_out_location', 'status', 'status_display',
                   'work_hours', 'overtime_hours', 'late_minutes', 'early_minutes', 'remarks']
    }
}

def extract_vue_fields(file_path):
    """从Vue文件中提取字段"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    fields = {
        'table_columns': [],
        'form_fields': [],
        'display_fields': []
    }
    
    # 提取 el-table-column 的 prop 属性
    table_column_pattern = r'<el-table-column[^>]*prop=["\']([^"\']+)["\'][^>]*>'
    fields['table_columns'] = re.findall(table_column_pattern, content)
    
    # 提取 el-form-item 的 v-model 绑定
    form_item_pattern = r'v-model=["\'](?:form|searchForm)\.([^"\']+)["\']'
    fields['form_fields'] = re.findall(form_item_pattern, content)
    
    # 提取数据展示字段（如 {{ item.field }} 或 row.field）
    display_pattern = r'(?:item|row|currentItem|todayRecord|monthSummary|stats|form)\.([a-zA-Z_][a-zA-Z0-9_]*)'
    display_fields = re.findall(display_pattern, content)
    # 去重并过滤常见字段
    common_fields = ['id', 'length', 'value', 'key']
    fields['display_fields'] = [f for f in set(display_fields) if f not in common_fields]
    
    # 提取 searchForm 字段
    search_pattern = r'searchForm\.([a-zA-Z_][a-zA-Z0-9_]*)'
    search_fields = re.findall(search_pattern, content)
    fields['form_fields'].extend(search_fields)
    
    # 提取 form 对象中的字段（从 reactive/form 定义中）
    form_def_pattern = r'(?:form|searchForm|returnForm)\s*[:=]\s*reactive\s*\(\s*\{([^}]+)\}'
    form_def_match = re.search(form_def_pattern, content, re.DOTALL)
    if form_def_match:
        form_content = form_def_match.group(1)
        form_field_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*[:=]'
        form_def_fields = re.findall(form_field_pattern, form_content)
        fields['form_fields'].extend(form_def_fields)
    
    # 去重
    fields['form_fields'] = list(set(fields['form_fields']))
    fields['display_fields'] = list(set(fields['display_fields']))
    
    return fields

def get_backend_fields(component_name):
    """根据组件名获取后端字段"""
    component_map = {
        'AnnouncementList': ('announcement', 'list'),
        'AssetList': ('asset', 'list'),
        'VehicleList': ('vehicle', 'list'),
        'VehicleRequestList': ('vehicle_request', 'list'),
        'MeetingList': ('meeting', 'list'),
        'ScheduleList': ('schedule', 'list'),
        'LeaveList': ('leave_request', 'list'),
        'Attendance': ('attendance', 'list'),
    }
    
    if component_name in component_map:
        serializer_name, view_type = component_map[component_name]
        return BACKEND_SERIALIZERS.get(serializer_name, {}).get(view_type, [])
    return []

def check_field_mismatch():
    """检查字段不匹配"""
    frontend_dir = Path('/home/administrator/erp/frontend/src/views/oa')
    results = []
    
    vue_files = list(frontend_dir.glob('*.vue'))
    
    for vue_file in vue_files:
        if vue_file.name.endswith('.bak3'):
            continue
            
        component_name = vue_file.stem
        print(f"检查文件: {component_name}")
        
        try:
            vue_fields = extract_vue_fields(vue_file)
            backend_fields = get_backend_fields(component_name)
            
            # 合并前端使用的所有字段
            all_frontend_fields = set()
            all_frontend_fields.update(vue_fields['table_columns'])
            all_frontend_fields.update(vue_fields['form_fields'])
            all_frontend_fields.update(vue_fields['display_fields'])
            
            # 过滤掉一些明显不是字段的项
            all_frontend_fields = {f for f in all_frontend_fields 
                                  if not f.startswith('$') and f not in ['length', 'value', 'key']}
            
            if not backend_fields:
                results.append({
                    'file': component_name,
                    'status': 'no_backend_mapping',
                    'frontend_fields': sorted(all_frontend_fields),
                    'backend_fields': []
                })
                continue
            
            backend_field_set = set(backend_fields)
            
            # 找出前端使用但后端未提供的字段
            missing_in_backend = all_frontend_fields - backend_field_set
            
            # 找出后端提供但前端未使用的字段（可选，用于参考）
            unused_backend_fields = backend_field_set - all_frontend_fields
            
            if missing_in_backend:
                results.append({
                    'file': component_name,
                    'status': 'mismatch',
                    'frontend_fields': sorted(all_frontend_fields),
                    'backend_fields': backend_fields,
                    'missing_in_backend': sorted(missing_in_backend),
                    'unused_backend_fields': sorted(unused_backend_fields)
                })
            else:
                results.append({
                    'file': component_name,
                    'status': 'ok',
                    'frontend_fields': sorted(all_frontend_fields),
                    'backend_fields': backend_fields
                })
                
        except Exception as e:
            results.append({
                'file': component_name,
                'status': 'error',
                'error': str(e)
            })
    
    return results

def generate_report(results):
    """生成报告"""
    report_lines = []
    report_lines.append("# OA模块前端字段与后端API不匹配检查报告\n")
    report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report_lines.append("=" * 80 + "\n\n")
    
    mismatch_count = 0
    
    for result in results:
        report_lines.append(f"## {result['file']}.vue\n")
        
        if result['status'] == 'error':
            report_lines.append(f"**错误**: {result.get('error', '未知错误')}\n\n")
            continue
        
        if result['status'] == 'no_backend_mapping':
            report_lines.append("**状态**: ⚠️ 未找到对应的后端序列化器映射\n")
            report_lines.append(f"**前端使用的字段**: {', '.join(result['frontend_fields'])}\n\n")
            continue
        
        if result['status'] == 'ok':
            report_lines.append("**状态**: ✅ 字段匹配正常\n\n")
        else:
            mismatch_count += 1
            report_lines.append("**状态**: ❌ 发现字段不匹配\n\n")
            
            report_lines.append("### 问题字段列表\n")
            report_lines.append("| 前端字段名 | 后端字段名 | 状态 |\n")
            report_lines.append("|-----------|----------|------|\n")
            
            for field in result.get('missing_in_backend', []):
                # 尝试找到可能的对应字段
                possible_match = None
                for backend_field in result['backend_fields']:
                    if field.lower() in backend_field.lower() or backend_field.lower() in field.lower():
                        possible_match = backend_field
                        break
                
                if possible_match:
                    report_lines.append(f"| `{field}` | `{possible_match}` | ⚠️ 可能对应 |\n")
                else:
                    report_lines.append(f"| `{field}` | - | ❌ 后端未提供 |\n")
            
            report_lines.append("\n### 建议修复方案\n")
            report_lines.append("1. **后端未提供的字段**:\n")
            for field in result.get('missing_in_backend', []):
                report_lines.append(f"   - `{field}`: 检查后端序列化器是否需要添加此字段，或前端是否应该使用其他字段名\n")
            
            if result.get('unused_backend_fields'):
                report_lines.append("\n2. **后端提供但前端未使用的字段**（参考）:\n")
                for field in result['unused_backend_fields'][:10]:  # 只显示前10个
                    report_lines.append(f"   - `{field}`\n")
        
        report_lines.append("\n" + "-" * 80 + "\n\n")
    
    report_lines.append(f"\n## 总结\n")
    report_lines.append(f"- 检查文件数: {len(results)}\n")
    report_lines.append(f"- 发现不匹配: {mismatch_count}\n")
    report_lines.append(f"- 正常匹配: {len([r for r in results if r.get('status') == 'ok'])}\n")
    
    return ''.join(report_lines)

if __name__ == '__main__':
    print("开始检查OA模块字段不匹配问题...")
    results = check_field_mismatch()
    report = generate_report(results)
    
    output_file = '/home/administrator/erp/OA_FIELD_MISMATCH_REPORT.md'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n检查完成！报告已保存到: {output_file}")
    print(f"\n发现 {len([r for r in results if r.get('status') == 'mismatch'])} 个文件存在字段不匹配问题")
