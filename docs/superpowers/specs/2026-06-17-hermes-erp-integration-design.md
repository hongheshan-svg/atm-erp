# Hermes Agent × ERP 联动设计(阶段① 地基:IM 只读查询）

- 日期：2026-06-17
- 状态：设计待评审
- 范围：**仅阶段①**——员工在企业微信里用自然语言查询 ERP(只读)。阶段②③④见文末"后续路线",不在本 spec 实现范围内。

---

## 1. 背景与现状(已确认事实)

- **Hermes Agent**(Nous Research 的自进化 AI agent)装在 `/home/administrator/.hermes/hermes-agent/`。其 **gateway 进程已经常驻运行**(systemd 用户服务 `hermes-gateway`),并**已接通企业微信(WeCom)**——员工已能在企微里和它对话(日志可见 `Unauthorized user: zhouxuan on wecom`,说明消息链路已通,只是 pairing 白名单在挡未授权用户)。
- **ERP**:Django 4.2 + DRF,JWT(simplejwt)鉴权,RBAC + 数据范围(`PermissionMixin` / `DataScopeMixin`),跑在 Docker(nginx 对外 `:8080`,backend `:8000`)。
- **身份可复用**:ERP `accounts.User` 已有 `wechat_work_id`(企业微信用户ID)字段(`apps/accounts/models.py:104`)。Hermes 接的企微与 ERP 填写的 `wechat_work_id` 是**同一个企业微信企业(同一 corpid)**,故同企业内 userid 跨自建应用一致,可直接对上,**无需新建映射表**。
- **关键技术约束(调研结论)**:
  - Hermes gateway 把当前 IM 用户身份(企微 userid 等)通过 Python `contextvars` 注入,**自定义工具内可用 `get_session_env("HERMES_SESSION_USER_ID")` 读到"现在是谁在问"**(`gateway/session_context.py`)。
  - Hermes 作为 MCP 客户端调用外部 MCP server 时,`call_tool` 只携带工具参数,**不携带会话身份**,env 仅启动时静态注入。→ 走 MCP **无法安全实现"每个员工用自己的身份"**,与本项目身份模型冲突,故排除。
  - Hermes 无 per-user 凭证存储;skills 是 Markdown 指令、不含可执行逻辑。

## 2. 目标与非目标

**目标(阶段①)**
- 员工在企业微信里用自然语言查询 ERP,Hermes 以**该员工自己的 ERP 身份与数据范围**返回结果。
- 覆盖四类只读查询:**单据状态、库存、我的待办、财务应收/应付**。
- 复用 ERP 现有 ViewSet 与 RBAC/数据范围,**不重写任何查询逻辑**。

**非目标(阶段①明确不做)**
- 任何写操作(下单/审批/改库存)。第一阶段一律只读。
- ERP 事件主动推送、定时日报、ERP 前端嵌入助手(=阶段③②④)。
- 独立 MCP server、给第三方 agent 复用 ERP 能力(=未来阶段④可选)。
- `wechat_work_id` 的批量补录运维(假设员工资料已基本维护;未绑定者得到友好提示)。

## 3. 架构与端到端数据流

```
员工(企业微信)
  │  自然语言:"PO-2026-0312 到货没?" / "我还有什么要审"
  ▼
Hermes gateway(已运行,已接企微) → Hermes agent
  │  命中 erp_* 工具
  ▼
erp_tool.py
  │  ① 读 contextvar:wecom_userid = get_session_env("HERMES_SESSION_USER_ID")
  │  ② 调 ERP REST API(只读 GET),请求头:
  │       X-Hermes-Service-Key: <单一服务密钥>
  │       X-Acting-Wecom-Userid: <wecom_userid>
  ▼
ERP（nginx :8080 → backend）
  │  HermesOnBehalfAuthentication:
  │    a. hmac.compare_digest 校验服务密钥(失败→401)
  │    b. User.objects.get(wechat_work_id=userid, is_active=True) → request.user
  │       (查不到→401 + 明确 code,工具转成"未绑定"话术)
  │    c. 在 request.auth 打标 {"hermes": True}
  │  HermesReadOnlyMiddleware:带 Hermes 头且非 SAFE_METHOD → 403(纵深防御)
  │  命中现有 ViewSet → PermissionMixin/DataScopeMixin 按该员工数据范围过滤
  ▼
返回 JSON → erp_tool 裁剪为精简结果 → agent 用自然语言回复员工
```

**三重安全边界**:① 单一服务密钥(进网关)② 只读强制(HTTP method)③ 每员工数据范围(RBAC,后端原生)。即便工具被诱导,也写不了、也越不了权。

## 4. 组件一:ERP 侧改动(小、集中、不动现有 ViewSet)

新增轻量集成子模块 `apps/core/integrations/`(集中放置,便于审计与回滚):

### 4.1 `hermes_auth.py` —— `HermesOnBehalfAuthentication(BaseAuthentication)`
- 触发条件:请求带 `X-Hermes-Service-Key` 头。
- 流程:
  1. `hmac.compare_digest(header_key, settings.HERMES_SERVICE_KEY)`,不等 → `AuthenticationFailed(code="hermes_bad_key")`。
  2. 读 `X-Acting-Wecom-Userid`,`User.objects.get(wechat_work_id=userid, is_active=True, is_deleted=False)`;`DoesNotExist` → `AuthenticationFailed(code="hermes_unbound")`。
  3. 返回 `(user, {"hermes": True, "wecom_userid": userid})`。
- 记一条结构化访问日志(logger `hermes.access`):`wecom_userid → erp_user(id/username) → method path`。便于追溯"Hermes 代谁查了什么"。
- 复用先例:`apps/sales/after_sales_service.py:894` 的 `CustomerPortalJWTAuthentication` 已验证"自定义 BaseAuthentication"在本代码库可行。
- 接入方式:加入 `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']`,**置于 JWTAuthentication 之前**;无 Hermes 头时返回 `None` 放行给 JWT,**不影响现有任何接口**。

### 4.2 `hermes_readonly.py` —— `HermesReadOnlyMiddleware`
- 若 `request` 带 `X-Hermes-Service-Key` 头且 `request.method` 不在 `{GET, HEAD, OPTIONS}` → 直接 `HttpResponseForbidden`。
- 与认证解耦的纯防御层;放 `settings.MIDDLEWARE` 靠前。阶段②放开写操作时,改为白名单放行特定写端点。

### 4.3 `hermes_views.py` + `urls.py` —— 健康/自检端点
- `GET /api/integrations/hermes/whoami`:认证换身份后返回当前 ERP 用户(`id/username/姓名/部门/角色/data_scope`)。用途:(a) 工具自检链路与绑定;(b) 解决"分配给我"——`?assignee=me` 不存在,工具先 whoami 拿 `user.id` 再传 `?assignee=<id>`;(c) 让 agent 能告诉员工"我在以谁的身份查"。
- 注册到 `config/urls.py`:`path('api/integrations/hermes/', include('apps.core.integrations.urls'))`。

### 4.4 配置
- `HERMES_SERVICE_KEY` 经 `python-decouple` 从 `.env` / `.env.docker` 读取(随机长串)。缺失时认证类对所有 Hermes 请求拒绝(fail-closed)。

### 4.5 不做的事
- 不改任何现有 ViewSet/Serializer/权限。数据范围、审批、审计中间件全部沿用。

## 5. 组件二:Hermes 侧改动(小)

新增 `/home/administrator/.hermes/hermes-agent/tools/erp_tool.py`,`registry.register(...)` 注册;形态参照 `tools/send_message_tool.py`(语义化、读 contextvar)。

### 5.1 统一 helper `_erp_get(path, params)`
- `wecom_userid = get_session_env("HERMES_SESSION_USER_ID", "")`;为空 → 返回"无法识别你的企微身份"。
- `requests.get(f"{ERP_BASE_URL}{path}", params=params, headers={X-Hermes-Service-Key, X-Acting-Wecom-Userid}, timeout=...)`。
- `401 hermes_unbound` → 返回友好话术:"你的企业微信尚未绑定 ERP 账号,请联系管理员在用户资料里填写企业微信用户ID"。其它错误 → 简明错误,不泄露栈。
- 成功 → **裁剪字段**后返回精简 JSON(只取展示必需字段,省 token、避免多余字段外泄)。
- 配置:`ERP_BASE_URL`(默认 `http://127.0.0.1:8080`,走 nginx 入口)、`HERMES_SERVICE_KEY` 放 Hermes 的 `.env`。

### 5.2 工具清单(4 个语义化只读工具)
每个工具内部锁定到固定 ERP 端点+过滤参数(LLM 调用准、好审计、端点不可被 LLM 自由拼接):

| 工具 | 用途 | 参数 | 映射端点(白名单) |
|---|---|---|---|
| `erp_query_documents` | 查单据状态/进度 | `doc_type`∈{sales_order, purchase_order, project, production_plan}、`keyword`(单号/名称)、`status?`、`limit?` | `GET /api/sales/orders/?search=`、`/api/purchase/orders/?search=`、`/api/projects/projects/?search=`、`/api/production/plans/?search=`(及对应 `/{id}/`) |
| `erp_query_inventory` | 查库存/预警/批次 | `item_keyword?`、`warehouse?`、`view`∈{stock, low_stock, alert, batch} | `/api/inventory/stocks/?search=`、`/stocks/low_stock/`、`/stock-alerts/active/`、`/batches/?search=` |
| `erp_my_todos` | 查我的待办 | `kind`∈{approvals, tasks, work_orders} | `/api/core/workflow/tasks/my_pending/`(自动按当前用户)、`/api/projects/tasks/?assignee=<whoami.id>`、`/api/projects/work-orders/?search=` |
| `erp_query_finance` | 查应收/应付/账龄 | `kind`∈{receivable, payable}、`keyword?`(客户/供应商/单号)、`view`∈{list, overdue, aging} | `/api/finance/receivables/`(+`/overdue/`、`/aging/`)、`/api/finance/payables/` |

注:`erp_my_todos` 的 `tasks` 分支需先调 `whoami` 取 `user.id`(`?assignee=me` 不存在);helper 内对每个 wecom_userid 缓存 whoami 结果(短 TTL)以省往返。

### 5.3 注册与启用
- `registry.register` 四个工具到合适 toolset;在 `hermes tools` 配置中对相关会话启用。
- 提供一条 skill/系统提示片段,告诉 agent 这些工具是"以提问者本人身份只读查 ERP",引导优先用语义化工具而非乱猜。

## 6. 安全与边界

- **身份**:仅凭后端 `wechat_work_id` 换身份,userid 由 gateway 注入、非 LLM 可控参数,杜绝"传别人 id 越权"。
- **越权**:数据范围由 ERP 后端 RBAC 决定,Hermes 不参与权限判断。
- **只读**:中间件按 HTTP method 强制(纵深防御),工具本身也只发 GET。
- **未绑定/停用用户**:明确 401 code → 工具转友好话术,不泄露数据。
- **未授权 IM 用户**:Hermes pairing 白名单先挡一层。
- **密钥**:单一 `HERMES_SERVICE_KEY`,两侧 `.env` 各存一份;`compare_digest` 防时序攻击;fail-closed。
- **网络**:Hermes(宿主机)→ ERP nginx `127.0.0.1:8080`,不出内网。
- **限流(可选,阶段①可不做)**:对 Hermes 来源加 DRF throttle,防异常高频。
- **返回裁剪**:工具只回展示必需字段,降低敏感字段外泄面与 token 成本。

## 7. 测试与验收

**ERP 后端(Django 单测,经 Docker 跑——本机无 venv)**
- 认证类:正确密钥+有效 userid → 换到对应 user;错误密钥 → 401;未知/停用 userid → 401(对应 code);无 Hermes 头 → 放行给 JWT(不影响现有接口)。
- 只读中间件:带 Hermes 头的 POST/PUT/DELETE → 403;GET → 放行。
- `whoami` 返回字段正确;数据范围:用两个不同数据范围的用户查同一 list,结果按各自范围过滤(回归保证不越权)。

**Hermes 工具(单测)**
- mock contextvar + mock ERP HTTP:四个工具的端点/参数映射正确;未绑定 → 友好话术;字段裁剪正确。

**端到端冒烟**
- 用真实企微账号在企微问四类问题各一,核对返回与该员工在 ERP 网页所见数据范围一致;用一个 `wechat_work_id` 未填的账号验证"未绑定"话术。

## 8. 部署 / 上线

- **ERP**:改动后需重建后端镜像(镜像打包源码,改动需 rebuild 才上线)——`docker compose up -d --build backend`;`.env.docker` 加 `HERMES_SERVICE_KEY`。无新表(认证只读),无需 migrate;`whoami` 不建模型。
- **Hermes**:放置 `erp_tool.py`、其 `.env` 加 `HERMES_SERVICE_KEY`/`ERP_BASE_URL`、启用工具后 `./scripts/hermes-gateway restart`。
- **顺序**:先上 ERP(认证+whoami 可用)→ 再上 Hermes 工具 → whoami 冒烟 → 放给小范围员工试用。

## 9. 风险与回滚

- 风险:`wechat_work_id` 未普遍维护 → 部分员工"未绑定"。缓解:友好话术 + 给管理员一份未绑定名单(可后续做)。
- 风险:服务密钥泄露 → 任何人可冒充任一 userid 只读查询。缓解:密钥仅内网两进程持有、可随时轮换、只读+数据范围兜底;必要时加来源 IP 限制。
- 回滚:ERP 移除认证类/中间件/url 注册即恢复原状(无数据变更);Hermes 删工具 + restart。互不影响。

## 10. 后续路线(不在本 spec 范围,各自独立设计周期)

- **阶段② ERP 日报/巡检**:复用①的查询能力 + Hermes cron,定时拉数生成日报推 IM。①完成后很轻。
- **阶段③ ERP 事件推送到 IM**:ERP 侧加 webhook(审批待办/库存预警/订单状态变更)→ Hermes gateway 收消息 → 投递到对应员工企微。较独立。
- **阶段④ Hermes 嵌入 ERP 前端**:ERP Vue 页面嵌对话框,接 Hermes `gateway/platforms/api_server.py`。较独立;问数据时复用①工具。
- **放开写操作**:在①稳定后,按"低风险写+二次确认+完整审计"逐个端点放开,改 `HermesReadOnlyMiddleware` 为白名单。

## 11. 开放问题

- 阶段①是否需要"未绑定员工名单"导出给管理员?(倾向后续做)
- 工具结果是否需要附"数据来自 ERP、以你本人权限查询"的固定脚注?(建议加,合规友好)

(`ERP_BASE_URL` 已定:默认走 nginx `:8080` 统一入口;如后续有内网直连 backend 的性能需求再议。)
