# B 专项:对照运行中的旧 Django 做业务逻辑对账

> 方法:用本地镜像把旧 Django 跑起来当**裁判**,对深度业务逻辑逐条核对 Go 移植"算得对不对"。
> 这类正确性(财务过账/库存账实/选流)无法靠读代码确认,必须有可运行的权威实现 diff。

## 裁判环境(可复用)

```bash
# 起旧 Django(本地镜像,跳过 ES/celery/nginx;backend 自动迁移+bootstrap)
IMAGE_TAG=local docker compose up -d postgres redis backend
# 等健康
until [ "$(docker inspect -f '{{.State.Health.Status}}' erp-backend)" = healthy ]; do :; done
# 跑裁判脚本(stdin 喂 Django shell)
docker exec -i erp-backend python manage.py shell < oracle.py
```
注意:创建被 ES 索引的模型(Item/Customer/Supplier)会触发 django-elasticsearch-dsl 实时索引,
ES 未起会报错——用 `Model.objects.bulk_create([...])` 绕过 post_save 信号。

## ✅ inventory — 移动加权平均成本(已验证一致)

权威:`apps.inventory.cost_accounting.CostCalculationService`(append-only `inventory_item_cost_record` 账本)。
- 入库:`new_unit = (prev_cost + qty×unit) / (prev_qty+qty)`,量化 4dp HALF_UP。
- 出库:`out_total = (qty × balance_unit_cost)` **先量化 2dp 再从结存金额扣减**(关键细节)。

裁判算例(入 10@100、10@200、2@13;出 5):
`bal_qty=17.0000  bal_cost=2338.27  bal_unit=137.5453`

Go 实现:`server/internal/inventory/cost/`(shopspring/decimal,禁 float64),
单测 `TestWeightedAverageMatchesDjangoOracle` 断言同一序列得到**完全相同数字**,PASS。

**库存移动 confirm → Stock 端到端**(独立于上面的成本账本,对齐 `StockMove._update_stock`):
`CompleteMove`/`CreateMove(COMPLETED)` → `applyMoveToStock`(IN/OUT/TRANSFER/ADJUSTMENT)→
`stockIn`(加权平均,行锁)/`stockOut`(库存不足报错)。裁判算例(IN 10@100、5@130、3@121.50、OUT 4):
Stock `qty=14.00 avg=111.92`;Go 集成测试 `TestStockMoveConfirmMatchesDjango` 断言一致,PASS。
并把 `stockIn` 的加权平均除法由 float64 改 decimal,消除分位四舍五入边界与 Django 的潜在偏差。

## ✅ workflow — 选流算法(已验证一致)

权威:`WorkflowService.get_workflow_for_business`:
`filter(business_type, is_active).order_by('-amount_threshold')`;给定金额时返回**首个**
`threshold is None or amount >= threshold` 者,否则首个。

关键细节:PG 对 `ORDER BY amount_threshold DESC` 为 **NULLS FIRST**,故**含 NULL 阈值的流程对任何金额都胜出**。
裁判:含 NULL → 全选 nothr;无 NULL → 5000/20000/100000 各选 low/mid/high。

Go 实现:`server/internal/workflow/repo.go: SelectForBusiness`——同 `Order("amount_threshold DESC")`(同 PG → 同 NULLS FIRST),算法逐行一致。
集成测试 `select_integration_test.go`(真库,因 NULLS 排序是 DB 行为)断言两场景与裁判一致,PASS。

## ✅ workflow — 跳步 / 会签(已对账并补齐)

**跳步**(`skip_amount_threshold`):Django `if step.skip_amount_threshold and instance.amount: if amount < threshold: continue`。
对账发现 Go 与之有真实差异——Go 只判 `!= nil`,而 Django 用 Python 真值(**0 视为假**),故 `amount=0` + 正阈值时
Go 会误跳、Django 不跳。**✅ 已修**:Go 改为"阈值与金额皆非 nil 且非 0 才比较"。裁判:`amount 0→step1`、
`3000→step2`、`8000→step1`、`None→step1`;Go 集成测试断言一致,PASS。

**会签**(`COUNTERSIGN`):Django **声明未实现**(每步单 task、单签即推进)——Go 新增能力。已实现:
`action_type=COUNTERSIGN` 时一步为全部审批人各生成一条 task,**全部 APPROVED 才推进**(任一拒绝整单驳回)。
集成测试(无 Django 裁判,验意图语义):2 审批人,签 1 实例仍 PENDING、签 2 实例 APPROVED,PASS。

**真实审批人 resolver**(对齐 Django `_get_step_assignee`):`accounts.WorkflowResolver` 实现
`workflow.AssigneeResolver` 并经 `RoutesWithService` 注入(引擎仍零业务 import,依赖方向 accounts→workflow):
- `USER`→step.approver_user;`ROLE`→该角色在岗用户(role_id + 兼容 user_roles M2M);
  `DEPARTMENT_MANAGER`/`SUPERIOR`→提交人部门负责人;兜底 approver_role→末位 superuser(对齐 Django,
  superuser 兜底越权风险见待定);`ResolveAll`(会签)ROLE 取该角色全部在岗用户。
- `PROJECT_MANAGER` 需业务上下文,返回 0 由引擎跳过,留 callback/port 接入(TODO)。
集成测试 `TestWorkflowResolverIAM`:step1 ROLE→角色用户、step2 DEPARTMENT_MANAGER→部门负责人,PASS。

## ✅ finance — 回款核销级联(已移植并验证)

权威:`apps.finance.collection_models.CollectionRecord.save()` 三级汇总:
1. 节点 `collected_amount = SUM(records.amount)`;状态:`>= planned → COLLECTED`(补 actual_date),`>0 → PARTIAL`。
2. 计划 `collected_amount = SUM(plan 下所有 records)`;状态:`>= total → COMPLETED`,`DRAFT → IN_PROGRESS`(否则不变)。
3. `plan.remaining_amount = total_amount - collected_amount`。

Go 实现:`server/internal/finance/collection/`(CollectionPlan/Milestone/Record 三级模型 +
`AddRecord` 事务级联 + 纯状态函数 `MilestoneStatus`/`PlanStatus`,decimal)。
裁判算例(计划 10w;m1 预付 3w、m2 尾款 7w):`m1+1w→PARTIAL/计划 IN_PROGRESS`;`m1+2w→COLLECTED`;
`m2+7w→计划 COMPLETED`;`remaining=0`。纯状态单测(默认)+ 级联集成测试(真库)均与裁判一致,PASS。

## 🐞 对账发现的真实 bug(共库阻断,待修)

**masterdata.Item 业务主键字段名不符**:Django `item` 表用 **`sku`**(必填),Go 移植用了 `code` 列。
A 波用 AutoMigrate 从 Go 模型建表,掩盖了与真实 Django schema 的不匹配。
**✅ 已修**:item 模型按真实列对齐(`sku`/`specification`/`category_id` FK/`standard_cost`/`purchase_price`/
`sale_price`,去掉不存在的 `code`/`price`/`spec`/`category`),连带 dto/repo/handler 与前端 api/视图/类型;
经真库 `\d item` 核对一致,前端 vue-tsc 通过。
提示:其它模块也应逐一用真库 schema 校验字段名(本轮发现并修了 item;建议下一波对每模块跑 `\d <table>` diff)。

## 🔍 全模块真库 schema diff(已完成)

用真库全表列(dump 494 表 / 8666 列到 `/tmp/real_schema.tsv`)对 10 个模块逐表 diff Go 模型列名。结论:

- **唯一系统性偏差:审计列命名**。真库审计外键列是 `created_by_id`/`updated_by_id`(Django FK 加 `_id`),
  而共享 `platform/model.Base` 的 gorm 标签写成 `created_by`/`updated_by`,且各模块 `iam.ApplyScope(…, "created_by")`
  把列名直接拼进 WHERE → 对真库 `column "created_by" does not exist`(非超管 self/dept 范围查询必失败)。
  **✅ 已修**:`Base` 标签改为 `created_by_id`/`updated_by_id`、`BeforeDelete` 同步 `updated_by_id`、
  全仓 22 处 ApplyScope ownerCol 统一为 `created_by_id`;build/test/vet 全绿,masterdata 集成测试真库 PASS。
- **其余模块业务列名全部匹配真库**(sales/purchase/inventory/projects/production/finance/oa/accounts/workflow):
  生成 agent 当初读了 Django models.py,列名基本正确;item 是早期手写切片,故唯一列名错(已先修)。
- 次要信息(无碍,未改):`project_drawing.file`(Django FileField)Go 未映射;`reference_id` integer vs Go `*int64`;
  `transaction_date` date vs Go `time.Time`——语义一致。

## 下一步

1. ✅ finance 回款核销接 REST 路由 + 前端:`/finance/collection` 计划 CRUD + 节点 + 收款记录(级联汇总);
   前端 `CollectionPlanList.vue` 列表/搜索/分页 + 新建/编辑/删除(草稿)计划 + 明细(节点 + 剩余应收)+
   加节点(类型对齐 Django MILESTONE_TYPE)+ 完整记收款表单(金额/日期/方式 PAYMENT_METHOD/备注 → 触发
   记录→节点→计划级联)。REST 集成测试覆盖级联 + PUT 更新 + DELETE 软删,前端 vue-tsc/vite build 全绿。
2. ✅ notify(站内信落库,`internal/notify`:system_notification + REST 列表/未读/已读)+ workflow
   待办/抄送/结果通知 + 超时提醒(对齐 Django check_workflow_deadline_reminders:仅提醒不改状态,
   asynq `@every 1h` 调度)均已落地并验证;✅ 前端通知中心(顶栏铃铛 + 未读角标 + 列表 + 一键已读,
   `web/src/components/NotificationBell.vue`)。
3. ✅ workflow PROJECT_MANAGER 解析(对齐 Django `_get_project_manager`):`accounts.WorkflowResolver.
   projectManager` 用真库表名直查 `business_type → 业务表.project_id → project.manager_id`(单跳 9 类 +
   PROJECT 直接 + DELIVERY_ORDER/CONTRACT_EXECUTION/PAYMENT_RECORD 多跳);全程 best-effort,
   解析不到 → 0 → 引擎兜底 approver_role→superuser(与 Django None 后一致)。引擎与 accounts 均不引业务包。
   集成测试 `TestWorkflowResolverProjectManager`(PROJECT 直接 / SALES_ORDER 单跳 / 无单据 → 兜底)PASS。
4. ✅ 站内信 WebSocket 实时推送:`notify.Service` 落库成功后经 `Pusher`(*ws.Hub 直接满足)`SendToUser`
   推 `{type:"notification",data}`;前端 `NotificationBell` 连 `/ws/notifications` 收到即刷新未读/列表
   (30s 轮询兜底 + 5s 重连)。worker 进程无 WS,超时提醒仅落库由轮询拾取。
   **WS 鉴权(安全评审):token 经 `Sec-WebSocket-Protocol` 子协议(`["access_token", <jwt>]`)传递,
   不进 URL**(避免 access log / 代理日志 / 浏览器历史泄漏);服务端 `bearerSubprotocol` 取 token、
   握手只回选哨兵子协议绝不回显 token(单测 `TestBearerSubprotocol` 覆盖)。
3. inventory 成本账本(ItemCostRecord)与 Stock 移动联动(目前 Stock 走 weighted_avg_cost,
   ItemCostRecord 账本由其它流程喂);若需两者统一,需评估 Django 侧实际喂账本的入口。
