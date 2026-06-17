# ERP 通知精准到人(第一批) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 7 类业务提醒的企微/钉钉**外部推送**从「一律群发脱敏」升级为「对有 `wechat_work_id` 的责任人推个人(含明细)+ 定位不到的群播兜底」,站内信逻辑保持不变。

**Architecture:** 在 `NotificationService` 加一个 `send_targeted_reminders` helper 封装「个人优先 + 群播兜底」决策;每个 task 把「拿责任人 + 构建明细」抽成无 DB 依赖的纯函数(便于单测),再调 helper。审批待办/结果是事件触发,直接在两个 notification 方法内分流。责任人全部用单据现成字段,不新建模型/字段。

**Tech Stack:** Django 4.2 / Celery / Django TestCase + `unittest.mock`。

## Global Constraints

- 本机无 venv,**测试/迁移须经 Docker**:`docker compose exec backend python manage.py test <dotted.path> -v 2`(backend 容器已 healthy)。
- 改了 Celery 任务定义后**须** `docker compose restart celery celery-beat`;代码上线须 `docker compose up -d --build backend`。本计划无迁移(不动模型)。
- 责任人字段(verbatim):审批待办 `WorkflowTask.assignee`;审批结果 `WorkflowInstance.submitter`;销售交期 `SalesOrder.created_by`;采购到货 `PurchaseOrder.created_by`;项目截止 `Project.manager`;项目任务 `ProjectTask.assignee`;售后 `AfterSalesOrder.assigned_to`。
- 「能精准」判定:`user and user.is_active and user.wechat_work_id`(三者皆真)。
- 个人消息可含明细;群播兜底沿用各 task 现有的脱敏 `safe_content`。
- `send_to_user(user, title, content)` 与 `send_custom_notification(title, content, *, group_safe_content=...)` 已存在,不改其签名。
- 提交信息结尾:`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

---

### Task 1: NotificationService.send_targeted_reminders helper

**Files:**
- Modify: `backend/apps/core/notification_service.py`(在 `NotificationService` 末尾,`send_payment_reminder` 之后加方法)
- Test: `backend/apps/core/tests/test_targeted_reminders.py`(新建)

**Interfaces:**
- Produces: `NotificationService.send_targeted_reminders(personal_messages, title, group_safe_content, has_unassigned=False) -> dict`
  - `personal_messages`: `list[tuple[User, str]]`(责任人 → 他的明细文本)
  - 返回 `{'personal_sent': int, 'personal_skipped': int}`
  - 行为:对每个 `user.is_active and user.wechat_work_id` 的项调 `send_to_user`;若 `has_unassigned` 或有被跳过的责任人或一个个人都没发出 → 调 `send_custom_notification` 群播兜底。

- [ ] **Step 1: Write the failing test**

```python
# backend/apps/core/tests/test_targeted_reminders.py
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase
from apps.core.notification_service import NotificationService


def _user(active=True, wxid='wx1'):
    return SimpleNamespace(is_active=active, wechat_work_id=wxid)


class SendTargetedRemindersTest(TestCase):
    def test_personal_sent_for_users_with_wechat_no_group(self):
        u = _user()
        with patch.object(NotificationService, 'send_to_user') as m_personal, \
             patch.object(NotificationService, 'send_custom_notification') as m_group:
            res = NotificationService.send_targeted_reminders(
                [(u, '明细A')], '标题', 'safe', has_unassigned=False)
        m_personal.assert_called_once_with(u, '标题', '明细A')
        m_group.assert_not_called()
        self.assertEqual(res, {'personal_sent': 1, 'personal_skipped': 0})

    def test_user_without_wechat_falls_back_to_group(self):
        u = _user(wxid='')
        with patch.object(NotificationService, 'send_to_user') as m_personal, \
             patch.object(NotificationService, 'send_custom_notification') as m_group:
            res = NotificationService.send_targeted_reminders([(u, 'x')], 't', 'safe')
        m_personal.assert_not_called()
        m_group.assert_called_once()
        self.assertEqual(res['personal_skipped'], 1)

    def test_has_unassigned_forces_group_even_when_personal_sent(self):
        u = _user()
        with patch.object(NotificationService, 'send_to_user') as m_personal, \
             patch.object(NotificationService, 'send_custom_notification') as m_group:
            NotificationService.send_targeted_reminders([(u, 'x')], 't', 'safe', has_unassigned=True)
        m_personal.assert_called_once()
        m_group.assert_called_once()

    def test_empty_personal_sends_group(self):
        with patch.object(NotificationService, 'send_to_user') as m_personal, \
             patch.object(NotificationService, 'send_custom_notification') as m_group:
            NotificationService.send_targeted_reminders([], 't', 'safe')
        m_personal.assert_not_called()
        m_group.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend python manage.py test apps.core.tests.test_targeted_reminders -v 2`
Expected: FAIL — `AttributeError: ... has no attribute 'send_targeted_reminders'`

- [ ] **Step 3: Write minimal implementation**

```python
# 加在 NotificationService 末尾(send_payment_reminder 之后)
    @classmethod
    def send_targeted_reminders(cls, personal_messages, title, group_safe_content, has_unassigned=False):
        """个人优先 + 群播兜底。personal_messages: list[(user, detail)]。"""
        sent = 0
        skipped = 0
        for user, content in personal_messages:
            if user and getattr(user, 'is_active', True) and getattr(user, 'wechat_work_id', ''):
                cls.send_to_user(user, title, content)
                sent += 1
            else:
                skipped += 1
        if has_unassigned or skipped > 0 or sent == 0:
            cls.send_custom_notification(title, group_safe_content, group_safe_content=group_safe_content)
        return {'personal_sent': sent, 'personal_skipped': skipped}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec backend python manage.py test apps.core.tests.test_targeted_reminders -v 2`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/apps/core/notification_service.py backend/apps/core/tests/test_targeted_reminders.py
git commit -m "feat(notify): 加 send_targeted_reminders(个人优先+群播兜底) helper

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 审批待办/审批结果 改个人优先

**Files:**
- Modify: `backend/apps/core/notification_service.py`(`send_approval_notification`、`send_workflow_result_notification` 方法体)
- Test: `backend/apps/core/tests/test_approval_personal.py`(新建)

**Interfaces:**
- Consumes: `send_targeted_reminders`(Task 1)
- 调用方 `apps/core/workflow/services.py:737,765` 不变(仍传 `task` / `(instance, result)`)。

- [ ] **Step 1: Write the failing test**

```python
# backend/apps/core/tests/test_approval_personal.py
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase
from apps.core.notification_service import NotificationService


def _task(wxid='wx1'):
    wf = SimpleNamespace(get_business_type_display=lambda: '采购订单')
    inst = SimpleNamespace(workflow=wf, business_no='PO-1')
    assignee = SimpleNamespace(is_active=True, wechat_work_id=wxid)
    return SimpleNamespace(instance=inst, assignee=assignee)


class ApprovalPersonalTest(TestCase):
    def test_approval_notifies_assignee_personally(self):
        t = _task()
        with patch.object(NotificationService, 'send_to_user') as m_personal, \
             patch.object(NotificationService, 'send_custom_notification') as m_group:
            NotificationService.send_approval_notification(t)
        m_personal.assert_called_once()
        self.assertIs(m_personal.call_args.args[0], t.assignee)
        m_group.assert_not_called()

    def test_approval_without_wechat_falls_back_group(self):
        t = _task(wxid='')
        with patch.object(NotificationService, 'send_to_user') as m_personal, \
             patch.object(NotificationService, 'send_custom_notification') as m_group:
            NotificationService.send_approval_notification(t)
        m_personal.assert_not_called()
        m_group.assert_called_once()

    def test_result_notifies_submitter_personally(self):
        wf = SimpleNamespace(get_business_type_display=lambda: '采购订单')
        submitter = SimpleNamespace(is_active=True, wechat_work_id='wx9')
        inst = SimpleNamespace(workflow=wf, business_no='PO-9', submitter=submitter)
        with patch.object(NotificationService, 'send_to_user') as m_personal:
            NotificationService.send_workflow_result_notification(inst, 'APPROVED')
        m_personal.assert_called_once()
        self.assertIs(m_personal.call_args.args[0], submitter)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend python manage.py test apps.core.tests.test_approval_personal -v 2`
Expected: FAIL（当前方法只群发，`send_to_user` 不会被调用）

- [ ] **Step 3: Write minimal implementation**

把 `send_approval_notification` 方法体改为(替换其内部群发逻辑):

```python
    @classmethod
    def send_approval_notification(cls, task):
        title = '📋 审批任务提醒'
        biz = task.instance.workflow.get_business_type_display()
        safe_content = f'### {title}\n\n您有一个新的 **{biz}** 审批任务待处理\n\n请登录ERP系统查看详情并及时处理！'
        assignee = getattr(task, 'assignee', None)
        detail = f'您有一个新的 **{biz}** 审批任务待处理:单据 {task.instance.business_no}。请登录ERP及时处理。'
        cls.send_targeted_reminders(
            [(assignee, detail)] if assignee else [],
            title, safe_content, has_unassigned=(assignee is None),
        )
```

把 `send_workflow_result_notification` 方法体改为:

```python
    @classmethod
    def send_workflow_result_notification(cls, instance, result):
        result_emoji = {'APPROVED': '✅', 'REJECTED': '❌', 'WITHDRAWN': '↩️'}.get(result, '📋')
        result_text = {'APPROVED': '已通过', 'REJECTED': '已拒绝', 'WITHDRAWN': '已撤回'}.get(result, result)
        title = f'{result_emoji} 审批结果通知'
        biz = instance.workflow.get_business_type_display()
        safe_content = f'### {title}\n\n您提交的 **{biz}** 审批{result_text}\n\n请登录ERP系统查看详情。'
        submitter = getattr(instance, 'submitter', None)
        detail = f'您提交的 **{biz}** 审批{result_text}:单据 {instance.business_no}。'
        cls.send_targeted_reminders(
            [(submitter, detail)] if submitter else [],
            title, safe_content, has_unassigned=(submitter is None),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec backend python manage.py test apps.core.tests.test_approval_personal -v 2`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/apps/core/notification_service.py backend/apps/core/tests/test_approval_personal.py
git commit -m "feat(notify): 审批待办推审批人本人、结果推提交人本人(无企微则群播兜底)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 销售交期提醒 个人化

**Files:**
- Modify: `backend/apps/sales/tasks.py`(`check_delivery_reminders` 的外部推送段 + 加纯函数 `build_personal_delivery_reminders`)
- Create: `backend/apps/sales/tests/__init__.py`(空)
- Test: `backend/apps/sales/tests/test_delivery_personal.py`

**Interfaces:**
- Consumes: `NotificationService.send_targeted_reminders`(Task 1)
- Produces(模块级纯函数,供测试):`build_personal_delivery_reminders(overdue_orders, upcoming_orders, today) -> tuple[list[tuple[User,str]], bool]`

- [ ] **Step 1: Write the failing test**

```python
# backend/apps/sales/tests/test_delivery_personal.py
from datetime import date
from types import SimpleNamespace
from django.test import TestCase
from apps.sales.tasks import build_personal_delivery_reminders


def _order(no, created_by, ddate, cust='客户A', amt=1000):
    return SimpleNamespace(order_no=no, created_by=created_by,
                           expected_delivery_date=ddate,
                           customer=SimpleNamespace(name=cust), total_amount=amt)


class BuildPersonalDeliveryTest(TestCase):
    def test_groups_by_created_by_and_flags_unassigned(self):
        u = SimpleNamespace(is_active=True, wechat_work_id='wx1')
        today = date(2026, 6, 17)
        overdue = [_order('SO-1', u, date(2026, 6, 10))]
        upcoming = [_order('SO-2', None, date(2026, 6, 19))]   # 无 created_by → unassigned
        messages, has_unassigned = build_personal_delivery_reminders(overdue, upcoming, today)
        self.assertEqual(len(messages), 1)
        self.assertIs(messages[0][0], u)
        self.assertIn('SO-1', messages[0][1])
        self.assertTrue(has_unassigned)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend python manage.py test apps.sales.tests.test_delivery_personal -v 2`
Expected: FAIL — `ImportError: cannot import name 'build_personal_delivery_reminders'`

- [ ] **Step 3: Write minimal implementation**

在 `backend/apps/sales/tasks.py` 顶部 import 下方加纯函数:

```python
def build_personal_delivery_reminders(overdue_orders, upcoming_orders, today):
    """按 SalesOrder.created_by 分组明细。返回 (personal_messages, has_unassigned)。"""
    from collections import defaultdict
    lines = defaultdict(list)
    has_unassigned = False
    for order in list(overdue_orders) + list(upcoming_orders):
        if getattr(order, 'created_by', None):
            d = (today - order.expected_delivery_date).days
            tag = f'逾期{d}天' if d > 0 else f'{-d}天后到期'
            lines[order.created_by].append(
                f'- {order.order_no} | {order.customer.name} | ¥{order.total_amount:,.2f} | {tag}')
        else:
            has_unassigned = True
    messages = [(u, '🚚 您负责的销售订单交货提醒:\n' + '\n'.join(ls)) for u, ls in lines.items()]
    return messages, has_unassigned
```

把 `check_delivery_reminders` 末尾的 `try: ... send_custom_notification(...) except: pass` 段替换为:

```python
    # 外部推送:个人优先 + 群播兜底
    try:
        title = '🚚 销售订单交货提醒'
        safe_content = f'### {title}\n\n'
        if overdue_items:
            safe_content += f'⚠️ **{len(overdue_items)}** 笔订单已逾期交货\n'
        if upcoming_items:
            safe_content += f'📅 **{len(upcoming_items)}** 笔订单即将到期\n'
        safe_content += '\n请登录ERP系统查看详情并及时安排发货！'
        messages, has_unassigned = build_personal_delivery_reminders(overdue_orders, upcoming_orders, today)
        NotificationService.send_targeted_reminders(messages, title, safe_content, has_unassigned=has_unassigned)
    except Exception:
        pass
```

并把两个 queryset 的 `.select_related('customer', 'project')` 改为 `.select_related('customer', 'project', 'created_by')`(两处)。

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec backend python manage.py test apps.sales.tests.test_delivery_personal -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/sales/tasks.py backend/apps/sales/tests/
git commit -m "feat(notify): 销售交期提醒按 created_by 推销售本人

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 采购到货提醒 个人化

**Files:**
- Modify: `backend/apps/purchase/tasks.py`(`check_delivery_reminders` + 纯函数 `build_personal_arrival_reminders`)
- Test: `backend/apps/purchase/tests/test_arrival_personal.py`(`apps/purchase/tests/__init__.py` 已存在)

**Interfaces:**
- Produces: `build_personal_arrival_reminders(overdue_orders, upcoming_orders, today) -> tuple[list[tuple[User,str]], bool]`(责任人 `PurchaseOrder.created_by`)

- [ ] **Step 1: Write the failing test**

```python
# backend/apps/purchase/tests/test_arrival_personal.py
from datetime import date
from types import SimpleNamespace
from django.test import TestCase
from apps.purchase.tasks import build_personal_arrival_reminders


def _order(no, created_by, ddate, sup='供应商A', amt=2000):
    return SimpleNamespace(order_no=no, created_by=created_by,
                           expected_delivery_date=ddate,
                           supplier=SimpleNamespace(name=sup), total_amount=amt)


class BuildPersonalArrivalTest(TestCase):
    def test_groups_by_created_by(self):
        u = SimpleNamespace(is_active=True, wechat_work_id='wx1')
        today = date(2026, 6, 17)
        messages, has_unassigned = build_personal_arrival_reminders(
            [_order('PO-1', u, date(2026, 6, 10))], [], today)
        self.assertEqual(len(messages), 1)
        self.assertIn('PO-1', messages[0][1])
        self.assertFalse(has_unassigned)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend python manage.py test apps.purchase.tests.test_arrival_personal -v 2`
Expected: FAIL — ImportError

- [ ] **Step 3: Write minimal implementation**

`backend/apps/purchase/tasks.py` 顶部 import 下方加:

```python
def build_personal_arrival_reminders(overdue_orders, upcoming_orders, today):
    """按 PurchaseOrder.created_by 分组明细。返回 (personal_messages, has_unassigned)。"""
    from collections import defaultdict
    lines = defaultdict(list)
    has_unassigned = False
    for order in list(overdue_orders) + list(upcoming_orders):
        if getattr(order, 'created_by', None):
            d = (today - order.expected_delivery_date).days
            tag = f'逾期{d}天' if d > 0 else f'{-d}天后到货'
            lines[order.created_by].append(
                f'- {order.order_no} | {order.supplier.name} | ¥{order.total_amount:,.2f} | {tag}')
        else:
            has_unassigned = True
    messages = [(u, '📦 您负责的采购订单到货提醒:\n' + '\n'.join(ls)) for u, ls in lines.items()]
    return messages, has_unassigned
```

把末尾外部推送 `try` 段替换为(沿用现有 `safe_content`,改发送):

```python
    try:
        title = '📦 采购订单到货提醒'
        safe_content = f'### {title}\n\n'
        if overdue_items:
            safe_content += f'⚠️ **{len(overdue_items)}** 笔采购订单已逾期到货\n'
        if upcoming_items:
            safe_content += f'📅 **{len(upcoming_items)}** 笔采购订单即将到货\n'
        safe_content += '\n请登录ERP系统查看详情并提前准备收货！'
        messages, has_unassigned = build_personal_arrival_reminders(overdue_orders, upcoming_orders, today)
        NotificationService.send_targeted_reminders(messages, title, safe_content, has_unassigned=has_unassigned)
    except Exception:
        pass
```

并把两个 queryset 的 `.select_related('supplier', 'project')` 改为加 `'created_by'`(两处)。

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec backend python manage.py test apps.purchase.tests.test_arrival_personal -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/purchase/tasks.py backend/apps/purchase/tests/test_arrival_personal.py
git commit -m "feat(notify): 采购到货提醒按 created_by 推采购本人

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 项目截止提醒 个人化

**Files:**
- Modify: `backend/apps/projects/tasks.py`(`check_project_deadline_reminders` + 纯函数 `build_personal_project_reminders`)
- Create: `backend/apps/projects/tests/__init__.py`(空)
- Test: `backend/apps/projects/tests/test_project_deadline_personal.py`

**Interfaces:**
- Produces: `build_personal_project_reminders(overdue_projects, upcoming_projects, today) -> tuple[list[tuple[User,str]], bool]`(责任人 `Project.manager`)

- [ ] **Step 1: Write the failing test**

```python
# backend/apps/projects/tests/test_project_deadline_personal.py
from datetime import date
from types import SimpleNamespace
from django.test import TestCase
from apps.projects.tasks import build_personal_project_reminders


def _proj(code, manager, edate, name='项目X'):
    return SimpleNamespace(code=code, name=name, manager=manager, end_date=edate)


class BuildPersonalProjectTest(TestCase):
    def test_groups_by_manager_and_flags_unassigned(self):
        u = SimpleNamespace(is_active=True, wechat_work_id='wx1')
        today = date(2026, 6, 17)
        msgs, unassigned = build_personal_project_reminders(
            [_proj('P-1', u, date(2026, 6, 10))], [_proj('P-2', None, date(2026, 6, 20))], today)
        self.assertEqual(len(msgs), 1)
        self.assertIn('P-1', msgs[0][1])
        self.assertTrue(unassigned)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend python manage.py test apps.projects.tests.test_project_deadline_personal -v 2`
Expected: FAIL — ImportError

- [ ] **Step 3: Write minimal implementation**

`backend/apps/projects/tasks.py` 顶部 import 下方加:

```python
def build_personal_project_reminders(overdue_projects, upcoming_projects, today):
    """按 Project.manager 分组明细。返回 (personal_messages, has_unassigned)。"""
    from collections import defaultdict
    lines = defaultdict(list)
    has_unassigned = False
    for p in list(overdue_projects) + list(upcoming_projects):
        if getattr(p, 'manager', None):
            d = (today - p.end_date).days
            tag = f'逾期{d}天' if d > 0 else f'{-d}天后到期'
            lines[p.manager].append(f'- {p.code} | {p.name} | {tag}')
        else:
            has_unassigned = True
    messages = [(u, '📋 您负责的项目截止提醒:\n' + '\n'.join(ls)) for u, ls in lines.items()]
    return messages, has_unassigned
```

把末尾外部推送 `try` 段替换为(沿用现有 `safe_content`):

```python
    try:
        title = '📋 项目截止日期提醒'
        safe_content = f'### {title}\n\n'
        if overdue_items:
            safe_content += f'⚠️ **{len(overdue_items)}** 个项目已逾期\n'
        if upcoming_items:
            safe_content += f'📅 **{len(upcoming_items)}** 个项目即将到期\n'
        safe_content += '\n请登录ERP系统查看详情并及时跟进！'
        messages, has_unassigned = build_personal_project_reminders(overdue_projects, upcoming_projects, today)
        NotificationService.send_targeted_reminders(messages, title, safe_content, has_unassigned=has_unassigned)
    except Exception:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec backend python manage.py test apps.projects.tests.test_project_deadline_personal -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/projects/tasks.py backend/apps/projects/tests/__init__.py backend/apps/projects/tests/test_project_deadline_personal.py
git commit -m "feat(notify): 项目截止提醒按 manager 推项目经理本人

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: 项目任务进度提醒 外部推送个人化

**Files:**
- Modify: `backend/apps/projects/tasks.py`(`check_project_task_reminders` 的外部推送段 + 纯函数 `build_personal_task_reminders`)
- Test: `backend/apps/projects/tests/test_task_reminder_personal.py`

**Interfaces:**
- Produces: `build_personal_task_reminders(assignee_reminders) -> tuple[list[tuple[User,str]], bool]`
  - 入参复用函数内已构建的 `assignee_reminders`(`dict[assignee_id, {...}]`)需改为按 `assignee` 对象分组——见实现。

**注:** 该函数站内信已按 assignee 精准,本任务只补**企微个人推送**;把现有按 `assignee_id` 的分组改为同时保留 `assignee` 对象以便取 `wechat_work_id`。

- [ ] **Step 1: Write the failing test**

```python
# backend/apps/projects/tests/test_task_reminder_personal.py
from types import SimpleNamespace
from django.test import TestCase
from apps.projects.tasks import build_personal_task_reminders


class BuildPersonalTaskTest(TestCase):
    def test_builds_personal_messages_per_assignee(self):
        u = SimpleNamespace(is_active=True, wechat_work_id='wx1')
        data = {u: {'overdue': ['[P-1] 任务A | 逾期2天 | 进度10%'], 'upcoming': [], 'behind': []}}
        msgs, has_unassigned = build_personal_task_reminders(data, unassigned_present=True)
        self.assertEqual(len(msgs), 1)
        self.assertIs(msgs[0][0], u)
        self.assertIn('任务A', msgs[0][1])
        self.assertTrue(has_unassigned)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend python manage.py test apps.projects.tests.test_task_reminder_personal -v 2`
Expected: FAIL — ImportError

- [ ] **Step 3: Write minimal implementation**

在 `backend/apps/projects/tasks.py` 加纯函数:

```python
def build_personal_task_reminders(assignee_map, unassigned_present=False):
    """assignee_map: dict[User, {'overdue':[str], 'upcoming':[str], 'behind':[str]}]
    返回 (personal_messages, has_unassigned)。"""
    messages = []
    for user, data in assignee_map.items():
        parts = ['📋 您负责的项目任务提醒:']
        for key, label in (('overdue', '【已逾期】'), ('upcoming', '【即将到期】'), ('behind', '【进度落后】')):
            if data.get(key):
                parts.append(label)
                parts.extend(data[key][:5])
        messages.append((user, '\n'.join(parts)))
    return messages, unassigned_present
```

在 `check_project_task_reminders` 内,把 `assignee_reminders`(键为 `assignee_id`)新增一个并行的按对象映射;最简做法:在现有 `add_to_assignee` 旁记录 `id->user`。在函数内 `assignee_reminders = {}` 后加 `assignee_objs = {}`,并在三处 `if task.assignee:` 分支里加 `assignee_objs[task.assignee_id] = task.assignee`。构建 `assignee_map = {assignee_objs[aid]: {k: [格式化行...]} ...}`——直接复用已构建的 `data`(其值已是 dict,但存的是 item dict,不是字符串)。为避免重构面过大,改为:在末尾外部推送段就地构建字符串映射:

```python
    # 外部推送:对每个 assignee 推个人(企微),无 assignee 的任务计入兜底群播
    try:
        title = '📋 项目任务进度提醒'
        safe_content = f'### {title}\n\n'
        if overdue_items:
            safe_content += f'⚠️ **{len(overdue_items)}** 个任务已逾期\n'
        if upcoming_items:
            safe_content += f'📅 **{len(upcoming_items)}** 个任务即将到期\n'
        if behind_items:
            safe_content += f'🔴 **{len(behind_items)}** 个任务进度落后\n'
        safe_content += '\n请登录ERP系统查看详情并及时跟进！'

        assignee_map = {}
        for aid, data in assignee_reminders.items():
            user = assignee_objs.get(aid)
            if not user:
                continue
            assignee_map[user] = {
                'overdue': [f"[{i['project_code']}] {i['task_name']} | 逾期{i['days_overdue']}天 | 进度{i['progress']}%" for i in data['overdue']],
                'upcoming': [f"[{i['project_code']}] {i['task_name']} | {i['days_until']}天后到期 | 进度{i['progress']}%" for i in data['upcoming']],
                'behind': [f"[{i['project_code']}] {i['task_name']} | 应完成{i['expected_progress']}% 实际{i['actual_progress']}%" for i in data['behind']],
            }
        unassigned_present = any(i['assignee_name'] == '未指定' for i in (overdue_items + upcoming_items + behind_items))
        messages, has_unassigned = build_personal_task_reminders(assignee_map, unassigned_present)
        NotificationService.send_targeted_reminders(messages, title, safe_content, has_unassigned=has_unassigned)
    except Exception:
        pass
```

并在函数前部 `assignee_reminders = {}` 之后加一行 `assignee_objs = {}`,在三个 `if task.assignee:` 分支各加 `assignee_objs[task.assignee_id] = task.assignee`。

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec backend python manage.py test apps.projects.tests.test_task_reminder_personal -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/projects/tasks.py backend/apps/projects/tests/test_task_reminder_personal.py
git commit -m "feat(notify): 项目任务提醒补企微个人推送(按 assignee)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 售后工单提醒 个人化

**Files:**
- Modify: `backend/apps/projects/tasks.py`(`check_aftersales_reminders` + 纯函数 `build_personal_aftersales_reminders`)
- Test: `backend/apps/projects/tests/test_aftersales_personal.py`

**Interfaces:**
- Produces: `build_personal_aftersales_reminders(overdue_orders, upcoming_orders, today) -> tuple[list[tuple[User,str]], bool]`(责任人 `AfterSalesOrder.assigned_to`;未指派工单计入 `has_unassigned`)

- [ ] **Step 1: Write the failing test**

```python
# backend/apps/projects/tests/test_aftersales_personal.py
from datetime import date
from types import SimpleNamespace
from django.test import TestCase
from apps.projects.tasks import build_personal_aftersales_reminders


def _order(no, assigned_to, edate, cust='客户A'):
    return SimpleNamespace(order_no=no, title='工单', assigned_to=assigned_to,
                           expected_date=edate, customer=SimpleNamespace(name=cust),
                           get_priority_display=lambda: '高')


class BuildPersonalAftersalesTest(TestCase):
    def test_groups_by_assigned_to(self):
        u = SimpleNamespace(is_active=True, wechat_work_id='wx1')
        today = date(2026, 6, 17)
        msgs, unassigned = build_personal_aftersales_reminders(
            [_order('AS-1', u, date(2026, 6, 10))], [_order('AS-2', None, date(2026, 6, 18))], today)
        self.assertEqual(len(msgs), 1)
        self.assertIn('AS-1', msgs[0][1])
        self.assertTrue(unassigned)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend python manage.py test apps.projects.tests.test_aftersales_personal -v 2`
Expected: FAIL — ImportError

- [ ] **Step 3: Write minimal implementation**

`backend/apps/projects/tasks.py` 加纯函数:

```python
def build_personal_aftersales_reminders(overdue_orders, upcoming_orders, today):
    """按 AfterSalesOrder.assigned_to 分组。返回 (personal_messages, has_unassigned)。"""
    from collections import defaultdict
    lines = defaultdict(list)
    has_unassigned = False
    for order in list(overdue_orders) + list(upcoming_orders):
        if getattr(order, 'assigned_to', None):
            d = (today - order.expected_date).days
            tag = f'逾期{d}天' if d > 0 else f'{-d}天后到期'
            lines[order.assigned_to].append(
                f'- {order.order_no} | {order.customer.name} | {order.get_priority_display()} | {tag}')
        else:
            has_unassigned = True
    messages = [(u, '🔧 您负责的售后工单提醒:\n' + '\n'.join(ls)) for u, ls in lines.items()]
    return messages, has_unassigned
```

把末尾外部推送 `try` 段替换为(沿用现有 `safe_content`):

```python
    try:
        title = '🔧 售后工单提醒'
        safe_content = f'### {title}\n\n'
        if overdue_items:
            safe_content += f'⚠️ **{len(overdue_items)}** 个工单已逾期\n'
        if upcoming_items:
            safe_content += f'📅 **{len(upcoming_items)}** 个工单即将到期\n'
        if unassigned_items:
            safe_content += f'🔴 **{len(unassigned_items)}** 个紧急工单待指派\n'
        safe_content += '\n请登录ERP系统查看详情并及时处理！'
        messages, has_unassigned = build_personal_aftersales_reminders(overdue_orders, upcoming_orders, today)
        # 未指派的紧急工单本就该群播提醒
        NotificationService.send_targeted_reminders(
            messages, title, safe_content, has_unassigned=(has_unassigned or bool(unassigned_items)))
    except Exception:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec backend python manage.py test apps.projects.tests.test_aftersales_personal -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/projects/tasks.py backend/apps/projects/tests/test_aftersales_personal.py
git commit -m "feat(notify): 售后工单提醒按 assigned_to 推处理人本人

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: 集成回归 + 部署

**Files:** 无代码改动(验证 + 部署)。

- [ ] **Step 1: 跑全部新增测试**

Run: `docker compose exec backend python manage.py test apps.core.tests.test_targeted_reminders apps.core.tests.test_approval_personal apps.sales.tests apps.purchase.tests.test_arrival_personal apps.projects.tests -v 2`
Expected: 全部 PASS。

- [ ] **Step 2: 回归——确认未改动的财务/库存通知不受影响**

Run: `docker compose exec backend python manage.py test apps.finance apps.inventory -v 1`
Expected: 与改动前同样的通过/失败基线(本计划未触碰这两块)。

- [ ] **Step 3: 部署**

```bash
docker compose up -d --build backend
docker compose restart celery celery-beat
```

- [ ] **Step 4: 冒烟验证**

Run: `docker compose exec backend python manage.py shell -c "from apps.sales.tasks import check_delivery_reminders; print(check_delivery_reminders())"`
Expected: 返回字符串(无异常);若当日有到期单且责任人填了 `wechat_work_id`,对应人收到企微个人消息,其余走群播。

---

## Self-Review

- **Spec coverage:** 7 类事件全部覆盖(Task 2 审批待办+结果、Task 3 销售交期、Task 4 采购到货、Task 5 项目截止、Task 6 项目任务、Task 7 售后);helper(Task 1)实现「个人优先+群播兜底」;财务/库存明确不在本批(spec 第 9 节)。✓
- **Placeholder scan:** 无 TBD;每个 task 含真实改造代码、真实测试、真实 Docker 命令。✓
- **Type consistency:** `send_targeted_reminders(personal_messages, title, group_safe_content, has_unassigned=False)` 在 Task 1 定义,Task 2-7 调用签名一致;各纯函数返回 `(list[(user, str)], bool)` 一致。✓
- **风险:** Task 6 改动面最大(需加 `assignee_objs` 旁路映射),已在步骤中明确三处插入点。
