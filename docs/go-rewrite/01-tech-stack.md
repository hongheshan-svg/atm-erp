# ATM-ERP 技术栈决策(后端 Go 重写 + 全新 Vue SPA)

> 背景:已在 `refactor/go-rewrite` 分支、版本 0.1.1,"离开 Django"为既定决策。本决策聚焦"选哪套 Go 栈",评估锚定**开发效率 + 生态成熟度**(在已稳定的运维/升级链路上做最低风险迁移)。

## 硬约束对齐
- **自托管 / Docker 一键**:目标态从 7 容器降到 `postgres + redis + app(+asynq worker)`,砍掉 elasticsearch / celery / celery-beat / nginx 多容器。
- **远程自动升级**:**沿用现有 `erp-updater` + `manifest.json` + GHCR digest(MODE_DOCKER)镜像原子替换 + 回滚**,不改机制。Go 静态二进制只贡献更小镜像/更快启动/更稳回滚。
- **复用 PostgreSQL 15**:schema 整体保留,新栈只接管增量迁移;搜索改用 PG 全文检索。

## 后端
| 用途 | 选型 | 理由 |
|------|------|------|
| 语言/HTTP | Go 1.23 + **Gin** | Go 生态最成熟、招聘面最广,15 模块逐个改写上手成本最低 |
| ORM 主层 | **GORM** | `DeletedAt`+钩子复刻 BaseModel 软删除/审计,拿回 Django 式速度,覆盖 ~80% CRUD |
| ORM 报表层 | **sqlc** | 仅啃 BOM 递归/成本核算/报表聚合的复杂只读 SQL,编译期类型安全、零反射 |
| 动态查询 | **Squirrel** | 列表页大量可选筛选,弥补 sqlc 对动态查询不友好 |
| 驱动 | **pgx/v5** | 原生 PG 协议、连接池、COPY/LISTEN-NOTIFY |
| 迁移 | **golang-migrate** | 纯 SQL 版本化、可 embed 启动期自动 up;接管增量,161 迁移已落库 |
| 认证/权限 | **golang-jwt/v5 + Casbin/v2** | Casbin 建 RBAC;**数据范围/字段脱敏/越权边界须 Casbin 外手写移植 + 强制回归** |
| 缓存/锁 | **redis/go-redis/v9** | 复用 Redis 7,缓存 + redsync 分布式锁 + 限流 |
| 异步任务 | **hibiken/asynq** | 基于现有 Redis,cron 定时 + asynqmon,一对一替换 Celery+Beat |
| WebSocket | **coder/websocket** + Redis Pub/Sub | 替代 Channels/Daphne;连接鉴权/重连自写 |
| 搜索 | **PostgreSQL tsvector+GIN+pg_trgm**(中文 zhparser) | 砍掉 ES JVM 重容器;强需求再上 Meilisearch |
| 配置 | **spf13/viper** | 兼容现有 .env/.env.docker |
| 可观测 | **slog + OpenTelemetry + prometheus/client_golang + Sentry-go** | 结构化日志+链路+指标+错误,无额外 agent |
| API 文档 | **swaggo/swag** | 注解生成 OpenAPI,补回 drf-spectacular |
| 升级 | **沿用 erp-updater + manifest digest(MODE_DOCKER)** | distroless 静态二进制使镜像更小/回滚更稳,机制不变 |

## 前端
| 用途 | 选型 | 理由 |
|------|------|------|
| 框架 | **Vue 3.5 + TypeScript(strict)** | 团队深耕,迁移风险最低 |
| 构建 | **Vite 6 + pnpm + vue-tsc** | 仅换工程基座,196 视图增量重构 |
| UI | **Element Plus** | 数据密集 ERP 表格/表单/树最全,与现界面一致,零成本 |
| 大表格 | **vxe-table** | 虚拟滚动支撑大列表 |
| 服务端状态 | **TanStack Query(Vue)** + Pinia(客户端态) | 统一缓存/重试/失效 |
| HTTP | 沿用 `request.ts`(JWT 刷新 + 401 排队重试) | 按模块组织 `api/<module>.ts` |
| 图表/甘特 | ECharts + vue-echarts + vue-ganttastic | 沿用现有报表/排程资产 |

## 主要否决项
- **纯 sqlc 单层**:与 ERP 海量动态筛选冲突 → 改 GORM+sqlc 双层。
- **React 全新前端**:双端推倒重写、migration 风险最高 → 保留 Vue+Element Plus。
- **Naive UI 换 Element Plus**:与"降重写"矛盾 → 保留 + vxe-table 补强。
- **Elasticsearch**:JVM 重容器、现场最常见故障源 → PG 全文检索。
- **selfupdate 单二进制热替换**:与既有 Docker 镜像升级链冲突 → 沿用 erp-updater。
- **River 第二队列 / centrifuge / oapi-codegen 契约先行 / 前端 embed 去 nginx / Atlas 声明式迁移**:均为相对现状的过度工程,本期不引入。

## 迁移风险红线(必须预留预算)
1. **权限非一一映射**:数据范围、敏感字段脱敏、`MODULE_MENU_MAP` 越权边界(C1/C2)须逐条手写移植并跑全部 `test_*permissions` 回归,否则即水平越权漏洞。
2. **工作流约 3100 行 + 审计中间件 + 编码规则**:用 GORM 钩子 + 自写状态机重建,需行为等价回归,建议新旧并行双跑验证期。
3. **中文分词**:zhparser 当前未装,需自定义 PG 镜像(仍远轻于运维 ES)。

