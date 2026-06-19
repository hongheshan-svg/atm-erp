# 完备性评审:缺口、风险与必修项

> 由完备性评审 agent 在综合蓝图后产出。**must_fix 必须在脚手架 / Phase 0-1 阶段解决。**

## 必修项(must_fix)
- Phase 0 冻结契约清单必须补三项当前缺失的对外面: (a) /static/ 静态资源服务收口方案(Swagger/admin 资产去留 + nginx 路由);(b) /media/ 与 media_files 命名卷的 app 挂载与服务方(谁读写、谁对外 serve);(c) drf-spectacular 自动 schema → swaggo 手工注解的契约保真策略(或保留一个 schema 生成 SoT)。否则 Django 一下线,前端/小程序/Swagger 三处契约同时断。
- Phase 0 BaseModel 复刻回归必须把'时区语义对齐'与软删除并列为退出标准: 写最小用例证明 Go(pgx 连接 TimeZone 设定 + GORM time.Time)与 Django(USE_TZ=True/Asia/Shanghai)对同一 timestamptz 列读写完全一致,否则共库期审计时间/到期/按日聚合静默漂移 8 小时。当前 exit_criteria 只验软删除互认,缺时间。
- Phase 0/1 必须先明确并冻结回滚红线: 显式声明'首个 golang-migrate 增量迁移(任何改列/加约束/加 tsvector 列)一旦执行,切回 Django 不再数据无损',并据此把所有 schema 变更尽量后置、对每个增量提供 down 迁移 + Django 兼容性验证。脚手架阶段就要把这条红线写进迁移剧本,否则团队会误以为整段并行期都能无损回退。
- Phase 0 必须先确立 token 失效/黑名单的真实基线再谈等价: token_blacklist 未装、BLACKLIST_AFTER_ROTATION=True 处于含糊态。脚手架阶段需查清现状注销/轮换实际是否生效,明确 Go 侧 Redis jti 黑名单是'修复'还是'等价',并把该决定写入认证契约,避免把一个行为变更当成等价迁移混过验收。
- Phase 1 安全地基必须把 WebSocket 纳入 DataScope/权限边界,而非只覆盖 REST: dashboard_updates 现为全员广播全量 KPI,迁 Go Hub 前必须决定是按 DataScope 过滤后定向推送还是维持现状(并显式记为已知越权)。三 WS 端点(notify/dashboard/upgrade)的鉴权与数据范围要与 REST 同源,纳入 C1/C2 越权回归,否则地基阶段就把越权广播固化进新架构。
- core 能力包决策必须在脚手架阶段补全 CustomField EAV 子系统的去留: 它是 542 行带 ViewSet + 动态值表的通用扩展点,属用户数据。必须在 Phase 0/1 明确它是 core 的第 8 能力(移植)还是裁剪(并给数据迁移/废弃方案),不能等业务切片时才发现 core 地基漏了一整个横切子系统。
- 脚手架阶段必须把小程序客户端纳入'对外契约冻结'与回归范围: miniprogram/ 独立代码库与 Vue 前端共用 /api 但单独维护。冻结清单要显式包含小程序依赖的登录信封/分页/字段命名,并在每个模块灰度切流时把小程序冒烟纳入双跑校验,否则它会成为切片期的盲区。

## 缺口(gaps)
- CustomField EAV 子系统遗漏: backend/apps/core/custom_fields.py (542行, CustomFieldDefinition + CustomFieldValue + CustomFieldService + 2 ViewSet) 是一套通用动态字段/EAV 扩展机制,被设计成可挂任意业务对象。蓝图第4节 core 七能力包(audit/attachment/notify/coderule/workflow/perm/sysconfig)完全未列入它,也没说裁剪还是移植。这是用户自定义数据,丢失即静默损坏租户配置数据。必须明确归类(第8能力 or 裁剪决策)。
- 时区/时间语义未设计: settings USE_TZ=True + TIME_ZONE=Asia/Shanghai,Django 存 UTC aware datetime。GORM/pgx + PostgreSQL timestamptz 的读写时区行为与 Django 不同(尤其 time.Time 的 Local vs UTC、pgx 连接 TimeZone 参数),共库期两栈对同一列的解释若不一致会产生静默 8 小时漂移,污染审计时间/到期判断/报表按日聚合。蓝图 BaseModel 复刻只提软删除/审计,未提时间语义对齐。
- 静态资源与 API 文档服务空洞: nginx location /static/ alias staticfiles/ 服务 drf-spectacular Swagger UI + DRF/admin 静态资源。Django 下线后 /static/ 谁来服务?swaggo 只产 /api/docs 的 OpenAPI,蓝图未交代 /static/ 路由收口、也未评估用 swaggo 手工注解重建 ~700 个端点 schema 的工作量与契约漂移风险(现状 schema 由 drf-spectacular 自动生成,前端/小程序据此对齐)。
- media/uploads 有状态卷遗漏: docker-compose 用 named volume media_files 挂到 backend/celery(rw)与 nginx(ro) 的 /app/uploads,Attachment(upload_to=attachments/%Y/%m)、company_logo、custom_fields 文件值、51 处 FileField 全落在此。蓝图把目标态收敛为 postgres+redis+app(+asynq)+updater+relay 且产物为 distroless 无状态二进制,但从未提 app 必须挂载并读写这同一个有状态卷、以及谁服务 /media/。文件存储抽象(本地 FS,无 S3/django-storages)被列为已设计主题却无落地方案。
- WebSocket 数据范围未设计: core/consumers.py 的 dashboard_updates 是全员共享广播组,向所有已认证用户推送 DashboardKPIService.get_all_kpis()(全量 KPI),无 DataScope 过滤。蓝图对 DataScope 的严谨只覆盖 REST get_queryset,WS 扇出层(notify + dashboard + upgrade 三端点)没有等价的数据范围/字段脱敏边界。迁到 Go Hub + Redis PubSub 若一比一复刻,会把现状的越权广播一并带过去。
- i18n 概念错配: 后端无 gettext/translation 调用、前端无 vue-i18n,根本没有可迁移的 i18n 框架。真实存在的是 LANGUAGE_CODE=zh-hans 下大量 model verbose_name(中文字段标签,经 DRF/drf-spectacular 暴露给前端/Swagger)。蓝图把 i18n 列为已设计主题属于伪需求;真正要保的是字段中文标签如何在 Go(GORM 无 verbose_name 等价物)侧重建并下发,这点反而没设计。
- 审批回调与跨上下文事件的事务边界仅在 purchase/BOM 提了 outbox,但 sales 的 createReceivables 幂等、production 库存联动、project 8 个跨域聚合改 Port 后的读一致性,没有统一的分布式事务/最终一致策略说明。共库期 Go 写 + Django 可能并发写同表(灰度只读双跑→读写),outbox 消费者在哪个进程、与 Django signals 是否重复触发,未交代。
- 小程序客户端契约验证缺位: miniprogram/ 独立客户端(pages/utils),CLAUDE.md 明确要求 API 契约变更同步该目录。蓝图只反复强调 frontend/request.ts 三件套零改,对小程序的登录响应信封/分页/字段命名兼容性一字未提,而它与 Vue 前端走同一 /api 但代码独立,极易在切片时被漏测。

## 风险(risks)
- 共库双写期数据竞争: Phase2-3 的'只读双跑→读写灰度'阶段,同一张表可能被 Go 与 Django 同时写(如 masterdata 被 60+ app 依赖,Django 侧 sales/purchase 仍在线时会写 customer/credit)。两套 ORM 不同事务隔离、不同序列号生成路径、GORM DeletedAt 钩子 vs Django soft_delete 的并发,存在丢更新/序列号重号/软删除状态不一致风险。蓝图称 coderule pgx 行锁解决重号,但跨栈(Django F()/select_for_update 与 Go FOR UPDATE)是否共用同一把行锁需验证。
- token 失效语义不等价风险: settings 设 BLACKLIST_AFTER_ROTATION=True 但 token_blacklist 未在 INSTALLED_APPS、无对应迁移表,当前 Django 的注销/轮换黑名单实际行为含糊(可能 inert)。蓝图直接断言用 Redis jti 白/黑名单'复刻 simplejwt 等价',却没先确立真实基线——若现状根本没有有效黑名单,Go 侧新增 Redis 黑名单是行为变更而非等价迁移,需明确是修复还是保持。
- 回滚的'数据无损'假设过强: 蓝图称每模块可独立回滚到 Django(upstream 切回+共库数据无损)。但 Go 一旦执行 golang-migrate 增量(改列/加约束/加索引/zhparser tsvector 列),Django 模型与新 schema 偏离,切回 Django 时其 ORM 对未知列/约束的行为、makemigrations 已冻结导致无法感知,可能令 Django 启动即报错或写入失败。回滚兜底只在'纯 upstream 切换、零 schema 变更'窗口成立,跨过首个增量迁移后回滚不再无损,蓝图未划这条红线。
- zhparser 自定义 PG 镜像 = 基础设施变更被低估: 蓝图复用现有 PostgreSQL 15 是核心卖点,但 PG tsvector + zhparser 需要安装 zhparser 扩展=自定义 PG 镜像或在现有实例 CREATE EXTENSION。这与'复用现有 PG'矛盾:生产现有 PG 容器若非自定义镜像,引入 zhparser 是一次有停机风险的数据库基础设施替换,且中文分词召回与 ES 对齐需大量调参回归。ES 下线的前置条件比蓝图描述重得多。
- asynq 不等价于 Celery 的全部语义: 36 个 task + 22 定时项一对一接管。Celery worker 当前用 host 网络访问局域网考勤机(ZKTECO TCP)。asynq worker 同样需 host 网络;蓝图保留了 host 网络但未确认 distroless 静态二进制能否在 host 网络下做 TCP 长连接/UDP 发现考勤机,以及 Celery 的 chain/group/retry/ETA 语义在 asynq 上的等价覆盖度。
- report_builder importlib 越权面是真实存在的现有漏洞: reports/report_builder.py:158/268 用 importlib.import_module + getattr 按字符串动态加载任意 model,export_service.py:472 apps.get_model 同理。蓝图正确点出要改命名查询白名单,但这意味着迁移期前现状是可被构造越权读取任意表的活漏洞;在 reportsbi 切到 Phase4 之前的整个并行期,Django 侧该漏洞持续暴露,蓝图未要求在地基阶段就先行收口或下线该入口。
- 前端推倒重写与'增量重构'自相矛盾的范围风险: 标题称全新 Vue 3.5 SPA、196 视图全部迁入新 SPA,同时又称前端 request.ts 三件套零改、单端增量重构。新建 web/ pnpm workspace + Element Plus/vxe-table/TanStack Query 是全新工程,196 视图重写是与后端迁移同等量级的第二条主线,其工作量、双栈并存期路由/登录态共享(两套 Vue 工程共用 JWT 与 Pinia)在蓝图里被一句'双栈并存'带过,严重低估。
