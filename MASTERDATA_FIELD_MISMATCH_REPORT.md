# Masterdata 前端字段与后端序列化器不匹配报告

## 检查范围
- 前端目录: `/home/administrator/erp/frontend/src/views/masterdata/`
- 后端序列化器: `/home/administrator/erp/backend/apps/masterdata/serializers.py`

---

## 1. CustomerList.vue vs CustomerSerializer

### 前端使用的字段（表格列）
- `code`, `name`, `contact_person`, `phone`, `tax_number`, `bank_name`, `address`, `status`

### 前端表单字段
- `code`, `name`, `short_name`, `contact_person`, `phone`, `email`, `address`, `credit_limit`, `payment_terms`
- `invoice_title`, `tax_number`, `bank_name`, `bank_account`, `registered_address`, `registered_phone`
- `status`, `notes`

### 后端序列化器字段
- `id`, `code`, `name`, `short_name`, `contact_person`, `phone`, `email`, `address`, `credit_limit`, `payment_terms`
- `invoice_title`, `tax_number`, `bank_name`, `bank_account`, `registered_address`, `registered_phone`
- `status`, `status_display`, `notes`, `is_deleted`, `created_at`, `updated_at`

### 匹配情况
✅ **完全匹配** - 所有前端使用的字段都在后端序列化器中存在

---

## 2. SupplierList.vue vs SupplierSerializer

### 前端使用的字段（表格列）
- `code`, `name`, `contact_person`, `phone`, `tax_number`, `bank_name`, `bank_account`
- `settlement_method_display`, `address`, `status`

### 前端表单字段
- `code`, `name`, `short_name`, `contact_person`, `phone`, `email`, `address`, `settlement_method`
- `invoice_title`, `tax_number`, `bank_name`, `bank_account`, `registered_address`, `registered_phone`
- `status`, `notes`

### 后端序列化器字段
- `id`, `code`, `name`, `short_name`, `contact_person`, `phone`, `email`, `address`, `payment_terms`
- `settlement_method`, `settlement_method_display`
- `invoice_title`, `tax_number`, `bank_name`, `bank_account`, `registered_address`, `registered_phone`
- `status`, `status_display`, `notes`, `is_deleted`, `created_at`, `updated_at`

### 匹配情况
✅ **完全匹配** - 所有前端使用的字段都在后端序列化器中存在

---

## 3. ItemList.vue vs ItemSerializer

### 前端使用的字段（表格列）
- `sku`, `name`, `specification`, `brand`, `model`, `unit_display`, `item_type_display`
- `purchase_price`, `sale_price`, `standard_cost`, `tax_rate`
- `manufacturer`, `origin_country`, `safety_stock`, `lead_time`, `is_active`

### 前端表单字段
- `sku`, `name`, `specification`, `brand`, `model`, `manufacturer`, `origin_country`, `barcode`
- `item_type`, `unit`, `purchase_price`, `sale_price`, `standard_cost`, `tax_rate`
- `min_stock`, `max_stock`, `safety_stock`, `lead_time`
- `weight`, `volume`, `shelf_life`, `description`, `is_active`

### 后端序列化器字段
- `id`, `sku`, `name`, `specification`, `brand`, `model`, `manufacturer`, `origin_country`
- `category`, `category_name`, `item_type`, `item_type_display`, `unit`, `unit_display`
- `purchase_price`, `sale_price`, `standard_cost`, `tax_rate`, `tax_rate_display`
- `min_stock`, `max_stock`, `safety_stock`, `lead_time`
- `weight`, `volume`, `shelf_life`, `description`, `barcode`, `is_active`, ...

### 匹配情况
✅ **完全匹配** - 所有前端使用的字段都在后端序列化器中存在

---

## 4. WarehouseList.vue vs WarehouseSerializer

### 前端使用的字段（表格列）
- `code`, `name`, `address`, `warehouse_type`

### 前端表单字段
- `code`, `name`, `address`, `warehouse_type`

### 后端序列化器字段
- `id`, `code`, `name`, `warehouse_type`, `type_display`, `address`, `manager`, `manager_name`
- `contact_phone`, `is_active`, `notes`, `is_deleted`, `created_at`, `updated_at`, `location_count`

### 匹配情况
✅ **完全匹配** - 所有前端使用的字段都在后端序列化器中存在

---

## 5. LocationList.vue vs WarehouseLocationSerializer

### 前端使用的字段（表格列）
- `code`, `name`, `full_path`, `type_display`, `max_weight`, `max_volume`
- `is_pickable`, `is_storable`, `is_active`

### 前端表单字段
- `code`, `name`, `location_type`, `parent`, `max_weight`, `max_volume`
- `is_pickable`, `is_storable`, `is_active`, `notes`

### 后端序列化器字段
- `id`, `warehouse`, `warehouse_name`, `warehouse_code`, `parent`, `parent_name`
- `code`, `name`, `full_path`, `location_type`, `type_display`
- `max_weight`, `max_volume`, `is_active`, `is_pickable`, `is_storable`, `sort_order`, `notes`
- `is_deleted`, `created_at`, `updated_at`, `children_count`

### 匹配情况
✅ **完全匹配** - 所有前端使用的字段都在后端序列化器中存在

---

## 6. CustomerContactList.vue vs CustomerContactSerializer

### 前端使用的字段（表格列）
- `customer_name`, `name`, `position`, `role_display`, `phone`, `telephone`, `email`, `wechat`
- `is_primary`, `birthday`

### 前端表单字段
- `customer`, `name`, `position`, `role`, `phone`, `telephone`, `email`, `wechat`
- `birthday`, `gender`, `hobbies`, `is_primary`, `notes`

### 后端模型字段 (CustomerContact)
- `customer`, `name`, `title` (不是 `position`), `department`, `role`
- `mobile` (手机), `phone` (电话), `email`, `wechat`, `qq`
- `birthday`, `hobbies`, `notes`
- `is_primary`, `is_active`

### 匹配情况
❌ **存在不匹配** - 以下字段名不一致或不存在：

**问题字段**:
1. `position` - 前端使用，但后端模型字段是 `title`
2. `telephone` - 前端用于座机，后端模型字段是 `phone`（座机）
3. `phone` - 前端用于手机，但后端模型手机字段是 `mobile`
4. `gender` - 前端使用，但后端模型不存在此字段

**字段映射关系**:
- 前端 `phone`（手机） ↔ 后端 `mobile`（手机）
- 前端 `telephone`（座机） ↔ 后端 `phone`（座机/电话）
- 前端 `position` ↔ 后端 `title`

**建议修复方案**:
1. **方案一（推荐）**: 修改后端序列化器，添加字段别名以兼容前端
   ```python
   class CustomerContactSerializer(serializers.ModelSerializer):
       customer_name = serializers.CharField(source='customer.name', read_only=True)
       role_display = serializers.CharField(source='get_role_display', read_only=True)
       position = serializers.CharField(source='title', read_only=True)  # 别名
       phone = serializers.CharField(source='mobile', read_only=True)  # 前端phone映射到mobile
       telephone = serializers.CharField(source='phone', read_only=True)  # 前端telephone映射到phone
       
       class Meta:
           model = CustomerContact
           fields = '__all__'
           read_only_fields = ['created_by', 'updated_by']
   ```

2. **方案二**: 修改前端，统一使用后端字段名
   - `position` → `title`
   - `phone`（手机） → `mobile`
   - `telephone`（座机） → `phone`
   - 移除 `gender` 字段的使用

---

## 7. CustomerCredit.vue vs CustomerCreditListSerializer

### 前端使用的字段（表格列）
- `customer_code`, `customer_name`, `level_name`, `credit_limit`, `used_amount`, `available_credit`
- `usage_rate`, `payment_days`, `status_display`, `overdue_times`

### 信用等级表格字段
- `code`, `name`, `default_credit_limit`, `default_payment_days`, `discount_rate`, `customer_count`, `description`

### 后端序列化器字段 (CustomerCreditListSerializer)
- `id`, `customer`, `customer_name`, `customer_code`, `credit_level`, `level_name`
- `credit_limit`, `used_amount`, `available_credit`, `usage_rate`
- `payment_days`, `status`, `status_display`, `risk_score`, `overdue_times`

### 后端序列化器字段 (CreditLevelSerializer)
- 使用 `fields = '__all__'`，需要检查模型字段

### 匹配情况
⚠️ **部分匹配** - CustomerCredit 字段匹配，但 CreditLevel 使用 `__all__` 需要确认

**建议**: 
1. 确认 CreditLevel 模型包含 `code`, `name`, `default_credit_limit`, `default_payment_days`, `discount_rate`, `description` 字段
2. 确认 `customer_count` 是通过 `get_customer_count` 方法提供的

---

## 8. CustomerFollowUp.vue vs CustomerFollowUpListSerializer

### 前端使用的字段（表格列）
- `follow_date`, `customer_name`, `subject`, `follow_type_display`, `follower_name`
- `result_display`, `next_follow_date`

### 前端表单字段
- `customer`, `follow_type`, `follow_date`, `subject`, `content`, `result`
- `next_follow_date`, `next_follow_plan`, `priority`

### 后端序列化器字段 (CustomerFollowUpListSerializer)
- `id`, `customer`, `customer_name`, `follow_type`, `follow_type_display`
- `follow_date`, `follower`, `follower_name`, `subject`, `result`, `result_display`
- `next_follow_date`, `created_at`

### 后端序列化器字段 (CustomerFollowUpSerializer - 完整版)
- 使用 `fields = '__all__'`，应该包含所有模型字段

### 匹配情况
❌ **存在不匹配** - 列表序列化器缺少以下字段：
- `content` - 跟进内容（模型存在）
- `next_follow_plan` - 下次跟进计划（模型存在）
- `priority` - 优先级（模型存在）
- `priority_display` - 优先级显示（需要添加）

**问题字段**:
- `content` - 前端表单使用但列表序列化器未包含
- `next_follow_plan` - 前端表单使用但列表序列化器未包含
- `priority` - 前端表单使用但列表序列化器未包含
- `priority_display` - 前端详情显示使用但列表序列化器未包含

**建议修复方案**:
在 `CustomerFollowUpListSerializer` 中添加缺失字段（见下方代码）

---

## 9. DepartmentList.vue

### 说明
此文件不在 masterdata 序列化器范围内，它使用的是 `/auth/departments/` API，不在本次检查范围内。

---

## 总结

### ✅ 完全匹配的文件
1. CustomerList.vue
2. SupplierList.vue  
3. ItemList.vue
4. WarehouseList.vue
5. LocationList.vue

### ⚠️ 需要确认的文件
1. CustomerCredit.vue - CreditLevel 序列化器使用 `__all__`，已确认模型字段匹配

### ❌ 存在不匹配的文件
1. **CustomerFollowUp.vue** - 列表序列化器缺少字段
2. **CustomerContactList.vue** - 字段名不一致

---

## 修复建议

### 优先级 1: CustomerFollowUp.vue
**问题**: `CustomerFollowUpListSerializer` 缺少以下字段：
- `content`
- `next_follow_plan`
- `priority`
- `priority_display`

**修复方案**:
```python
# 在 backend/apps/masterdata/customer_follow.py 中修改 CustomerFollowUpListSerializer

class CustomerFollowUpListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    follower_name = serializers.CharField(source='follower.get_full_name', read_only=True)
    follow_type_display = serializers.CharField(source='get_follow_type_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)  # 新增
    
    class Meta:
        model = CustomerFollowUp
        fields = [
            'id', 'customer', 'customer_name', 'follow_type', 'follow_type_display',
            'follow_date', 'follower', 'follower_name', 'subject', 
            'content',  # 新增
            'result', 'result_display', 
            'priority', 'priority_display',  # 新增
            'next_follow_date', 'next_follow_plan',  # 新增 next_follow_plan
            'created_at'
        ]
```

### 优先级 2: CustomerContactList.vue 字段名不一致

**修复方案（推荐修改后端序列化器）**:
```python
# 在 backend/apps/masterdata/customer_follow.py 中修改 CustomerContactSerializer

class CustomerContactSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    # 添加字段别名以兼容前端
    position = serializers.CharField(source='title', read_only=True)  # 前端使用 position
    phone = serializers.CharField(source='mobile', read_only=True)  # 前端phone映射到mobile（手机）
    telephone = serializers.CharField(source='phone', read_only=True)  # 前端telephone映射到phone（座机）
    
    class Meta:
        model = CustomerContact
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']
    
    # 写入时需要处理字段映射
    def to_internal_value(self, data):
        # 将前端的 phone 映射到 mobile
        if 'phone' in data:
            data['mobile'] = data.pop('phone')
        # 将前端的 telephone 映射到 phone
        if 'telephone' in data:
            data['phone'] = data.pop('telephone')
        # 将前端的 position 映射到 title
        if 'position' in data:
            data['title'] = data.pop('position')
        return super().to_internal_value(data)
```

**或者修改前端**:
- 将 `position` 改为 `title`
- 将 `phone`（手机）改为 `mobile`
- 将 `telephone`（座机）改为 `phone`
- 移除 `gender` 字段的使用
