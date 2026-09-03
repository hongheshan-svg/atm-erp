# Backend 约定（`backend/`）

Django REST Framework 后端。以下约定不可从代码直接推断，改动前必读。

## 模型

- **BaseModel**: 所有业务模型继承自 `apps.core.models.BaseModel`，自带 `created_at`/`updated_at`/`created_by`/`updated_by` 时间戳和 `is_deleted`/`deleted_at` 软删除。
- **软删除**: `objects` 管理器默认过滤 `is_deleted=False`，绕过用 `all_objects`。删除调用 `instance.soft_delete()`，不要用 `queryset.delete()`。
- **附件**: 通用 `Attachment` 模型，通过 `related_model` + `related_id` 关联任意业务对象。
- **编码规则**: 业务编号通过 `CodeRule` 模型动态生成，**不要硬编码前缀/序号格式**。

## ViewSet

- **统一权限 Mixin**: `apps.core.permission_mixin.PermissionMixin` 是最新的权限方案（替代旧的 `DataPermissionMixin`/`FinanceDataMixin`/`OperationPermissionMixin`/`SensitiveFieldMixin`），配置 `permission_module`/`permission_resource`/`context_role_fields` 三个类属性即可。旧代码可能还在用 `DataPermissionMixin`。
- **标准 Mixins**: 新 ViewSet 应组合 `UserTrackingMixin`（自动设 created_by/updated_by）、`SoftDeleteMixin`（perform_destroy 走软删除）、`DataScopeMixin`（按角色数据范围过滤）——均在 `apps.core.mixins`。
- **工作流**: `WorkflowEnforcementMixin`（在 `apps.core.workflow.mixins`）用于 ViewSet 级别的审批控制，需设置 `workflow_business_type`/`workflow_amount_field`/`workflow_no_field`。
- 修改 ViewSet 时**保留上述 Mixin 与审计日志中间件的预期，不要手写一套替代逻辑**。
- **分页**: `StandardPagination` 默认 20 条/页。

## 其他

- **审计日志**: `AuditLogMiddleware` 自动记录所有变更，无需手动埋点。
- 后端 API 契约变化要同步前端 API 封装（`frontend/src/api/`）与权限测试。
