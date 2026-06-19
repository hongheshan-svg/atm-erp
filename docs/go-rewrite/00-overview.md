# ATM-ERP Go 重构架构蓝图 · 总览

## 1. 目标
把 ~158k 行 Django(13 App,161 迁移)+ Vue2 时代沉积的 ERP,重写为 **Go 模块化单体后端 + 全新 Vue 3.5 SPA**,在**复用现有 PostgreSQL 15 / Redis 7 与既有 Docker 升级链路**的前提下,达成:运维面收敛(7 容器 → `postgres + redis + app(+asynq worker)`)、并发与一致性可控、权限/工作流行为等价且无水平越权、前端单端增量重构而非双端推倒。仓库已在 `refactor/go-rewrite`(v0.1.1),"离开 Django"为既定前提,本蓝图聚焦"选哪套 Go 栈 + 怎么安全切过去"。

## 2. 设计原则
1. **复用而非重建基础设施**:同物理库同表名,`golang-migrate` 只接管增量;Redis/升级链路/前端 base `/erp/` 与 nginx 路由全部沿用,前端 `request.ts` 三件套契约零改。
2. **先地基后切片**:认证/RBAC/BaseModel/中间件/工作流引擎等横切内核先于任意业务模块落地,业务上下文逐个挂接已稳定的地基。
3. **双系统并行 + 可回滚**:Go 与 Django 共库,按 15 模块灰度切流;每步可经 nginx upstream 与 manifest digest 镜像原子回滚。
4. **依赖单向**:内核(platform/core)零业务 import;业务→内核;跨上下文走 Port 接口,反转现状的 signals/延迟 import/反向依赖。
5. **安全攸关逻辑不做一一映射**:Casbin 只承载 menu RBAC;数据范围/上下文角色/字段脱敏/`MODULE_MENU_MAP` 越权边界手写移植并逐条回归。
6. **双层数据访问**:GORM 复刻 BaseModel(软删除/审计/created_by)吃 ~80% CRUD;sqlc 啃 BOM 递归/成本核算/报表聚合等复杂只读 SQL;Squirrel 拼列表动态筛选;共用同一 `pgxpool`。
7. **删死代码、收边界**:operation/field 三级权限、字段脱敏 inert 层、core 越界功能、三套对账/三套排程/双套成本等过度设计在迁移期一次性收敛或裁剪。

## 3. 整体架构(文字图)
```
                         ┌──────────────────────────────────────┐
   浏览器 / 小程序  ───▶ │ nginx (8080/8443, base /erp/, /api /ws)│
                         └───────────────┬──────────────────────┘
                          静态(前端镜像)│  /api  /ws
                                         ▼
   ┌─────────────────────────  erpd (单一 Go 二进制 · 多子命令)  ─────────────────────────┐
   │  Gin 中间件链: Recovery→RequestID→SecHeaders→CORS→RateLimit→JWTAuth→Casbin→DataScope→Audit │
   │                                                                                          │
   │  internal/platform(真内核·零业务依赖): BaseModel/分页/响应/db(pgxpool)/cache/obs        │
   │  internal/core(七横切能力·接口注入): audit attachment notify coderule workflow perm sysconfig│
   │  internal/iam(统一鉴权服务): Authorizer(HasPermission/ResolveDataScope/CheckObject)       │
   │                                                                                          │
   │  internal/<15 限界上下文>: iam・masterdata・quotetocash/crm/aftersales・purchase・        │
   │     inventory・projects(+equipment/fieldservice/cost/knowledge…)・production・finance・    │
   │     oa・reportsbi   —— 各含 handler/service/repo/model/dto,跨上下文经 Port 接口            │
   │                                                                                          │
   │  数据访问: GORM(CRUD/软删除/审计钩子) + sqlc(只读重聚合) + Squirrel(动态筛选) → pgxpool   │
   │  子命令: erpd serve | worker | scheduler | upgrade-relay | migrate | healthcheck         │
   └───────┬───────────────┬────────────────┬───────────────────┬────────────────────────────┘
           │ asynq(Redis)  │ go-redis        │ WS hub(coder/ws)   │ Redis 队列+PubSub
           ▼               ▼ 缓存/锁/限流    ▼ +Redis PubSub 扇出  ▼
   ┌──────────────┐  ┌───────────┐    (user_{id}/dashboard/    ┌────────────────────┐
   │ asynq worker │  │  Redis 7  │     upgrade_{job})           │ erp-updater(distroless│
   │ +scheduler   │  └───────────┘                              │ 特权代理·持docker.sock│
   │ (替 celery+beat)                                            │ 备份→拉镜像→健康门→回滚│
   └──────┬───────┘                                             └─────────┬──────────┘
          ▼                                                               │原子替换/回滚
   ┌──────────────────────────  PostgreSQL 15 (现有 schema)  ──────────────┘
   │  161 迁移=baseline · golang-migrate 接管增量 · tsvector+GIN+pg_trgm(zhparser) 替代 ES │
   └──────────────────────────────────────────────────────────────────────────────────────┘
```

## 4. 模块边界划分(15 限界上下文 + 内核)
- **横切内核**:`platform`(BaseModel/分页/响应/db/obs,零业务依赖)、`core` 七能力包(audit/attachment/notify/coderule/workflow/perm/sysconfig)、`iam`(认证+授权+数据范围+菜单树)。
- **上游基础**:`masterdata`(item/customer/supplier/warehouse/credit/crm)——被 60+ 处依赖,信用对 finance 的反向依赖改为 `RefreshUsedAmount` 接口/事件。
- **业务主线**:`quotetocash/crm/aftersales`(原 sales 拆三)、`purchase`(PR/RFQ/PO/GR/委外为核心,门户/协同冻结为只读代理)、`inventory`(ledger/batch/material/mrp/alert/cost/recon,sparepart 二期)、`projects`(project/bom/drawing/ecn 核心 + equipment/fieldservice/cost/knowledge 独立 BC,IoT/CAD 裁剪)、`production`(processes/routing/aps/andon/kanban/sn… 收敛三套排程)、`finance`(ledger/receivable/payable/payment/expense/invoice/reconciliation/bank/tax/asset/budget/currency,统一对账抽象 + decimal + 行锁)。
- **协同与读侧**:`oa`(vehicle/asset/archive/signature/attdevice/wechat,日程/公告/考勤记录仍属 core/accounts 仅路由聚合)、`reportsbi`(reports+analytics 只读 BFF,sqlc 取代 pandas,补 DataScope 修越权)。
- **关键边界规则**:工作流以 `ApprovalCallback` 注册表反转依赖(引擎零业务 import);BOM 联动由 signals 改 PO/GR confirm 显式领域事件;Project/credit/sales 等跨域聚合改 Port 接口注入。

## 5. 技术栈(一句话)
后端 **Go 1.23 + Gin + GORM(主 CRUD)/sqlc(报表聚合)/Squirrel(动态筛选) + pgx/v5 + golang-migrate + golang-jwt/v5+Casbin/v2(RBAC,数据范围/脱敏手写) + go-redis(+redsync) + asynq(替 Celery+Beat) + coder/websocket(替 Channels) + PG tsvector/zhparser(替 ES) + viper + slog/OTel/Prometheus/Sentry + swaggo**;前端 **Vue 3.5 + TS(strict) + Vite 6 + pnpm + Element Plus + vxe-table + TanStack Query(Vue) + Pinia(客户端态) + ECharts/vue-ganttastic**;升级沿用 **erp-updater + manifest digest(MODE_DOCKER)**,产物为 **distroless 静态二进制**。

## 6. 与旧系统的关系
- **共库共表**:Go 与 Django 同连 PostgreSQL 15/Redis 7,表名/列名不变(GORM 显式 `TableName()`),Django migrations 冻结、不再 `makemigrations`,新增量一律 golang-migrate;`gorm.DeletedAt` 映射 `deleted_at` 并经钩子同步维护 `is_deleted` 布尔,保证共库期两侧软删除互认。
- **契约兼容**:保留 `/api/*`、`/ws` 路由与 URL 别名、`StandardPagination(20/页)` 语义、登录响应 `{access,refresh,user{permissions,menus,data_scopes}}`,前端 `request.ts`/Pinia/`v-permission` 三件套零改,旧 Vue 工程与新 SPA 双栈并存。
- **运维兼容**:升级机制、install.sh/ps1、GHCR 多架构 CI + manifest digest 回填全部保留;升级 relay 由 `manage.py` 子命令改为 `erpd upgrade-relay`,读写同一 Redis 进度通道,前端无感。
- **替换关系**:Go 二进制只贡献"更小镜像/更快启动/更稳回滚",不引入 selfupdate 单文件热替换;ES/Daphne/celery/celery-beat 容器整体下线。



## 目标目录布局

```
atm-erp/                                  # 仓库根(refactor/go-rewrite,v0.1.x)
├── backend/                              # 旧 Django(灰度期保留,逐模块下线后归档)
│   └── apps/ ...                         # core/accounts/masterdata/sales/... 切完即 freeze
│
├── server/                              # 【新】Go 模块化单体后端  (module: github.com/atm-erp/server)
│   ├── go.mod  go.sum
│   ├── sqlc.yaml                        # sqlc 生成配置(报表/聚合只读查询)
│   ├── cmd/
│   │   └── erpd/
│   │       └── main.go                  # 单一二进制入口,子命令分发
│   │                                    #   serve | worker | scheduler | upgrade-relay
│   │                                    #   | migrate | healthcheck | seed
│   ├── internal/
│   │   ├── platform/                    # 真内核 · 零业务依赖
│   │   │   ├── model/base.go            # BaseModel{ID,CreatedAt,UpdatedAt,CreatedBy,UpdatedBy,DeletedAt}
│   │   │   ├── db/                      # pgxpool + GORM 装配 + tx 助手 + Scopes(NotDeleted)
│   │   │   ├── httpx/                   # 统一响应信封 / StandardPagination / keyset 分页
│   │   │   ├── cache/                   # go-redis + ristretto 三级缓存 + singleflight + redsync
│   │   │   ├── config/                  # viper(env>yaml>默认,吃现有 .env/.env.docker 键)
│   │   │   └── obs/                     # slog(JSON,trace_id) + otelgin + promhttp + sentry
│   │   │
│   │   ├── middleware/                  # Gin 中间件链(固定顺序)
│   │   │   ├── chain.go                 # Recovery→RequestID→SecHeaders→CORS→RateLimit
│   │   │   ├── auth.go                  # AuthRequired(): Bearer→验签→注入 *AuthUser
│   │   │   ├── rbac.go                  # RequireSystemAdmin / RequirePermission / DataScope 注入
│   │   │   ├── ratelimit.go             # redis_rate GCRA(login 5/min 等)
│   │   │   └── audit.go                 # defer 审计(登录/4xx/5xx 元数据)
│   │   │
│   │   ├── iam/                         # 统一鉴权服务(替 permission_service/mixin/permissions.py)
│   │   │   ├── authorizer.go            # Authorizer 接口 + Casbin enforce(menu RBAC+父码通配)
│   │   │   ├── datascope.go             # ResolveDataScope(多角色取最宽,fail-closed self,Redis 5min)
│   │   │   ├── menu.go                  # BuildMenuTree(补全祖先容器,内嵌登录响应)
│   │   │   ├── token.go                 # golang-jwt/v5 双令牌+轮换+Redis 白/黑名单(jti)
│   │   │   ├── loginlog.go              # 一等 login_log(成功/失败/IP/UA/原因)
│   │   │   └── casbin/model.conf
│   │   │
│   │   ├── core/                        # 七横切能力(接口注入,零业务 import)
│   │   │   ├── audit/                   # GORM AfterSave/AfterDelete 真实主键+字段级 diff+脱敏
│   │   │   ├── attachment/              # related_model+related_id 通用附件
│   │   │   ├── notify/                  # Channel 接口(DingTalk/WeCom)+ 站内信(WS)+ asynq 推送
│   │   │   ├── coderule/               # GenerateCode(ctx,ruleType): pgx 事务+SELECT FOR UPDATE
│   │   │   ├── workflow/               # 四模型引擎 + ApprovalCallback 注册表(反转依赖)
│   │   │   │   ├── engine.go            #   选流/跳步/会签(COUNTERSIGN 补齐)/超时/自动批准兜底
│   │   │   │   ├── registry.go          #   map[businessType]ApprovalCallback
│   │   │   │   └── resolver.go          #   AssigneeResolver(USER/ROLE/DEPT_MGR/PROJ_MGR/SUPERIOR)
│   │   │   ├── permission/              # ApplyScopeFilter(Squirrel) + Scopable + 逐条回归
│   │   │   └── sysconfig/              # 单行 config + viper 加载 + Redis 缓存
│   │   │
│   │   ├── masterdata/                  # 上游基础(被 60+ 依赖)
│   │   │   ├── item/  customer/  supplier/  warehouse/  credit/  crm/
│   │   │   │      └── {model,repo,service,handler,dto}.go
│   │   │   └── enums/                   # 单位/状态/物料类型中英双向映射(集中)
│   │   ├── quotetocash/                 # 原 sales 拆分①:报价/SO/DO/合同 + StateMachine
│   │   ├── crm/                         # 拆分②:线索/商机/预测/漏斗/RFM/赢丢单(sqlc)
│   │   ├── aftersales/                  # 拆分③:服务/门户/培训(低频子域只读兼容)
│   │   ├── purchase/
│   │   │   ├── request/ order/ receipt/ contract/ rfq/ outsource/
│   │   │   └── shared/                  # codegen/workflow/event(BomOrderedEvent/BomReceivedEvent)
│   │   ├── inventory/
│   │   │   ├── domain/                  # MoveCommand 值对象 + StockChanged 事件
│   │   │   ├── ledger/                  # StockLedgerService.Apply(tx,cmd):FOR UPDATE 锁行
│   │   │   ├── batch/ material/ mrp/ alert/ cost/ recon/
│   │   │   └── sparepart/               # 二期(stub)
│   │   ├── projects/                    # 核心域
│   │   │   ├── project/ bom/ drawing/ ecn/
│   │   │   └── ports/                   # ProjectFinanceReader/ProjectInventoryReader 接口
│   │   ├── equipment/  fieldservice/  cost/  knowledge/   # 原 projects 拆出的独立 BC
│   │   ├── production/
│   │   │   ├── processes/ routing/ aps/ andon/ kanban/ sn/ capacity/ assembly/ dataacq/
│   │   │   └── ports/inventory_port.go  # CompletionInbound/MaterialIssue
│   │   ├── finance/
│   │   │   ├── ledger/ receivable/ payable/ payment/ expense/ invoice/
│   │   │   ├── reconciliation/          # 统一 Reconciliation 接口(三类合一)
│   │   │   ├── bank/ tax/ asset/ budget/ currency/
│   │   │   └── ports/                   # ProjectRef/OrderRef Provider(窄接口)
│   │   ├── oa/
│   │   │   ├── vehicle/ asset/ archive/ signature/ wechat/
│   │   │   ├── attdevice/               # ZKTECO TCP/云/推送 + iclock 解析(独立 service)
│   │   │   └── flow/                    # 泛型借用/调拨/维护状态机(共用抽象)
│   │   ├── reportsbi/                   # reports+analytics 只读 BFF
│   │   │   ├── registry.go              # 命名查询白名单(替 importlib 动态加载)
│   │   │   ├── costcalc/                # 三套成本合一(单 sqlc CostCalc)
│   │   │   └── bizrule/                 # 口径单一事实源(含税优先/状态集/账龄分桶)
│   │   ├── upgrade/                     # 升级编排 + 进度中继 + manifest client + UpgradeJob 库
│   │   ├── ws/                          # coder/websocket Hub + Redis PubSub 扇出
│   │   ├── tasks/                       # asynq 任务定义 + scheduler(cron,替 beat 22 项)
│   │   └── platformsvc/                 # 越界搬离: print/import_export/backup/email/dict/...
│   │
│   ├── db/
│   │   ├── migrations/                  # golang-migrate 纯 SQL(//go:embed),161=baseline 不重放
│   │   │   └── 0162_*.up.sql / *.down.sql
│   │   └── queries/                     # sqlc .sql(BOM 递归 CTE/成本/账龄/看板聚合)
│   ├── api/openapi/                     # swaggo 生成的 swagger.json/yaml
│   └── pkg/                             # 可对外复用小工具(decimal 助手/枚举等)
│
├── web/                                 # 【新】Vue 3.5 SPA(pnpm workspace)
│   ├── package.json  pnpm-workspace.yaml  vite.config.ts  tsconfig.json(strict)
│   ├── packages/
│   │   └── ui/                          # 业务组件层 + design tokens
│   │       └── src/                     # CrudTable/SearchForm/PageHeader/StatusTag/MoneyText/...
│   └── apps/
│       └── erp/
│           ├── index.html              # base: '/erp/'(与 nginx 一致)
│           └── src/
│               ├── main.ts
│               ├── api/                # <module>.ts(沿用 28 模块划分)+ openapi-typescript 类型
│               ├── utils/request.ts    # 1:1 复刻 JWT 刷新 + 401 排队重试 + 三段回灌
│               ├── stores/             # Pinia 纯客户端态: user/permission/companyConfig/ui
│               ├── router/             # meta.menuId + 父码通配 hasPermission
│               ├── directives/         # v-permission(1:1 移植)
│               ├── composables/        # TanStack Query 封装(useXxxQuery/useXxxMutation)
│               └── views/              # 196 视图按模块增量迁移(双栈并存)
│
├── deploy/
│   ├── updater/                        # erp-updater(沿用,distroless 特权代理 + .service)
│   ├── docker-compose.yml              # postgres+redis+app+asynq+ws +updater+relay(去 es/celery/nginx 重容器)
│   ├── install.sh  install.ps1         # 一键脚本(保留)
│   └── pg/Dockerfile.zhparser          # 自定义 PG 镜像(中文分词,新增)
│
├── docker/
│   ├── server/Dockerfile               # 两阶段 distroless: builder(swag+sqlc+migrate embed)→static:nonroot
│   ├── web/Dockerfile                  # 前端独立镜像(不 embed 进 Go)
│   ├── updater/Dockerfile              # 沿用
│   └── nginx/nginx.conf                # /erp 静态 + /api /ws 代理(upstream 灰度切流点)
│
├── .github/workflows/                  # buildx 多架构 + 语义化 tag + manifest digest 回填
│                                       #   新增: golangci-lint / go test / govulncheck / Trivy
├── manifest.json                       # 升级清单(沿用 + digest 回填)
├── docs/                               # 架构/迁移/ADR/业务流程(沿用 + 新增本蓝图)
│   ├── architecture/blueprint.md
│   ├── adr/                            # 每条 ADR 单文件
│   └── migration/phases.md
└── CLAUDE.md  README.md  LICENSE(AGPL-3.0)
```

