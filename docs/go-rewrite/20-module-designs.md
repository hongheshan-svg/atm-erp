# 模块与跨域设计(21 份)

> 11 个限界上下文设计 + 10 个跨域关注点设计。

---

## 身份与访问(IAM/RBAC)边界上下文

将横跨 accounts + core 权限内核的 IAM 重写为单一 Go 鉴权服务(internal/iam)。保留 RBAC 表结构与菜单级授权语义,收敛分散的鉴权入口为统一中间件 + Authorizer 接口;借迁移彻底砍掉新旧双轨字段、死代码的 operation/field 层与字段脱敏,部门树改 PG 递归 CTE,企业微信同步移出请求路径转 asynq 异步任务。Casbin 仅承载 menu RBAC + 父码通配;数据范围/上下文角色/MODULE_MENU_MAP 越权边界在 Casbin 之外手写并逐条回归。

### 关键决策
- 单一鉴权服务:新建 internal/iam 包,对外暴露 Authorizer 接口(HasPermission/ResolveDataScope/CheckObject),取代散落在 permission_service + permission_mixin + permissions.py + 各 ViewSet @action 的判定
- Gin 中间件三段式替代 PermissionMixin:RequirePermission(module,resource) 做操作级 + 菜单兜底;DataScope(module) 注入 scope 到 ctx 供 repo 过滤;无 get_serializer 字段脱敏(C2 inert,直接删)
- Casbin v2 model.conf 仅建 menu RBAC:策略 = (role, code),matcher 内实现父码通配(g 分组 + keyMatch 风格自写 matcher 或预展开子树);超管短路返回 true
- 数据范围在 Casbin 之外手写 ResolveDataScope:GORM 查 DataScope 表取多角色最宽 scope(priority all>custom/dept_tree>dept>self),fail-closed 默认 self,5min Redis 缓存
- 数据过滤下沉到 repository 层:不再靠 hasattr 反射,改为每个聚合 repo 显式声明 OwnerField/DeptField(编译期可见),ApplyScope(db,scope,userID,deptID) 拼 WHERE;字段缺失编译期暴露而非静默 none()
- 部门树用 PG 递归 CTE(WITH RECURSIVE)一次查全,取代 get_department_tree_ids 的 N 次递归查库
- 彻底删除新旧双轨:迁移期将 User.role FK 合并入 role_user 关联表、Role.data_scope JSON + permissions JSON 丢弃只留 core_data_scope + role_permission 表,Go 侧无 get_active_user_roles 的 OR 兼容
- operation/field 两层 Permission 与 get_hidden_fields 不移植(死代码);Permission.type 仅保留 menu;若未来需字段脱敏再独立加
- 企业微信同步(拉通讯录/推送)移出 UserViewSet,改 hibiken/asynq 任务 + 重试,IAM 只保留 wechat_id 字段
- 缓存:go-redis 存 user_permissions:{id} 与 user_data_scope:{id}:{module};角色/权限变更走 asynq 或 service 内显式失效 + 引入单调 version 号(perm_ver:{uid})避免依赖 delete_pattern
- IsSystemAdmin 硬门槛保留为独立中间件 RequireSystemAdmin,在 RequirePermission 之前执行,封死 system:* 菜单兜底越权(C1)
- 菜单树下发:登录 handler 调 BuildMenuTree(user) 内存建树并补全祖先容器,内嵌登录响应,逻辑与 get_menus 一致

### 设计要点
## internal/iam 目录\n```\ninternal/iam/\n  domain/        user.go role.go department.go permission.go datascope.go\n  authz/         authorizer.go  casbin.go(menu RBAC+父码通配)\n                 datascope.go(resolve 最宽 scope, fail-closed self)\n                 objperm.go(@owner/@assignee)\n                 module_menu_map.go(C1 越权边界, 硬编码移植)\n  middleware/    require_perm.go require_admin.go inject_scope.go\n  repo/          user.go role.go dept.go(WITH RECURSIVE CTE) perm.go\n  cache/         perm_cache.go(go-redis, version 号失效)\n  service/       auth.go(JWT 签发/刷新) profile.go(menu 树内嵌)\n  task/          wechat_sync.go(asynq, 移出请求路径)\n```\n核心接口:\n```go\ntype Authorizer interface {\n  HasPermission(uid int64, code string) bool      // 父码通配\n  ResolveDataScope(uid int64, module string) Scope // 最宽, self 兜底\n  CheckObject(uid int64, code string, obj OwnedRow) bool\n}\n```\n仓储层显式声明归属字段, 取代 hasattr 反射:\n```go\nfunc (r ProjectRepo) ScopeFields() ScopeCols {\n  return ScopeCols{Owner:\"created_by\", Dept:\"department_id\"}\n}\n```\n**收敛点**:鉴权唯一入口 = 中间件 + Authorizer;**简化点**:删 operation/field 层与字段脱敏(C2 死代码)、删双轨兼容、部门树改 CTE;**保留**:menu 级授权、父码通配、最宽 scope、对象级角色、IsSystemAdmin 硬门槛、登录内嵌菜单。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `gorm.io/gorm`
- `github.com/jackc/pgx/v5`
- `github.com/golang-jwt/jwt/v5`
- `github.com/casbin/casbin/v2`
- `github.com/redis/go-redis/v9`
- `github.com/hibiken/asynq`
- `github.com/Masterminds/squirrel`
- `github.com/golang-migrate/migrate/v4`

### 风险
- 数据范围/上下文角色/MODULE_MENU_MAP 是安全攸关的非一一映射,Casbin 只覆盖一半;手写部分若回归不全极易引入越权(尤其 C1 的 system 菜单兜底边界、@owner/@assignee 对象级)
- 父码通配语义('purchase:order' 覆盖子树但 leaf 不互相覆盖)需在 Casbin matcher 精确复刻,实现偏差会放大或缩小授权面
- 数据过滤从反射改 repo 显式字段是行为变更:Django 下字段缺失静默 none(),Go 改编译期声明可能暴露此前被默默隐藏的越权或反向数据丢失,需逐 ViewSet 比对 skip_data_scope / data_scope_user_field 特例(H13/H14)
- 双轨字段合并迁移有数据一致性风险:User.role FK 与 roles M2M 可能不一致,合并前需做一致性盘点与回填脚本
- 缓存失效模型从 delete_pattern 改 version 号是语义升级,迁移期两套并存易出现脏读;需明确切换点
- 17 个预设角色 + DataScope 的 init_roles/init_permissions 需用 golang-migrate SQL 种子重写,与现有 161 迁移已落库的 schema 对齐,种子幂等性要保证

### 待定问题
- 父码通配在 Casbin 内用自定义 matcher 实现,还是策略加载时预展开子树(perm→所有祖先 code)?后者实现简单、查询快但策略表膨胀,需定夺
- 上下文角色 @owner/@assignee 当前靠 context_role_fields 配置 + obj 字段比对;Go 侧是放进 Casbin ABAC matcher 还是保留 service 层手写 CheckObject?倾向后者(显式可测)
- 缓存一致性用 version 号还是直接短 TTL + 主动失效?跨多实例 + 无 delete_pattern 依赖,version 号更稳但需所有读路径带 version 拼 key,改造面更大
- 数据范围 'custom' 的 custom_departments 与 dept_tree 都映射到 department_id__in,二者优先级同为 4,max 取值不确定;现状是否有同时配置二者的角色需确认,否则迁移后结果可能漂移
- 考勤模块(AttendanceConfig/Record/Leave/Overtime)归 IAM 包还是独立 attendance 包?其 data_scope_user_field='user' 特例与 IAM 数据范围耦合,拆分边界需明确
- 企业微信同步移异步后,wechat_work_users 拉取的同步返回语义如何改(前端期望同步拿到通讯录)?需前端配合改为任务 id + 轮询/WS 通知

---

## 平台内核 apps/core 是全部 15 个业务 App 依赖的共享基础层,聚合七大横切能力,并越界承载大量非内核功能(共16771行)。

apps/core 的 Go 重写策略:把当前 16771 行膨胀内核拆成「真内核(platform 共享库,无业务依赖)」+「七个横切能力包」+「越界功能各归其位」。GORM 钩子复刻 BaseModel(软删除/审计/created_by);CodeRule 用 pgx 行锁(SELECT FOR UPDATE)生成序列号;工作流引擎是改造重点——用「业务回调注册表(registry/事件总线)」彻底反转 _on_workflow_complete 对 30+ 业务模型的反向依赖,内核只发 WorkflowCompleted 事件,各业务包自行订阅改状态;RBAC 数据范围/字段脱敏/MODULE_MENU_MAP 在 Casbin 之外手写并逐条回归;Schema 整体保留,golang-migrate 只接管增量。

### 关键决策
- 真内核与横切能力分包:internal/platform(BaseModel/审计/分页/响应,零业务依赖)独立于 internal/core 下的七个能力子包(audit/attachment/notify/coderule/workflow/permission/sysconfig),每个能力暴露 service 接口供业务包注入,杜绝当前 core 反依赖全部业务 App 的循环。
- BaseModel 用 GORM 嵌入式 struct + 钩子复刻:gorm.Model 风格的 BaseModel{ID,CreatedAt,UpdatedAt,CreatedBy,UpdatedBy *uint, DeletedAt gorm.DeletedAt}。gorm.DeletedAt 原生支持软删除(自动 WHERE deleted_at IS NULL),取代 SoftDeleteManager;BeforeCreate/BeforeUpdate 钩子从 ctx 注入 created_by/updated_by(取代 UserTrackingMixin);需要绕过软删除时用 db.Unscoped()(取代 all_objects)。
- CodeRule 序列号生成迁到 pgx 显式事务 + SELECT ... FOR UPDATE(复刻 select_for_update 行锁),在 service 层一次性完成「判断周期重置→递增→拼模板→写 CodeHistory」,删除 Django 运行时猴补丁 _generate_code_wrapper 反模式,改为类型安全的 GenerateCode(ctx, ruleType) (string,error)。
- 工作流回调彻底解耦(核心改造):内核 workflow 包定义 BusinessHandler 接口{OnComplete(ctx, instance, result) error; ResolveProjectManager(ctx, instance) (*User,error)},各业务包在 init/wire 时按 business_type 注册自己的 handler 到 registry。引擎完成审批后只查表分发,不再 import 任何业务模型——反转依赖方向、满足开闭原则,新增业务类型只在业务包加 handler。
- RBAC 分层:Casbin v2 建模角色→权限码的 RBAC0,但 DataScope 数据范围(all/dept/dept_tree/self/custom)、context_role(@owner/@assignee)对象级、MODULE_MENU_MAP 菜单兜底为安全攸关逻辑,在 Casbin 之外用 Go 手写 PermissionService(ApplyScopeFilter 用 Squirrel 动态拼 WHERE)并对每条规则写回归测试。
- 审计从中间件粗放抓取升级为可靠记录:Gin 中间件仅记 LOGIN/LOGOUT 与请求元数据;CREATE/UPDATE/DELETE 的 model_name/object_id/changes 由 GORM AfterSave/AfterDelete 钩子产出真实主键与字段级 diff(取代 URL 切片猜模型、object_id 恒空、直存请求体),敏感字段在钩子内脱敏。
- 越界功能搬离内核:dashboard/mobile_api/print/import_export/backup/email/announcement/schedule/dict/custom_field/webhook 不进 core——dashboard→analytics 包、mobile→各业务包的 mobile handler、其余进独立 internal/platformsvc 或对应业务包;UpgradeJob 留在 core(属平台运维)。
- 通知双通道(钉钉/企微)用 go-redis 入队 + asynq worker 异步推送(取代 Celery),NotificationService 定义 Channel 接口,DingTalk/WeCom 各实现;站内信走 PG + WebSocket(coder/websocket hub + Redis Pub/Sub 多实例广播),取代 Channels。
- SystemConfig 去掉 pk=1 单例 hack,改为 config 表单行 + 启动期 viper 加载 + Redis 缓存,GetConfig() 命中缓存,写时失效。

### 设计要点
## platform 内核 Go 设计(apps/core)

把 16771 行膨胀内核拆为「真内核 + 七能力 + 越界搬离」。

```
internal/
  platform/           # 零业务依赖共享库
    model/base.go     # BaseModel(GORM 嵌入+钩子)
    httpx/ pagination/ response/
  core/
    audit/            # 钩子级 diff + 中间件
    attachment/       # 字符串软外键(沿用)
    notify/           # 站内信+钉钉/企微 Channel
    coderule/         # pgx FOR UPDATE 序列号
    workflow/         # 引擎 + BusinessHandler 注册表
    permission/       # Casbin + 手写 DataScope/脱敏
    sysconfig/        # 单行配置 + Redis 缓存
    upgrade/          # UpgradeJob
```

BaseModel 复刻:
```go
type BaseModel struct {
  ID uint `gorm:"primaryKey"`
  CreatedAt, UpdatedAt time.Time
  CreatedBy, UpdatedBy *uint
  DeletedAt gorm.DeletedAt `gorm:"index"` // 原生软删除
}
```

工作流去耦(核心):引擎不再反向 import 业务模型,改注册表分发:
```go
type BusinessHandler interface {
  OnComplete(ctx, inst *Instance, result string) error
  ResolveProjectManager(ctx, inst *Instance) (*User, error)
}
workflow.Register("SALES_ORDER", salesHandler) // 业务包侧 wire
```
内核完成审批仅发事件,各业务包自订阅改状态——反转依赖、满足开闭。

RBAC:Casbin 管角色→权限码;DataScope(all/dept/dept_tree/self/custom)、@owner 对象级、MODULE_MENU_MAP 兜底手写并逐条回归。Schema 保留,golang-migrate 只接增量。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `gorm.io/gorm`
- `gorm.io/driver/postgres`
- `github.com/jackc/pgx/v5`
- `github.com/Masterminds/squirrel`
- `github.com/golang-jwt/jwt/v5`
- `github.com/casbin/casbin/v2`
- `github.com/redis/go-redis/v9`
- `github.com/go-redsync/redsync/v4`
- `github.com/hibiken/asynq`
- `github.com/coder/websocket`
- `github.com/golang-migrate/migrate/v4`
- `github.com/spf13/viper`
- `github.com/swaggo/swag`
- `github.com/getsentry/sentry-go`
- `log/slog`

### 风险
- 工作流回调解耦后,若某 business_type 未注册 handler,审批通过但业务状态不更新会静默失败——必须在引擎完成时对未注册类型显式报错/告警并写 audit,且迁移期保留兼容性回归(逐 business_type 比对 Django 旧行为:PR APPROVED 还会联动生成 ProjectBOM、SALES_ORDER 置 CONFIRMED 等副作用)。
- 字段级脱敏在 Django 现状是 inert(从不种子化 field 权限,get_hidden_fields 恒空)。Go 若如实复刻则薪资/成本/银行账号仍未脱敏(安全债);若顺手修复则改变现有可见行为,需产品确认是修复还是等值迁移。
- MODULE_MENU_MAP 菜单前缀兜底语义晦涩(accounts 故意不映射 system、system 兜底放行 oa),逐条手写极易引入越权;必须 1:1 移植该映射表 + IsSystemAdmin 硬门槛,并用现有 test_comprehensive_permissions.py 等价用例回归。
- Attachment 仍是字符串软外键(related_model+related_id 无 DB 约束),Go 端无法靠 FK 级联/JOIN,孤儿数据风险延续;GORM 多态关联也救不了跨表,需要后台清理任务兜底。
- CodeRule 行锁迁移期:Django 与 Go 双写同一 code_rule 表会争抢 current_seq,迁移切流必须保证同一 rule_type 只由一侧生成,否则编号重复/跳号。
- GORM 在工作流多表 JOIN/BOM 递归/成本聚合上易退化;这部分必须走 sqlc 只读查询,边界划分错误会拖慢报表。
- WebSocket 从 Channels/Daphne 换 coder/websocket+自建 hub,连接鉴权(JWT)、断线重连、多实例 Redis Pub/Sub 广播需自写,实时通知/升级进度回归成本高。

### 待定问题
- 字段级脱敏:Go 端是等值复刻当前 inert 行为(薪资/成本仍可见),还是借迁移修复并种子化 field 权限?需产品/安全定调。
- BaseModel 软删除落地:DB 现有 is_deleted+deleted_at 两列,Go 用 gorm.DeletedAt(仅 deleted_at)需迁移列;等值迁移建议保留两列由钩子同步——确认是否可改 schema。
- 工作流 _on_workflow_complete 的跨模块副作用(PR 通过联动生成 ProjectBOM、库存调整执行应收生成等)是否全部迁入对应业务包 handler?需逐 business_type 清点 30+ 分支并确认归属。
- UpgradeJob/远程升级是否确定留在 core(平台运维)而非独立 ops 服务?
- 全局搜索:确认砍 ES 改 PG tsvector+zhparser 能满足现有 /search 中文检索召回,还是需 Meilisearch?
- MODULE_MENU_MAP 是否趁迁移收敛为真正的操作级权限(view/create/edit/delete 区分),还是 1:1 保留菜单兜底语义?
- 通知 NotificationService 用 hasattr 探测字段的弱契约,Go 强类型下需为各 business_type 定义显式通知 payload 结构——映射关系待梳理。

---

## 主数据(masterdata)边界上下文

主数据是全系统被引用最广的上游基础边界(60+ 文件依赖 Item/Customer/Supplier/Warehouse/WarehouseLocation 五大主数据及信用/CRM 扩展)。Go 实现以 GORM 复刻 BaseModel 软删除/审计为主层、sqlc+Squirrel 承接报表与动态列表查询,Gin 暴露与现有 DRF 路由一一对齐的 REST API。Schema 整体保留(golang-migrate 只接管增量),物理表名/字段不变,前端无感切换。核心工程量集中在:Item 编码生成器(select_for_update 并发锁→pgx 行锁/Redis redsync)、Excel 智能导入导出的中文列名模糊匹配与枚举映射、库位树 full_path 级联、以及解除信用模块对 finance 的反向依赖。complexity=3:领域逻辑不深,主要是 CRUD+导入导出+树+信用规则。

### 关键决策
- 按聚合根拆包:internal/masterdata/{item,customer,supplier,warehouse,credit,crm},每个聚合 model.go/repo.go/service.go/handler.go/dto.go 分明,根治现状 views.py 1494 行与 models+serializers+viewsets 混写同文件的问题
- 抽出 service 层:把现状塞在视图里的 Excel 解析/列名模糊匹配/枚举映射/编码生成/查重全部下沉到 service,handler 只做参数绑定与响应,可单测
- 物理 schema 不变:沿用 item/customer/supplier/warehouse/warehouse_location/masterdata_customer_credit 等现有表名与列,golang-migrate 仅接管新增量,GORM struct 用 TableName() 显式锁定表名
- BaseModel 用 GORM 内嵌结构体复刻:gorm.DeletedAt(软删除)+ created_at/updated_at + created_by/updated_by,经 BeforeCreate/BeforeUpdate 钩子从 ctx 注入操作人,默认 scope 过滤已删(对齐 Django objects vs all_objects)
- 物料编码生成走 DB 事务+行锁:在事务内 SELECT max(sku) ... FOR UPDATE(pgx),或对前缀 prefix(level1+level2+yy)用 redsync 分布式锁,严格复刻现有 select_for_update 并发语义与 10 位格式(1位有图无图+1位类型+2位年份+6位流水)
- 解除边界倒置:信用模块不再 import finance。CustomerCredit.used_amount 改为由 finance 侧通过领域事件/内部接口回写,或 masterdata 暴露 RefreshUsedAmount(customerID, amount) 由 finance 调用;check_customer_credit_for_order 保留为 masterdata 内纯函数(只读 used_amount 快照)
- 报表/聚合用 sqlc:信用 statistics(by_status/by_level 聚合)、warning_list/overdue_list 改为 SQL 内 usage_rate 计算+过滤,消除现状 Python 内遍历全部信用记录的 N+1
- 列表动态筛选用 Squirrel 拼装:items/customers 大量可选条件(类型/属性/ABC/状态/类别)动态 WHERE,配合 vxe-table 虚拟滚动+keyset 分页
- 库位树:full_path 在 service 保存时拼接并对子树批量级联更新;tree/descendants 改用单条 PG 递归 CTE(WITH RECURSIVE)替代现状 Python 递归 get_descendants,带深度上限
- 信用调整原子化:adjust_credit 的 save credit + create CreditAdjustment 包进单个 DB 事务(现状非原子),对齐审计
- 枚举映射集中到 internal/masterdata/enums:单位/状态/物料类型/二级代码的中英文双向映射统一定义,导入导出复用,消除现状视图内重复硬编码

### 设计要点
## Go 包结构(internal/masterdata/)

```
internal/masterdata/
├── item/        # SKU/规格/技术参数;编码生成器(行锁)
│   ├── code.go        # 10位编码生成/解析(原 item_code_generator)
│   ├── excel.go       # 智能导入导出(列名模糊匹配+枚举映射)
│   ├── model.go repo.go service.go handler.go dto.go
├── customer/    # 含开票/银行信息;Excel 导入
├── supplier/    # 同 customer + 结款方式
├── warehouse/   # 仓库 + 库位树(WITH RECURSIVE/full_path 级联)
├── credit/      # CreditLevel/CustomerCredit/CreditAdjustment
│   └── check.go       # CheckCustomerCreditForOrder(纯函数,供 sales)
├── crm/         # FollowUp/Reminder/Contact(低价值,可后置)
├── enums/       # 单位/状态/类型 中英双向映射(集中)
└── query/       # sqlc 生成(信用统计/预警聚合)
```

## 与 Django 行为差异/简化
- 软删除:GORM `gorm.DeletedAt` 自动过滤,查软删记录需 `Unscoped()`(对齐 all_objects)。
- 信用 used_amount:由实时聚合 finance 改为**接口回写**,解除反向依赖。
- 树查询:Python 递归 → PG 递归 CTE,带深度上限,消除 N+1。
- 搜索:ES → PG tsvector+pg_trgm。

## 编码生成(核心)
```go
// 事务内对前缀加行锁,严格复刻 select_for_update
tx.Raw(`SELECT max(sku) FROM item
  WHERE sku LIKE ? AND deleted_at IS NULL FOR UPDATE`, prefix+"%")
```

## API(路由与 DRF 完全对齐)
`/api/masterdata/{items,customers,suppliers,warehouses,locations,
customer-credits,credit-levels,customer-followups...}` 及
`items/generate_code|import_excel|export_excel`、
`customer-credits/check_order|warning_list|statistics` 等 action。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `gorm.io/gorm`
- `gorm.io/driver/postgres`
- `github.com/jackc/pgx/v5`
- `github.com/Masterminds/squirrel`
- `github.com/golang-migrate/migrate/v4`
- `sqlc (codegen)`
- `github.com/redis/go-redis/v9`
- `github.com/go-redsync/redsync/v4 (编码生成分布式锁)`
- `github.com/xuri/excelize/v2 (替代 pandas+xlsxwriter+openpyxl)`
- `github.com/golang-jwt/jwt/v5`
- `github.com/casbin/casbin/v2`
- `github.com/swaggo/swag`
- `github.com/spf13/viper`
- `log/slog`

### 风险
- 编码生成并发正确性:现状靠 PG select_for_update + Django transaction.atomic 保证唯一流水号。Go 侧若行锁范围或事务隔离级别处理不当会产生重复 SKU(全系统唯一约束兜底但会报错失败),需压测并发生成
- Excel 智能导入是隐性高风险:现状 import_excel 700+ 行含中文列名模糊匹配、枚举别名映射、all_objects 复活软删记录、查重合并等大量隐式业务规则,Go 重写极易遗漏边角 case,必须用真实历史 Excel 做回归
- 信用→财务解耦改动跨边界:used_amount 由实时聚合 finance.AccountReceivable 改为事件/接口回写后,存在时序与一致性窗口(下单校验读到的是快照而非实时),需与 finance 上下文协同设计,可能引入短暂超额风险
- 60+ 下游依赖耦合面巨大:任何字段语义/默认值/枚举值漂移都会波及 projects/sales/purchase/inventory/finance/production,迁移期需保持 API 契约与字段值字节级一致
- 软删除唯一约束语义:Customer/Supplier code 唯一约束不区分软删,现状用 all_objects 查重并复活记录;GORM 默认 scope 会过滤软删,repo 必须显式 Unscoped() 才能命中,易漏导致导入时唯一冲突
- Elasticsearch 砍掉换 PG tsvector+pg_trgm(中文 zhparser):Item/Customer/Supplier 搜索召回与分词效果可能下降,跨边界搜索体验需验证,必要时回退 Meilisearch
- Item 60+ 字段+双 JSONField 瘦身的取舍:若激进删字段会破坏下游;保守全保留则延续过度设计。需按下游真实引用做字段使用率盘点后再定

### 待定问题
- Item 60+ 字段 + technical_params/extra_fields 双 JSONB 是否瘦身?需先对 60+ 下游文件做字段引用盘点,确认哪些字段实际被读写
- 信用 used_amount 解耦的最终形态:领域事件(asynq/Redis Pub-Sub)异步回写 vs finance 同步调用 masterdata 接口?涉及下单校验的一致性窗口可接受度
- CRM 模块(FollowUp/Reminder/Contact,现状自承认低价值)是否纳入首期重写,还是标记为后置/可裁剪?
- 搜索是否首期就上 PG tsvector+zhparser(需自定义 PG 镜像),还是先用 pg_trgm 模糊匹配过渡、强搜索需求再引 Meilisearch?
- 条码/二维码生成现状依赖 inventory.barcode_service:Go 侧由 masterdata 自带还是仍调 inventory 上下文?涉及边界归属
- 信用额度调整是否需要接入 core 的可配置审批流(WorkflowEnforcementMixin 对等物),还是保留现状的即时调整+记录?

---

## Django ERP「销售与CRM」边界上下文 Go 实现方案

将 1.1 万行单体 sales app 按 DDD 拆为三个 Go 限界上下文(quotetocash / crm / aftersales),以集中状态机替代 @action 手写迁移,以显式领域服务+Port 契约层替代函数内延迟 import 跨 app 耦合。GORM 复刻 BaseModel(软删除/审计/created_by),sqlc+Squirrel 承接漏斗/RFM/赢丢单报表聚合。确认订单→应收/付款计划、发货→StockMove 等编排从 ViewSet 上移到领域服务,与审批回写共用单一路径。审批仍强依赖 core.workflow(WorkflowService)Go 实现,workflow_business_type 作为显式契约。报价估算/预测/模板三套子系统与客户培训按低利用率先冷冻为只读兼容,不在首期重写。

### 关键决策
- 按 DDD 拆三个上下文:internal/quotetocash(报价/SO/DO/合同)、internal/crm(线索/商机/预测/分析)、internal/aftersales(服务/门户/培训),不再单一 sales 包
- 状态机集中化:每个聚合定义 StateMachine(map[Status][]Transition),submit/confirm/cancel/return_to_draft 等迁移声明式校验,杜绝 DO 11 态非法跃迁
- 跨 app 解耦:定义 finance/inventory/masterdata/projects 的 Port 接口(契约层),领域服务依赖接口而非具体实现,替代十余处函数内延迟 import
- 确认单路径:OrderService.Confirm 与审批回写复用同一 createReceivables(幂等),复刻 services.create_sales_order_receivables 语义
- 数据访问双层:GORM 走 80% CRUD + 软删除钩子;sqlc 仅承接 funnel/trend/ranking/RFM/win-loss 只读聚合;列表多筛选用 Squirrel 拼 SQL
- 金额计算从 Model.save 上移到领域层 Recalculate(),序列化与持久化共用一处口径,消除三列冗余漂移
- 低利用率子域(quote_estimation/quote_prediction/quote_templates/customer_training)首期只读兼容,不重写,避免重做疑似过度设计
- Excel 导入导出从 ViewSet 600 行内联抽为 asynq 异步任务 + excelize

### 设计要点
## 目录结构(三上下文)
```
internal/
  quotetocash/        # 报价→SO→DO→合同
    domain/           # Quotation/Order/Delivery/Contract 聚合 + 状态机
    statemachine/     # transitions.go(声明式迁移表)
    service/          # OrderService.Confirm 等编排,共用 createReceivables
    repo/             # GORM(CRUD)+ sqlc(报表)
    port/             # Finance/Inventory/Masterdata/Workflow 接口
    http/             # Gin handler + swag 注解
  crm/                # Lead/Opportunity/Forecast/funnel/winloss/rfm
  aftersales/         # service/portal/training(首期只读)
  platform/event/     # 领域事件总线(OrderConfirmed→应收)
```
## 状态机示例
```go
var orderSM = StateMachine[OrderStatus]{
  Draft:     {Submit: Pending},
  Pending:   {Approve: Confirmed, Reject: Draft},
  Confirmed: {Cancel: Cancelled},
}
func (o *Order) Transition(a Action) error { /* 校验+审计 */ }
```
## 关键 Port(替代延迟 import)
```go
type FinancePort interface { EnsureReceivable(ctx, so) error } // 幂等
type InventoryPort interface { CreateStockMove(ctx, do) error }
```
确认/审批回写共用 OrderService.confirm() 单路径;金额在 domain.Recalculate() 一处算。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `gorm.io/gorm + gorm.io/driver/postgres`
- `github.com/jackc/pgx/v5`
- `github.com/Masterminds/squirrel`
- `sqlc-dev/sqlc(生成)`
- `github.com/golang-migrate/migrate/v4`
- `github.com/golang-jwt/jwt/v5 + github.com/casbin/casbin/v2`
- `github.com/redis/go-redis/v9 + go-redsync/redsync/v4`
- `github.com/hibiken/asynq`
- `github.com/coder/websocket`
- `github.com/spf13/viper`
- `github.com/swaggo/swag`
- `github.com/xuri/excelize/v2`

### 风险
- 审批引擎(core.workflow WorkflowService)是 SO/Quotation/DO/Contract 强依赖,若其 Go 版未先就绪则确认/提交全链路阻塞——必须先定义 workflow Port 并桩实现
- 数据范围(context_role_fields)/敏感字段脱敏/MODULE_MENU_MAP 越权边界 Casbin 无法直接表达,需手写移植并逐条回归,漏移即越权
- DO 11 态长流程 + 发货联动 StockMove 出库,状态机/库存事务边界拆错会导致出库与单据状态不一致
- 确认订单写 AccountReceivable+PaymentSchedule 的幂等性依赖 finance 侧实现,Go 重写两侧若时序不一致会重复生成应收
- models.py from .xxx import * 聚合 30+ 模型、字段散落 12 文件,Go 结构体抽取易遗漏字段/默认值/save 内重算逻辑
- migrations/migrations 嵌套重复目录是技术债,golang-migrate 只接管增量,需先确认 161 迁移落库 schema 真实态再写增量
- 报价三套子系统 + 培训 + 门户若实际在用,冷冻策略会触发业务投诉,需先用埋点/查询验证利用率

### 待定问题
- 报价估算/预测/模板三套子系统与客户培训、客户门户的真实使用率?决定冷冻还是重写
- core.workflow WorkflowService 的 Go 版由哪个上下文负责、契约(workflow_business_type/金额路由)是否已冻结
- context_role_fields 数据范围与敏感字段脱敏的完整清单在哪份文档,能否逐条枚举回归
- Excel 导入的客户/项目/物料模糊匹配规则(原 customer_cache/item_cache)是否保留还是改严格 code 匹配
- 三列金额(total/tax/with_tax)历史数据是否一致,Recalculate 迁移时是否需一次性回填校正
- DeliveryOrder 出库与单据状态的事务边界:是否引入 outbox 保证 StockMove 与状态一致

---

## 采购边界上下文（PR→RFQ→PO→GR→合同→委外）

采购是全仓最重模块之一（约12.8k行 Python、约63 模型、约50 DRF 路由），覆盖 PR→RFQ→PO→GR→合同→委外核心链路，外扩供应商评价/资质/预算/合同执行/门户/供应链协同等重型子系统。Go 重写按 Gin + GORM（主 CRUD）+ sqlc/Squirrel（比价聚合与列表动态筛选）落地：先收敛到 PR/RFQ/PO/GR/委外核心子域，把供应商门户、供应链协同拆为独立上下文（先冻结、后改写），并将与 projects.ProjectBOM 的 signals 隐式耦合改为显式领域事件（asynq + 同事务 outbox）。复用现有 PG schema（golang-migrate 只接管增量），编号、审批、权限数据范围在 Gin 中间件/领域服务层手写移植并逐条回归。

### 关键决策
- 核心子域优先：第一阶段只改写 PR/PO/GR/RFQ/委外（约 12 表 + signals + budget/comparison/rfq 三个 service），门户与协同平台先以只读代理保留 Django，后续作为独立 BC 改写
- BOM 状态机收口：废弃 signals.py 的 post_save 隐式写 projects.ProjectBOM，改为 PO confirm / GR confirm 在领域服务内显式发布 BomOrderedEvent/BomReceivedEvent，由 projects BC 的消费者落库；过渡期可保留 Go 服务直接事务内写 ProjectBOM 但集中到单一 BomSyncService，消除 signals+views 双处
- 数据访问双层：GORM gorm.DeletedAt + BeforeCreate/BeforeUpdate 钩子复刻 BaseModel(软删除/审计/created_by)，比价 QuotationScore 加权排序、价格历史聚合、项目预算汇总用 sqlc 编译期类型安全查询，列表页可选筛选用 Squirrel 拼装
- 金额/税额计算从 model.save 上移到领域服务（OrderService.Recalculate），line_amount=qty*price、tax_amount、total_with_tax 统一在 service，用 shopspring/decimal 替代 Python Decimal 保精度
- 审批/编号/权限沿用中间件化移植：WorkflowEnforcementMixin→workflow 中间件读 workflow_business_type/amount_field/no_field 元数据触发 core.workflow；generate_code(PR/PO...) 走共享 codegen 服务；PermissionMixin 的 permission_module='purchase'+resource 映射 Casbin，但 context_role_fields/数据范围手写
- 预算口径保留兼容：get_used_material_budget 的 max(PR估算, 实际移库) 近似口径先 1:1 迁移（sqlc 双查询取 max），打标记 TODO 待业务确认后改精确口径，避免迁移期核算结果漂移
- 包结构按子域而非按文件：internal/purchase/{request,order,receipt,contract,rfq,outsource}/ 各含 model/repo/service/handler/dto，shared 放 codegen/workflow/event

### 设计要点
## 采购 BC Go 实现

目录（按子域）:
```
internal/purchase/
  request/   {model,repo,service,handler,dto}.go  # PR + budget 校验
  order/     ...                                   # PO + 税额/付款条款
  receipt/   ...                                   # GR + 质检
  contract/  ...                                   # 合同 + 执行跟踪
  rfq/       ...                                   # 询价/报价/比价(sqlc)
  outsource/ ...                                   # 委外单/发料/收货/检验/索赔
  shared/    codegen.go workflow.go events.go bomsync.go
  query/     *.sql  (sqlc: 比价排序/价格历史/预算汇总)
internal/purchase/portal      # 冻结期只读代理 Django
internal/purchase/collab      # 同上,后续独立 BC
```
关键迁移点:
- BaseModel→GORM 钩子: `gorm.DeletedAt`+`BeforeCreate` 写 created_by/编号。
- BOM 联动: PO/GR confirm 在 service 内调 `BomSyncService` 或发事件,**取代 signals.py**。
- 审批: handler 标注 `workflow_business_type=PURCHASE_REQUEST/ORDER/CONTRACT`,中间件触发 core.workflow。
- 金额: `decimal.Decimal`,line_amount=qty*price,total_with_tax 在 service 算。
- 异步: asynq cron 替 `check_delivery_reminders`,复用 NotificationService。
对外 API 路径/契约 1:1 保留(`/api/purchase/requests/`含 check_budget、project_budget_summary;orders/receipts/contracts/rfqs/comparisons/outsource-*/evaluations/budgets 等),前端 api/purchase.ts 不动。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `gorm.io/gorm`
- `gorm.io/driver/postgres`
- `github.com/jackc/pgx/v5`
- `github.com/Masterminds/squirrel`
- `sqlc (kyleconroy/sqlc 生成)`
- `github.com/shopspring/decimal`
- `github.com/hibiken/asynq`
- `github.com/golang-jwt/jwt/v5`
- `github.com/casbin/casbin/v2`
- `github.com/redis/go-redis/v9`
- `github.com/golang-migrate/migrate/v4`
- `github.com/spf13/viper`
- `github.com/swaggo/swag`

### 风险
- BOM 双向状态机是最高风险点：signals(post_save) + views.perform_create/destroy 两处写 ProjectBOM(ordered_qty/received_qty/order_status/actual_cost)，Go 改显式事件后必须逐状态(NOT_ORDERED→PR_PENDING→ORDERED→PARTIAL→IN_TRANSIT→RECEIVED)回归，含软删回退逻辑，漏一处即库存/成本错
- 权限数据范围(context_role_fields)+敏感字段脱敏非 Casbin 能覆盖，采购涉及价格/供应商敏感数据，手写移植若不逐条回归会越权泄露报价
- RFQ/委外/供应商门户各存在两套并行模型(rfq_models vs supply_chain_collaboration.RFQCollaboration、outsource_models vs outsource_tracking、supplier_portal vs supply_chain_collaboration)，照搬会把概念分裂带进 Go；需先决定保留哪套再写
- Celery 到货提醒(check_delivery_reminders 每日)迁 asynq cron 时，NotificationService 的企微/钉钉 webhook 群播+个人推送语义要对齐，否则提醒丢失
- 预算 used 取 max(PR估算,实际移库) 近似口径若直接固化进 sqlc，核算准确性隐患被带入新栈
- 跨上下文 FK(masterdata.Item/Supplier、inventory.StockMove、finance.Expense、projects.Project/ProjectBOM)在 GORM 下需明确是同库 JOIN 还是 BC 间接口调用，迁移期建议同库以降风险

### 待定问题
- RFQ/委外/供应商门户的两套并行模型,业务上保留哪套?supply_chain_collaboration 是否实际在用还是低成熟度死代码可直接弃?
- 门户与协同平台是否拆为独立 BC(supplier-portal-bc),还是合并进采购?拆分则需定义采购↔门户的接口契约
- BOM 状态机改显式事件后,projects.ProjectBOM 的写权归 projects BC 还是采购 BC 过渡期可直接写?事件是同步(同事务)还是异步(asynq+outbox)?
- 预算 used 的 max(PR估算,实际移库)近似口径是否要在 Go 重写时纠正为精确口径?涉及核算准确性,需财务确认
- context_role_fields 数据范围与敏感字段(价格/供应商)脱敏的完整规则清单在哪?需逐条列出供 Casbin 之外手写
- 跨 BC 调用 masterdata/inventory/finance:迁移期同库直读,目标态是否要改 RPC?
- 重复嵌套的 migrations/migrations/ 目录确认为误提交可删除?

---

## 库存与MRP边界上下文

将 ~7000 行 Django inventory 重写为 Go (Gin+GORM+sqlc)。核心是把藏在 StockMove.save() 多层嵌套事务里的账实一致性逻辑，显式抽取为「库存移动指令(MoveCommand)+领域服务(StockLedgerService)+领域事件」，StockMove 退化为不可变流水。GORM 复刻 BaseModel 软删除/审计，sqlc+Squirrel 承接成本核算/MRP/对账等重聚合与动态筛选只读 SQL。备件子域与数据校验模块按现状过度设计标记为可裁剪/二期。保留全部 REST 契约与 URL 别名以兼容前端。复杂度 4/5。

### 关键决策
- 按子域拆 Go 包:ledger(Stock/StockMove/调整盘点)、batch(批次/FIFO/Lot)、material(领退料)、mrp、alert(预警+规则引擎)、cost(成本核算)、recon(数据校验对账)、sparepart(备件,标记二期),共享 internal/inventory/domain 放领域模型与事件
- 账实一致性显式建模:定义 MoveCommand 值对象(In/Out/Transfer/Adjustment 四方向)+ StockLedgerService.Apply(ctx,tx,cmd) 在单个 pgx 事务内 SELECT...FOR UPDATE 锁 Stock 行→校验非负→更新加权平均→追加 StockMove 流水→发 StockChanged 事件。彻底取代 save() 重写
- StockMove 设为 append-only 不可变流水(去掉 DRAFT→COMPLETED 隐式状态机与残留假 COMPLETED 记录的历史 Bug),状态机移到上层单据(Adjustment/Requisition)
- 双层数据访问:GORM 承接 80% CRUD(列表/详情/软删除/审计钩子);sqlc 承接 FIFO 消耗排序、加权平均重算、MRP 缺料展开、对账全表扫描、期间成本汇总等只读重聚合;Squirrel 拼列表页动态筛选
- ADJUSTMENT 方向 Bug 在领域层根治:Adjustment.Confirm() 显式产出 In 或 Out 指令(按 qty_diff 正负),不再靠仓库字段非空兜底注释补丁
- 保留 URL 别名(moves/stock-moves、adjustments/stock-adjustments)与全部 actions(low_stock/valuation/fifo_cost),Gin 路由显式注册具体路径在通配 :id 之前
- 对账校验从逐行 Python 循环改为 sqlc 集合查询(负库存/成本不匹配/账实差异用单条 SQL GROUP BY 检出),消除全表 N 次往返性能隐患
- 定时任务 check_low_stock_levels/check_expiring_batches 用 asynq cron 一对一替换 Celery Beat;通知走 NotificationService 接口(钉钉/企微/邮件)注入

### 设计要点
## Go 包结构(internal/inventory/)
```
domain/        # 领域模型+事件:Stock,StockMove,MoveCommand,StockChanged
  movecmd.go   # In/Out/Transfer/Adjustment 四方向值对象
  ledger.go    # StockLedgerService.Apply(ctx,tx,cmd) 唯一写库存入口
ledger/        # Stock/StockMove/调整盘点 ViewSet→handler
batch/         # Batch/InventoryLot/LotConsumption/BatchMove + FIFO
material/      # 领料/退料
mrp/           # 缺料计算(sqlc 展开 BOM)
alert/         # StockAlertRule/StockAlert 规则引擎(5类)
cost/          # 加权平均/FIFO + PeriodCostSummary(sqlc)
recon/         # 校验+对账(sqlc 集合查询,替代逐行循环)
sparepart/     # 备件(标记二期/可裁剪)
store/         # GORM repo + sqlc 生成代码 + Squirrel 动态查询
http/          # Gin 路由,保留 URL 别名与 actions
task/          # asynq cron:低库存/效期检查
```
### 核心:库存写入唯一入口(伪码)
```go
func (s *Ledger) Apply(ctx, tx, cmd MoveCommand) error {
  // 按(wh,item)升序 SELECT FOR UPDATE 防死锁
  st := s.lockStock(tx, cmd.WH, cmd.Item)
  if cmd.IsOut() && st.OnHand.LessThan(cmd.Qty) {
     return ErrInsufficientStock // 事务回滚,不残留假流水
  }
  st.applyWeightedAvg(cmd)       // 入库重算加权平均
  s.appendMove(tx, cmd.toMove()) // append-only 流水
  return s.emit(StockChanged{...})
}
```
StockMove 改为不可变流水;DRAFT→COMPLETED 隐式状态机移到上层单据。对外 REST 契约/分页/权限(permission_module='inventory')全部保留。

### 主要 Go 包
- `internal/inventory/domain`
- `internal/inventory/ledger`
- `internal/inventory/batch`
- `internal/inventory/material`
- `internal/inventory/mrp`
- `internal/inventory/alert`
- `internal/inventory/cost`
- `internal/inventory/recon`
- `internal/inventory/sparepart`
- `internal/inventory/store (GORM+sqlc+Squirrel)`
- `internal/inventory/http (Gin)`
- `internal/inventory/task (asynq cron)`
- `github.com/shopspring/decimal`
- `github.com/boombuler/barcode`

### 风险
- 加权平均成本与 FIFO 消耗涉及金额,Go decimal(shopspring/decimal)精度与 Python Decimal 量纲必须逐用例比对,否则成本/对账系统性偏差
- StockMove.save() 内多处历史 Bug 修复(ADJUSTMENT 方向、出库不足残留假 COMPLETED)是隐性契约,重写若不逐条回归会复活旧账实问题
- Stock 行级锁 SELECT FOR UPDATE 在高并发出入库下的死锁顺序,需统一按 (warehouse_id,item_id) 升序加锁
- MRP 强耦合 projects 的 ProjectBOM/Project,Go 侧需先确定 projects 上下文边界(直连库表 vs 服务接口),否则迁移阻塞
- 数据校验/对账 989 行逻辑迁移成本高且业务价值与现状不匹配,全量重写易超期
- 审批流联动(StockAdjustment 走 WorkflowEnforcementMixin)依赖 core 工作流引擎,Go 侧 core 未就绪前 mrp/调整确认动作无法闭环
- 条码/二维码 python-barcode+qrcode 换 Go 库(boombuler/barcode)输出格式/DPI 需与现有打印模板对齐

### 待定问题
- projects 上下文(ProjectBOM/Project)Go 迁移进度?MRP 依赖其库表,决定直连还是走服务接口
- core 工作流引擎(WorkflowEnforcementMixin)Go 侧是否就绪?StockAdjustment 审批确认依赖它闭环
- 备件子域(8模型+寿命预测+采购建议)是否裁剪或降级为二期最小实现?现状代码注释自承价值不大
- 数据校验/对账 989 行是否全量迁移,还是仅保留负库存/成本不匹配核心三项检测
- 成本方法默认值(加权平均 vs FIFO)与现有 InventoryCostConfig 配置如何在 Go 侧加载与切换
- 条码/二维码现有打印模板对 DPI/格式的要求,boombuler/barcode 输出能否对齐

---

## backend/apps/projects (项目与工程核心域)

将 31.7k 行的巨型 Django app 按子域拆为多个 Go 限界上下文:核心保留 project(项目主数据/成员/任务/WBS/工时/里程碑/预警)、bom、drawing、ecn 四个,设备/现场服务/成本/知识库等独立为同进程内的 bounded context(各自 internal/<ctx>),共享 pkg/platform(GORM BaseModel/软删除/审计/CodeRule/PermissionMixin 移植)。Project 内嵌的 8 个直查 finance/inventory 的聚合方法改为通过显式只读接口(CostReader/ReceivableReader)注入,边界反转;IoT 远程监控、CAD/Creo 集成裁剪为可选独立服务或暂缓。报表/BOM 卷积走 sqlc,CRUD 走 GORM,复用现有 PG schema(golang-migrate 只接管增量)。

### 关键决策
- 按子域拆分:不复刻单一巨型包。核心域 project/bom/drawing/ecn 进 internal/projects/*;equipment、fieldservice、cost、knowledge、bug、document 各自独立 bounded context(同二进制、不同包),避免 60+ 模型挤在一个包。
- 边界反转消除泄漏:Project 的 8 个 get_actual_*/get_total_receivables 等方法不再 import finance/inventory 模型。改为在 project 包定义 ProjectFinanceReader/ProjectInventoryReader 接口,由 finance/inventory 包实现并在 wire 时注入;projects 只依赖接口。
- 双层数据访问:BOM 递归卷积(cost-rollup)、成本汇总、健康看板用 sqlc 写编译期类型安全的递归 CTE / 聚合 SQL;项目/任务/BOM 行的 CRUD 与列表筛选用 GORM + Squirrel 动态拼条件。
- BaseModel 移植为内嵌结构:type Base struct{ID; CreatedAt; UpdatedAt; CreatedBy; UpdatedBy; gorm.DeletedAt(软删除); }。GORM BeforeCreate 钩子写 created_by、CodeRule 生成编号,复刻 PermissionMixin/UserTrackingMixin/SoftDeleteMixin 三件套。
- 裁剪超前功能:remote_monitoring(IoT 数据点/预测维护)、creo_integration(1258 行)、cad_integration(988 行)、equipment_oee 标记为 optional module,首期 Go 重写不做或降级为 stub/独立微服务;去重 requirement.py≡requirements.py、cost_tracking 与 advanced_cost_tracking 合并为单套。
- Project 状态机显式化:DRAFT→PLANNING→(审批)→IN_PROGRESS→COMPLETED→ARCHIVED 抽到 project/domain 的 transition 函数,带前置校验,脱离 ViewSet @action。
- REST 路径与前缀保持 /api/projects/* 不变,前端 api/<module>.ts 零改;121 个路由按子域分组到各包的 RegisterRoutes(r *gin.RouterGroup)。

### 设计要点
## 目录结构(核心域)
```
internal/
  projects/        # 限界上下文:项目/任务/WBS/里程碑/工时
    domain/        # Project 实体+状态机+ProjectFinanceReader 接口
    repo/          # GORM CRUD + Squirrel 动态筛选
    query/         # sqlc 生成:健康看板/进度聚合(只读)
    service/       # 业务规则(状态流转、预警)
    http/          # Gin handler + RegisterRoutes
  bom/             # 工位装配/版本快照/对比/递归卷积(sqlc CTE)
  drawing/         # Drawing+Version+DCN+受影响零件
  ecn/             # 工程变更 ECN/Item/Approval
  equipment/       # 设备档案/发货/安装/验收/维护(独立 ctx)
  fieldservice/    # 派工/技师排程/技能/签到/服务工单
  cost/            # 单套成本追踪(合并 cost+advanced)
  knowledge/ bug/ document/   # 知识库/缺陷/文档协同
pkg/platform/      # Base(软删除/审计) CodeRule 权限/数据范围
```
## 边界反转(消泄漏)
```go
// internal/projects/domain
type ProjectFinanceReader interface {
  ActualExpense(ctx, projectID) (Money, error)
  Receivables(ctx, projectID) (Money, error)
}
// finance 包实现并注入,projects 不再 import finance 模型
```
设备 OEE/IoT、CAD/Creo 首期裁剪;成本/需求去重并表。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `gorm.io/gorm`
- `gorm.io/driver/postgres`
- `github.com/jackc/pgx/v5`
- `github.com/Masterminds/squirrel`
- `github.com/golang-jwt/jwt/v5`
- `github.com/casbin/casbin/v2`
- `github.com/redis/go-redis/v9`
- `github.com/hibiken/asynq`
- `github.com/golang-migrate/migrate/v4`
- `github.com/xuri/excelize/v2`
- `github.com/swaggo/swag`
- `sqlc(生成代码)`

### 风险
- 数据范围/敏感字段不能靠 Casbin 一键映射:context_role_fields(如 manager/创建人维度)、MODULE_MENU_MAP 越权边界、字段脱敏需在 Casbin 之外手写并逐 ViewSet 回归,projects 有 166 处 PermissionMixin,遗漏即越权。
- 跨域聚合的事务/一致性:成本卷积、AR/AP 汇总跨 finance/inventory/purchase,Django 靠同库 ORM 直查;Go 改接口注入后若拆库或加缓存,易出现读不一致,需明确这些聚合是只读弱一致还是强一致。
- BOM God Model(68 字段)直译为 68 字段 Go struct 会延续坏味道;拆分(主表+采购追踪+成本快照子结构)需重写 serializer 契约,前端字段名必须保持兼容。
- views.py 3706 行 + 56 个 @action 的隐式业务规则(状态联动、采购/下单状态回写)缺测试,Go 重写抽 service 层时极易丢分支,需先补特征测试。
- Elasticsearch 索引(Project/ProjectTask)替换为 PG tsvector+pg_trgm,中文需 zhparser 自定义镜像;搜索召回与排序行为会变,需业务确认可接受。
- Excel BOM 导入(pandas/openpyxl)Go 侧用 excelize 重写,复杂合并单元格/公式解析可能不等价,导入失败率需对比。

### 待定问题
- remote_monitoring(IoT 数据点/告警/预测维护)、cad_integration、creo_integration、equipment_oee 是否有真实在用客户?可否首期裁剪/下线或转独立服务?
- cost_tracking 与 advanced_cost_tracking 两套成本逻辑哪套为准、能否合并为单套?字段差异如何收敛?
- Project 跨域聚合(material/labor/expense 成本、AR/AP、发票、银行流水)要求实时强一致还是可接受异步/缓存弱一致?决定 Reader 接口是同步直查还是走读模型/事件。
- ProjectBOM 68 字段是否可借机拆表?前端哪些字段为列表/详情强依赖,拆分后 serializer 契约怎样保持兼容?
- Elasticsearch 检索行为(召回/高亮/排序)替换为 PG tsvector 后业务能否接受差异?中文是否必须 zhparser?
- field_service(派工/技师排程/技能)与 oa、production(MES/APS)是否职责重叠?排程是否应归 production 而非 projects?
- drawing/document/document_collaboration/tech-documents 多套文档模型是否重叠,可否统一为单一文档子域?

---

## production app (生产/MES/APS 边界上下文)

将 Django production 应用(约40模型/28 ViewSet/110+端点)按业务域拆为 Go internal/production 子包,GORM 复刻 BaseModel 软删除/审计三件套,sqlc+Squirrel 承接看板/产能聚合,asynq 替代轮询升级,WS hub 推送大屏。重写期收敛三套排程模型、修复 N×M 聚合性能、重设库存联动契约,但保留 schema 与升级机制不变。复杂度 4/5。

### 关键决策
- 按业务域分子包(processes/routing/aps/scheduling/finite/andon/kanban/sn/capacity/assembly/dataacq),非按 model/svc/handler 横切,贴合现有'每域独立文件'组织
- BaseModel 三件套用 GORM:gorm.DeletedAt 软删除 + BeforeCreate/BeforeUpdate 钩子写 created_by/updated_by + 审计中间件,消除 28 处 PermissionMixin+SoftDeleteMixin+UserTrackingMixin 样板
- 看板/产能/甘特等只读聚合走 sqlc(编译期类型安全)+Squirrel(动态筛选),把 kanban.py / get_capacity_view 的 Python 循环逐工作中心逐天 aggregate 改为单条 GROUP BY SQL,消灭 N×M 往返
- CRUD 骨架域(sn/capacity/assembly/dataacq/equipment_capability/kanban_wip)用 GORM 通用 Repository[T] 泛型,减少重复
- 库存联动:在 production 内定义 InventoryPort 接口(CompletionInbound/MaterialIssue),由 inventory 包实现,production 仅依赖接口,去掉延迟 import hack
- 排程收敛:保留 aps.ScheduleOrder 作主排程入口,scheduling/finite_capacity 标注为待统一,Go 侧用统一 WorkCenter 实体 + 策略接口(贪心/有限产能),不再三套并存的物理表分裂
- 安灯升级/WIP 告警/数据采集告警从同步轮询改为 asynq cron 周期任务 + WS hub(Redis Pub/Sub)推送,大屏由前端定时拉改为订阅推送(可选,先保留轮询兼容)

### 设计要点
## Go 包结构(internal/production)
```
internal/production/
  domain/        # 实体+枚举(GORM model,复刻 40 表)
  processes/     # ProductionProcess/Plan/PlanProcess/Log/Debug*/QualityInspection/InspectionItem
  routing/       # WorkStation/RoutingTemplate/Operation/OperationMaterial/ProjectRouting*
  aps/           # ScheduleOrder/APSScheduleTask + Scheduler 策略(贪心)
  scheduling/    # WorkCenter/ProductionSchedule/ScheduleTask(待与 aps 收敛)
  finite/        # FiniteCapacityPlan/ScheduledTask(有限产能策略)
  andon/         # Type/Station/Call/Escalation/Action 闭环
  kanban/        # 只读聚合(sqlc) 大屏/负载/趋势/告警/WIP
  sn/            # SerialNumber/Trace/ComponentBinding/SNRule
  capacity/      # ResourceType/Resource/Allocation/Conflict/Dashboard
  assembly/      # AssemblyGuide/Step/Part/Session/Record
  dataacq/       # DataSource/Point/Record/Alarm(CRUD 骨架)
  port/          # InventoryPort 接口(完工入库/领料)
  http/          # Gin 路由注册 /api/production/*
```
**领域模型**:每实体对应 GORM struct 内嵌 `BaseModel{ID,CreatedAt,UpdatedAt,CreatedBy,UpdatedBy,DeletedAt gorm.DeletedAt}`,JSONField→`datatypes.JSON`。
**对外 API**:沿用现有 110+ 端点路径与契约(processes/plans/routing-templates/schedule-orders/andon-calls/serial-numbers/...);聚合端点 kanban/capacity dashboard/gantt 保持响应结构。
**库存联动**:`port.InventoryPort.CompletionInbound(orderID,qty,mats)` 由 inventory 实现,事务内调用,替代延迟 import。
小例:`func (s *Scheduler) AutoSchedule(ctx, orders) ([]Task,error)` 内贪心选最早可用 WorkCenter,setup+效率算时长。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `gorm.io/gorm`
- `gorm.io/driver/postgres`
- `gorm.io/datatypes`
- `github.com/jackc/pgx/v5`
- `github.com/Masterminds/squirrel`
- `github.com/golang-jwt/jwt/v5`
- `github.com/casbin/casbin/v2`
- `github.com/redis/go-redis/v9`
- `github.com/hibiken/asynq`
- `github.com/coder/websocket`
- `github.com/golang-migrate/migrate/v4`
- `github.com/spf13/viper`
- `github.com/swaggo/swag`
- `sqlc-dev/sqlc(生成)`

### 风险
- 数据范围(context_role_fields)/敏感字段脱敏/MODULE_MENU_MAP 越权边界 Casbin 无法表达,需手写移植并逐条回归,生产域权限点多,遗漏即越权
- 排程算法语义重写风险:aps 前向贪心有冗余 best_wc 逻辑,finite_capacity 与其意图重叠,收敛时若改变排程结果会影响已下达工单/甘特,需保留旧算法行为快照对比
- 库存联动契约:现用 ADJUSTMENT move_type + reference hack 实现生产入库,缺 IN_PRODUCTION 类型;重写须先与 inventory 边界协商新 move_type,否则库存余额方向/对账出错
- 看板聚合改 SQL 后数值需与 Django 旧实现逐字段比对(在制/负载/趋势),口径差异会在大屏暴露
- JSONField(安灯升级路径/通知角色、采集点配置)在 Go 需用 jsonb + 自定义类型,反序列化与旧数据兼容性
- migrations 嵌套重复目录(migrations/migrations 下 0001/0002 各两份)是历史遗留,golang-migrate 接管增量前须确认线上实际已落 schema 基线
- data_acquisition 无真实采集逻辑(无 MQTT/Modbus/OPC-UA),若 Go 侧补真实采集属新增范围,易范围蔓延

### 待定问题
- 三套排程(aps/scheduling/finite_capacity)是否物理合并为单一 WorkCenter+Schedule 模型,还是仅 domain 层统一物理表暂留?合并需迁移历史工单数据
- 库存联动是否借此引入 inventory 的 IN_PRODUCTION move_type 正式契约,替代 ADJUSTMENT+reference hack?需 inventory 边界配合
- data_acquisition 是否在 Go 侧补真实采集(MQTT/Modbus/OPC-UA)还是维持 CRUD 骨架?决定是否引入采集网关与范围
- 看板大屏是否从前端定时拉升级为 WS 推送,还是先保留轮询兼容以降迁移风险?
- 3D装配指导/序列号追溯/设备能力矩阵等单薄模块是否原样平移,还是借机精简删减?
- migrations 嵌套重复目录的历史成因与线上实际生效版本需确认,影响 golang-migrate 基线

---

## finance bounded context (backend/apps/finance, ~11660 行 Python, 最大最复杂上下文: AR/AP、费用、收付款计划、发票、共摊、三类对账、银行流水、总账、税务、固定资产、预算)

将 finance 上下文从 DRF 胖 ViewSet(逻辑全内联在 action、无 service 层、三套对账与 AR/AP/收付款计划镜像重复、金融计算分散精度/并发风险高)重写为 Go 1.23 + Gin。核心策略:抽出领域服务层与四个聚合(Ledger 总账、Receivable/Payable、Reconciliation 统一抽象、Asset),把 record_payment/核销/凭证借贷平衡/折旧等内联逻辑收敛到 service,统一 decimal 精度与 select_for_update 行锁(GORM Clauses+pgx 事务)。约 40 模型/30+ ViewSet/110+ action 映射为按子域分包的 handler+service+repo;CRUD 走 GORM 复刻 BaseModel 软删除/审计,对账/账龄/试算平衡/余额聚合等只读重 SQL 走 sqlc,列表多筛选走 Squirrel。schema 完整保留(161 迁移已落库,golang-migrate 只接管增量),JWT/Casbin + 手写数据范围与敏感字段脱敏。Celery 9 定时任务一对一映射 asynq cron。

### 关键决策
- 按子域拆包(ledger/receivable/payable/payment/expense/invoice/reconciliation/bank/tax/asset/budget/currency),每子域 model/repo/service/handler 四文件分离,终结现状单文件 model+serializer+view 混写
- 引入显式 service 层:record_payment、核销(write-off)、凭证借贷平衡校验、折旧计提、共摊分配、账龄/试算平衡全部从 action 下沉到 service,handler 只做参数绑定+鉴权+调用
- 三类对账(Purchase/Sales/Invoice)抽象出统一 Reconciliation 接口 + 泛型/策略实现,消除镜像重复;AR/AP 同理共享 Ledgerable 行为(状态机、amount_paid 累加、状态推导)
- 金融计算统一用 shopsp商业 decimal(github.com/shopspring/decimal),DB 侧 NUMERIC(18,2)/(12,6),禁用 float;写路径统一 tx + SELECT FOR UPDATE 行锁(GORM clause.Locking)消除并发核销竞态
- 双层数据访问:GORM 覆盖约 80% CRUD 并以钩子复刻 BaseModel(gorm.DeletedAt 软删除、BeforeCreate/Update 写 created_by/updated_by);账龄、试算平衡、余额结转、对账聚合等只读重 SQL 用 sqlc 编译期类型安全
- schema 整体保留,db_table 名沿用(currency/account_receivable/fin_journal_voucher/finance_tax_*/erp_fixed_asset 等),golang-migrate 只接管 Go 重写后的增量列;新旧可灰度并存
- 跨上下文耦合(projects/sales/purchase)收敛为窄接口(ProjectRef/OrderRef Provider),用接口而非直接表 JOIN,降低对外部上下文表结构的硬依赖
- Celery 9 个 finance 定时任务(逾期 AR/AP 检查、到期提醒、日报、收付款计划提醒等)一对一映射为 asynq cron handler

### 设计要点
## Go 包结构(internal/finance)
```
internal/finance/
  domain/        # 聚合与值对象: Money(decimal), 状态机, Ledgerable/Reconcilable 接口
  ledger/        # ChartOfAccount FiscalPeriod JournalVoucher/Line AccountBalance
  receivable/    payable/    payment/    expense/
  invoice/       # +pdf (excelize/maroto)
  reconciliation/# Purchase/Sales/Invoice 统一抽象,消除三套镜像
  bank/  tax/  asset/  budget/  currency/
  每子域: model.go(GORM) repo.go service.go handler.go
  query/         # sqlc 生成(账龄/试算平衡/余额结转/对账聚合)
  jobs/          # asynq: 逾期/到期/日报 等 9 个 cron
```
**分层**:handler(Gin,绑定+鉴权)→ service(事务+领域逻辑)→ repo(GORM CRUD)/query(sqlc 报表)。关键修复:`record_payment`/核销/借贷平衡下沉 service,`tx.Clauses(clause.Locking{Strength:"UPDATE"})` 行锁,`decimal.Decimal` 统一精度。BaseModel 用内嵌 struct + GORM 钩子复刻软删除/审计。schema 不变,golang-migrate 只接管增量。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `gorm.io/gorm`
- `gorm.io/driver/postgres`
- `github.com/jackc/pgx/v5`
- `github.com/shopspring/decimal`
- `github.com/Masterminds/squirrel`
- `sqlc (kyleconroy/sqlc-gen-go)`
- `github.com/golang-migrate/migrate/v4`
- `github.com/golang-jwt/jwt/v5`
- `github.com/casbin/casbin/v2`
- `github.com/redis/go-redis/v9`
- `github.com/hibiken/asynq`
- `github.com/xuri/excelize/v2`
- `github.com/johnfercher/maroto/v2`
- `github.com/spf13/viper`
- `github.com/swaggo/swag`

### 风险
- 凭证借贷平衡、核销累加、折旧计提为资金正确性攸关逻辑;Go 重写若 decimal 精度/舍入策略与 Django Decimal 不一致会产生对不上账,必须建对账回归基线(同一数据双跑比对)
- 数据范围(context_role_fields)/敏感字段脱敏/MODULE_MENU_MAP 越权边界 Casbin 无法表达,需手写移植并逐条回归,遗漏即越权高危
- 并发核销/多币种换算原现状即有竞态风险;迁移期新旧系统并存写同库,跨系统行锁不互斥,灰度需按子域整体切换而非按 API 切
- 三类对账与 AR/AP 抽象成统一接口若过度泛化,可能丢失各自细分字段/状态机差异,需保留逃生口
- 跨 projects/sales/purchase 强耦合:这些上下文若仍在 Django,Go finance 需经 DB 直读或内部 API 调用,事务边界跨进程后一致性变弱
- reportlab 生成发票 PDF、Excel 银行流水导入需用 Go 库(maroto/excelize)重写,格式细节(中文字体、模板)易回归

### 待定问题
- 跨上下文 projects/sales/purchase 在迁移期是否仍为 Django?若是,finance(Go) 访问其数据走 DB 直读还是内部 HTTP API?事务边界如何界定
- Payment.save 当前用 F() 表达式原子自增 amount_paid 并在外层再 refresh+状态推导,Go 是否统一改为 service 内单事务行锁累加(推荐),需确认无其他调用方依赖旧 save 副作用
- 三类对账抽象成统一接口的收益 vs 各自字段/状态机差异,是否值得泛型化,还是仅抽公共 service 函数
- decimal 舍入模式(银行家舍入 vs 四舍五入)在 Django 当前实际行为需确认并在 Go 显式固定,避免分账误差
- 预算(budget)ViewSet 现由 purchase 包提供并在 finance urls 注册,Go 拆分后归属 finance 还是 purchase
- 发票 PDF(reportlab)与银行流水 Excel 导入模板,Go 用 maroto/excelize 能否 1:1 还原中文字体与既有模板格式
- MODULE_MENU_MAP / context_role_fields / 敏感字段脱敏 的完整清单与回归用例从何处取得,确保越权边界零遗漏

---

## OA与协同 (backend/apps/oa)

OA 是六个弱关联子域(车辆/资产/档案/电子签章/考勤机集成/企业微信同步)的拼盘 + 从 core/accounts 反向 register 的日程/会议/公告/考勤记录路由聚合。Go 重写按子域拆分为独立内部包,各自 model+repo+service+handler,统一挂在 /api/oa 路由组。借用/调拨/维护在 asset/archive 间高度同构,抽公共 flow 抽象。审批统一接入 workflow 引擎,移除车辆"异常即自动批准"兜底。考勤机集成(三连接模式 + iclock 文本协议 + mock 回退)与企业微信同步因含外部 IO 单独成 service,定时任务由 Celery 迁移到 asynq cron。schema 整体保留,golang-migrate 仅接管增量。

### 关键决策
- 按子域拆分:internal/oa 下 vehicle/asset/archive/signature/attdevice/wechat 六个子包,各含 model.go+repo.go(GORM)+service.go+handler.go。日程/会议/公告/考勤记录仍属 core/accounts 包,OA 仅在路由层 aggregate 注册到 /api/oa 命名空间(复刻 Django urls.py 反向 register)
- 抽公共流转抽象:asset/archive 的 borrow/transfer/maintenance/destruction 高度同构,提取 internal/oa/flow 泛型状态机(Go 1.23 泛型),统一 submit/approve/reject/pickup/return 转换,各子域注入实体与转换钩子,消除重复硬编码 @action
- 审批统一走 workflow 引擎:全部申请类实体接入复用 Workflow 服务(对应 WorkflowEnforcementMixin),删除 vehicle.submit '工作流异常即自动批准'兜底,杜绝静默绕过
- Mixin 三件套用 Gin 中间件 + GORM 钩子复刻:软删除靠 gorm.DeletedAt,created_by/updated_by 靠 context user + BeforeCreate/BeforeUpdate 钩子,权限 module 恒 'oa' 在 handler 层声明 resource
- 考勤机集成独立 service:attdevice/sync.go 实现 TCP/云拉取/推送三模式,iclock 文本协议解析器单独成文件并补单测;移除 mock 回退到生产路径(改为显式 test fixture)
- 企业微信同步 service:access_token 用 go-redis 缓存 + redsync 锁防并发刷新;用户映射表查询缓存
- 定时任务 Celery→asynq:7 个 task(单/全设备同步、未处理日志、健康检查、日报、企微同步、日志清理)一对一映射为 asynq cron
- webhook 路由保留:POST /api/oa/webhook/attendance/:device_sn 与 /iclock/cdata 用裸 Gin handler 解析 form/json/iclock,返回 'OK' 裸文本以兼容 ZKTECO 设备,免 JWT/CSRF
- 电子签章保持半成品:sign 仍为 sha256 + 状态翻转模拟,预留 SignProvider 接口待接第三方
- 报表聚合(资产折旧/考勤日报/到期提醒)用 sqlc 写只读查询,列表页多可选筛选用 Squirrel,CRUD 走 GORM

### 设计要点
## Go 包结构(单体内按子域拆分)
```
internal/oa/
├── router.go            # 注册 /api/oa/* + 反向聚合 core/accounts 路由
├── flow/                # 泛型流转状态机(submit/approve/reject/pickup/return)
├── vehicle/             # Vehicle/VehicleRequest/VehicleMaintenance
├── asset/               # Asset/Category/Borrow/Transfer/Maintenance
├── archive/            # Archive/Category/Borrow/Transfer/Destruction
├── signature/          # Seal/Document/Participant/Log(模拟,预留 Provider)
├── attdevice/          # Device/UserMapping/AttendanceLog/SyncLog
│   ├── sync.go         # TCP/云/推送 三模式
│   └── iclock.go       # 文本协议解析(独立单测)
└── wechat/             # Config/UserMapping/CheckinRecord/SyncLog
```
每子包: `model.go`(GORM,嵌 BaseModel: ID/时间戳/created_by/DeletedAt)+ `repo.go` + `service.go` + `handler.go`(Gin)。
## 对外 API(沿用路径,零改前端)
- `/vehicle-requests/:id/{submit,approve,reject,pickup,return}`
- `/asset-borrows` `/asset-transfers` `/archive-destructions` 等
- `/signature-documents/:id/{add_participant,send_for_signing,sign}`
- `webhook/attendance/:device_sn` + `iclock/cdata`(返回裸 `OK`)
## 定时任务(asynq cron 复刻 Celery 7 任务)
单/全设备同步、未处理日志、健康检查、日报、企微同步、日志清理。
## 关键差异
审批统一接 workflow,删 vehicle 自动批准兜底;borrow/transfer/maintenance 抽公共 flow;mock 移出生产路径;签章保持模拟。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `gorm.io/gorm`
- `gorm.io/driver/postgres`
- `github.com/jackc/pgx/v5`
- `github.com/Masterminds/squirrel`
- `sqlc (sqlc.dev codegen)`
- `github.com/hibiken/asynq`
- `github.com/redis/go-redis/v9`
- `github.com/go-redsync/redsync/v4`
- `github.com/golang-jwt/jwt/v5`
- `github.com/casbin/casbin/v2`
- `github.com/golang-migrate/migrate/v4`
- `github.com/go-resty/resty/v2`
- `github.com/spf13/viper`
- `github.com/swaggo/swag`
- `log/slog`

### 风险
- 考勤机 TCP 直连依赖 pyzk,Go 无对等成熟库,需自研 ZKTECO 协议子集或仅支持云/推送两模式,直连模式可能短期降级
- iclock 文本协议是隐性契约(设备固件差异大),Django 靠多套 punch/verify 映射表试错积累,迁移需真实设备/抓包回归,否则打卡丢失
- 审批统一化改变 vehicle '静默自动批准'行为,虽是修 bug,但若生产流程依赖该兜底,上线后审批可能卡住,需迁移期灰度
- 企微 access_token 缓存键/过期与 Django cache 不一致会导致双系统并行期 token 互踩或频繁刷新触发企微限流
- 云 API verify=False 是安全隐患,Go 重写若强制校验证书可能因自签证书连接失败,需评估证书链
- 公共 flow 泛型抽象过度设计风险:六子域转换钩子差异(里程/费用/车辆状态联动)若强塞统一状态机,反而难维护
- 跨上下文反向依赖(core schedule/announcement、accounts attendance/User)在 Go 模块化后若拆库/拆服务,OA 聚合路由将跨服务调用,需明确聚合层次

### 待定问题
- OA 在 Go 架构里是单体内一个包还是按 bounded context 拆独立服务? 若拆服务,聚合 core/accounts 路由走服务间调用还是网关聚合?
- 考勤机 TCP 直连模式是否必须保留? 还是可降级为仅云拉取+设备推送两模式(Go 无 pyzk 等价库)?
- 云 API verify=False 是否改为强制 TLS 校验? 自签证书是否需配自定义 CA 或保留跳过开关?
- 审批统一接 workflow 后,asset/archive/signature 原硬编码状态子域是否都需动态审批流? 还是仅 vehicle 等高价值申请接?
- 电子签章第三方 provider 是否在本次重写排期内? 还是继续 sha256 模拟?
- 公共 flow 泛型抽象边界: borrow/transfer/maintenance/destruction 四类流转差异多大,是否值得统一?
- iclock 文本协议是否有真实设备/抓包样本用于回归? 缺样本则解析迁移风险高

---

## 「报表与BI」边界上下文(backend/apps/reports + backend/apps/analytics)Go 实现方案

该上下文是只读聚合/BFF 层,自身仅持有 7 张元数据表(ReportTemplate/Execution/Favorite、PredictionModel/Result、RiskAlert、ExportTemplate/History/ScheduledExport),核心价值在横向聚合 sales/purchase/projects/inventory/finance/production/masterdata 几乎全部业务域。Go 实现的关键决策:(1) 双层数据访问完美契合本上下文——GORM 仅管 9 张元数据表的 CRUD;所有跨域聚合/账龄/成本核算/KPI 改用 sqlc 编译期类型安全只读查询,彻底替代 Django F() 表达式 + pandas DataFrame,把 management_dashboard 的十余次全表聚合收敛为单/少数 SQL,N+1 循环计算改为一次 GROUP BY。(2) 抛弃 report_builder 的 importlib 动态加载模型(越权+注入面),改为 sqlc 命名查询白名单 + 显式字段映射的安全报表引擎。(3) 统一"口径单一事实源":含税优先(total_with_tax→total_amount)、状态集合、账龄分桶在一处 Go 常量/SQL 定义,消除现状 5 处漂移。(4) 成本三套逻辑(cost_service/analytics.project_costs/industry_reports)合并为单一 CostCalc sqlc 查询。(5) 必须补齐现状缺失的数据范围(DataScope)过滤——现状 function-based view 仅 IsAuthenticated、任何登录用户可看全量财务数据,Go 侧在 SQL WHERE 层强制注入 DataScope,安全攸关需逐条回归。(6) Celery 夜间成本预热 → asynq cron;导出 pandas/xlsxwriter → excelize;Redis 缓存口径保留(项目利润 1h)。schema 整体保留,golang-migrate 仅接管增量(修复 migrations 嵌套目录异常)。

### 关键决策
- 数据访问严格双层:GORM 只处理 reports/analytics 自有的 9 张元数据表(BaseModel 软删除/审计钩子复刻);所有跨域聚合(利润/账龄/KPI/周转/呆滞/行业报表)一律走 sqlc 编译期类型安全只读查询 + Squirrel 拼装列表页可选筛选,不用 GORM 重 JOIN。
- 用 sqlc 命名查询 + slog 结构化日志替代 pandas:DataFrame 计算(利润聚合、月度趋势、成本明细)全部下推到 PostgreSQL GROUP BY/窗口函数;Go 侧只做 float 换算与 JSON 序列化。
- report_builder 安全重构:废弃 importlib 动态 import 模型 + qs.values() 无白名单方案,改为预定义 sqlc 命名报表查询注册表(data_source→named query)+ 显式字段白名单 + DataScope 注入;ReportTemplate.config 仅作 UI 配置不再驱动反射。
- 建立口径单一事实源(pkg/bizrule):含税优先回退规则、各域有效状态集合(SalesOrder CONFIRMED/PARTIAL/COMPLETED 等)、AR/AP 账龄分桶(0-30/31-60/61-90/90+)集中定义,reports 与 analytics 共享,消除现状多处漂移。
- 成本核算三套合一:cost_service(pandas+缓存)、analytics.project_costs(逐项目循环)、industry_reports 统一为单个 CostCalc sqlc 查询(material=OUT_PROJECT StockMove qty*unit_cost;labor=ProjectMember actual_hours*hourly_rate;expense=Expense APPROVED/REIMBURSED;revenue=SalesOrder 含税),消除 N+1 与 5000 行硬上限。
- 补齐 DataScope:所有聚合查询在 SQL WHERE 层强制注入数据范围(按 context_role_fields 的 manager/owner/dept),修复现状 function-based view 仅 IsAuthenticated 导致全量财务数据越权可见的安全缺陷,逐条回归。
- 权限用 golang-jwt/v5 + Casbin RBAC 判定 module/resource(reports.report_template 等),但 DataScope/敏感字段脱敏(财务金额)在 Casbin 之外手写移植。
- 缓存:go-redis/v9 保留项目利润 1h 缓存(key project_profit_{id}),仪表盘/账龄补加短 TTL 缓存(现状无缓存实时全表聚合);refresh-cache 端点保留;缓存不可用时降级直算(复刻现状容错)。
- 异步:Celery 夜间成本预热 shared_task → asynq cron task(asynqmon 面板);ScheduledExport 定时导出 → asynq 周期任务。
- 导出:pandas+xlsxwriter → xuri/excelize(Excel)、标准库 encoding/csv、JSON;_get_field_value 的 field_path 点路径解析改为结构体 tag 映射 + 白名单。
- API 路由清理:analytics 现状 analytics/analytics 重复前缀与 slow_moving/slow_moving_items 双别名,Go 侧 Gin 路由规范为单一 /api/analytics/<action>,旧别名保留 301/兼容路由一个发布周期。
- 目录修复:reports/migrations 嵌套重复 migrations/ 子目录在 Go 迁移中不再复制,golang-migrate 以现有 schema 为基线只写增量。

### 设计要点
## 「报表与BI」上下文 Go 实现

只读聚合/BFF 层:GORM 管 9 张元数据表,跨域聚合全走 sqlc。

```
internal/reportbi/
  handler/        # Gin: reports.go analytics.go export.go prediction.go builder.go
  model/          # GORM 元数据: report_template/execution/favorite,
                  #   prediction_model/result, risk_alert,
                  #   export_template/history/scheduled_export
  repo/
    meta_gorm.go  # 9 表 CRUD(BaseModel 软删除/审计钩子)
    sqlc/         # 跨域只读聚合(编译期类型安全)
      query.sql   # profitability/aging/dashboard_kpi/turnover/
                  #   slow_moving/industry_*/cost_calc/cashflow_forecast
  service/
    costcalc.go   # 成本三套合一(替代 pandas)
    dashboard.go  # management_dashboard 拆分+缓存
    builder.go    # 白名单命名查询(替代 importlib)
    export.go     # excelize/csv/json
  task/asynq.go   # 夜间成本预热 + 定时导出(替代 Celery)
pkg/bizrule/      # 口径单一事实源:含税回退/状态集合/账龄分桶
```

要点:① 含税优先 `COALESCE(total_with_tax,total_amount)` 一处定义;② 利润 = 含税收入 − (OUT_PROJECT 物料 + ProjectMember 工时 + APPROVED/REIMBURSED 费用),单 SQL GROUP BY 替代 N+1;③ 所有聚合 WHERE 注入 DataScope(补现状越权缺口);④ go-redis 保留利润 1h 缓存,降级直算;⑤ Gin 路由清理 `analytics/analytics` 重复与 `slow_moving` 双别名。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `gorm.io/gorm`
- `github.com/jackc/pgx/v5`
- `github.com/jackc/pgx/v5/pgxpool`
- `sqlc-dev (生成 internal/reportbi/repo/sqlc)`
- `github.com/Masterminds/squirrel`
- `github.com/redis/go-redis/v9`
- `github.com/hibiken/asynq`
- `github.com/golang-jwt/jwt/v5`
- `github.com/casbin/casbin/v2`
- `github.com/xuri/excelize/v2`
- `github.com/golang-migrate/migrate/v4`
- `github.com/spf13/viper`
- `log/slog`
- `github.com/swaggo/swag`

### 风险
- 跨域读模型对几乎所有业务域表结构强耦合:sqlc 查询直接 JOIN sales/purchase/projects/inventory/finance/production/masterdata 的物理表,任一上游表/字段在其各自 Go 重写中改名或拆分,本上下文 sqlc 查询编译即断——需建立上游 schema 变更对本上下文的回归门禁。
- 口径迁移正确性风险:含税回退、状态集合、账龄分桶若未与现状逐字段比对,财务数字会静默偏差;必须用同一数据集对 Django 与 Go 输出做数值 diff 验收。
- DataScope 补齐是行为变更而非平移:现状任何登录用户可见全量财务/利润,收紧后部分用户会看到更少数据,需与业务确认授权矩阵,否则上线即'功能丢失'投诉。
- report_builder 从动态引擎改白名单是能力收窄:现状可对任意映射模型 values() 全字段导出,新方案只放开预定义查询,历史保存的 ReportTemplate.config 可能不再可执行,需迁移脚本与停用提示。
- 成本三套合一后口径必然变化(现状本身不一致,含税 vs 不含税),无论选哪套都会让某些历史报表数字变动,需对账与公告。
- management_dashboard 单 action 350+ 行堆十余聚合,逻辑隐含业务规则多,直译易遗漏;需先穷举其每个子指标再用 sqlc 重建。
- pandas 移除后,原 DataFrame 隐式的列重排/中文列名/空值处理需在 Go 显式复刻,导出文件列序/表头若变会影响下游 Excel 模板使用者。

### 待定问题
- 成本三套口径合一选哪套为准?现状 cost_service 与 analytics.project_costs/industry_reports 含税口径不一致,需业务拍板统一口径(建议 cost_service 含税优先方案),并接受历史数字变动。
- DataScope 收紧的授权矩阵:报表/财务利润数据各角色应见范围(全公司/本部门/本人项目)需业务明确,否则无法判定现状越权是 bug 还是默许特性。
- report_builder 是否仍需保留'用户自助配置任意数据源'的产品诉求?若需,白名单命名查询的覆盖范围(放开哪些 data_source/字段)需产品确认;若实际使用率低,可考虑直接下线该引擎。
- management_dashboard 的十余个子指标是否全部仍在用?前端高管仪表盘实际消费哪些 key,可借机裁剪无用聚合。
- 预测分析(cost-trend/delivery-risk/capacity-load)是否需要真实模型?现状仅为简单 SQL 聚合+规则(超期判 high),PredictionModel/Result 表近乎空壳,Go 侧是否保留表或简化为纯计算端点待定。
- 导出 PDF:现状 export_service 列了 PDF 能力但需确认实际使用;Go 侧 excelize 不出 PDF,如需 PDF 要额外引库(如 maroto/gofpdf),按使用率决定是否实现。
- timelog 报表的工时数据源(ProjectMember.actual_hours 还是独立 TimeLog 模型)需在 projects 上下文 Go 重写中对齐,影响本上下文 sqlc 查询。

---

## 权限系统简化

现有 RBAC 横跨 accounts 与 core 权限内核(约1300行+526行种子)。复杂度三处:Permission 树声称三级实际只种子化 menu 级,operation/field 为 inert 死代码字段脱敏恒空;新旧双轨字段(role FK+roles M2M、permissions JSON+M2M、data_scope 列+表)使鉴权函数满是 Q 兼容;菜单码与 module:resource:action 粒度错配靠硬编码 MODULE_MENU_MAP 桥接退化为有菜单即全 CRUD 双处兜底放行易越权。数据范围 5 种 scope 取最宽默认 self 绑死字段反射。Go 重写扁平为单层 resource:action、删 field 级、统一单一角色集合、数据范围抽可插拔策略接口、Casbin 承载 RBAC 但数据范围与越权边界手写移植。

### 关键决策
- Casbin v2 RBAC-with-domains 承载授权 域=module policy 经 gorm-adapter 存 PG Redis watcher 失效
- 权限扁平为单层 resource:action 删除三级与 field 脱敏死代码 菜单改前端静态表
- 删除 MODULE_MENU_MAP 桥接 权限码与检查码 1:1 取消菜单兜底放行
- 双轨字段合并为单一 user_roles + role_permissions Go 只读单一来源
- 数据范围抽为可插拔 ScopeStrategy 接口 经 GORM Scopes 注入 WHERE 模型实现 Scopable 取代反射
- 判定结果缓存 Redis 角色变更经 asynq 失效 super_admin 短路保留
- Gin 中间件 RequirePermission 对象级 context role 降级为 service 层 CheckObject

### 设计要点
权限系统简化 Go 版。根因: 三级权限树仅 menu 生效 operation/field 为死代码; 双轨字段使鉴权满是兼容分支; 菜单码与 module:resource:action 粒度错配靠 MODULE_MENU_MAP 硬桥接退化为有菜单即全 CRUD 且双处兜底放行易越权。简化表达力等价: 角色经 Casbin RBAC-with-domains 授权 permission 扁平为 resource:action; 数据范围用 ScopeStrategy 接口 All Dept DeptTree Self Custom 经 GORM Scopes 注入 WHERE 模型实现 Scopable。中间件 RequirePermission resource action 装饰路由 db.Scopes 链式过滤。对比: 三层加桥接转单层 resource:action; 双轨转单一 user_roles; 反射转显式接口; 隐式兜底转码 1:1 无兜底。前端三件套等价: 登录下发 permissions 与 menus 纯 resource:action; hasPermission 改精确或 resource 通配; meta.permission 与 v-permission 不变; menus 后端按码过滤静态菜单生成。迁移: 收敛单表 转 DataScope 对账补 self 转 init_roles 黄金样本逐条回归。

### 风险
- MODULE_MENU_MAP 兜底是隐式越权边界 逐条迁移漏掉会致 403 或越权 必须用 init_roles 黄金样本全量回归
- field 脱敏当前 inert 但 finance 薪资成本银行账号未来或真需脱敏 删除后须在 service 层另起方案
- 数据范围依赖 created_by department 约定 Go 改 Scopable 接口需逐模型实现 漏实现会静默返回全集或空集
- Casbin 管 action 授权而 scope 仍手写 两套判定需同一请求两关都过 易出困惑型 403
- Redis 缓存失效广播失败会致角色变更后旧权限残留最长 5 分钟

---

## 认证与会话

为 Go 1.23 + Gin 重写设计跨域「认证与会话」关注点:复刻并强化现有 simplejwt 行为(访问/刷新双令牌、刷新轮换 ROTATE_REFRESH_TOKENS、轮换后旧刷新令牌入黑名单 BLACKLIST_AFTER_ROTATION、Bearer 头、user_id 声明),用 golang-jwt/v5 自签 HS256/RS256;以 Redis 7 承载刷新令牌白名单+黑名单(jti+TTL),取代 simplejwt 的 DB outstanding/blacklist 表,实现 O(1) 撤销与登出。补齐当前系统缺失的一等 login_log(成功/失败、IP、UA、原因)。登录响应内嵌 user+permissions+menus+data_scopes(沿用现有契约,前端 request.ts 与三件套零改动),鉴权中间件解析 Bearer→注入用户上下文,与简化后 RBAC(Casbin enforce + 手写数据范围)在中间件链上串联。WebSocket 复用同一 access token(query token,后续可换 Sec-WebSocket-Protocol)。

### 关键决策
- 令牌方案:短 access(默认 30~120min,env 可调)+ 长 refresh(默认 7d);access 自包含 JWT(claims: sub/user_id、jti、exp、iat、token_type),refresh 亦为 JWT 但其 jti 在 Redis 维护状态。沿用现有 AUTH_HEADER_TYPES=Bearer、USER_ID_CLAIM=user_id 以保持前端兼容。
- 刷新轮换 + 黑名单用 Redis 而非 DB:每次 /auth/refresh 校验旧 refresh jti 是否在白名单(sess:refresh:<jti> 存 user_id,TTL=refresh 寿命),通过后签发新 access+新 refresh、删除旧 jti 并把旧 jti 写入黑名单 bl:<jti>(TTL 到旧 exp)。登出删除 refresh jti 即时失效;access 因短寿不强制查黑名单,高安全动作可选查 bl:。替代 simplejwt 的 OutstandingToken/BlacklistedToken 两张表。
- 签名密钥:首选 RS256(私钥签发、各服务/网关持公钥校验,利于未来拆服务),单体期可 HS256 + viper 注入的 JWT_SECRET;密钥与寿命全部走 viper(env+yaml),兼容现有 JWT_ACCESS_LIFETIME_MINUTES/JWT_REFRESH_LIFETIME_DAYS。
- 认证为 Gin 中间件 AuthRequired():提取 Bearer→验签→(可选查黑名单)→注入 *AuthUser 到 gin.Context;其后接 RBAC 中间件做 Casbin enforce(menu 级)与数据范围解析,登录/刷新/健康检查路由跳过。鉴权失败统一 401/403,与前端 401 排队重试约定一致。
- 登录响应契约保持:{access, refresh, user:{...permissions, menus, data_scopes}},前端 request.ts、Pinia permission store、v-permission 三件套与 localStorage(access_token/refresh_token)无需改动。
- 新增一等 login_log 表(当前 Django 仅 UPDATE_LAST_LOGIN+通用 AuditLog,无专表):记录成功/失败、用户、IP(X-Forwarded-For 解析)、UA、失败原因;失败计数+锁定走 Redis 计数器+go-redis,替代当前 DRF ScopedRateThrottle 登录限流。
- WebSocket 鉴权复用 access token(初期 query ?token=,与现 JWTAuthMiddleware 一致;建议迁移到 Sec-WebSocket-Protocol 头避免 URL 泄漏),由 coder/websocket hub 在握手期校验。

### 设计要点
## 认证与会话(Go 重写)

复刻现 simplejwt 语义并用 Redis 强化:双令牌 + 刷新轮换 + 黑名单 + Bearer + user_id 声明,登录响应内嵌 permissions/menus/data_scopes(前端三件套与 request.ts 零改动)。

### 令牌生命周期
- access(短,自包含 JWT)+ refresh(长,jti 在 Redis 维护)。
- /auth/refresh:校验旧 refresh jti 在白名单 → 签发新 access+refresh、删旧 jti、旧 jti 入黑名单(对应现 ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION)。
- /auth/logout:删 refresh jti 即时失效。

```
internal/auth/
  handler.go      # login/refresh/logout
  jwt.go          # golang-jwt 签发/校验 (RS256|HS256)
  store_redis.go  # sess:refresh:<jti> / bl:<jti> / login:fail
  middleware.go   # AuthRequired -> 注入 *AuthUser
  loginlog.go     # 新增一等登录日志(IP/UA/原因)
```

### 中间件链
`AuthRequired()`(验签+可选查黑名单)→ RBAC(Casbin menu 级 enforce + 手写数据范围)→ 业务 handler;login/refresh/health 跳过。WS 握手复用 access token。

### 与现状差异
弃用 simplejwt 的 outstanding/blacklist 两表改 Redis(O(1) 撤销);补齐 Django 缺失的 login_log 专表与失败锁定(替代 DRF 登录限流)。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `github.com/golang-jwt/v5`
- `github.com/redis/go-redis/v9`
- `github.com/google/uuid`
- `golang.org/x/crypto/bcrypt`
- `github.com/spf13/viper`
- `github.com/coder/websocket`
- `github.com/casbin/casbin/v2`
- `gorm.io/gorm`
- `github.com/jackc/pgx/v5`
- `github.com/golang-migrate/migrate/v4`
- `log/slog`

### 风险
- access token 不查黑名单:被盗 access 在剩余寿命内有效(最长 ~30~120min)。缓解:缩短 access 寿命、敏感操作强制查 bl:、提供 logout-all。
- PBKDF2→bcrypt 迁移若实现不当会导致存量用户无法登录或明文风险;透明 rehash 需严密测试。
- Redis 为会话唯一真相源,Redis 故障即全员需重登;需持久化/高可用,且与现有缓存实例隔离避免误 FLUSH。
- WS query token 易被日志/Referer 泄漏;迁移期需限制日志记录 URL query。
- 登录响应内嵌大体量 menus/permissions,RBAC 装配性能与缓存需跟上,否则登录变慢(现 Django 已有 Redis 缓存 has_permission,Go 端需复刻)。
- 多实例下 Casbin policy 与黑名单一致性依赖 Redis/Pub-Sub,部署期需验证。
- RS256 私钥管理(轮换、泄漏应对)较 HS256 复杂,需密钥版本(kid)预留。

### 待定问题
- access 寿命取现 settings 的 120min 还是 security_settings 生产档的 30min?二者并存需统一。
- 是否需要并发会话上限/单点登录(踢旧会话)?现 Django 无此能力。
- 刷新令牌是否绑定设备/IP 指纹以抗重放?
- 登录响应继续内嵌全量 menus,还是 SPA 改为登录后单独拉 /profile(现 request.ts 刷新后已单独回拉 profile,可统一)?
- 单体期 HS256 vs 直接上 RS256(为后续拆鉴权服务铺路)?
- login_log 写入走同步还是 asynq 异步(高频登录场景)?
- 小程序端是否同栈鉴权、token 存储与刷新策略是否一致?

---

## 数据模型与持久化 + 数据迁移

在 Go 侧用 GORM 复刻 Django BaseModel(created_at/updated_at/is_deleted/deleted_at/created_by/updated_by),软删除直接采用 gorm.DeletedAt 字段 + 全局默认过滤,审计/created_by 经 GORM Callback 注入;沿用现有 PostgreSQL 15 schema 与全部 161 条 Django 迁移结果,Go 新栈只接管增量(golang-migrate embed),不重建表。迁移策略采用"原地共库 + 同步切换"为主:不动数据、只对齐 ORM 字段映射,先在影子库做兼容性回归,再做模块级灰度只读双跑校验,最终低峰短停机切流量,DNS/反代回滚 + manifest 镜像原子回滚兜底。无需大规模 ETL 双写,因为 Go 与 Django 共用同一物理库与表结构。

### 关键决策
- BaseModel 等价物:定义共享 struct `Base{ID uint; CreatedAt; UpdatedAt; DeletedAt gorm.DeletedAt; CreatedBy/UpdatedBy *uint }`,内嵌进各业务模型。gorm.DeletedAt(软删除)语义与 is_deleted+deleted_at 不完全一致,采用『生成列/双写』方案:DeletedAt 映射到 deleted_at 列,并用 BeforeDelete/查询作用域同步维护 is_deleted 布尔,保证 Django 与 Go 共库期间两侧软删除互认。
- 默认查询过滤:GORM 对 gorm.DeletedAt 字段自动加 `deleted_at IS NULL`,等价 Django objects 管理器;需要 all_objects 时用 `.Unscoped()`。统一封装 db.Scopes(NotDeleted) 与 Repo 基类避免漏过滤。
- created_by/updated_by/updated_at 注入:用 GORM 全局 Callback(BeforeCreate/BeforeUpdate)从 context 取当前用户写入,替代 Django auto_now/auto_now_add 与 UserTrackingMixin;不靠 DB 触发器,保持业务可见。
- 沿用现有 PostgreSQL 15 schema:表结构、约束、索引、序列、161 条迁移产物全部保留;Go 端按既有列名/表名写 gorm tag(显式 TableName() 对齐 masterdata 的 item/customer 等显式 db_table 与其余 app_model 约定),禁止 GORM AutoMigrate 改表。
- 迁移版本管理:Django migrations 冻结(不再 makemigrations),新增 schema 变更一律走 golang-migrate 纯 SQL,embed 进二进制启动期 up;建一张映射表/基线记录,声明 Go 从某个 Django 迁移点接管,避免两套迁移工具互相覆盖。
- 双层数据访问落地:GORM 负责 80% CRUD(含软删除/审计),sqlc 负责 BOM 递归/成本核算/报表只读聚合(共用 pgx/v5 连接池),Squirrel 拼装列表页动态筛选;三者复用同一 *pgxpool.Pool,事务边界以 GORM 为主、sqlc 接收同一 tx。
- 迁移执行策略:原地共库为主(同物理库同表),不做一次性 ETL 拷贝、不做长期应用层双写。按 15 模块灰度逐个把读写从 Django 切到 Go,切换期同表共存;仅在 ID 生成、并发核销等强一致点用 DB 行锁/redsync 协调两栈。

### 设计要点
## 数据模型与持久化 + 数据迁移

**Go 侧 BaseModel 等价物**(内嵌进各业务 struct):
```go
type Base struct {
  ID        uint64    `gorm:"primaryKey"`        // 对齐 BigAutoField
  CreatedAt time.Time
  UpdatedAt time.Time                            // Callback 维护
  DeletedAt gorm.DeletedAt `gorm:"index;column:deleted_at"` // 默认过滤
  IsDeleted bool      `gorm:"column:is_deleted"` // 与 Django 双向同步
  CreatedBy *uint64
  UpdatedBy *uint64
}
func (Item) TableName() string { return "item" } // 显式对齐 db_table
```
- 软删:GORM 自动 `deleted_at IS NULL`;`.Unscoped()`=all_objects。BeforeDelete 同步 is_deleted=true。
- 审计/by 字段:全局 Callback 从 ctx 取用户写入,替代 mixin。

**Schema/迁移**:沿用现有 PG15 + 全部 161 条 Django 迁移产物,**不重建表**;Django migrations 冻结,增量改 schema 改走 `golang-migrate`(SQL + embed 启动 up)。

**切换策略**:原地共库(同库同表)→ 影子库跑兼容回归 → 模块级灰度只读双跑校验 → 低峰短停机切流量;回滚=反代/manifest 镜像原子回退。**不做 ETL 一次性拷贝、不做长期双写**(两栈共用物理库)。强一致点(序列号/核销/库存)用行锁+redsync 协调。

### 主要 Go 包
- `gorm.io/gorm`
- `gorm.io/driver/postgres`
- `gorm.io/datatypes`
- `github.com/jackc/pgx/v5`
- `github.com/jackc/pgx/v5/pgxpool`
- `github.com/golang-migrate/migrate/v4`
- `github.com/Masterminds/squirrel`
- `sqlc-dev/sqlc(代码生成器,生成 pgx 查询)`
- `github.com/go-redsync/redsync/v4`

### 风险
- gorm.DeletedAt 与 Django is_deleted(布尔)+deleted_at 双字段语义错位:若只维护一侧,Django objects 或 Go 默认过滤会漏/多查到软删数据(共库期最大风险),必须双向同步并加回归。
- BigAutoField PK 在 Go 必须用 uint64/int64;若误用 uint32 或与序列当前值不一致,共库期插入会撞 PK。需校验每张表 sequence 当前值且两栈共用同一序列。
- Django auto_now_add/auto_now 由 ORM 维护、DB 无默认值;Go 端若漏注入 Callback 会写入零值时间。需用 NOT NULL + 应用层保证或补 DB default。
- Go 接管后若误开 GORM AutoMigrate,可能擅自改列类型/加索引,破坏 161 迁移产出的 schema 与 Django 兼容性。须显式禁用并代码评审拦截。
- JSONField(masterdata 等 5 处,如 Item 双 JSON、permissions/data_scope)映射:Go 用 datatypes.JSON 或 pgtype.JSONB,结构松散,反序列化易类型漂移;数据范围/权限相关 JSON 错配直接导致越权。
- 共库灰度期两栈并发写同表的事务隔离/锁竞争(财务借贷平衡、库存 StockMove、CodeRule 行锁序列号),跨进程一致性不能只靠单栈事务,需 DB 锁/分布式锁统一。
- 审计日志(AuditLog object_id 恒空、靠 URL 猜模型)在 Go 重写时若照搬旧实现则继续脏数据;若改为正确填充,新旧审计记录格式不一致,报表口径漂移。

### 待定问题
- 是否在共库灰度期彻底以 deleted_at 为软删除单一真相、把 is_deleted 降级为生成列(GENERATED ALWAYS AS (deleted_at IS NOT NULL)),以消除双字段同步风险?需确认 Django 端读 is_deleted 的代码是否兼容生成列。
- GORM Callback 注入 created_by 依赖请求级 context 传当前用户;异步任务(asynq)/批处理无 HTTP 上下文时 by 字段如何取值(系统账户?留空?)需定规则。
- 报表层 sqlc 与 GORM 软删除过滤如何统一:sqlc 手写 SQL 不会自动加 deleted_at IS NULL,是否在每条聚合查询模板强制约定 WHERE,或建只含未删行的视图?
- 共库期两栈同写同序列,是否需要把所有自增序列改为两栈共用并冻结手工干预?以及 CodeRule 行锁序列号在 Go 与 Django 并存时的唯一性保证方案。
- 审计日志是否借迁移机会重构(正确填充 object_id、显式模型),还是先 1:1 兼容旧脏数据格式以免报表口径漂移?

---

## 自动升级重设计

将现有 Django 远程升级链路(manifest 客户端 + 升级编排 + Redis 队列 + updater 代理 + 进度中继 + WS 推送)1:1 迁移到 Go，完整保留既有安全模型,并修复 Docker 同路径挂载缺陷、补全原生升级一键能力。架构分两个二进制:erp(主后端,内含 manifest client / 升级编排 / 进度中继 / WS hub)与 erp-updater(distroless 静态特权代理,持 docker.sock,执行 备份→拉镜像→健康门→回滚)。两者经 Redis 队列(list)+ Pub/Sub(进度)解耦,与现状语义一一对应。

### 关键决策
- 保留双进程边界:特权操作(docker.sock、systemctl、写 .env/软链)只在 erp-updater 内,主后端无特权;两者只经 Redis 通信(队列 erp:upgrade:queue + 进度 Pub/Sub erp:upgrade:events),与 Django 现状同构,避免把特权拉进 Gin
- manifest 客户端用自定义 *http.Client + CheckRedirect 对 3xx 主动报错(禁跟随重定向);scheme 必 https;host 用与现状一致白名单(精确 + .suffix 匹配 raw.githubusercontent.com|github.com|objects.githubusercontent.com|ghcr.io);设 Timeout,拒 非 dict / 缺 latest_version
- check_update 缓存(go-redis SET key=erp:upgrade:check TTL=1200)+ 升级互斥锁 SET NX EX=3600(redsync,LOCK_KEY=erp:upgrade:lock),入队失败 defer 释放锁,语义同 _acquire/_release_lock
- WS 用 coder/websocket + 自建 hub + Redis Pub/Sub 扇出,鉴权双重:已认证(JWT)且持 system:upgrade(或 :前缀,superuser 旁路);未认证 close 4401,无权 close 4403,复刻 UpgradeProgressConsumer
- 进度中继作为主后端常驻 goroutine(替 upgrade_progress_relay):SUBSCRIBE erp:upgrade:events → GORM 落库 UpgradeJob(status/steps/finished_at)→ hub 广播 upgrade_<job_id> 组
- 原生升级:复刻 sha256 流式校验 + target_version 正则 [A-Za-z0-9._-]{1,64} 禁 . 前缀/.. + filepath.Clean 后校 commonpath 不逃逸 RELEASES_DIR;不再返 '暂未支持',真实现 解压→migrate→collectstatic→symlink+rename 原子换软链→systemctl 重启
- Docker 镜像优先用 manifest digest(ghcr.io@sha256)而非 tag,保不可变与可回滚;digest 占位(全 0)时回退 image_tag,记 _old_tag 供回滚
- 修复同路径挂载缺陷:updater 经 docker.sock 调宿主 daemon 时 compose 解析相对卷路径用的是宿主路径,与容器内 ERP_PROJECT_DIR=/project 不一致致 .env 与 compose 工作目录错配。修复=把宿主项目目录以同一绝对路径挂进 updater(host-path==container-path)+显式 compose --project-directory <abs>,消除漂移
- JobStore 用 GORM(gorm.DeletedAt 复刻 BaseModel),steps JSONB;append_step 改为中继侧整段覆盖(代理在 Redis 累积 state)避免并发写丢失

### 设计要点
## 自动升级重设计(Go)

目录:
```
cmd/erp/            主后端(Gin)
cmd/erp-updater/    distroless 特权代理
internal/upgrade/
  manifest.go       白名单+仅HTTPS+禁重定向
  orchestrator.go   check(缓存+单飞)/lock(NX)/enqueue
  relay.go          SUBSCRIBE→GORM落库→WS广播
  ws.go             coder/websocket hub(4401/4403)
  store.go          GORM UpgradeJob
internal/agent/     备份→拉镜像(digest)→健康门→回滚
```

要点:
- manifest:`http.Client{CheckRedirect: 3xx→err}`,host 精确+`.`子域白名单,缺 latest_version 报错。
- 编排:`SET check TTL1200`+redsync 单飞;`SET lock NX EX3600`,失败/异常 defer 释放。
- updater:优先 `ghcr.io@sha256`(digest)拉取,回退 tag;sha256 流式校验、`target_version` 正则+`filepath.Clean` 防穿越。
- 修缺陷:host 项目目录以**同一绝对路径**挂进 updater,`compose --project-directory <abs>` 与写 `.env` 同指,消除 `/project` vs `.` 漂移。
- 原生:真正实现 解压→migrate→collectstatic→`symlink+rename` 原子换链→systemctl,补全现状存根。
- WS/中继搬进主后端 goroutine,Redis 键/频道不变,与旧 Python updater 可互通灰度。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `gorm.io/gorm + gorm.io/driver/postgres`
- `github.com/jackc/pgx/v5`
- `github.com/redis/go-redis/v9`
- `github.com/go-redsync/redsync/v4`
- `github.com/coder/websocket`
- `github.com/golang-jwt/jwt/v5`
- `github.com/docker/docker/client (经 docker.sock 拉镜像/重建)`
- `github.com/spf13/viper`
- `github.com/golang-migrate/migrate/v4`
- `log/slog + go.opentelemetry.io/otel`
- `stdlib: net/http(CheckRedirect)、crypto/sha256、archive/tar、path/filepath、os/exec`

### 风险
- docker.sock 特权边界:Go updater 仍 root 等价,distroless 只缩小攻击面不消除;需确保不暴露网络入口、只读 sock 不可行(需写)、严限镜像来源
- 同路径挂载修复若宿主部署目录非 . 推断(用户自定义 compose 路径),探测错误会致 pull/up 错目录甚至误删——需启动期校验 compose 文件与 IMAGE_TAG 行存在
- 原生升级新启用:systemctl/软链原子切换在不同发行版/权限下行为差异,健康门失败回滚若软链已切但服务未起会留中间态
- WS 鉴权依赖手写 system:upgrade 前缀匹配(非 Casbin),权限服务返回格式变化易静默放行——必须逐条回归越权测试
- redsync 锁 TTL=3600 安全上限:进程已死会锁死至 TTL,期间无法重试;Go 需补看门狗续期或显式 force-unlock 入口
- Docker daemon 拉私有 GHCR digest 需登录态(现状 publish-manifest 已遇 GHCR 鉴权问题),updater 内须配 ghcr 凭据且不泄漏到 steps 日志

### 待定问题
- 原生升级目标用户是否仍存在?若全量 Docker,native 分支可降为存根省回归成本
- compose 项目目录如何可靠探测:是否约定固定宿主绝对路径(如 /opt/erp)并在安装脚本写死,彻底消除漂移?
- digest 拉取的 GHCR 凭据注入方式:docker login 持久化 vs 每次 X-Registry-Auth header?凭据轮换归谁管?
- 进度 steps 是否无限累积(现 86400s TTL)还是设上限防 JSONB 膨胀?
- 是否需多后端实例?若是 hub 必走 Redis Pub/Sub 扇出(已纳入);单实例可省一层
- 健康门期望版本比较:digest 升级时 health 返回 version 仍是 tag,需明确比对字段与口径

---

## 异步任务 / 实时 / 搜索

将 Celery+Beat、Django Channels、Elasticsearch 三套重型依赖收敛为复用现有 Redis/PG 的 Go 原生方案:asynq(含 cron) 一对一替换 celery+celery-beat 两个常驻容器(27 任务/约22 定时项);coder/websocket+自建 hub+Redis Pub/Sub 替换 Channels/Daphne(3 个 WS 端点:通知/仪表盘/升级进度);PostgreSQL tsvector+GIN+pg_trgm(中文 zhparser) 替换 ES,因实际索引仅 Item/Customer/Supplier 三类、搜索面浅。砍掉 JVM(ES)+Daphne 两类重容器,基础设施只剩 PG+Redis。

### 关键决策
- 异步任务用 hibiken/asynq:基于现有 Redis,asynq.Scheduler 承载 cron(对齐现 beat_schedule),asynqmon 面板替代 flower;一个 asynq 二进制同时跑 worker+scheduler,合并 celery/celery-beat 两容器
- 每分钟轮询型任务(process_webhook_deliveries、考勤 */5~*/30)优先改为 asynq 周期任务;考勤机 TCP/云同步因需局域网访问,保留 host 网络部署模式
- WebSocket 用 coder/websocket + 自建 Hub;沿用现有 group 语义:user_{id}(通知)、dashboard_updates(广播)、upgrade_{jobid}(升级进度);多实例间用 go-redis Pub/Sub 扇出,Hub 订阅频道再投递给本地连接
- WS 鉴权沿用 ?token= 查询参数 + golang-jwt/v5 在 Upgrade(握手)前校验;升级进度端点额外校验 system:upgrade 权限(对齐现 _can_watch),断线重连/心跳 ping-pong 自写
- 广播契约统一为 {type,data} JSON 信封,与现 group_send(type,...) 一致,前端 NotificationCenter/websocket store 零改动
- 搜索用 PG:在 item/customer/supplier 表加 tsvector 生成列 + GIN 索引,中文走 zhparser 自定义 PG 镜像;pg_trgm 支持编码/SKU 模糊;全局搜索聚合 5 类(items/customers/suppliers/projects/tasks)走 UNION 查询
- 升级进度 relay(Redis pub/sub→DB→WS)已是现成桥接模式,直接并入 Go Hub 的 Redis 订阅循环,无需独立常驻命令
- asynq 任务 payload 用 JSON,任务名沿用 module.action 命名;失败重试/超时/唯一性(asynq.Unique)替代 celery 默认行为

### 设计要点
## 异步/实时/搜索 Go 化

**异步(asynq)** 一个二进制合并 celery+celery-beat:
```
cmd/worker/  → asynq.Server(worker) + asynq.Scheduler(cron)
internal/jobs/{inventory,finance,oa,...}.go  // 27 handler
```
27 任务/约22 定时项逐条搬迁;`process_webhook_deliveries`(每分钟)与考勤 `*/5~*/30` 轮询优先评估事件化。asynqmon 替代 flower。

**实时(coder/websocket + Hub + Redis PubSub)** 保留 3 端点与 group 语义:
```
ws/notifications/ → user_{id}
ws/dashboard/     → dashboard_updates(广播)
ws/system/upgrade/{id}/ → upgrade_{id}
```
多实例经 go-redis Pub/Sub 扇出,信封 `{type,data}` 与现 `group_send` 一致 → 前端零改。握手用 `?token=` + golang-jwt 校验,升级端点加 `system:upgrade` 权限。现有 upgrade relay(Redis→DB→WS)直接并入 Hub 订阅循环。

**搜索(PG)** 砍掉 ES/JVM 容器。实测仅 Item/Customer/Supplier 三类入索引:
```sql
ALTER TABLE masterdata_item ADD search_vector tsvector
  GENERATED ALWAYS AS (to_tsvector('chinese', ...)) STORED;
CREATE INDEX ... USING GIN(search_vector);
-- SKU/编码: pg_trgm gin_trgm_ops
```
中文需 zhparser 自定义镜像;Squirrel 拼 to_tsquery。强搜索再上 Meilisearch 兜底。三块均可在 nginx 按路径灰度,与旧栈并存切流。

### 主要 Go 包
- `github.com/hibiken/asynq`
- `github.com/hibiken/asynqmon`
- `github.com/coder/websocket`
- `github.com/redis/go-redis/v9`
- `github.com/golang-jwt/jwt/v5`
- `github.com/jackc/pgx/v5`
- `github.com/Masterminds/squirrel`
- `github.com/google/uuid`
- `log/slog`

### 风险
- zhparser 需自编译 PG 镜像并 CREATE EXTENSION,部署/升级链路新增复杂度;若 ES 召回质量(分词/相关性)实际依赖较深,PG 全文检索可能不达预期,需预留 Meilisearch 单二进制兜底
- asynq 无 celery 的 chain/group/chord 编排原语,若现任务存在隐式链式依赖需手写编排或拆分
- 考勤机同步(TCP/iclock 解析/云 API)是最脆任务,host 网络 + 外部 IO 在 Go 重写时易引入连接/编码差异,需重点回归
- WS 多实例 Redis Pub/Sub 无 ack/持久化,实例重启或消息风暴可能丢推送(Channels 同样如此但需评估对升级进度的影响)
- search_vector 生成列在大表上首次回填会锁表/耗时,需在低峰执行或用 CONCURRENTLY 建索引
- ES 实时索引由 django-elasticsearch-dsl signals 维护;PG 生成列是事务内自动更新,语义更强,但跨域聚合搜索(projects/tasks)若无生成列需另设方案

### 待定问题
- 全局搜索的 projects/tasks 两类是否也需 tsvector 生成列?现 ES 索引这两类但 documents.py 仅见 masterdata 三类,需确认 projects 侧 ES Document 是否真实启用
- 考勤每分钟/5分钟轮询是否可改 LISTEN/NOTIFY 或设备推送事件驱动,以减少空轮询?
- 升级进度 relay 现为独立 management command,Go 端是合并进 Hub 进程还是保留独立 sidecar?
- ES 实际查询是否用到高亮/聚合/拼音/同义词等 PG 难复刻特性?决定是否必须上 Meilisearch
- dashboard 广播频率与数据量——是否需要在 Go 侧加节流/合并,避免 KPI 重算压垮 PG
- asynq 是否需要任务结果持久化(celery result backend 当前是否被消费)

---

## 审批工作流引擎

将 Django 现有「可配置审批流 + WorkflowEnforcementMixin」迁移为 Go 实现。保留四模型(定义/步骤/实例/任务)与按 business_type+amount_threshold 选流、按金额跳步、超时、抄送、自动批准兜底等语义;ViewSet 级强制改为 service 层强制 + Gin 中间件双层。核心架构修正:消除现有 _on_workflow_complete 巨型 if/elif 反向 import 全部业务域的反依赖 —— 改为「审批结果领域事件 + 回调注册表(Handler Registry)」,各业务域在启动时向 engine 注册自己的 ApprovalCallback,engine 只持有接口不持有任何业务包,恢复开闭原则与单向依赖。

### 关键决策
- 四模型 1:1 保留:WorkflowDefinition/WorkflowStep/WorkflowInstance/WorkflowTask,GORM 模型嵌入 BaseModel(gorm.DeletedAt 软删除 + created_by 钩子),schema 复用现有 workflow_* 表,golang-migrate 仅接管增量(如新增 approver_type 枚举)
- 选流算法保留:按 business_type 过滤 is_active,按 amount_threshold DESC 取首个 threshold<=amount(或 threshold IS NULL)者
- 消除反依赖:废弃 _on_workflow_complete 巨型 if/elif。定义 ApprovalCallback 接口 {OnApproved/OnRejected/OnWithdrawn(ctx, businessID, instance)},引入 CallbackRegistry(map[businessType]ApprovalCallback);各业务 service 在 init/wire 时 engine.Register("SALES_ORDER", soCallback)。engine 包零业务 import,依赖方向倒置为业务→engine
- 双层强制:(1) service 层为唯一真相 —— SubmitForApproval / TryDirectAction 必经 engine.Guard;(2) Gin 中间件 ApprovalGuard(businessType, idParam) 作为快速失败前置,拦截 PENDING 实例下的直接 confirm/approve 路由。中间件不替代 service 校验,只做边界拦截
- 自动批准兜底保留:engine.SubmitForApproval 找不到启用流程时返回 AutoApproved=true,调用方据此置「已批准」终态,语义对齐现有 start_workflow_or_auto_approve
- 审批人解析(USER/ROLE/DEPARTMENT_MANAGER/PROJECT_MANAGER/SUPERIOR)抽成 AssigneeResolver 接口,ROLE/DEPT 走 IAM 服务,PROJECT_MANAGER 这类需业务上下文的改由 callback 提供 ResolveContext 而非 engine 反查业务表,去掉 _get_project_manager 的反向 import
- 状态流转放 service,用显式状态常量 + 校验(task 仅 PENDING 可 approve/reject),transaction 走 GORM tx;审批/拒绝/撤回三入口统一经 engine.Transition,完成时同事务内 publish 领域事件后触发 callback
- COUNTERSIGN 会签补齐:现有 model 声明却未实现,Go 版 action_type=COUNTERSIGN 时一步生成多 task,全部 APPROVED 才进下一步(用 step 级 task 计数),修复既有缺陷
- 超时:WorkflowTask.deadline 落库,用 asynq 定时任务(替代 Celery beat)扫描超时 task,按策略 escalate/auto-pass;通知与抄送经 notification 服务异步派发

### 设计要点
## 审批工作流引擎(Go)

**包结构**
```
internal/workflow/
  model/     # 4 表 GORM 模型 + 枚举常量
  engine/    # 选流/启流/Transition 状态机(零业务 import)
  callback/  # ApprovalCallback 接口 + CallbackRegistry
  resolver/  # AssigneeResolver(USER/ROLE/DEPT/SUPERIOR)
  guard/     # Gin 中间件 + service 级 Guard
  repo/ task/ api/
```

**反依赖修正(关键)** 现 Django `_on_workflow_complete` 用巨型 if/elif 反向 import 全部 15 域直改状态。Go 改为回调注册:
```go
type ApprovalCallback interface {
  OnApproved(ctx, businessID int64) error
  OnRejected(ctx, businessID int64) error
  OnWithdrawn(ctx, businessID int64) error
}
// 业务侧:engine.Register("SALES_ORDER", soCallback)
```
engine 只持接口,依赖方向倒置为「业务→engine」,恢复开闭。

**双层强制**
- service 唯一真相:`SubmitForApproval` 无流程→`AutoApproved=true`(对齐 auto-approve 兜底);`Guard` 校验 task assignee/状态。
- Gin 中间件 `ApprovalGuard(bizType,idParam)`:PENDING 实例下拦截直接 confirm/approve,fast-fail,不替代 service 校验。

**补齐 COUNTERSIGN**:同 step 生成多 task,全 APPROVED 方进下一步(修复既有声明未实现缺陷)。超时走 asynq 替代 Celery beat。

### 主要 Go 包
- `internal/workflow (engine 核心:零业务依赖)`
- `internal/workflow/model (GORM 模型 + 枚举常量)`
- `internal/workflow/engine (选流/启流/状态机/Transition)`
- `internal/workflow/callback (ApprovalCallback 接口 + CallbackRegistry)`
- `internal/workflow/resolver (AssigneeResolver: USER/ROLE/DEPT/SUPERIOR;PROJECT_MANAGER 走 callback context)`
- `internal/workflow/guard (Gin 中间件 ApprovalGuard + service 级 Guard 校验)`
- `internal/workflow/repo (GORM 仓储;复杂只读用 sqlc 待办聚合)`
- `internal/workflow/task (asynq 超时扫描 + 通知派发 handler)`
- `internal/workflow/api (Gin handler: 待办/审批/拒绝/撤回/流程定义 CRUD)`

### 风险
- 回调注册表若某业务域忘记 Register,审批通过后业务状态不翻转(静默失败)。需启动期校验:engine 已知 business_type 集合必须全部有 callback,缺失则 fail-fast 启动报错
- 敏感:Casbin RBAC 不覆盖「待办 assignee 越权」与 skip_assignee_check 旁路,需在 engine.Guard 内手写 assignee/superuser 校验并逐条回归,不能仅靠中间件
- COUNTERSIGN 现有代码声明未实现,Go 若补齐属行为变更,可能与某些已配置会签步骤的历史预期冲突,需确认现网是否有会签流程
- 中间件与 service 双层校验若不一致(如中间件放行但 service 拦截)会产生迷惑性错误;须以 service 为唯一真相,中间件仅做 fast-fail
- AssigneeResolver 的 PROJECT_MANAGER/SUPERIOR 依赖 IAM 部门树与业务上下文,跨服务调用失败时现有代码 fallback 到 superuser —— 此兜底可能造成越权审批,迁移时需评估是否保留
- asynq 超时任务替代 Celery beat,定时漂移或 worker 未起会导致超时 task 永不触发;需 asynqmon 监控 + 幂等
- 事务边界:现有 approve 在同事务内 _create_next_task 递归并触发 callback,callback 内若调用别的业务事务,Go 下需明确 callback 在同 tx 还是事务后经事件异步,避免长事务与跨域死锁

### 待定问题
- 回调执行时机:OnApproved 应在审批事务内同步执行(强一致,但耦合事务/有长事务风险),还是事务提交后经领域事件异步(松耦合,但需补偿)?现有是同事务同步
- PROJECT_MANAGER/SUPERIOR 解析失败兜底到 superuser 的越权兜底是否保留,还是改为审批挂起/报错?
- COUNTERSIGN 会签是否现网真实使用?决定是补齐实现还是先标记 unsupported
- 待办列表(my-tasks)聚合是否量大到需要 sqlc + 物化/缓存,还是 GORM 直查即可?
- 审批通知/抄送(站内信+钉钉/企微)迁移到 asynq 后,失败重试与去重策略
- amount 字段多币种问题:现有单一 Decimal 无币种,选流阈值跨币种是否需要归一化(财务域已知多币种风险)
- Gin 中间件如何拿到 businessID(路由参数 vs body),不同业务 ViewSet 单号字段不统一(workflow_no_field 各异)

---

## 性能策略

为 Go 1.23 + Gin + GORM/sqlc 双层数据访问的 ERP 重写定义统一性能策略:GORM 主层默认 Preload/Joins 消除 N+1、对标 StandardPagination(20/页, max 1000) 的键集+偏移分页、go-redis 多级缓存与 singleflight 防击穿、pgxpool 连接池、报表聚合用 sqlc 下推 PostgreSQL、并发安全用 redsync 分布式锁与 SELECT FOR UPDATE。覆盖现有四大热点:部门/BOM 树递归、看板 N×M 聚合、management_dashboard 巨型聚合、库存/校验全表 Python 循环。

### 关键决策
- 读写分层:GORM 负责 80% CRUD,所有列表/详情查询默认显式 Preload/Joins 关联,杜绝隐式懒加载(Go 无 Django ORM 隐式查询,但 Preload 漏配会退化为多次查询)——以 lint/code review 强制;复杂只读聚合(BOM 递归 CTE、成本核算、报表账龄)一律走 sqlc 编译期类型安全查询,零反射跑满 PG
- 分页对标 StandardPagination:默认 page_size=20、max=1000;深翻页(导出/大列表)改用 keyset/游标分页(WHERE id > last_id ORDER BY id LIMIT n)避免 OFFSET 全表扫描;COUNT 与数据查询并发执行(errgroup),超大表 COUNT 走估算(pg_class.reltuples)或缓存
- 缓存三级:进程内 LRU(ristretto,菜单树/编码规则等低频变更)→ Redis(权限/数据范围/会话,复刻现有 user_permissions:{id} 键, TTL+主动失效)→ DB;缓存击穿用 singleflight 合并并发回源,雪崩用 TTL 抖动;写后失效在领域事件钩子统一处理而非散落
- 连接池:pgxpool 统一管理,MaxConns 按 (核数*2~4) 与 PG max_connections 折算(现 CONN_MAX_AGE 长连接思路升级为连接池),设 HealthCheckPeriod、MaxConnLifetime/IdleTime;Redis go-redis 连接池 PoolSize 独立配置;避免每请求新建连接
- 热点接口优化:部门/BOM 树用递归 CTE 一次查询替代逐层查库(现状递归 N 次);看板/产能看板用单条 GROUP BY 聚合替代 Python 逐工作中心逐天循环(现 N×M 查询),结果缓存+前端轮询改 WebSocket 推送;库存/数据校验全表循环改为 SQL 批量聚合(负库存/账实差异用窗口函数一次算出)
- 报表聚合下推 DB:management_dashboard/KPI/账龄/库存周转等跨域聚合用 sqlc 写成单条聚合 SQL,口径(含税/账龄/状态)集中在 SQL view 或共享查询定义,避免现状多处口径漂移;重报表结果进 Redis 缓存并按业务事件失效,可选物化视图(REFRESH MATERIALIZED VIEW CONCURRENTLY)
- 并发安全:库存移动(StockMove 唯一真相源)、编码序列号生成、财务核销用 SELECT ... FOR UPDATE 行锁保证账实/借贷一致;跨实例临界区(MRP 生成、对账)用 redsync 分布式锁;加权平均成本更新在单事务内完成,避免现状非原子调整;乐观锁(version 列)用于低冲突的表单更新

### 设计要点
# 性能策略(Go 侧)

**默认实践**
- 数据访问双层:GORM 主 CRUD,列表/详情**显式 Preload/Joins**,禁隐式多查;复杂聚合切 **sqlc**(编译期类型安全,跑满 PG)。动态筛选用 squirrel。
- 分页对标 `StandardPagination`:`page_size=20 / max=1000`;深翻页改 keyset。
```go
db.Where("id > ?", cursor).Order("id").Limit(20) // 替代 OFFSET
g.Go(countFn); g.Go(dataFn) // errgroup 并发 COUNT+数据
```
- 缓存三级:ristretto(进程内)→ go-redis(权限/会话, 复刻 `user_permissions:{id}`)→ DB;`singleflight` 防击穿、TTL 抖动防雪崩。
- 连接池:`pgxpool`(MaxConns=核数×2~4)、go-redis PoolSize 独立。

**热点优化清单**
| 现状痛点 | Go 方案 |
|---|---|
| 部门/BOM 树递归 N 次查库 | `WITH RECURSIVE` 一次取 |
| 看板 N×M 逐天 aggregate | 单条 GROUP BY + 缓存 + WS 推送 |
| management_dashboard 巨型聚合无缓存 | sqlc 聚合 SQL 下推 + Redis 缓存 + 物化视图 |
| 库存/校验全表 Python 循环 | 窗口函数批量算账实差异 |

**并发安全**:StockMove/序列号/财务核销用 `SELECT FOR UPDATE`;跨实例临界区用 `redsync`;加权平均成本单事务内原子更新。索引增量加(`is_deleted` 部分索引、keyset 复合索引、`CONCURRENTLY`)。

### 主要 Go 包
- `github.com/jackc/pgx/v5 + pgxpool (原生 PG 协议连接池)`
- `gorm.io/gorm + gorm.io/driver/postgres (主 CRUD, 复用 pgx)`
- `sqlc-dev/sqlc (报表/聚合编译期类型安全, 配 pgx/v5 驱动)`
- `Masterminds/squirrel (列表页动态可选筛选 SQL 拼装)`
- `redis/go-redis/v9 (缓存/会话/限流)`
- `go-redsync/redsync/v4 (分布式锁)`
- `dgraph-io/ristretto (进程内 LRU 缓存)`
- `golang.org/x/sync/singleflight + errgroup (回源合并 / 并发 COUNT+数据)`
- `golang.org/x/time/rate 或 go-redis 限流 (热点接口限流)`
- `github.com/prometheus/client_golang + go.opentelemetry.io/otel (慢查询/接口耗时指标与链路追踪定位热点)`

### 风险
- GORM Preload 漏配会静默退化为 N+1(无 Django 式可观测懒加载告警),需 OTel 慢查询+查询计数埋点 + code review 兜底
- GORM 重 JOIN/复杂条件易生成低效 SQL,边界(报表/递归)必须切 sqlc,否则性能退化
- Redis 缓存与 DB 一致性:写后失效若遗漏(领域事件未覆盖某写路径)导致脏读,权限/数据范围缓存尤甚(安全攸关)
- FOR UPDATE 行锁范围过大或顺序不一致引发死锁;分布式锁(redsync)故障转移期锁失效需配合 DB 唯一约束/幂等兜底
- 物化视图刷新窗口内数据陈旧,需明确报表实时性 SLA;CONCURRENTLY 刷新要求唯一索引
- 连接池 MaxConns 与 PG max_connections、asynq worker、多实例叠加易耗尽连接,需全局容量预算

### 待定问题
- 报表/看板可接受的数据陈旧度(缓存/物化视图 TTL)各域 SLA 是否统一?
- 深翻页是否全面切 keyset,还是仅导出场景?前端 vxe-table 虚拟滚动是否改用游标契约?
- 多实例部署的目标实例数与 PG max_connections 上限,用于定 pgxpool MaxConns 与 asynq 并发
- 权限缓存失效策略:沿用现有 user_permissions:{id} 主动失效,还是改短 TTL + 事件驱动双保险?
- 是否引入读写分离/只读副本承载报表聚合,避免重查询冲击主库 OLTP?

---

## 安全模型

跨域安全模型:以 Gin 中间件链统一承载鉴权、CORS、限流、安全响应头、审计;数据访问全程参数化(GORM/pgx/sqlc 均不拼接 SQL,Squirrel 仅生成占位符)杜绝注入,弃用现有正则式 SQL 注入检测中间件;请求体用 validator/v10 结构化校验;审计模型对标并修复 AuditLogMiddleware 的三大缺陷(URL 猜模型/object_id 恒空/直存请求体);敏感字段脱敏从 Django 的"inert by design"升级为真正在序列化层按角色生效;密钥与配置经 viper 从 env/yaml 注入、绝不入库不入日志;Redis 滑动窗口限流复刻 login 5/min 等策略;依赖与镜像安全靠 govulncheck + Trivy + distroless 静态二进制 + GHCR digest 锁定。

### 关键决策
- 鉴权采用双层:golang-jwt/v5 解析校验 token(HS256,access 120min/refresh 7d,沿用现有 .env 的 JWT_* 变量与 lifetime),Casbin/v2 做 menu 级 RBAC enforce;数据范围(data_scope)、上下文角色(@owner/@assignee)、敏感字段脱敏在 Casbin 之外手写并逐条回归——安全攸关不做一一映射。
- 中间件链固定顺序:Recovery → RequestID → SecurityHeaders → CORS → RateLimit → JWTAuth → Casbin 授权 → DataScope 注入 context → Audit(defer 写入)→ 业务 handler;鉴权失败短路,审计仍记录。
- SQL 注入防护改为纯参数化:GORM 用占位符与 Session、sqlc 编译期生成预编译语句、Squirrel 动态拼装只产 $N 占位符、pgx/v5 扩展协议绑定参数;删除现有 SQLInjectionProtectionMiddleware 正则黑名单(误报且不可靠),改为白名单式排序/筛选字段校验(防止动态 ORDER BY/列名注入)。
- CORS 用 gin-contrib/cors,白名单 origin(读 CORS_ALLOWED_ORIGINS)、AllowCredentials=true;前后端分离 + Bearer JWT(非 Cookie 会话),CSRF 风险天然降低,默认不发 CSRF token;若引入 cookie 态 refresh 再补 SameSite=Strict + 双提交 token。
- 审计对标 AuditLogMiddleware 但修三处缺陷:不靠 URL 猜模型而由 handler/repo 钩子显式上报 resource+object_id;changes 记录结构化 before/after diff 而非原始请求体(顺带过滤敏感字段);失败请求(4xx/5xx)与登录登出也入审计(安全事件)。审计写入异步(asynq 或 goroutine+channel)不阻塞主请求。
- 敏感字段脱敏真正落地:在响应序列化层按当前用户角色对 phone/银行卡/成本/工资等打码,字段→所需权限映射集中配置;修正 Django 中脱敏从未生效的过度设计。
- 密钥/配置经 spf13/viper 分层加载(默认值<yaml<env),SECRET_KEY/JWT 密钥/DINGTALK/WECHAT secret 等仅从环境注入;slog 输出加敏感字段 redaction,杜绝密钥/token/密码进日志;WebSocket 鉴权不再用 ?token= query(会进 access log),改 Sec-WebSocket-Protocol 子协议或首帧鉴权。
- 限流用 go-redis/v9 + redis_rate(GCRA 滑动窗口)复刻现有策略:login 5/min/IP、password-reset 3/h/IP、认证用户 1000/h、匿名 100/h;429 返回 retry_after。分布式锁与幂等用 redsync。
- 依赖与镜像安全纳入 CI:govulncheck 扫 Go 依赖 CVE、Trivy 扫镜像与 SBOM、多阶段构建产 distroless/static 非 root 二进制、镜像经 GHCR digest 锁定并由现有 erp-updater 原子替换回滚;依赖用 go.sum 校验和 + dependabot。

### 设计要点
## 安全模型(跨域)

**中间件链(顺序敏感)**
```
Recovery → RequestID → SecurityHeaders → CORS
 → RateLimit(redis_rate) → JWTAuth(jwt/v5)
 → Casbin(menu RBAC) → DataScope(注入 ctx)
 → Audit(defer 异步写) → handler
```

**九大关注点落地**
- 输入校验:validator/v10 结构体 tag + bluemonday 富文本消毒。
- 防注入:GORM/sqlc/pgx 全参数化,Squirrel 仅生成 `$N`;**删除** Django 正则黑名单中间件,改排序/列名白名单。
- 鉴权:jwt/v5 验签 + Casbin enforce;data_scope、@owner/@assignee、字段脱敏 Casbin 外手写并逐条回归。
- CORS/CSRF:白名单 origin;Bearer 态免 CSRF,cookie 态再补 SameSite。
- 脱敏:序列化层按角色打码(修正 Django inert design),policy 表驱动。
- 审计:对标 `AuditLogMiddleware`,修三缺陷——显式上报 resource+object_id、存 before/after diff、4xx/5xx 与登录也记。
- 密钥:viper env 注入,slog redaction,WS 鉴权移出 query。
- 依赖/镜像:govulncheck + Trivy + distroless 非 root + GHCR digest。
- 限流:GCRA 滑窗,login 5/min、reset 3/h、用户 1000/h。

**目录**
```
internal/middleware/{auth,casbin,cors,ratelimit,audit,secheaders}.go
internal/security/{datascope,masking,jwt}.go
```

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `github.com/golang-jwt/jwt/v5`
- `github.com/casbin/casbin/v2`
- `github.com/gin-contrib/cors`
- `github.com/go-playground/validator/v10`
- `github.com/redis/go-redis/v9`
- `github.com/go-redis/redis_rate/v10`
- `github.com/go-redsync/redsync/v4`
- `github.com/spf13/viper`
- `github.com/microcosm-cc/bluemonday`
- `golang.org/x/crypto/bcrypt`
- `github.com/jackc/pgx/v5`
- `gorm.io/gorm`
- `github.com/Masterminds/squirrel`
- `golang.org/x/vuln/cmd/govulncheck`
- `github.com/getsentry/sentry-go`
- `log/slog`

### 风险
- data_scope/上下文角色/MODULE_MENU_MAP 越权边界在 Casbin 之外手写,易与 Django 原行为偏差产生越权——必须逐条回归,这是最高风险项。
- Django 现有字段脱敏 inert(从未生效),Go 真正启用后可能暴露此前前端依赖完整字段的隐性契约,需排查 196 个视图。
- 审计从 URL 猜测改显式上报,需在每个 repo/handler 插桩,遗漏点会丢审计;迁移期建议双写比对。
- WebSocket query token 改造涉及前端 request.ts/重连逻辑,需同步改动否则连接失败。
- 删除正则式 SQL 注入中间件后,动态 ORDER BY/列名等若未加白名单仍可注入,需在 Squirrel 拼装处强制字段白名单。
- CORS_ALLOW_CREDENTIALS=true + 通配 origin 是经典漏洞,迁移时务必严格白名单。

### 待定问题
- refresh token 续期是否引入 httpOnly cookie 态?若是则需补 CSRF 防护(SameSite+双提交),纯 Bearer 则不需。
- 敏感字段→权限映射清单由谁定义?需业务确认 phone/成本/工资/银行卡等具体脱敏范围与可见角色。
- 审计是否需保留请求体快照用于取证,还是仅 diff?diff 更安全但取证信息少。
- Casbin 模型用 RBAC with domains 还是扁平 menu 码?取决于是否需多租户/部门维度 enforce。
- 限流维度是否需按 API 分组细化(如导出类更严),还是沿用现有四档?
- 密钥轮转策略:JWT 签名密钥是否支持多 kid 平滑轮转,还是停机更换?

---

## 前端新 SPA 与 UI 易用性

在不更换前端语言栈(Vue 3.5 + TS strict + Vite 6 + pnpm + Element Plus)的前提下,另起新 SPA 工程,作为 Go 后端的唯一 Web 客户端。新栈仅换工程基座与数据层范式:引入 TanStack Query(Vue) 统一服务端状态(缓存/重试/失效,替代手写 loading),vxe-table 补齐大数据虚拟表格,Pinia 收敛为纯客户端态(user/permission/companyConfig/ui)。完整复刻 request.ts 的 JWT 刷新 + 401 排队重试 + 刷新后回灌 profile/permissions/menus/dataScopes 三段式契约,并把权限三件套(路由 meta.menuId / hasPermission 父码通配 / v-permission 指令)按现有语义 1:1 移植。196 个旧视图走"增量重构、按模块迁移、双栈并存"路线而非一次性重写。后端 Gin 侧补 OpenAPI(swaggo) 以便前端按 schema 生成类型化 api 客户端。

### 关键决策
- 另起新 SPA 但沿用 Vue 3.5+TS strict+Vite6+pnpm+Element Plus,只换工程基座,不改语言/UI 框架;196 视图增量重构、按模块迁移、新旧双栈并存(单仓多入口或 monorepo workspace),禁止 big-bang 重写
- 服务端状态统一交 TanStack Query(Vue):每个 api/<module>.ts 暴露 useXxxQuery/useXxxMutation,统一 staleTime/重试/失效,删除视图内手写 loading/error 样板;客户端态(登录态/权限/公司配置/UI 偏好)留 Pinia
- 完整复刻 request.ts 契约:request 拦截器注入 Bearer;响应拦截器解包 response.data、blob 透传;401 单飞刷新(isRefreshing+failedQueue 排队重放)、刷新成功后回灌 setPermissions/setMenus/setDataScopes 再 processQueue;刷新失败清 token 跳 /login。TanStack Query 复用同一 axios 实例,不绕过拦截器
- 权限三件套 1:1 等价:路由 meta 用 menuId+requiresAuth,全局 beforeEach 校验登录与 hasPermission(menuId);hasPermission 保留 '*' 全通+精确命中+父码通配(a:b:c→a:b→a 逐级回退);保留 v-permission 指令(display 隐藏+watchEffect 响应权限变更);dataScopes 仅前端展示用,真实数据范围过滤在 Go 后端 get_queryset 等价层
- 组件库+设计系统:Element Plus 为基座,在其上抽 packages/ui 业务组件层(CrudTable/SearchForm/PageHeader/StatusTag/MoneyText/AuditTrail/AttachmentUploader),沉淀 design tokens(色板/间距/字号/圆角 CSS vars + Element 主题变量覆盖),统一空态/加载骨架/确认弹窗/批量操作交互;大列表一律 vxe-table 虚拟滚动,普通表单/小表用 Element
- API 客户端按模块组织 api/<module>.ts(沿用现有 28 个模块划分),由 swaggo 生成的 OpenAPI schema 用 openapi-typescript 生成 types,query/mutation 包一层;路径前缀仍 /api,保持 /erp/ base 与 nginx 一致
- 可访问性与易用性:导航做面包屑+多标签页(keep-alive)+可搜索侧边菜单+菜单按权限裁剪;表单做即时校验+错误聚焦+脏值离开拦截+键盘提交;表格做列固定/列设置持久化/服务端分页排序筛选/批量选择/导出统一入口;反馈做 toast+全局错误边界+乐观更新回滚+操作二次确认,补 ARIA/焦点环/对比度/键盘可达

### 设计要点
## 新 SPA 设计要点

工程基座换 Vite6+pnpm,语言/UI 框架不变(Vue3.5+TS strict+Element Plus)。

目录:
```
src/
  api/<module>.ts   # 28 模块,query/mutation 封装
  stores/           # Pinia 仅客户端态: user/permission/companyConfig/ui
  packages/ui/      # 业务组件: CrudTable/SearchForm/StatusTag...
  router/  meta:{menuId,requiresAuth}
  utils/request.ts  # 原样移植
```

**数据层**:TanStack Query 管服务端态(缓存/重试/失效),复用同一 axios 实例(不绕拦截器);客户端态留 Pinia。

**request.ts 契约复刻**:Bearer 注入→response.data 解包(blob 透传)→401 单飞刷新(isRefreshing+failedQueue 排队重放)→刷新成功回灌 setPermissions/Menus/DataScopes→processQueue;失败清 token 跳登录。

**权限三件套等价**:
- 路由 `meta.menuId` + beforeEach 校验 hasPermission
- hasPermission 保留 `*`+精确+父码通配(`a:b:c→a:b→a`)
- v-permission 指令(display 隐藏 + watchEffect 响应)
- dataScopes 仅 UI 展示,真实过滤在 Go 后端

**易用性**:导航(面包屑+多标签 keep-alive+可搜菜单+按权裁剪);表单(即时校验+错误聚焦+脏值拦截);表格(vxe-table 虚拟滚动+列持久化+服务端分页/排序/筛选+统一导出);反馈(toast+错误边界+乐观回滚+二次确认),补 ARIA/焦点环/对比度。

后端配 swaggo 生成 OpenAPI,前端 openapi-typescript 生成类型消除 any。

### 主要 Go 包
- `github.com/swaggo/swag + github.com/swaggo/gin-swagger(注解生成 OpenAPI/Swagger UI,供前端 openapi-typescript 生成类型)`
- `github.com/gin-gonic/gin(提供前端所需的 /api 路由、CORS、静态资源/SPA history fallback 中间件)`
- `github.com/gin-contrib/cors(本地 pnpm dev 跨域)、github.com/gin-contrib/static 或自写 NoRoute 把非 /api 请求回退到 index.html 支撑 history 路由`
- `github.com/golang-jwt/v5(签发 access/refresh,匹配前端 /auth/login 与 /accounts/refresh 刷新契约)`
- `前端工具(非 Go):pnpm、vite@6、@tanstack/vue-query、vxe-table、openapi-typescript、vue-tsc(strict)、eslint/prettier`

### 风险
- 权限语义漂移:hasPermission 父码通配 + MODULE_MENU_MAP 桥接是越权高发区,新栈若与 Go 鉴权层(Casbin+手写数据范围)实现不一致会造成前端可见但后端拒绝(或反之)的体验/安全裂缝,必须以后端为准并逐条回归权限测试
- request.ts 复刻不完整:401 单飞队列、刷新后 profile 回灌、blob 分支、解包语义任一遗漏都会引发并发刷新风暴、登录态丢失或下载损坏;TanStack Query 若另起 fetch 绕过该 axios 实例会丢失拦截器保护
- 双栈并存期复杂度:新旧路由/样式/Element 版本/构建产物共存易冲突,base /erp/ 与 nginx 路由需同步,迁移拖长则长期维护两套
- data_scope 仅前端展示但被误当真实过滤,导致敏感数据范围在前端被绕过的安全误判;字段脱敏旧栈本就惰性失效,新栈不可沿用该错觉
- 196 视图 + 60+ 字段宽模型(如 ProjectBOM/Item)迁到 strict TS + 类型化 schema 工作量被低估,any 兜底清不干净则 TS strict 价值打折
- vxe-table/TanStack Query 学习曲线与 Element Plus 交互范式融合成本,设计系统若不先定 tokens 与业务组件契约,各模块各写一套会再次产生臃肿视图

### 待定问题
- 新旧 SPA 共存形态:同一仓库 pnpm workspace 双包 + nginx 按路径分流,还是新工程独立仓?迁移完成的判定标准与下线旧栈时间点?
- 后端是否统一改造登录/profile 响应为稳定 OpenAPI schema(规范化 data_scope 枚举、统一分页信封),以便前端用 openapi-typescript 生成类型并消除 any?
- data_scope 在新前端的定位是否明确仅 UI 展示、所有真实过滤后端执行?是否需要前端据 dataScope 调整列表查询参数(如默认部门筛选)?
- 设计系统目标:是仅做 Element Plus 主题 token 覆盖,还是要建独立 packages/ui 组件库并文档化(Storybook/Histoire)?投入与 196 视图收益比?
- 可访问性目标等级(是否对标 WCAG 2.1 AA)?多标签页 keep-alive 与 TanStack Query 缓存的内存/失效策略如何协调?
- 导出从前端 xlsx 切换为后端 blob 导出的范围与节奏?Web 客户端是否仍需兼容微信小程序的 API 契约约束(避免改动 /api 破坏 miniprogram)?

---

## 项目布局 / 构建 / 部署 / 可观测

为 Go 重写设计跨域工程基座:模块化单体目录(cmd/internal/domain 按 15 限界上下文切分,共享 platform 内核)、viper 配置、distroless 多阶段 Dockerfile、对标现有 9 服务的 docker-compose(用 asynq 取代 celery/celery-beat;ES 用 PG tsvector 替代;沿用 updater+relay 升级机制)、保留 install.sh/ps1 一键脚本、slog+OTel+prometheus 三件套可观测、/healthz 与 /readyz 探针、GHCR 多架构 CI 与 manifest digest 回填全部保留。schema 整体保留,golang-migrate 只接管增量。

### 关键决策
- 模块化单体而非微服务:单一二进制 cmd/erpd 内挂 Gin 路由,15 上下文落在 internal/domain/<ctx>,每个含 handler/service/repo/model;共享能力归 internal/platform(auth/audit/code/workflow/attach/notify/cache/db/obs)。砍掉 celery/celery-beat/elasticsearch 三个容器,新 compose 为 7 业务+updater+relay,JVM 重容器消除。
- 异步任务用 asynq 内嵌同一镜像:开 worker 子命令(erpd worker / erpd scheduler)对一 celery+beat,复用 Redis,不再单独打包;asynqmon 面板可选 profile 暴露。
- 配置用 viper:env > yaml(config.yaml)> 默认值,直接吃现有 .env/.env.docker 的同名键(DB_HOST/REDIS_URL/SECRET_KEY 等),零迁移成本;敏感项仍走环境变量。
- Dockerfile 两阶段 distroless:builder(golang:1.23)CGO_ENABLED=0 静态编译 + swag 生成 + sqlc 生成 + golang-migrate 文件 embed;runtime 用 gcr.io/distroless/static:nonroot,无 shell、非 root、镜像由 ~400MB 降至 ~30MB,升级回滚更稳。
- 迁移内嵌二进制:golang-migrate 用 //go:embed migrations 打包,启动期(RUN_BOOTSTRAP=1 等价)自动 up;现有 161 迁移视为 baseline 不重放,只接管增量编号。
- 健康检查双探针:/healthz(liveness,进程存活)与 /readyz(readiness,探 PG/Redis 连通);compose healthcheck 由 curl 改为二进制自带 `erpd healthcheck` 子命令(distroless 无 curl)。
- 可观测三件套:log/slog(JSON handler,注入 trace_id/request_id)+ otelgin 中间件导出 trace(OTLP)+ promhttp 暴露 /metrics(RED 指标:请求量/错误率/延迟+ asynq 队列深度);Sentry-go 接 panic/error。链路与日志通过 trace_id 串联。
- 升级机制完全沿用:erp-updater(Docker socket 镜像原子替换+回滚)与 erp-upgrade-relay(进度中继)不改;relay 由 manage.py 子命令改为 `erpd upgrade-relay` 子命令,读写同一 Redis 进度通道,前端无感。
- CI 保留多架构 buildx(linux/amd64+arm64)+ metadata-action 语义化 tag + manifest.json digest 回填 job;新增 lint(golangci-lint)、test、govulncheck 三步,镜像名 atm-erp-backend/frontend/updater 不变以兼容现有 manifest。

### 设计要点
## 目录布局
```
cmd/erpd/main.go         # cobra: serve|worker|scheduler|migrate|seed|upgrade-relay|healthcheck
internal/
  platform/              # 共享内核(对标 apps/core)
    config(viper) db(gorm+pgx池) obs(slog+otel+prom) auth(jwt+casbin)
    audit code workflow attach notify cache(redis+redsync) task(asynq)
  domain/<ctx>/          # 15 限界上下文: iam/masterdata/sales/purchase/
    inventory/projects/production/finance/oa/reports ...
    handler.go service.go repo_gorm.go query.sql(sqlc) model.go
  migrations/*.sql        # golang-migrate, //go:embed 启动自动 up
api/docs/                 # swag 生成 OpenAPI
deploy/{updater,compose} install.sh install.ps1 manifest.json
```
## 关键取舍
- 单二进制多子命令:web/worker/scheduler/relay 同镜像,celery+beat 两容器 → asynq;ES → PG tsvector,9 服务降为 7+updater+relay。
- 多阶段 distroless(~30MB,nonroot,无 shell),healthcheck 改 `erpd healthcheck` 子命令。
- 可观测:slog(JSON,带 trace_id)+ otelgin + /metrics(RED+队列深度)+ Sentry;探针 /healthz(live)、/readyz(探 PG/Redis)。
- CI:buildx amd64/arm64 + 语义 tag + manifest digest 回填全保留,加 golangci-lint/test/govulncheck;镜像名不变以兼容远程升级。

### 主要 Go 包
- `github.com/gin-gonic/gin`
- `gorm.io/gorm`
- `gorm.io/driver/postgres`
- `github.com/jackc/pgx/v5`
- `github.com/jackc/pgx/v5/pgxpool`
- `github.com/sqlc-dev/sqlc (codegen)`
- `github.com/Masterminds/squirrel`
- `github.com/golang-migrate/migrate/v4`
- `github.com/golang-jwt/jwt/v5`
- `github.com/casbin/casbin/v2`
- `github.com/redis/go-redis/v9`
- `github.com/go-redsync/redsync/v4`
- `github.com/hibiken/asynq`
- `github.com/coder/websocket`
- `github.com/spf13/viper`
- `github.com/spf13/cobra (子命令: serve/worker/scheduler/migrate/upgrade-relay/healthcheck)`
- `go.opentelemetry.io/otel + otelgin + otlptracegrpc`
- `github.com/prometheus/client_golang/prometheus/promhttp`
- `github.com/getsentry/sentry-go`
- `github.com/swaggo/swag + swaggo/gin-swagger`
- `log/slog (标准库)`

### 风险
- distroless 无 curl/sh:现有 compose 与 nginx healthcheck、entrypoint shell 脚本需全部改写为二进制子命令或 wget-less 探测,迁移期易漏导致容器被判 unhealthy。
- 双层数据访问(GORM+sqlc)需共用同一 pgx/v5 连接池与同一事务上下文,否则报表读与 CRUD 写出现读己写不一致;事务边界要在 service 层统一注入。
- golang-migrate baseline 标记错误会重放 161 迁移破坏生产库;首发必须 force 到对应 version 并演练。
- asynq 与 celery 任务语义不完全等价(重试/幂等/可见性超时),host 网络访问考勤机的 worker 需保留 network_mode: host 特例,容器网络模型与其余 erp-network 混用易踩坑。
- OTel + Sentry + prometheus 多导出叠加在热路径中间件,若采样/批量未调好会引入延迟与内存压力。
- manifest digest 回填依赖镜像名与 owner 不变,任一改名都会断掉已部署实例的远程升级检查。

### 待定问题
- 升级 relay 与 worker/web 是否合并为单二进制多子命令(部署简单)还是保持独立容器(故障隔离)?
- 中文全文检索 zhparser 自定义 PG 镜像由谁维护、是否纳入 compose 默认,还是仅强搜索需求实例再上 Meilisearch?
- OTLP trace 后端落地选型(自托管 Jaeger/Tempo vs 仅本地 stdout exporter)在非标制造现场是否有运维能力承接?
- 配置 secret 是否引入 SOPS/age 还是继续裸 .env(现状)?生产合规要求待确认。
- golang-migrate 增量编号与遗留 Django migration 编号如何共存命名,避免冲突?
