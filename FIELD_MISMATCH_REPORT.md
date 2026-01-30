# 前端Vue组件与后端API字段不匹配检查报告

## 检查范围
- **前端目录**：`/home/administrator/erp/frontend/src/views/purchase/`
- **后端序列化器**：`/home/administrator/erp/backend/apps/purchase/serializers.py` 和 `rfq_serializers.py`

---

## 检查结果汇总

### ✅ 无问题的文件
1. **RequestList.vue** - 采购申请列表
2. **OrderList.vue** - 采购订单列表
3. **PurchaseOrderDetail.vue** - 采购订单详情
4. **RFQList.vue** - 询价单列表
5. **ComparisonList.vue** - 比价分析列表（创建时使用`rfq_id`是正确的，因为`CreateComparisonSerializer`使用此字段）

### ❌ 发现问题的文件

---

## 1. GoodsReceiptList.vue

### 问题描述
收货单列表表格中使用了 `created_by_name` 字段，但后端 `GoodsReceiptSerializer` 未提供此字段。

### 详细位置
**文件**：`/home/administrator/erp/frontend/src/views/purchase/GoodsReceiptList.vue`  
**行号**：61  
**代码**：
```vue
<el-table-column prop="created_by_name" label="创建人" width="100" />
```

### 后端序列化器
**文件**：`/home/administrator/erp/backend/apps/purchase/serializers.py`  
**类名**：`GoodsReceiptSerializer`  
**当前字段列表**：
```python
fields = [
    'id', 'receipt_no', 'po', 'po_no', 'purchase_order_no', 'supplier_name', 
    'warehouse', 'warehouse_name',
    'receipt_date', 'status', 'status_display', 'notes', 'lines',
    'is_deleted', 'created_at', 'updated_at'
]
```

### 问题字段
- **前端字段名**：`created_by_name`
- **后端字段名**：无（缺失）
- **影响**：列表无法显示创建人信息

### 建议修复方案

#### 方案1：在后端序列化器中添加字段（推荐）

在 `GoodsReceiptSerializer` 类中添加：

```python
class GoodsReceiptSerializer(serializers.ModelSerializer):
    """GoodsReceipt serializer."""
    po_no = serializers.CharField(source='po.order_no', read_only=True)
    purchase_order_no = serializers.CharField(source='po.order_no', read_only=True)
    supplier_name = serializers.CharField(source='po.supplier.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()  # 新增
    lines = GoodsReceiptLineSerializer(many=True, read_only=True)
    
    def get_created_by_name(self, obj):
        """获取创建人姓名"""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return ''
    
    class Meta:
        model = GoodsReceipt
        fields = [
            'id', 'receipt_no', 'po', 'po_no', 'purchase_order_no', 'supplier_name', 
            'warehouse', 'warehouse_name',
            'receipt_date', 'status', 'status_display', 'notes', 'lines',
            'created_by', 'created_by_name',  # 添加 created_by_name
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['receipt_no', 'created_at', 'updated_at']
```

#### 方案2：前端移除该列（不推荐）
如果不需要显示创建人，可以移除该列。

---

## 修复步骤

1. **修改后端序列化器**
   - 打开 `/home/administrator/erp/backend/apps/purchase/serializers.py`
   - 在 `GoodsReceiptSerializer` 类中添加 `created_by_name` 字段
   - 在 `Meta.fields` 中添加 `'created_by_name'`

2. **测试验证**
   - 重启后端服务
   - 访问收货单列表页面
   - 确认"创建人"列能正常显示

---

## 其他说明

### ComparisonList.vue 中的 rfq_id 字段
前端在创建比价表单中使用 `rfq_id` 字段是正确的，因为：
- `CreateComparisonSerializer`（用于创建请求）使用 `rfq_id` 字段
- `QuotationComparisonSerializer`（用于返回数据）使用 `rfq` 字段
- 这是正常的，创建请求和返回数据的序列化器可以不同

### 字段命名一致性
大部分字段命名保持一致，前端使用的字段名与后端提供的字段名匹配良好。

---

## 总结

**发现的问题数量**：1个  
**严重程度**：中等（影响列表显示，但不影响核心功能）  
**修复优先级**：中（建议尽快修复以完善用户体验）

**建议**：优先修复 `GoodsReceiptSerializer` 中缺失的 `created_by_name` 字段。
