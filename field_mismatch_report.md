# 前端Vue组件与后端API字段不匹配检查报告

## 检查范围
- 前端目录：`/home/administrator/erp/frontend/src/views/purchase/`
- 后端序列化器：`/home/administrator/erp/backend/apps/purchase/serializers.py`

---

## 1. PurchaseOrderDetail.vue

### 问题字段

#### 订单明细表格（PurchaseOrderLine）
- **`unit`** - 前端使用 `prop="unit"`，后端提供 `unit` 字段（兼容字段）✓ 已提供
- **`specification`** - 前端使用 `prop="specification"`，后端提供 `specification` 字段 ✓ 已提供
- **`item_sku`** - 前端使用 `prop="item_sku"`，后端提供 `item_sku` 字段 ✓ 已提供
- **`item_name`** - 前端使用 `prop="item_name"`，后端提供 `item_name` 字段 ✓ 已提供
- **`qty`** - 前端使用 `prop="qty"`，后端提供 `qty` 字段 ✓ 已提供
- **`received_qty`** - 前端使用 `prop="received_qty"`，后端提供 `received_qty` 字段 ✓ 已提供
- **`unit_price`** - 前端使用 `prop="unit_price"`，后端提供 `unit_price` 字段 ✓ 已提供

**结论：无问题**

---

## 2. OrderList.vue

### 问题字段

#### 订单明细表格（PurchaseOrderLine）
前端在表格中使用的字段：
- `item` - 用于选择物料（表单字段，非显示字段）✓
- `qty` - ✓ 已提供
- `unit_price` - ✓ 已提供

**结论：无问题**

---

## 3. GoodsReceiptList.vue

### 问题字段

#### 收货单列表（GoodsReceipt）
- **`purchase_order_no`** - 前端使用 `prop="purchase_order_no"`，后端提供 `purchase_order_no` 字段（兼容字段）✓ 已提供
- **`created_by_name`** - 前端使用 `prop="created_by_name"`，后端未提供此字段 ✗

#### 收货明细表格（GoodsReceiptLine）
- **`item_sku`** - ✓ 已提供
- **`item_name`** - ✓ 已提供
- **`ordered_qty`** - ✓ 已提供（SerializerMethodField）
- **`received_qty`** - ✓ 已提供（SerializerMethodField）
- **`qty`** - ✓ 已提供
- **`quality_status`** - ✓ 已提供

**问题：**
- `created_by_name` 字段在 GoodsReceiptSerializer 中缺失

**建议修复方案：**
在 `GoodsReceiptSerializer` 中添加：
```python
created_by_name = serializers.SerializerMethodField()

def get_created_by_name(self, obj):
    if obj.created_by:
        return obj.created_by.get_full_name() or obj.created_by.username
    return ''
```

---

## 4. RequestList.vue

### 问题字段

#### 采购申请列表（PurchaseRequest）
所有使用的字段都在后端序列化器中提供 ✓

#### 采购申请明细（PurchaseRequestLine）
所有使用的字段都在后端序列化器中提供 ✓

**结论：无问题**

---

## 5. RFQList.vue

### 问题字段

#### 询价单列表（RFQ）
- **`rfq_no`** - ✓ 已提供
- **`project_name`** - ✓ 已提供
- **`request_date`** - ✓ 已提供
- **`response_deadline`** - ✓ 已提供
- **`status_display`** - ✓ 已提供

#### 询价明细（RFQLine）
- **`item`** - ✓ 已提供（表单字段）
- **`qty`** - ✓ 已提供
- **`required_date`** - ✓ 已提供

**结论：无问题**

---

## 6. ComparisonList.vue

### 问题字段

#### 比价分析（QuotationComparison）
- **`rfq_id`** - 前端在创建表单中使用 `v-model="createForm.rfq_id"`，但后端 `QuotationComparisonSerializer` 中没有 `rfq_id` 字段，只有 `rfq` 字段 ✗

**问题：**
- `rfq_id` 字段在 QuotationComparisonSerializer 中缺失

**建议修复方案：**
在 `QuotationComparisonSerializer` 中添加：
```python
rfq_id = serializers.IntegerField(source='rfq.id', read_only=True)
```

或者在创建时使用 `rfq` 字段而不是 `rfq_id`。

---

## 总结

### 发现的问题

1. **GoodsReceiptList.vue**
   - 字段：`created_by_name`
   - 位置：收货单列表表格
   - 后端序列化器：`GoodsReceiptSerializer`
   - 状态：缺失

2. **ComparisonList.vue**
   - 字段：`rfq_id`
   - 位置：创建比价表单
   - 后端序列化器：`QuotationComparisonSerializer`
   - 状态：缺失（但有 `rfq` 字段）

### 建议修复优先级

**高优先级：**
1. GoodsReceiptList.vue - `created_by_name` 字段缺失，影响列表显示

**中优先级：**
2. ComparisonList.vue - `rfq_id` 字段缺失，但可以使用 `rfq` 字段替代，或添加 `rfq_id` 作为只读字段

### 修复建议

1. **GoodsReceiptSerializer** - 添加 `created_by_name` 字段
2. **QuotationComparisonSerializer** - 添加 `rfq_id` 字段（可选，或前端改用 `rfq` 字段）
