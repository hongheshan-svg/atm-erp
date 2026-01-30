# 前端Vue组件与后端API字段不匹配检查报告 - Production模块

## 检查范围
- 前端目录: `/home/administrator/erp/frontend/src/views/production/`
- 后端目录: `/home/administrator/erp/backend/apps/production/`

---

## 1. QualityInspectionList.vue

### 前端使用的字段（表格列）:
- `inspection_no` ✓
- `title` ✓
- `project_code` ✓
- `inspection_type_display` ✓
- `status_display` ✓
- `result_display` ✓
- `pass_rate` ✓ (计算字段)
- `pass_qty` ✓
- `fail_qty` ✓
- `sample_qty` ✓
- `inspection_date` ✓
- `inspector_name` ✓

### 后端Serializer字段 (QualityInspectionSerializer):
- 所有字段匹配 ✓

### 问题:
**无问题** - 所有字段匹配

---

## 2. DebugRecordList.vue

### 前端使用的字段（表格列）:
- `record_no` ✓
- `title` ✓
- `project_code` ✓
- `debug_type_display` ✓
- `status_display` ✓
- `result_display` ✓
- `pass_items` ✓ (统计字段)
- `fail_items` ✓ (统计字段)
- `total_items` ✓ (统计字段)
- `debug_date` ✓
- `debugger_name` ✓

### 后端Serializer字段 (DebugRecordSerializer):
- 所有字段匹配 ✓

### 问题:
**无问题** - 所有字段匹配

---

## 3. ResourceTypeList.vue

### 前端使用的字段（表格列）:
- `code` ✓
- `name` ✓
- `category_display` ❌ **后端未提供**
- `description` ✓
- `default_efficiency` ✓
- `default_cost_rate` ✓
- `resource_count` ❌ **后端未提供**
- `is_active` ✓

### 后端Serializer字段 (ResourceTypeSerializer):
- `category_display` - **后端未提供**
- `resource_count` - **后端未提供**

### 问题:
1. **category_display**: 前端使用但后端ResourceTypeSerializer未提供
   - 后端模型有`category`字段，但serializer未添加`category_display`
   - **建议**: 在`ResourceTypeSerializer`中添加 `category_display = serializers.CharField(source='get_category_display', read_only=True)`

2. **resource_count**: 前端使用但后端未提供
   - 前端显示资源数量统计
   - **建议**: 在`ResourceTypeSerializer`中添加 `resource_count = serializers.SerializerMethodField()` 并实现`get_resource_count`方法

---

## 4. CapacityPlanning.vue

### 前端使用的字段:
- `totalResources` - 来自dashboard API ✓
- `avgUtilization` - 来自dashboard API ✓
- `overloadedResources` - 来自dashboard API ✓
- `conflictsCount` - 来自dashboard API ✓
- `code` ✓
- `name` ✓
- `resource_type_name` ✓
- `is_available` ❌ **后端字段为`status`**
- `efficiency` ✓
- `currentLoad` ❌ **后端未提供**
- `daily_capacity` ❌ **后端字段为`capacity_per_day`**
- `hourly_cost` ✓
- `conflictCount` ❌ **后端未提供**

### 后端Serializer字段 (ResourceSerializer):
- `is_available` - **后端字段为`status`，不是`is_available`**
- `currentLoad` - **后端未提供**
- `daily_capacity` - **后端字段为`capacity_per_day`**
- `conflictCount` - **后端未提供**

### 问题:
1. **is_available**: 前端使用`is_available`，但后端模型字段为`status`（值为'AVAILABLE'等）
   - **建议**: 
     - 方案1: 前端改为使用`status === 'AVAILABLE'`
     - 方案2: 后端serializer添加 `is_available = serializers.SerializerMethodField()` 返回 `obj.status == 'AVAILABLE'`

2. **currentLoad**: 前端使用但后端未提供
   - **建议**: 在`ResourceSerializer`中添加计算字段或从dashboard API获取

3. **daily_capacity**: 前端使用`daily_capacity`，但后端字段为`capacity_per_day`
   - **建议**: 
     - 方案1: 前端改为`capacity_per_day`
     - 方案2: 后端serializer添加别名字段 `daily_capacity = serializers.DecimalField(source='capacity_per_day', read_only=True)`

4. **conflictCount**: 前端使用但后端未提供
   - **建议**: 在`ResourceSerializer`中添加 `conflictCount = serializers.SerializerMethodField()` 计算冲突数量

---

## 5. ProcessList.vue

### 前端使用的字段（表格列）:
- `project_code` ✓
- `process_no` ✓
- `name` ✓
- `process_type_display` ✓
- `sequence` ✓
- `planned_hours` ✓
- `actual_hours` ✓
- `work_center` ✓
- `assignee_name` ✓

### 后端Serializer字段 (ProductionProcessSerializer):
- 所有字段匹配 ✓

### 问题:
**无问题** - 所有字段匹配

---

## 6. RoutingTemplateDetail.vue

### 前端使用的字段:
- `template_code` ❌ **后端字段为`code`**
- `name` ✓
- `version` ✓
- `product_category_name` ✓
- `status_display` ✓
- `total_standard_hours` ✓
- `description` ✓
- `operations` ✓
- `operation_code` ✓
- `name` (operation) ✓
- `work_center_name` ✓
- `standard_hours` ✓
- `setup_hours` ✓

### 后端Serializer字段 (RoutingTemplateSerializer):
- `template_code` - **后端字段为`code`**

### 问题:
1. **template_code**: 前端使用`template_code`，但后端字段为`code`
   - **建议**: 
     - 方案1: 前端改为`code`
     - 方案2: 后端serializer添加 `template_code = serializers.CharField(source='code', read_only=True)`

---

## 7. SmartScheduling.vue

### 前端使用的字段:
- `scenario_code` ❌ **后端模型没有此字段**
- `name` ✓
- `objective_display` ❌ **后端未提供**
- `status` ✓
- `status_display` ✓
- `created_at` ✓

### 后端Serializer字段 (SchedulingScenarioListSerializer):
- `scenario_code` - **后端模型没有此字段，只有`name`**
- `objective_display` - **后端未提供，但有`objectives_data`**

### 问题:
1. **scenario_code**: 前端使用但后端模型没有此字段
   - 后端模型`SchedulingScenario`只有`name`字段，没有`code`或`scenario_code`
   - **建议**: 
     - 方案1: 前端改为使用`name`或`id`
     - 方案2: 后端模型添加`scenario_code`字段或serializer添加计算字段

2. **objective_display**: 前端使用但后端未提供
   - 后端有`objectives_data`（数组），但没有`objective_display`（字符串）
   - **建议**: 
     - 方案1: 前端改为使用`objectives_data`并自行格式化显示
     - 方案2: 后端serializer添加 `objective_display = serializers.SerializerMethodField()` 格式化目标显示

---

## 8. SchedulingScenarioDetail.vue

### 前端使用的字段:
- `scenario_code` ❌ (同SmartScheduling.vue)
- `name` ✓
- `objective_display` ❌ (同SmartScheduling.vue)
- `status_display` ✓
- `created_at` ✓
- `created_by_name` ❌ **后端未提供**
- `result` ❌ **后端字段为`results`（数组）**
- `tasks` ❌ **后端字段为`results`**
- `order_no` ✓ (在SchedulingResultSerializer中)
- `product_name` ❌ **后端未提供**
- `work_center_name` ✓
- `planned_start` ❌ **后端字段为`scheduled_start`**
- `planned_end` ❌ **后端字段为`scheduled_end`**
- `quantity` ❌ **后端未提供**

### 后端Serializer字段 (SchedulingScenarioSerializer):
- `created_by_name` - **后端未提供**
- `result` - **后端字段为`results`（数组）**
- `tasks` - **后端字段为`results`**
- `product_name` - **后端未提供**
- `planned_start` - **后端字段为`scheduled_start`**
- `planned_end` - **后端字段为`scheduled_end`**
- `quantity` - **后端未提供**

### 问题:
1. **created_by_name**: 前端使用但后端未提供
   - **建议**: 在`SchedulingScenarioSerializer`中添加 `created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)`

2. **result/tasks**: 前端使用`result.tasks`，但后端字段为`results`（数组）
   - **建议**: 前端改为使用`results`

3. **product_name**: 前端使用但后端未提供
   - 后端`SchedulingResult`关联`production_order`，但没有`product_name`字段
   - **建议**: 在`SchedulingResultSerializer`中添加 `product_name = serializers.CharField(source='production_order.product_name', read_only=True)`

4. **planned_start/planned_end**: 前端使用`planned_start/planned_end`，但后端字段为`scheduled_start/scheduled_end`
   - **建议**: 
     - 方案1: 前端改为`scheduled_start/scheduled_end`
     - 方案2: 后端serializer添加别名字段

5. **quantity**: 前端使用但后端未提供
   - **建议**: 需要确认quantity的含义，可能来自`production_order.quantity`

---

## 9. AssemblyGuideList.vue

### 前端使用的字段:
- `guide_code` ✓
- `name` ✓
- `product_name` ✓
- `version` ✓
- `steps_count` ❌ **后端字段为`total_steps`**
- `status` ✓
- `status_display` ✓

### 后端Serializer字段 (AssemblyGuideListSerializer):
- `steps_count` - **后端字段为`total_steps`**

### 问题:
1. **steps_count**: 前端使用`steps_count`，但后端字段为`total_steps`
   - **建议**: 
     - 方案1: 前端改为`total_steps`
     - 方案2: 后端serializer添加 `steps_count = serializers.IntegerField(source='total_steps', read_only=True)`

---

## 10. AssemblyGuideDetail.vue

### 前端使用的字段:
- `guide_code` ✓
- `name` ✓
- `version` ✓
- `product_name` ✓
- `status_display` ✓
- `created_by_name` ❌ **后端未提供**
- `steps` ✓
- `sequence` ✓
- `name` (step) ❌ **后端字段为`title`**
- `instructions` ❌ **后端字段为`description`**
- `model_url` ✓

### 后端Serializer字段 (AssemblyGuideSerializer, AssemblyStepSerializer):
- `created_by_name` - **后端未提供**
- `name` (step) - **后端字段为`title`**
- `instructions` - **后端字段为`description`**

### 问题:
1. **created_by_name**: 前端使用但后端未提供
   - **建议**: 在`AssemblyGuideSerializer`中添加 `created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)`

2. **name** (step): 前端使用`name`，但后端字段为`title`
   - **建议**: 
     - 方案1: 前端改为`title`
     - 方案2: 后端serializer添加 `name = serializers.CharField(source='title', read_only=True)`

3. **instructions**: 前端使用`instructions`，但后端字段为`description`
   - **建议**: 
     - 方案1: 前端改为`description`
     - 方案2: 后端serializer添加 `instructions = serializers.CharField(source='description', read_only=True)`

---

## 11. RoutingTemplate.vue

### 前端使用的字段:
- `code` ✓
- `name` ✓
- `product_category_name` ✓
- `version` ✓
- `is_current` ✓
- `operation_count` ✓
- `total_standard_hours` ✓
- `total_setup_hours` ✓
- `status_display` ✓

### 后端Serializer字段 (RoutingTemplateListSerializer):
- 所有字段匹配 ✓

### 问题:
**无问题** - 所有字段匹配

---

## 12. WorkStationList.vue

### 前端使用的字段:
- `code` ✓
- `name` ✓
- `work_center_name` ✓
- `station_type_display` ✓
- `capacity` ❌ **后端字段为`standard_capacity`**
- `is_active` ✓

### 后端Serializer字段 (WorkStationSerializer):
- `capacity` - **后端字段为`standard_capacity`**

### 问题:
1. **capacity**: 前端使用`capacity`，但后端字段为`standard_capacity`
   - **建议**: 
     - 方案1: 前端改为`standard_capacity`
     - 方案2: 后端serializer添加 `capacity = serializers.DecimalField(source='standard_capacity', read_only=True)`

---

## 13. PlanList.vue

### 前端使用的字段:
- 该文件使用的是`/inventory/mrp-plans/` API，不在production模块范围内
- 所有字段与inventory模块匹配

### 问题:
**无问题** - 不在production模块检查范围

---

## 14. SerialNumberList.vue

### 前端使用的字段:
- 该文件未完整读取，需要进一步检查

### 后端Serializer字段 (SerialNumberListSerializer):
- 基本字段匹配

### 问题:
需要进一步检查具体字段使用情况

---

## 总结

### 需要修复的字段不匹配问题:

1. **ResourceTypeList.vue**:
   - `category_display` - 后端未提供
   - `resource_count` - 后端未提供

2. **CapacityPlanning.vue**:
   - `is_available` - 后端字段为`status`
   - `currentLoad` - 后端未提供
   - `daily_capacity` - 后端字段为`capacity_per_day`
   - `conflictCount` - 后端未提供

3. **RoutingTemplateDetail.vue**:
   - `template_code` - 后端字段为`code`

4. **SmartScheduling.vue**:
   - `scenario_code` - 后端模型没有此字段
   - `objective_display` - 后端未提供

5. **SchedulingScenarioDetail.vue**:
   - `created_by_name` - 后端未提供
   - `result` - 后端字段为`results`
   - `tasks` - 后端字段为`results`
   - `product_name` - 后端未提供
   - `planned_start/planned_end` - 后端字段为`scheduled_start/scheduled_end`
   - `quantity` - 后端未提供

6. **AssemblyGuideList.vue**:
   - `steps_count` - 后端字段为`total_steps`

7. **AssemblyGuideDetail.vue**:
   - `created_by_name` - 后端未提供
   - `name` (step) - 后端字段为`title`
   - `instructions` - 后端字段为`description`

8. **WorkStationList.vue**:
   - `capacity` - 后端字段为`standard_capacity`

### 建议修复优先级:

**高优先级** (影响功能):
1. CapacityPlanning.vue - `is_available`, `daily_capacity` (影响资源列表显示)
2. AssemblyGuideDetail.vue - `name`, `instructions` (影响步骤显示)
3. SchedulingScenarioDetail.vue - `result`, `tasks`, `planned_start/planned_end` (影响排产结果显示)

**中优先级** (影响显示):
1. ResourceTypeList.vue - `category_display`, `resource_count`
2. RoutingTemplateDetail.vue - `template_code`
3. AssemblyGuideList.vue - `steps_count`
4. WorkStationList.vue - `capacity`
5. SmartScheduling.vue - `scenario_code`, `objective_display`

**低优先级** (可选):
1. CapacityPlanning.vue - `currentLoad`, `conflictCount` (可能需要额外计算)
2. AssemblyGuideDetail.vue - `created_by_name` (可选字段)
3. SchedulingScenarioDetail.vue - `created_by_name`, `product_name`, `quantity` (可选字段)
