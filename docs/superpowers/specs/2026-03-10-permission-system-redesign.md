# 权限管理体系重新设计

> 日期：2026-03-10
> 范围：用户管理、角色管理、菜单权限、操作权限、数据权限、敏感字段控制、审批工作流打通

## 一、设计目标

将现有散落在 6 处的权限逻辑（Role.data_scope、Role.permissions JSON、permission_config.py 硬编码、permission_models.py 数据库配置、data_permission.py 4个Mixin、前端 hasMenuAccess），统一为一套以"权限树"为核心的可配置 RBAC 体系。

核心原则：
- 所有权限配置存数据库，通过管理界面操作，不再硬编码
- 权限树统一管理菜单、操作、敏感字段三类权限
- 用户多角色，权限取并集
- 后端强制校验，前端辅助控制（菜单/按钮/字段三级）
- 工作流审批人配置引用新角色体系

## 二、整体架构

```
用户 ──M:N──> 角色 ──M:N──> 权限节点（树形）
                │
                └──> 数据权限规则（五级范围，按模块可覆盖）
```

### 删除的内容

- `permission_config.py` 整个文件（695行硬编码）
- `permission_models.py` 中的 `ModulePermissionRule`、`RoleModulePermission`
- `Role.permissions` JSON 字段（改为关联权限节点）
- `Role.data_scope` 单一字段（改为独立的 DataScope 表）
- `DataPermissionMixin`、`FinanceDataMixin`、`OperationPermissionMixin`、`SensitiveFieldMixin` 四个独立 Mixin（合并为一个 `PermissionMixin`）

## 三、数据模型

### 3.1 Permission（权限节点 — 树形结构）

```python
class Permission(BaseModel):
    parent = ForeignKey('self', null=True)          # 父节点
    code = CharField(unique=True)                    # 唯一编码，如 'projects:bom:view_price'
    name = CharField()                               # 显示名称，如 '查看BOM单价'
    type = CharField(choices=[                       # 节点类型
        'menu',       # 菜单（对应前端路由）
        'operation',  # 操作（增删改查审批导出等）
        'field',      # 敏感字段
    ])
    resource = CharField(blank=True)                 # 关联资源标识，如 'purchase_order'
    field_name = CharField(blank=True)               # 模型字段名（仅 field 类型），如 'unit_price'
    route_path = CharField(blank=True)               # 前端路由路径（仅 menu 类型）
    icon = CharField(blank=True)                     # 菜单图标（仅 menu 类型）
    sort_order = IntegerField(default=0)             # 排序
    is_active = BooleanField(default=True)
```

编码规则示例：
```
system                          # 系统管理（menu）
system:user                     # 用户管理（menu）
system:user:create              # 新增用户（operation）
system:user:edit                # 编辑用户（operation）
system:user:delete              # 删除用户（operation）
purchase:order                  # 采购订单（menu）
purchase:order:create           # 创建采购单（operation）
purchase:order:approve          # 审批采购单（operation）
purchase:order:view_price       # 查看采购单价（field）
finance:expense:view_amount     # 查看费用金额（field）
```

### 3.2 Role（角色 — 重构）

```python
class Role(BaseModel):
    name = CharField(unique=True)
    code = CharField(unique=True)
    description = TextField(blank=True)
    permissions = ManyToManyField(Permission, through='RolePermission')
    is_active = BooleanField(default=True)
    sort_order = IntegerField(default=0)
```

### 3.3 RolePermission（角色-权限关联）

使用普通 Model 而非 BaseModel，避免软删除语义干扰 M2M 查询：

```python
class RolePermission(models.Model):
    role = ForeignKey(Role, on_delete=CASCADE)
    permission = ForeignKey(Permission, on_delete=CASCADE)
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['role', 'permission']
```

### 3.4 DataScope（数据权限规则）

不继承 BaseModel，避免软删除与 unique_together 冲突：

```python
class DataScope(models.Model):
    role = ForeignKey(Role, on_delete=CASCADE)
    module = CharField(blank=True)                   # 空表示全局默认
    scope_type = CharField(choices=[
        'all',              # 全部数据
        'dept_tree',        # 本部门及子部门
        'dept',             # 仅本部门
        'self',             # 仅自己
        'custom',           # 自定义部门列表
    ])
    custom_departments = ManyToManyField(Department, blank=True)  # 仅 custom 时使用
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['role', 'module']
```

### 3.5 User（用户 — 调整关联）

```python
# 改动点：role ForeignKey → roles ManyToManyField
class User(AbstractUser, SoftDeleteModel):
    roles = ManyToManyField(Role, blank=True)        # 多角色
    department = ForeignKey(Department, null=True)
    # ... 其余字段不变
```

### 3.6 WorkflowStep（审批步骤 — 无需改表结构）

`WorkflowStep.approver_role` FK 字段已存在于当前代码中，无需新增。只需改造 `WorkflowService._get_step_assignee` 中 `ROLE` 类型的查询逻辑：

```python
# 现有代码（需修改）：
User.objects.filter(role=step.approver_role)
# 改为：
User.objects.filter(roles=step.approver_role)
```

`approver_type` 选项保持不变：`USER`、`ROLE`、`DEPARTMENT_MANAGER`、`PROJECT_MANAGER`、`SUPERIOR`。

## 四、后端权限校验

### 4.1 统一 PermissionMixin（替代现有 4 个 Mixin）

```python
class PermissionMixin:
    # ViewSet 声明自己的模块和资源
    permission_module = ''        # 如 'purchase'
    permission_resource = ''      # 如 'order'

    # 上下文角色映射 — 支持 owner/assignee/member 等动态权限
    # 子类可覆盖，key 为上下文角色名，value 为对象上的字段名或可调用对象
    context_role_fields = {
        'owner': 'created_by',        # 创建人
        'assignee': 'assignee',       # 负责人
        # 'member': lambda obj, user: user in obj.members.all(),
    }

    def get_queryset(self):
        """数据权限过滤"""
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        scope = resolve_data_scope(user, self.permission_module)
        return apply_scope_filter(qs, user, scope)

    def check_permissions(self, request):
        """操作权限校验（列表/创建等无对象的操作）"""
        super().check_permissions(request)
        action_map = {
            'list': 'view', 'retrieve': 'view',
            'create': 'create', 'update': 'edit',
            'partial_update': 'edit', 'destroy': 'delete',
        }
        action = action_map.get(self.action, self.action)
        code = f'{self.permission_module}:{self.permission_resource}:{action}'
        if not has_permission(request.user, code):
            raise PermissionDenied()

    def check_object_permissions(self, request, obj):
        """对象级权限校验 — 支持上下文角色（owner/assignee/member）"""
        super().check_object_permissions(request, obj)
        user = request.user
        if user.is_superuser:
            return

        action_map = {
            'retrieve': 'view', 'update': 'edit',
            'partial_update': 'edit', 'destroy': 'delete',
        }
        action = action_map.get(self.action, self.action)
        code = f'{self.permission_module}:{self.permission_resource}:{action}'

        # 先检查静态角色权限
        if has_permission(user, code):
            return

        # 再检查上下文角色权限（如 owner 可编辑自己创建的对象）
        for ctx_role, field_or_func in self.context_role_fields.items():
            ctx_code = f'{self.permission_module}:{self.permission_resource}:{action}:@{ctx_role}'
            if has_permission(user, ctx_code):
                if callable(field_or_func):
                    if field_or_func(obj, user):
                        return
                else:
                    field_value = getattr(obj, field_or_func, None)
                    if field_value == user or field_value == user.id:
                        return

        raise PermissionDenied()

    def get_serializer(self, *args, **kwargs):
        """敏感字段过滤"""
        serializer = super().get_serializer(*args, **kwargs)
        hidden = get_hidden_fields(
            self.request.user, self.permission_module, self.permission_resource
        )
        for field_name in hidden:
            serializer.fields.pop(field_name, None)
        return serializer
```

上下文角色权限编码约定：在操作权限后追加 `@角色名`，例如：

```
projects:task:edit              # 任何有此权限的角色都能编辑任务
projects:task:edit:@owner       # 仅任务创建人可编辑（上下文角色）
projects:task:edit:@assignee    # 仅任务负责人可编辑（上下文角色）
```

权限树中，上下文角色权限作为操作权限的子节点挂载：

```
projects:task                   # 任务管理（menu）
  projects:task:view            # 查看任务（operation）
  projects:task:create          # 创建任务（operation）
  projects:task:edit            # 编辑任务（operation）
    projects:task:edit:@owner   # 创建人可编辑（operation, 上下文角色）
    projects:task:edit:@assignee # 负责人可编辑（operation, 上下文角色）
  projects:task:delete          # 删除任务（operation）
    projects:task:delete:@owner # 创建人可删除（operation, 上下文角色）
```

### 4.2 核心权限函数

```python
def get_user_permissions(user):
    """获取用户所有角色的权限并集，带缓存"""
    cache_key = f'user_perms:{user.id}'
    perms = cache.get(cache_key)
    if perms is None:
        perms = set(
            Permission.objects.filter(
                role_permissions__role__in=user.roles.filter(is_active=True),
                is_active=True
            ).values_list('code', flat=True)
        )
        cache.set(cache_key, perms, timeout=300)
    return perms


def has_permission(user, permission_code):
    """检查用户是否拥有某权限（支持父节点通配）"""
    if user.is_superuser:
        return True
    perms = get_user_permissions(user)
    if permission_code in perms:
        return True
    # 父节点匹配：拥有 'purchase:order' 则自动拥有 'purchase:order:*'
    parts = permission_code.rsplit(':', 1)
    while len(parts) > 1:
        parent_code = parts[0]
        if parent_code in perms:
            return True
        parts = parent_code.rsplit(':', 1)
    return False


def resolve_data_scope(user, module):
    """解析用户在某模块的数据范围（多角色取最宽）

    合并策略：
    - 非 custom 类型按优先级取最宽（all > dept_tree > dept > self）
    - custom 类型的部门列表跨角色取并集
    - custom 与非 custom 比较时：custom 视为与 dept_tree 同级（优先级 4）
    - 最终返回 (scope_type, custom_dept_ids)
    """
    SCOPE_PRIORITY = {'all': 5, 'custom': 4, 'dept_tree': 4, 'dept': 3, 'self': 2}
    best_type = 'self'
    best_priority = 0
    custom_depts = set()

    for role in user.roles.filter(is_active=True):
        scope = (
            DataScope.objects.filter(role=role, module=module).first()
            or DataScope.objects.filter(role=role, module='').first()
        )
        if not scope:
            continue
        priority = SCOPE_PRIORITY.get(scope.scope_type, 0)
        if priority > best_priority:
            best_priority = priority
            best_type = scope.scope_type
        if scope.scope_type == 'custom':
            custom_depts.update(scope.custom_departments.values_list('id', flat=True))

    return best_type, custom_depts


def apply_scope_filter(queryset, user, scope_result):
    """根据数据范围过滤查询集

    Args:
        queryset: 原始查询集
        user: 当前用户
        scope_result: resolve_data_scope 返回的 (scope_type, custom_dept_ids)
    """
    scope_type, custom_depts = scope_result

    if scope_type == 'all':
        return queryset
    elif scope_type == 'self':
        return queryset.filter(created_by=user)
    elif scope_type == 'dept':
        return queryset.filter(created_by__department=user.department)
    elif scope_type == 'dept_tree':
        # 获取当前部门及所有子部门 ID
        dept_ids = get_department_tree_ids(user.department_id)
        return queryset.filter(created_by__department_id__in=dept_ids)
    elif scope_type == 'custom':
        return queryset.filter(created_by__department_id__in=custom_depts)
    else:
        return queryset.none()


def get_department_tree_ids(dept_id):
    """递归获取部门及所有子部门 ID"""
    from apps.accounts.models import Department
    ids = {dept_id}
    children = Department.objects.filter(parent_id=dept_id, is_deleted=False).values_list('id', flat=True)
    for child_id in children:
        ids.update(get_department_tree_ids(child_id))
    return ids


def get_hidden_fields(user, module, resource):
    """获取用户在某资源上不可见的敏感字段列表"""
    if user.is_superuser:
        return []
    perms = get_user_permissions(user)
    # 查找该资源下所有 field 类型的权限节点
    field_permissions = Permission.objects.filter(
        type='field',
        code__startswith=f'{module}:{resource}:',
        is_active=True,
    )
    hidden = []
    for fp in field_permissions:
        if fp.code not in perms:
            hidden.append(fp.field_name)  # 使用专用的 field_name 字段
    return hidden
```

### 4.3 缓存失效策略

```python
def on_role_permission_change(role):
    """角色权限变更时清除相关用户缓存"""
    user_ids = User.objects.filter(roles=role).values_list('id', flat=True)
    cache.delete_many([f'user_perms:{uid}' for uid in user_ids])

def on_user_role_change(user):
    """用户角色变更时清除缓存"""
    cache.delete(f'user_perms:{user.id}')
```

通过 Django signal 或在 ViewSet 的 perform_update 中触发。

## 五、前端权限控制

### 5.1 登录接口返回结构

```json
{
  "user": { "id": 1, "username": "zhangsan", "..." : "..." },
  "roles": ["project_manager", "engineer"],
  "permissions": ["projects:bom:view", "projects:bom:create", "purchase:order:view"],
  "menus": [
    {
      "code": "projects",
      "name": "项目管理",
      "icon": "Folder",
      "route": "/projects",
      "children": [
        { "code": "projects:bom", "name": "BOM管理", "route": "/projects/bom", "children": [] }
      ]
    }
  ],
  "data_scopes": { "": "all", "finance": "self", "purchase": "dept_tree" }
}
```

`menus` 由后端根据用户权限动态生成，只返回有权限的菜单节点。

### 5.2 Permission Store

```js
// stores/permission.js
export const usePermissionStore = defineStore('permission', {
  state: () => ({
    permissions: new Set(),
    menus: [],
    dataScopes: {},
  }),
  actions: {
    setPermissions(perms) {
      this.permissions = new Set(perms)
    },
    hasPermission(code) {
      if (this.permissions.has('*')) return true
      if (this.permissions.has(code)) return true
      const parts = code.split(':')
      for (let i = parts.length - 1; i > 0; i--) {
        if (this.permissions.has(parts.slice(0, i).join(':'))) return true
      }
      return false
    },
  },
})
```

### 5.3 v-permission 指令

```js
// directives/permission.js
app.directive('permission', {
  mounted(el, binding) {
    const store = usePermissionStore()
    if (!store.hasPermission(binding.value)) {
      el.parentNode?.removeChild(el)
    }
  },
})
```

使用方式：

```html
<!-- 按钮级控制 -->
<el-button v-permission="'purchase:order:create'">新建采购单</el-button>
<el-button v-permission="'purchase:order:approve'">审批</el-button>
<el-button v-permission="'purchase:order:delete'" type="danger">删除</el-button>

<!-- 敏感字段控制 -->
<el-table-column v-permission="'purchase:order:view_price'" prop="unit_price" label="单价" />
<el-table-column v-permission="'finance:expense:view_amount'" prop="amount" label="金额" />
```

### 5.4 路由守卫

```js
router.beforeEach((to, from, next) => {
  const permStore = usePermissionStore()
  const requiredPerm = to.meta?.permission
  if (requiredPerm && !permStore.hasPermission(requiredPerm)) {
    next('/403')
  } else {
    next()
  }
})
```

### 5.5 动态菜单渲染

前端直接渲染后端返回的菜单树，不再自行过滤。

## 六、工作流与权限体系打通

### 6.1 审批步骤审批人解析

`WorkflowStep.approver_type` 保留现有选项，`ROLE` 类型改为引用新 Role 模型：
- `ROLE`：查询拥有该角色且在相关部门范围内的用户
- `USER`、`DEPARTMENT_MANAGER`、`PROJECT_MANAGER`、`SUPERIOR`：逻辑不变

### 6.2 审批权限纳入权限树

```
purchase:request:submit         # 提交采购申请（operation）
purchase:request:approve        # 审批采购申请（operation）
purchase:request:withdraw       # 撤回采购申请（operation）
finance:expense:submit          # 提交报销（operation）
finance:expense:approve         # 审批报销（operation）
```

WorkflowEnforcementMixin 在执行审批动作前，先检查用户是否拥有对应的 `approve` 权限节点，再走工作流引擎的审批人匹配逻辑。双重校验。

## 七、管理界面

### 7.1 权限树管理（仅超级管理员）

- 树形展示所有权限节点
- 支持新增/编辑/删除/拖拽排序
- 按类型（菜单/操作/字段）图标区分
- 一般不需要频繁操作，系统升级时通过迁移脚本维护

### 7.2 角色管理（改造现有页面）

- 基本信息：名称、编码、描述
- 权限分配：权限树勾选（带全选/半选状态）
- 数据权限：默认数据范围 + 按模块覆盖配置
- 关联用户列表

### 7.3 用户管理（改造现有页面）

- 角色分配：从单选改为多选（Tag 形式展示已分配角色）
- 权限预览：展示该用户所有角色的权限并集（只读，方便排查）

### 7.4 工作流配置（改造现有页面）

- 审批步骤的"按角色指定"改为下拉选择新 Role
- 其余不变

## 八、迁移策略

### 8.1 数据库迁移（单次迁移文件）

1. 创建新表：Permission、RolePermission、DataScope
2. User 模型新增 `roles` ManyToManyField（与旧 `role` FK 并存）
3. 数据迁移（RunPython）：
   - 从 `permission_config.py` 的 `DEFAULT_ROLES`、`OPERATION_PERMISSIONS`、`SENSITIVE_FIELDS` 生成权限树初始数据
   - 从前端路由定义生成菜单类型权限节点
   - 从现有 `Role.permissions` JSON 迁移到 RolePermission 关联
   - 从现有 `Role.data_scope` 迁移到 DataScope 记录
   - 从 `User.role` FK 迁移到 `User.roles` M2M（每个用户的单角色转为多角色中的一个）

### 8.2 代码切换（一次性，不做并行期）

迁移脚本执行完成后，直接切换到新代码：

1. 所有 ViewSet 的旧 Mixin 替换为 PermissionMixin
2. `User.has_permission()` 方法改为调用 `permission_service.has_permission()`
3. `WorkflowService._get_step_assignee` 中 `User.objects.filter(role=...)` 改为 `User.objects.filter(roles=...)`
4. 前端登录流程改为读取新接口返回的 permissions/menus 结构
5. MainLayout.vue 中 60+ 处 `v-if="hasMenuAccess(...)"` 替换为动态菜单渲染
6. 路由定义中的 `menuId` meta 替换为 `permission` meta

### 8.3 清理（下个版本）

确认新系统运行稳定后：
- 删除 `User.role` FK 字段
- 删除 `Role.permissions` JSON 字段
- 删除 `Role.data_scope` 字段
- 删除 `permission_config.py`
- 删除 `permission_models.py` 中的 ModulePermissionRule、RoleModulePermission
- 删除 `permissions.py` 中的 DataScopePermission
- 删除 `data_permission.py` 中的旧 Mixin

### 8.4 回滚方案

迁移前对数据库做快照。如果新系统出现严重问题：
- 回滚代码到旧版本
- 旧字段（`User.role`、`Role.permissions`、`Role.data_scope`）未删除，可直接使用
- 新表（Permission、RolePermission、DataScope）不影响旧代码运行

## 九、涉及的文件清单

### 后端 — 新增

- `backend/apps/core/models/permission.py` — Permission、RolePermission、DataScope 模型
- `backend/apps/core/permission_mixin.py` — 统一 PermissionMixin
- `backend/apps/core/permission_service.py` — has_permission、resolve_data_scope、apply_scope_filter 等核心函数
- `backend/apps/core/permission_views.py` — Permission CRUD ViewSet（权限树管理 API）
- `backend/apps/core/permission_serializers.py` — Permission、DataScope 序列化器
- `backend/apps/accounts/migrations/xxxx_permission_redesign.py` — 数据迁移脚本
- `backend/apps/core/management/commands/init_permissions.py` — 权限树初始数据（幂等，按 code 创建或更新）

### 后端 — 改造

- `backend/apps/accounts/models.py` — User.roles M2M、Role 重构
- `backend/apps/accounts/serializers.py` — UserProfileSerializer 返回新结构
- `backend/apps/accounts/views.py` — 角色管理 CRUD、用户多角色分配
- `backend/apps/core/workflow/models.py` — WorkflowStep.approver_role
- `backend/apps/core/workflow/mixins.py` — 审批前权限校验
- `backend/apps/core/workflow/services.py` — ROLE 类型审批人解析
- 所有使用旧 Mixin 的 ViewSet（约 20+ 个）— 替换为 PermissionMixin

### 后端 — 删除

- `backend/apps/core/permission_config.py`
- `backend/apps/core/permission_models.py` 中的 ModulePermissionRule、RoleModulePermission
- `backend/apps/core/permissions.py` 中的 DataScopePermission（功能已合并到 PermissionMixin）

### 前端 — 新增

- `frontend/src/stores/permission.js` — 权限 Store
- `frontend/src/directives/permission.js` — v-permission 指令
- `frontend/src/views/system/PermissionTree.vue` — 权限树管理页面

### 前端 — 改造

- `frontend/src/stores/user.js` — 登录后设置权限数据
- `frontend/src/layout/MainLayout.vue` — 动态菜单渲染
- `frontend/src/router/index.js` — 路由守卫改造
- `frontend/src/views/system/RoleList.vue` — 角色管理（权限树勾选 + 数据权限配置）
- `frontend/src/views/system/UserList.vue` — 用户管理（多角色选择 + 权限预览）
- `frontend/src/composables/usePermission.js` — 改用新 Store
- 所有业务页面中的按钮/字段 — 添加 v-permission 指令
