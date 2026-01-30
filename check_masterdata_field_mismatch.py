#!/usr/bin/env python3
"""
检查 masterdata Vue组件与后端序列化器字段匹配情况
"""
import re
import os
from pathlib import Path

# 定义序列化器字段映射
SERIALIZER_FIELDS = {
    'Customer': [
        'id', 'code', 'name', 'short_name', 'contact_person', 'phone',
        'email', 'address', 'credit_limit', 'payment_terms',
        'invoice_title', 'tax_number', 'bank_name', 'bank_account',
        'registered_address', 'registered_phone',
        'status', 'status_display', 'notes', 'is_deleted', 'created_at', 'updated_at'
    ],
    'Supplier': [
        'id', 'code', 'name', 'short_name', 'contact_person', 'phone',
        'email', 'address', 'payment_terms', 'settlement_method', 'settlement_method_display',
        'invoice_title', 'tax_number', 'bank_name', 'bank_account',
        'registered_address', 'registered_phone',
        'status', 'status_display', 'notes', 'is_deleted', 'created_at', 'updated_at'
    ],
    'Item': [
        'id', 'sku', 'name', 'specification', 'brand', 'model', 'manufacturer', 'origin_country',
        'category', 'category_name', 'item_type', 'item_type_display',
        'unit', 'unit_display',
        'item_property', 'item_property_display', 'abc_class', 'abc_class_display',
        'drawing_no', 'drawing_version', 'material', 'surface_treatment', 'heat_treatment',
        'length', 'width', 'height', 'diameter', 'technical_params',
        'inspection_type', 'inspection_type_display', 'inspection_standard',
        'is_critical', 'is_long_lead', 'can_substitute', 'alternate_items', 'full_specification',
        'standard_cost', 'purchase_price', 'sale_price', 'last_purchase_price',
        'tax_rate', 'tax_rate_display',
        'default_supplier', 'default_supplier_name',
        'min_stock', 'max_stock', 'safety_stock', 'reorder_point', 'economic_order_qty',
        'lead_time', 'default_warehouse', 'default_warehouse_name', 'default_location',
        'description', 'image', 'barcode', 'qr_code', 'weight', 'volume', 'shelf_life',
        'is_active', 'is_deleted', 'created_at', 'updated_at', 'extra_fields'
    ],
    'Warehouse': [
        'id', 'code', 'name', 'warehouse_type', 'type_display', 'address',
        'manager', 'manager_name', 'contact_phone', 'is_active', 'notes',
        'is_deleted', 'created_at', 'updated_at', 'location_count'
    ],
    'WarehouseLocation': [
        'id', 'warehouse', 'warehouse_name', 'warehouse_code',
        'parent', 'parent_name', 'code', 'name', 'full_path',
        'location_type', 'type_display', 'max_weight', 'max_volume',
        'is_active', 'is_pickable', 'is_storable', 'sort_order', 'notes',
        'is_deleted', 'created_at', 'updated_at', 'children_count'
    ],
    'CustomerContact': [
        # 使用 '__all__'，需要从模型推断，但通常包括：
        'id', 'customer', 'customer_name', 'name', 'position', 'role', 'role_display',
        'phone', 'telephone', 'email', 'wechat', 'birthday', 'gender', 'hobbies',
        'is_primary', 'is_active', 'notes', 'created_at', 'updated_at'
    ],
    'CustomerCredit': [
        'id', 'customer', 'customer_name', 'customer_code', 'credit_level', 'level_name', 'level_code',
        'credit_limit', 'used_amount', 'available_credit', 'usage_rate',
        'payment_days', 'status', 'status_display', 'risk_score', 'overdue_times'
    ],
    'CustomerFollowUp': [
        'id', 'customer', 'customer_name', 'follow_type', 'follow_type_display',
        'follow_date', 'follower', 'follower_name', 'subject', 'content',
        'result', 'result_display', 'priority', 'priority_display',
        'next_follow_date', 'next_follow_plan', 'created_at', 'updated_at'
    ]
}

def extract_vue_fields(file_path):
    """从Vue文件中提取使用的字段"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    fields = set()
    
    # 提取 el-table-column 的 prop 属性
    prop_pattern = r'prop=["\']([^"\']+)["\']'
    props = re.findall(prop_pattern, content)
    fields.update(props)
    
    # 提取 el-form-item 的 v-model 绑定
    vmodel_pattern = r'v-model=["\']([^"\']+)["\']'
    vmodels = re.findall(vmodel_pattern, content)
    # 过滤掉 form. 前缀
    for vm in vmodels:
        if vm.startswith('form.'):
            fields.add(vm.replace('form.', ''))
        elif vm.startswith('searchForm.'):
            fields.add(vm.replace('searchForm.', ''))
        else:
            fields.add(vm)
    
    # 提取模板中的字段引用（如 row.field, currentRow.field 等）
    row_field_pattern = r'(?:row|currentRow|current|selected|form|searchForm|bankMatchForm|paymentForm)\.([a-zA-Z_][a-zA-Z0-9_]*)'
    row_fields = re.findall(row_field_pattern, content)
    fields.update(row_fields)
    
    # 提取对象属性访问（如 row.field_name）
    obj_field_pattern = r'\.([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:[|}]|\)|,|;|\s)'
    obj_fields = re.findall(obj_field_pattern, content)
    fields.update(obj_fields)
    
    # 清理字段名（移除可能的函数调用等）
    cleaned_fields = set()
    for field in fields:
        # 移除可能的函数调用、数组访问等
        field = field.split('(')[0].split('[')[0].strip()
        if field and field[0].isalpha() or field[0] == '_':
            cleaned_fields.add(field)
    
    return cleaned_fields

def check_field_mismatch(vue_file, serializer_type):
    """检查Vue文件与序列化器的字段匹配"""
    vue_fields = extract_vue_fields(vue_file)
    backend_fields = set(SERIALIZER_FIELDS.get(serializer_type, []))
    
    # 前端使用但后端未提供的字段
    missing_in_backend = vue_fields - backend_fields
    
    # 过滤掉一些常见的非字段引用（如方法、计算属性等）
    common_non_fields = {
        'id', 'value', 'key', 'index', 'label', 'type', 'status', 'name',
        'length', 'size', 'page', 'total', 'count', 'results', 'data',
        'loading', 'visible', 'dialog', 'form', 'ref', 'row', 'column'
    }
    missing_in_backend = {f for f in missing_in_backend if f not in common_non_fields}
    
    return missing_in_backend, vue_fields, backend_fields

def main():
    base_dir = Path('/home/administrator/erp/frontend/src/views/masterdata')
    results = []
    
    # 定义文件与序列化器的映射
    file_mappings = {
        'CustomerList.vue': 'Customer',
        'SupplierList.vue': 'Supplier',
        'ItemList.vue': 'Item',
        'ItemListUpdated.vue': 'Item',
        'WarehouseList.vue': 'Warehouse',
        'LocationList.vue': 'WarehouseLocation',
        'CustomerContactList.vue': 'CustomerContact',
        'CustomerCredit.vue': 'CustomerCredit',
        'CustomerFollowUp.vue': 'CustomerFollowUp',
    }
    
    for filename, serializer_type in file_mappings.items():
        file_path = base_dir / filename
        if not file_path.exists():
            continue
        
        print(f"\n检查文件: {filename}")
        missing, vue_fields, backend_fields = check_field_mismatch(file_path, serializer_type)
        
        if missing:
            results.append({
                'file': filename,
                'serializer': serializer_type,
                'missing_fields': sorted(missing),
                'vue_fields_count': len(vue_fields),
                'backend_fields_count': len(backend_fields)
            })
            print(f"  发现 {len(missing)} 个不匹配字段:")
            for field in sorted(missing):
                print(f"    - {field}")
        else:
            print(f"  ✓ 字段匹配正常")
    
    # 生成报告
    print("\n" + "="*80)
    print("字段不匹配报告")
    print("="*80)
    
    for result in results:
        print(f"\n文件: {result['file']}")
        print(f"序列化器: {result['serializer']}")
        print(f"前端字段数: {result['vue_fields_count']}")
        print(f"后端字段数: {result['backend_fields_count']}")
        print(f"不匹配字段 ({len(result['missing_fields'])} 个):")
        for field in result['missing_fields']:
            print(f"  - {field}")
        print("\n建议修复方案:")
        print(f"  1. 检查后端序列化器 {result['serializer']} 是否包含这些字段")
        print(f"  2. 如果字段不存在，需要在序列化器中添加")
        print(f"  3. 如果字段名不一致，需要统一命名")
        print("-" * 80)

if __name__ == '__main__':
    main()
