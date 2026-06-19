# 分阶段迁移计划

> 原则:先地基后切片、双系统共库并行、每步可经 nginx upstream 与 manifest digest 镜像回滚。

---

## Phase 0 · 工程基座与契约冻结

**目标**: 搭好 Go 单体骨架与双系统并行的物理前提,冻结对外契约,确保后续每一步都能回滚。

**范围**:
- 建 server/ 模块化单体目录(cmd/erpd + internal/platform + middleware 空挂载)与 web/ 新 SPA pnpm workspace 骨架
- viper 吃现有 .env/.env.docker 同名键;pgxpool + GORM 双装配共用连接池;slog/OTel/Prometheus/Sentry 接好;/healthz /readyz 探针
- golang-migrate embed:声明 161 Django 迁移为 baseline 不重放,建基线接管记录;Django 侧停止 makemigrations
- GORM BaseModel 复刻 + gorm.DeletedAt↔deleted_at 映射 + 钩子同步 is_deleted 布尔(共库软删除互认),写最小回归证明两栈互认
- distroless 两阶段 Dockerfile(swag+sqlc+migrate embed);新 docker-compose 去 es/celery/celery-beat/Daphne;CI 加 golangci-lint/test/govulncheck/Trivy;manifest digest/updater/install 脚本保持不动
- 冻结对外契约清单:/api 路由别名、StandardPagination、登录响应信封、/ws 信封、前端 request.ts 三件套

**退出标准**: erpd 能在共库上启动并通过 /readyz 探活;一条空白 increment 迁移可 up/down;GORM 软删除与 Django objects/all_objects 行为在同一张表上互认通过自动化校验;CI 四步绿;新旧 compose 可同时拉起、nginx upstream 可在 Go 与 Django 间切换且前端无感。

---

## Phase 1 · 安全地基(认证 / IAM-RBAC / 工作流引擎 / 横切内核)

**目标**: 先把全系统依赖的横切内核与安全攸关逻辑在 Go 侧建成且行为等价,业务切片才有可挂接的稳定地基。此阶段不切任何业务流量。

**范围**:
- 认证与会话:golang-jwt/v5 双令牌 + 轮换 + Redis 白/黑名单(jti),复刻 simplejwt(Bearer/user_id claim/lifetime env);新增一等 login_log + Redis 登录限流;WS 握手鉴权
- iam 统一鉴权服务:Authorizer 接口 + Casbin menu RBAC(父码通配)+ RequireSystemAdmin 前置(封 C1)+ 手写 ResolveDataScope(fail-closed self,Redis 缓存+version 号)+ BuildMenuTree 内嵌登录响应;删 operation/field 死代码与 MODULE_MENU_MAP 兜底放行
- 双轨字段收敛:role FK→role_user 关联表、丢弃 data_scope JSON/permissions JSON 只留表,Go 侧单一来源
- core 七能力包:audit(钩子真实 diff+脱敏)、coderule(pgx 行锁)、notify(asynq+WS)、attachment、sysconfig、permission(ApplyScopeFilter)、workflow 引擎(四模型+ApprovalCallback 注册表+会签补齐+自动批准兜底+asynq 超时扫描)
- 中间件链固定顺序落地;asynq worker/scheduler 子命令 + WS Hub(Redis PubSub)就绪(空业务订阅)
- PG 全文检索基座:tsvector+GIN+pg_trgm 列与自定义 zhparser PG 镜像验证(仅 item/customer/supplier)

**退出标准**: 全部 test_*permissions / 数据范围 / 越权边界(C1/C2)回归在 Go 侧逐条通过,与 Django 行为等价无水平越权;一个样例业务类型走通 工作流 提交→审批→callback 回写 且引擎零业务 import;登录/刷新/登出/WS 鉴权契约与前端零改;coderule 并发生成序列号压测无重号。地基可被后续模块直接注入。

---

## Phase 2 · 上游主数据切片(masterdata,首个业务流量)

**目标**: 把被引用最广、领域逻辑最浅的上游基础数据作为第一个真实切片,验证'地基挂业务 + 双系统并行 + 灰度回滚'整链路。

**范围**:
- 按聚合根落地 item/customer/supplier/warehouse/credit/crm,抽出 service 层(Excel 导入/列名模糊匹配/枚举映射/编码生成/查重下沉)
- 物料编码生成走 pgx 事务+FOR UPDATE / redsync,严格复刻 10 位格式与并发语义;库位树改 PG 递归 CTE;信用调整原子化
- 解除边界倒置:credit 不再 import finance,改暴露 RefreshUsedAmount 接口供 finance 回写;信用 statistics/warning/overdue 改 sqlc 聚合
- 列表动态筛选用 Squirrel + vxe-table 虚拟滚动 + keyset 分页;前端对应模块视图迁到新 SPA
- nginx upstream 将 /api/masterdata/* 灰度切到 Go(先只读双跑校验,再读写)

**退出标准**: masterdata 全部 REST 契约与 URL 别名兼容,前端无感;只读双跑期 Go 与 Django 返回一致(影子比对);物料编码并发不重号;信用对 finance 的依赖已反转且 used_amount 回写正确;该模块可独立回滚到 Django(upstream 切回 + 数据无损,因共库)。形成可复制的'单模块迁移剧本'。

---

## Phase 3 · 业务主线批量切片(主数据下游 6 大重模块)

**目标**: 按依赖顺序批量复刻核心业务上下文,每个模块沿用 Phase 2 剧本独立灰度、独立回滚,内核与跨上下文 Port 边界在此规模化验证。

**范围**:
- inventory:MoveCommand+StockLedgerService(FOR UPDATE 锁行/非负校验/加权平均/append-only 流水),修 ADJUSTMENT 方向 Bug;对账改 sqlc 集合查询;sparepart 二期 stub
- purchase:收敛 PR/RFQ/PO/GR/委外核心,门户/协同先只读代理 Django;BOM 联动由 signals 改 PO/GR confirm 显式领域事件(同事务 outbox)→ projects 消费;金额/税额上移 service 用 decimal
- quotetocash/crm/aftersales:原 sales 拆三,状态机集中化(DO 11 态),跨 app 改 Port 接口;确认单与审批回写共用 createReceivables(幂等);低频子域只读兼容
- projects:核心 project/bom/drawing/ecn + equipment/fieldservice/cost/knowledge 独立 BC;8 个跨域聚合方法改 ProjectFinanceReader/ProjectInventoryReader 接口注入;BOM 卷积走 sqlc 递归 CTE;裁剪 IoT/CAD/重复文件
- production:按业务域拆子包,收敛三套排程为统一 WorkCenter+策略接口;库存联动走 InventoryPort;看板/产能改单条 GROUP BY + WS 推送;告警/采集改 asynq cron
- finance:抽 service 层与四聚合(Ledger/AR-AP/统一 Reconciliation/Asset),decimal+FOR UPDATE 行锁;三套对账与 AR/AP 镜像合并;跨上下文窄接口;Celery 9 定时任务→asynq cron
- asynq 一对一接管 Celery 27 任务/22 定时项;前端对应模块视图逐个迁入新 SPA

**退出标准**: 六大模块逐个完成只读双跑校验→读写灰度→稳定运行;库存账实一致性与财务借贷/核销并发在压测下无竞态、无精度漂移;工作流/审批/编号在各模块行为等价并通过回归;BOM 联动事件链端到端可达且幂等;每个已切模块仍可单独回滚;Celery/Beat 容器可下线(asynq 全量接管);前端已迁模块功能对齐旧栈。

---

## Phase 4 · 协同/读侧切片 + 搜索/实时/升级收口

**目标**: 完成剩余上下文,把 ES/Daphne 与升级 relay 等基础设施彻底收口到 Go,运维面收敛到目标态。

**范围**:
- oa:vehicle/asset/archive/signature/attdevice/wechat 子域 + 泛型 flow 状态机;全部申请类接入 workflow(删车辆'异常即自动批准'兜底);考勤机 host 网络保留,webhook 裸 handler 兼容 ZKTECO;Celery 7 任务→asynq
- reportsbi:GORM 仅管 9 元数据表,跨域聚合全走 sqlc(替 pandas/F());report_builder 改命名查询白名单+字段映射(去 importlib 越权面);补 DataScope 修复全量财务越权;成本三套合一;Celery 夜间预热→asynq;导出→excelize
- 搜索:PG tsvector/zhparser 全量接管 item/customer/supplier + 全局搜索 UNION,ES 容器下线
- 实时:通知/仪表盘/升级进度三 WS 端点全部走 Go Hub+Redis PubSub,Daphne/Channels 下线
- 升级链路收口:erpd 内置 manifest client/编排/进度中继/WS,erp-updater 沿用并修同路径挂载缺陷(host-path==container-path + --project-directory abs);原生升级补全 sha256 流式校验+路径防逃逸+原子换软链;Docker 优先 digest
- 前端剩余视图迁完,旧 backend/ 与旧 Vue 工程归档冻结

**退出标准**: ES 与 Daphne/celery 容器全部下线,运维态收敛为 postgres+redis+app(+asynq)+updater+relay;中文搜索召回与现状对齐;三 WS 端点契约与前端零改;升级一键 Docker 镜像原子替换+回滚验证通过(含同路径挂载修复)、原生升级真实跑通;reportsbi 越权缺陷修复并逐条回归;196 视图全部迁入新 SPA,Django 不再承载任何线上流量,具备整体回滚兜底(manifest 镜像回退)直至稳定观察期结束后正式退役。
