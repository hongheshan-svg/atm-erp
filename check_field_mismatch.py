#!/usr/bin/env python3
"""
检查前端Vue组件与后端API序列化器字段不匹配问题
"""
import re
import os
from pathlib import Path
from collections import defaultdict

# 后端序列化器字段定义
SERIALIZER_FIELDS = {
    'PurchaseRequest': [
        'id', 'request_no', 'project', 'project_name', 'supplier', 'supplier_name',
        'requestor', 'requestor_name', 'request_date', 'required_date', 'status', 'status_display',
        'tax_rate', 'tax_rate_display', 'total_amount', 'tax_amount', 'total_with_tax',
        'notes', 'lines', 'is_deleted', 'created_at', 'updated_at', 'budget_info'
    ],
    'PurchaseRequestLine': [
        'id', 'pr', 'item', 'item_sku', 'item_name', 'item_unit', 'item_property',
        'qty', 'estimated_price', 'line_amount', 'required_date', 'project', 'project_name',
        'bom_item', 'bom_item_id', 'bom_planned_qty',
        'is_critical', 'is_long_lead', 'function_module',
        'notes', 'is_deleted'
    ],
    'PurchaseOrder': [
        'id', 'order_no', 'supplier', 'supplier_name', 'project', 'project_name',
        'order_date', 'delivery_date', 'expected_date', 'status', 'status_display',
        'tax_rate', 'tax_rate_display', 'total_amount', 'tax_amount', 'total_with_tax',
        'payment_terms', 'payment_terms_display', 'payment_method', 'payment_method_display',
        'payment_terms_detail', 'notes', 'lines', 'is_deleted', 
        'created_by', 'created_by_name', 'created_at', 'updated_at'
    ],
    'PurchaseOrderLine': [
        'id', 'po', 'item', 'item_sku', 'item_name', 'item_unit', 'unit', 'item_property',
        'specification',
        'qty', 'unit_price', 'line_amount', 'received_qty', 'remaining_qty',
        'bom_item', 'bom_item_id', 'bom_planned_qty', 'bom_project_code',
        'is_critical', 'is_long_lead', 'function_module',
        'drawing_no', 'technical_requirement',
        'notes', 'is_deleted'
    ],
    'GoodsReceipt': [
        'id', 'receipt_no', 'po', 'po_no', 'purchase_order_no', 'supplier_name', 
        'warehouse', 'warehouse_name',
        'receipt_date', 'status', 'status_display', 'notes', 'lines',
        'is_deleted', 'created_at', 'updated_at'
    ],
    'GoodsReceiptLine': [
        'id', 'receipt', 'po_line', 'item', 'item_sku', 'sku', 'item_name', 'item_unit',
        'qty', 'ordered_qty', 'received_qty',
        'quality_status', 'quality_status_display', 'notes', 'is_deleted'
    ],
    'RFQ': [
        'id', 'rfq_no', 'project', 'project_name', 'request_date',
        'response_deadline', 'status', 'status_display', 'notes',
        'lines', 'supplier_rfqs', 'created_at', 'updated_at'
    ],
    'RFQLine': [
        'id', 'rfq', 'item', 'item_name', 'item_sku', 'qty',
        'required_date', 'specifications', 'created_at', 'updated_at'
    ],
    'QuotationComparison': [
        'id', 'comparison_no', 'rfq', 'rfq_no', 'project_name',
        'weight_price', 'weight_quality', 'weight_delivery', 'weight_service',
        'recommended_quotation', 'recommended_supplier', 'recommendation_reason',
        'min_price', 'max_price', 'avg_price',
        'status', 'status_display',
        'approved_by', 'approved_by_name', 'approved_at',
        'notes', 'scores', 'supplier_count',
        'created_at', 'updated_at'
    ],
}

def extract_vue_fields(file_path):
    """从Vue文件中提取字段"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    fields = set()
    
    # 提取 el-table-column 的 prop 属性
    prop_pattern = r'prop=["\']([^"\']+)["\']'
    props = re.findall(prop_pattern, content)
    fields.update(props)
    
    # 提取 v-model 绑定的字段
    vmodel_pattern = r'v-model=["\']([^"\']+)["\']'
    vmodels = re.findall(vmodel_pattern, content)
    for vm in vmodels:
        # 处理嵌套字段，如 form.supplier, row.item_name
        parts = vm.split('.')
        if len(parts) > 1:
            fields.add(parts[-1])  # 只取最后一部分
        else:
            fields.add(vm)
    
    # 提取数据访问字段，如 row.field, data.field
    data_access_pattern = r'(?:row|data|line|item|order|receipt|form|current)\.([a-zA-Z_][a-zA-Z0-9_]*)'
    data_fields = re.findall(data_access_pattern, content)
    fields.update(data_fields)
    
    # 提取模板中的字段引用
    template_pattern = r'\{\{\s*(?:row|data|line|item|order|receipt|form|current)\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
    template_fields = re.findall(template_pattern, content)
    fields.update(template_fields)
    
    return fields

def check_file(file_path, serializer_type):
    """检查单个文件"""
    if not os.path.exists(file_path):
        return None
    
    vue_fields = extract_vue_fields(file_path)
    backend_fields = set(SERIALIZER_FIELDS.get(serializer_type, []))
    
    # 找出前端使用但后端未提供的字段
    missing_in_backend = vue_fields - backend_fields
    
    # 过滤掉一些常见的非数据字段
    filtered_missing = set()
    ignore_patterns = ['index', 'label', 'width', 'align', 'fixed', 'type', 'size', 
                      'loading', 'saving', 'dialog', 'visible', 'title', 'ref',
                      'rules', 'pagination', 'search', 'query', 'params', 'page',
                      'pageSize', 'total', 'count', 'results', 'data', 'response']
    
    for field in missing_in_backend:
        if not any(ignore in field.lower() for ignore in ignore_patterns):
            # 检查是否是嵌套字段的一部分
            if '.' not in field and field not in ['id', 'value', 'key', 'name', 'label']:
                filtered_missing.add(field)
    
    return {
        'vue_fields': vue_fields,
        'backend_fields': backend_fields,
        'missing_in_backend': filtered_missing
    }

def main():
    """主函数"""
    frontend_dir = Path('/home/administrator/erp/frontend/src/views/purchase')
    
    # 文件映射：Vue文件 -> 对应的序列化器类型
    file_mappings = {
        'RequestList.vue': ('PurchaseRequest', 'PurchaseRequestLine'),
        'OrderList.vue': ('PurchaseOrder', 'PurchaseOrderLine'),
        'PurchaseOrderDetail.vue': ('PurchaseOrder', 'PurchaseOrderLine'),
        'GoodsReceiptList.vue': ('GoodsReceipt', 'GoodsReceiptLine'),
        'RFQList.vue': ('RFQ', 'RFQLine'),
        'ComparisonList.vue': ('QuotationComparison',),
    }
    
    results = []
    
    for vue_file, serializer_types in file_mappings.items():
        file_path = frontend_dir / vue_file
        if not file_path.exists():
            continue
        
        print(f"\n检查文件: {vue_file}")
        print("=" * 80)
        
        for serializer_type in serializer_types:
            result = check_file(file_path, serializer_type)
            if result and result['missing_in_backend']:
                results.append({
                    'file': vue_file,
                    'serializer': serializer_type,
                    'missing_fields': sorted(result['missing_in_backend'])
                })
                print(f"\n序列化器: {serializer_type}")
                print(f"前端使用但后端未提供的字段:")
                for field in sorted(result['missing_in_backend']):
                    print(f"  - {field}")
    
    # 生成报告
    print("\n\n" + "=" * 80)
    print("检查报告")
    print("=" * 80)
    
    if not results:
        print("\n✓ 未发现字段不匹配问题")
    else:
        print(f"\n发现 {len(results)} 个文件存在字段不匹配问题:\n")
        for result in results:
            print(f"\n文件: {result['file']}")
            print(f"序列化器: {result['serializer']}")
            print(f"问题字段:")
            for field in result['missing_fields']:
                print(f"  - {field}")
            print()

if __name__ == '__main__':
    main()
