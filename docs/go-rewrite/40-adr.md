# 架构决策记录(ADR)

---

## ADR-001 离开 Django,后端整体重写为 Go 1.23

**决策**: 以 Go 1.23 重写后端;评估锚定开发效率+生态成熟度而非纯性能/纯运维,聚焦'选哪套 Go 栈'。

**理由**: 仓库已在 refactor/go-rewrite(v0.1.1),'是否离开 Django'为既定决策。真正成本中心是 ~158k 行业务逻辑(权限/工作流/视图)的等价重建,故选型以最低迁移风险为先。

---

## ADR-002 模块化单体而非微服务

**决策**: 单一二进制 erpd 内挂 Gin 路由,15 限界上下文落 internal/<ctx>,共享能力归 internal/platform+core;子命令 serve/worker/scheduler/upgrade-relay 复用同镜像。

**理由**: 自托管/Docker 一键约束下微服务徒增运维与分布式事务复杂度;模块化单体既能逐模块改写,又保留清晰边界(Port 接口),未来需要时可沿包边界拆分。

---

## ADR-003 GORM(主)+sqlc(报表)双层数据访问,Squirrel 兜底动态查询

**决策**: GORM 钩子复刻 BaseModel 吃 ~80% CRUD;sqlc 只啃 BOM 递归/成本核算/报表聚合等复杂只读 SQL;ERP 列表大量可选筛选用 Squirrel 拼装;共用同一 pgxpool。

**理由**: 纯 sqlc 零反射哲学与海量动态筛选天然冲突(要么写 N 个查询要么退回手拼丢类型安全);纯 GORM 在大 JOIN 反射退化。双层各取所长,拿回 Django 式 CRUD 速度同时报表编译期类型安全跑满 PG。

---

## ADR-004 复用现有 PostgreSQL schema,golang-migrate 只接管增量

**决策**: schema/表名/列名/161 迁移产物整体保留(GORM 显式 TableName,禁 AutoMigrate);Django migrations 冻结,新增量一律 golang-migrate 纯 SQL embed 进二进制启动期 up,161 视为 baseline 不重放。

**理由**: Go 与 Django 共用同一物理库,无需大规模 ETL 或长期应用层双写,迁移=原地共库+灰度切换。否决 Atlas 声明式迁移:纯 SQL 与现有增量同源、心智更简单。

---

## ADR-005 RBAC 用 Casbin,但数据范围/字段脱敏/越权边界手写

**决策**: golang-jwt/v5 + Casbin/v2 仅承载 menu 级 RBAC(策略=role,code + 父码通配);DataScope(all/dept/dept_tree/self/custom)、上下文角色(@owner/@assignee)、MODULE_MENU_MAP 越权边界、敏感字段脱敏在 Casbin 之外用 Go 手写并对每条规则写回归测试。

**理由**: 这些是安全攸关逻辑,做一一映射即水平越权漏洞。RBAC 扁平为单层 resource:action、删 operation/field 死代码,删 MODULE_MENU_MAP'有菜单即全 CRUD'兜底放行,RequireSystemAdmin 前置封死 system:* 越权(C1)。

---

## ADR-006 BaseModel 用 GORM 内嵌结构体 + gorm.DeletedAt 钩子复刻

**决策**: Base{ID,CreatedAt,UpdatedAt,CreatedBy/UpdatedBy *uint,DeletedAt gorm.DeletedAt};gorm.DeletedAt 映射 deleted_at 列并经 BeforeDelete/Scope 同步维护 is_deleted 布尔;BeforeCreate/Update 从 ctx 注入操作人;.Unscoped() 等价 all_objects。

**理由**: 1:1 复刻 Django BaseModel 软删除/审计/created_by 三件套;is_deleted 双写保证 Django 与 Go 共库期两侧软删除互认,这是双系统并行的硬前提。

---

## ADR-007 工作流引擎用回调注册表反转依赖

**决策**: 保留四模型(定义/步骤/实例/任务)与选流/跳步/超时/抄送/自动批准语义;废弃 _on_workflow_complete 巨型 if/elif,定义 ApprovalCallback 接口 + CallbackRegistry,业务包启动时注册自己的 handler,引擎只发事件/查表分发,零业务 import。

**理由**: 现状内核反依赖全部 30+ 业务模型、违反开闭。反转为业务→引擎单向依赖,新增业务类型只在业务包加 handler。顺带补齐声明却未实现的 COUNTERSIGN 会签。

---

## ADR-008 异步任务用 asynq 一对一替换 Celery+Beat

**决策**: hibiken/asynq 基于现有 Redis,一个二进制同跑 worker+scheduler(cron 对齐 beat_schedule),asynqmon 替 flower,27 任务/22 定时项一对一映射;考勤机同步保留 host 网络。

**理由**: 语义最贴近 Celery+Beat,复用 Redis、砍掉两个常驻容器。否决 River(PG 队列)作主队列:避免两套队列复杂度,财务强一致用 DB 事务+幂等而非另起队列。

---

## ADR-009 WebSocket 用 coder/websocket+自建 Hub+Redis PubSub 替 Channels/Daphne

**决策**: 自建 Hub 沿用 group 语义(user_{id}/dashboard_updates/upgrade_{job}),多实例 Redis PubSub 扇出,{type,data} 信封与现 group_send 一致;握手期 JWT 鉴权,断线重连/心跳自写。

**理由**: 砍掉 Daphne 重容器、前端 NotificationCenter/websocket store 零改。否决 centrifuge:内网 ERP 实时规模有限,自管足够,真需大规模再上。

---

## ADR-010 搜索用 PostgreSQL 全文检索替换 Elasticsearch

**决策**: item/customer/supplier 加 tsvector 生成列+GIN 索引,中文走 zhparser 自定义 PG 镜像,pg_trgm 支持编码/SKU 模糊,全局搜索 UNION 5 类;强搜索需求再上单二进制 Meilisearch。

**理由**: 实际索引仅三类、搜索面浅;ES 是自托管现场最常见故障源(JVM 吃内存、单独重容器),与 Docker 一键/复用 PG 冲突。zhparser 净新增工作量但远轻于运维 ES。

---

## ADR-011 前端保留 Vue+Element Plus,只换工程基座增量重构

**决策**: 另起新 SPA 但沿用 Vue 3.5+TS(strict)+Element Plus,换 Vite 6+pnpm 基座,补 TanStack Query(Vue,服务端态)+vxe-table(大表格)+Pinia(客户端态);196 视图增量迁移、双栈并存;swaggo OpenAPI + openapi-typescript 生成类型。

**理由**: 把双端重写压成单端重写,规避 React 全量重写的最高 migration 风险。否决 React 全新前端、Naive UI 换 Element Plus(均与降重写矛盾)、oapi-codegen 契约先行(契约漂移双坑前后端,swaggo 后置生成足够)、前端 embed 进 Go(妨碍独立发布/灰度,保留独立前端镜像)。

---

## ADR-012 远程升级沿用 erp-updater+manifest digest,不引入热替换

**决策**: 保留双进程边界(特权 docker.sock 操作只在 erp-updater,主后端无特权,两者经 Redis 队列+PubSub 通信),Docker 优先用 ghcr.io@sha256 digest 原子替换+回滚;Go 产物为 distroless 静态二进制使镜像更小/回滚更稳;修复同路径挂载缺陷;补全原生升级一键。

**理由**: 升级机制是仓库已落地资产(MODE_DOCKER),Go 二进制只贡献镜像与回滚优势。否决 selfupdate/go-update 单文件热替换:与既有 Docker 镜像升级链冲突、属重复造轮子。
