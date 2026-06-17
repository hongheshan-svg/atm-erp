# ERP 通知精准推送到责任人个人(第一批)

- 日期：2026-06-17
- 状态：设计待评审
- 范围：**第一批**——把"责任人字段现成、能直接精准到人"的 7 类通知,从"只群发脱敏"改为"个人优先 + 群播兜底"。财务(应收/应付/收款)回退逻辑、库存预警配置化 = **第二批**,不在本 spec。

---

## 1. 背景

ERP 已有完整企微通知能力(`apps/core/notification_service.py` 的 `send_to_user` / `send_personal_notification` 走个人应用消息;群机器人走 `send_custom_notification`)。但现状是**绝大多数业务事件只调群发、脱敏、不点名**,责任人收不到精准提醒,个人应用消息能力闲置。

调研已确认:第一批 7 类事件的责任人字段**全部现成、FK→User、无需新建模型/字段**;且 `check_project_task_reminders()` 已实现"按 assignee 分组发个人"的范式,可作示范。

## 2. 目标与非目标

**目标**
- 7 类通知改为:能定位责任人 → 推**个人**(含明细);定位不到 → **群播兜底**(脱敏,沿用现有 safe_content)。
- 同一责任人在一次任务里的多条提醒**合并为一条**,减少打扰。
- 复用现有 `send_personal_notification` / `send_to_user`,不新建通知基础设施。

**非目标(本批不做)**
- 财务应收/应付/收款提醒(需经 SO/PO→created_by→project.manager→角色的多级回退,复杂度高)= 第二批。
- 库存预警(物料无负责人,需读 `StockAlertRule.notify_users`/`notify_roles` 配置)= 第二批。
- 不新建任何模型/字段;不动权限、数据范围、审批逻辑;不改通知发送底层(只改调用方)。

## 3. 统一改造范式

**定时批量类**(销售交期、采购交期、项目截止、项目任务、售后):
```python
from collections import defaultdict
per_user = defaultdict(list)        # responsible_user -> [items]
orphans = []                        # 无责任人/责任人无企微id
for obj in due_objects:
    user = resolve_responsible(obj)              # 见下表
    if user and user.is_active and user.wechat_work_id:
        per_user[user].append(obj)
    else:
        orphans.append(obj)
# 个人:每人一条合并消息(含明细)
for user, items in per_user.items():
    NotificationService.send_personal_notification([user], title, build_detail(items))
# 兜底:无法定位个人的,群播脱敏汇总(保留现有 safe_content 逻辑)
if orphans:
    NotificationService.send_custom_notification(title, group_safe_content=build_safe(orphans))
```

**事件触发类**(审批待办、审批结果,单条):
```python
def send_approval_notification(task):
    user = task.assignee
    if user and user.is_active and user.wechat_work_id:
        NotificationService.send_to_user(user, title, build_detail(task))   # 个人,含明细
    else:
        NotificationService.send_custom_notification(title, group_safe_content=safe)  # 兜底群播
```

**内容分级**:个人消息可含明细(单号/客户/金额/到期日——推给本人不进群);群播兜底沿用脱敏 safe_content。

## 4. 各事件改造点(责任人来源已核实)

| 事件 | 触发位置 | 责任人 | 回退 |
|---|---|---|---|
| 审批待办 | `apps/core/workflow/services.py:737`(`send_approval_notification(task)`) | `WorkflowTask.assignee`(models.py:233) | 群播兜底 |
| 审批结果 | `services.py:765`(`_notify_submitter`→`send_workflow_result_notification`) | `WorkflowInstance.submitter`(models.py:185) | 群播兜底 |
| 销售交期 | `apps/sales/tasks.py` `check_delivery_reminders` | `SalesOrder.created_by` | 群播兜底 |
| 采购交期 | `apps/purchase/tasks.py` `check_delivery_reminders` | `PurchaseOrder.created_by` | 群播兜底 |
| 项目截止 | `apps/projects/tasks.py:205` `check_project_deadline_reminders` | `Project.manager` | 群播兜底 |
| 项目任务 | `apps/projects/tasks.py:12` `check_project_task_reminders` | `ProjectTask.assignee`(已实现个人) | **对齐范式**(统一兜底/合并),非重写 |
| 售后 | `apps/projects/tasks.py:305` `check_aftersales_reminders` | `ServiceRequest.assigned_to`(可空) | 群播兜底 |

> 注:`send_approval_notification`/`send_workflow_result_notification` 当前签名只收 `task`/`instance`,已能取到 `assignee`/`submitter`,**改方法体即可,调用方不变**。

## 5. 边界与错误处理

- **责任人字段为空 / 无 `wechat_work_id` / 已停用** → 计入兜底群播,不静默丢。
- `send_personal_notification` 内部已 try/except 记 log;个人发送失败不应中断整批。
- **合并去重**:定时类按 user 分组合并;事件类单条无需合并。
- **群播开关**:兜底群播受现有 `NOTIFICATION_CHANNELS_ENABLED` / `_is_wechat_enabled()` 控制,保持不变。

## 6. 测试(经 Docker 跑——本机无 venv)

每个改造函数 Django 单测,mock `NotificationService`:
- 有责任人(含 `wechat_work_id`)→ 断言调 `send_personal_notification`/`send_to_user`、对象正确分组、明细含关键字段。
- 责任人为空/无企微id/停用 → 断言走 `send_custom_notification` 兜底,不发个人。
- 多条同责任人 → 断言合并为一条。
- 审批待办/结果:assignee/submitter 存在 → 个人;缺失 → 兜底。
- 回归:确认未改动的财务/库存预警通知行为不变。

## 7. 部署

- 改 `apps/*/tasks.py` 与 `apps/core/workflow/services.py` → **重建 backend 镜像**(`docker compose up -d --build backend`)。
- ⚠️ **改了 Celery 任务,必须 `docker compose restart celery celery-beat`**,否则旧 worker 仍持旧任务定义。
- 无迁移(不动模型)。

## 8. 风险与回滚

- 风险:员工 `wechat_work_id` 未普遍维护 → 大量走兜底群播(等于退回现状,不会更差)。可配合"未绑定名单"运维(与 Hermes #1 共享同一诉求)。
- 风险:个人消息含明细 → 确认明细字段不超企微 512 字符限制(`send_personal_notification` 已截断 500)。
- 回滚:每个函数改动独立,逐个 revert 即可;无数据变更。

## 9. 第二批(预告,独立设计)

- **财务**(应收逾期/应付/收款提醒):责任人经 `SO/PO.created_by` → `project.manager` → 角色 多级回退。
- **库存预警**:读 `StockAlertRule.notify_users`(个人)/`notify_roles`(角色),物料无负责人故走配置化。
- 两者范式同本批,只是 `resolve_responsible` 是多级/查配置,故单列一批处理回退分支。
