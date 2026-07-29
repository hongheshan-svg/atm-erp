"""
Workflow service for managing approval processes.
"""

import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import WorkflowDefinition, WorkflowEvent, WorkflowInstance, WorkflowTask

logger = logging.getLogger(__name__)


class WorkflowConfigurationError(Exception):
    """Raised when a published workflow cannot safely create its next task."""


class WorkflowService:
    """
    Service class for workflow operations.
    """

    @classmethod
    def get_workflow_for_business(cls, business_type, amount=None):
        """
        Get the appropriate workflow definition for a business type and amount.
        """
        workflows = WorkflowDefinition.objects.filter(business_type=business_type, is_active=True, is_deleted=False)

        if amount is None:
            return workflows.filter(amount_threshold__isnull=True).order_by('-id').first()

        return (
            workflows.filter(Q(amount_threshold__isnull=True) | Q(amount_threshold__lte=amount))
            .order_by(F('amount_threshold').desc(nulls_last=True), '-id')
            .first()
        )

    @staticmethod
    def is_missing_workflow_error(error):
        return bool(error and error.startswith('未找到适用于 '))

    @classmethod
    def start_workflow(cls, business_type, business_id, business_no, submitter, amount=None):
        """
        Start a new workflow instance for a business object.

        Returns:
            tuple: (WorkflowInstance, error_message)
        """
        workflow = cls.get_workflow_for_business(business_type, amount)

        if not workflow:
            return None, f'未找到适用于 {business_type} 的审批流程'

        if not workflow.steps.filter(is_deleted=False).exists():
            return None, '审批流程没有审批步骤，无法启动'

        try:
            with transaction.atomic():
                existing = (
                    WorkflowInstance.objects.select_for_update()
                    .filter(business_type=business_type, business_id=business_id, status='PENDING', is_deleted=False)
                    .first()
                )

                if existing:
                    return None, '该单据已有进行中的审批流程'

                instance = WorkflowInstance.objects.create(
                    workflow=workflow,
                    business_type=business_type,
                    business_id=business_id,
                    business_no=business_no,
                    submitter=submitter,
                    amount=amount,
                    status='PENDING',
                    current_step=1,
                    created_by=submitter,
                )
                cls._create_next_task(instance)
                cls._record_event(
                    instance,
                    'STARTED',
                    submitter,
                    from_status='',
                    to_status=instance.status,
                    metadata={'business_type': business_type, 'business_id': business_id},
                )
        except WorkflowConfigurationError as exc:
            return None, str(exc)
        except IntegrityError:
            if WorkflowInstance.objects.filter(
                business_type=business_type,
                business_id=business_id,
                status='PENDING',
                is_deleted=False,
            ).exists():
                return None, '该单据已有进行中的审批流程'
            raise

        return instance, None

    @classmethod
    def _create_next_task(cls, instance):
        """
        Create the next approval task for the workflow instance.
        """
        steps = instance.workflow.steps.filter(is_deleted=False).order_by('step_order')

        current_step = None
        for step in steps:
            if step.step_order >= instance.current_step:
                # Check if step should be skipped based on amount
                if step.skip_amount_threshold is not None and instance.amount is not None:
                    if instance.amount < step.skip_amount_threshold:
                        continue
                current_step = step
                break

        if not current_step:
            # No more steps, workflow is complete
            instance.status = 'APPROVED'
            instance.completed_at = timezone.now()
            instance.save()
            cls._on_workflow_complete(instance, 'APPROVED')
            return None

        # Determine assignee(s). A COUNTERSIGN (会签) or OR_SIGN (或签) step
        # resolves to MULTIPLE assignees (e.g. every active user of a role);
        # every other action type keeps the single-approver behavior (exactly
        # one assignee).
        assignees = cls._get_step_assignees(current_step, instance)

        if not assignees:
            raise WorkflowConfigurationError(f'步骤“{current_step.name}”无法确定审批人，流程未启动')

        # Calculate deadline
        deadline = timezone.now() + timedelta(hours=current_step.timeout_hours)

        # Create one PENDING task per resolved assignee. For a single-approver
        # step this is exactly one task (unchanged); for a COUNTERSIGN or
        # OR_SIGN step it fans out to one concurrent task per candidate approver.
        tasks = []
        for assignee in assignees:
            task = WorkflowTask.objects.create(
                instance=instance,
                step=current_step,
                assignee=assignee,
                status='PENDING',
                deadline=deadline,
                created_by=instance.submitter,
            )
            transaction.on_commit(lambda task=task: cls._notify_assignee(task))
            tasks.append(task)

        # Return the first task for backward compatibility with callers.
        return tasks[0] if tasks else None

    @classmethod
    def _get_step_assignees(cls, step, instance):
        """
        Resolve the list of assignees for a workflow step.

        For a multi-assignee step whose approver is a ROLE — COUNTERSIGN (会签,
        all must approve) or OR_SIGN (或签, any one suffices) — this returns
        EVERY active user holding that role, so the engine can create one
        concurrent approval task per candidate approver. In every other case it
        returns a single-element list using the standard single-assignee
        resolution, preserving the legacy single-approver behavior.

        Note: explicit multi-user countersign/or-sign is not representable today
        because WorkflowStep only carries a single ``approver_user`` FK; ROLE
        membership is the supported multi-assignee source (see residual risk /
        follow-up).
        """
        from apps.accounts.models import User

        if step.action_type in ('COUNTERSIGN', 'OR_SIGN') and step.approver_type == 'ROLE' and step.approver_role:
            users = list(
                User.objects.filter(
                    roles=step.approver_role,
                    is_active=True,
                    is_deleted=False,
                ).distinct()
            )
            if users:
                return users
            # Role has no members -> fall back to single-assignee resolution below.

        assignee = cls._get_step_assignee(step, instance)
        return [assignee] if assignee else []

    @classmethod
    def _get_step_assignee(cls, step, instance):
        """
        Determine the assignee for a workflow step.
        Falls back to approver_role if dynamic assignee is not found.
        """
        from apps.accounts.models import User

        assignee = None

        if step.approver_type == 'USER':
            assignee = step.approver_user

        elif step.approver_type == 'ROLE':
            if step.approver_role:
                # Get first active user with this role
                assignee = User.objects.filter(roles=step.approver_role, is_active=True, is_deleted=False).first()

        elif step.approver_type == 'DEPARTMENT_MANAGER':
            # Get submitter's department manager
            if instance.submitter.department and instance.submitter.department.manager:
                assignee = instance.submitter.department.manager

        elif step.approver_type == 'PROJECT_MANAGER':
            # Get project manager from business object
            assignee = cls._get_project_manager(instance)

        elif step.approver_type == 'SUPERIOR':
            # Get submitter's superior (department manager or higher)
            if instance.submitter.department and instance.submitter.department.manager:
                assignee = instance.submitter.department.manager

        # 职责分离:当动态解析出的审批人恰是提交人本人(如部门经理自己发起本部门单据),
        # 上溯到上级部门经理,避免自审自签(审计 batch1 #5)。上溯是「尽力路由」:仅当
        # 找到有效上级时才替换审批人;找不到则保留原审批人,让单据仍能进入审批流,
        # 由 approve_task 的强制门(提交人非超管不得审批自己的单据)兜底,绝不能因上溯失败
        # 把审批人置空导致 start_workflow 抛「无法确定审批人」而使提交 500。
        if assignee and assignee.id == instance.submitter_id:
            superior = cls._escalate_to_superior(instance.submitter)
            if superior is not None:
                assignee = superior

        if assignee and (not assignee.is_active or getattr(assignee, 'is_deleted', False)):
            assignee = None

        # Fallback to approver_role if no assignee found
        if not assignee and step.approver_role:
            assignee = User.objects.filter(roles=step.approver_role, is_active=True, is_deleted=False).first()

        # 兜底解析出的审批人仍可能==提交人,再尽力上溯一次(职责分离,审计 batch1 #5;
        # 同样非破坏:找不到上级则保留)。
        if assignee and assignee.id == instance.submitter_id:
            superior = cls._escalate_to_superior(instance.submitter)
            if superior is not None:
                assignee = superior

        return assignee

    @classmethod
    def _escalate_to_superior(cls, submitter):
        """沿部门树上溯,返回第一个不是提交人本人的上级部门经理(职责分离)。

        提交人是本部门经理时,其审批应由上级部门经理处理;逐级上溯,找不到(已到顶或无经理)
        返回 None,由 approve_task 的强制门确保提交人无论如何不能审批自己的单据。
        """
        dept = getattr(submitter, 'department', None)
        seen = set()
        while dept is not None and dept.id not in seen:
            seen.add(dept.id)
            manager = getattr(dept, 'manager', None)
            if (
                manager
                and manager.id != submitter.id
                and manager.is_active
                and not getattr(manager, 'is_deleted', False)
            ):
                return manager
            dept = getattr(dept, 'parent', None)
        return None

    @classmethod
    def _get_project_manager(cls, instance):
        """
        Get project manager from the business object.
        Returns None if no project manager is associated.
        """
        try:
            if instance.business_type == 'PURCHASE_REQUEST':
                from apps.purchase.models import PurchaseRequest

                pr = PurchaseRequest.objects.get(id=instance.business_id)
                if pr.project:
                    return pr.project.manager

            elif instance.business_type == 'PURCHASE_ORDER':
                from apps.purchase.models import PurchaseOrder

                po = PurchaseOrder.objects.get(id=instance.business_id)
                if hasattr(po, 'project') and po.project:
                    return po.project.manager

            elif instance.business_type == 'EXPENSE':
                from apps.finance.models import Expense

                expense = Expense.objects.get(id=instance.business_id)
                if expense.project:
                    return expense.project.manager

            elif instance.business_type == 'PAYMENT':
                from apps.finance.models import PaymentRequest

                payment_req = PaymentRequest.objects.get(id=instance.business_id)
                if payment_req.project:
                    return payment_req.project.manager

            elif instance.business_type == 'QUOTATION':
                from apps.sales.models import SalesQuotation

                quot = SalesQuotation.objects.get(id=instance.business_id)
                if hasattr(quot, 'project') and quot.project:
                    return quot.project.manager

            elif instance.business_type == 'SALES_ORDER':
                from apps.sales.models import SalesOrder

                so = SalesOrder.objects.get(id=instance.business_id)
                if hasattr(so, 'project') and so.project:
                    return so.project.manager

            elif instance.business_type == 'SALES_CONTRACT':
                from apps.sales.models import SalesContract

                contract = SalesContract.objects.get(id=instance.business_id)
                if hasattr(contract, 'project') and contract.project:
                    return contract.project.manager

            elif instance.business_type == 'DELIVERY_ORDER':
                from apps.sales.models import DeliveryOrder

                delivery = DeliveryOrder.objects.get(id=instance.business_id)
                if delivery.so and hasattr(delivery.so, 'project') and delivery.so.project:
                    return delivery.so.project.manager

            elif instance.business_type == 'PROJECT':
                from apps.projects.models import Project

                project = Project.objects.get(id=instance.business_id)
                return project.manager

            elif instance.business_type == 'STOCK_ADJUSTMENT':
                # 库存调整没有项目经理，返回None
                return None

            elif instance.business_type == 'ECN':
                from apps.projects.models import ECN

                ecn = ECN.objects.get(id=instance.business_id)
                if ecn.project:
                    return ecn.project.manager

            elif instance.business_type == 'PURCHASE_CONTRACT':
                from apps.purchase.models import PurchaseContract

                contract = PurchaseContract.objects.get(id=instance.business_id)
                if contract.project:
                    return contract.project.manager

            elif instance.business_type in ['CONTRACT_EXECUTION', 'PAYMENT_RECORD']:
                from apps.purchase.contract_execution import ContractExecution

                if instance.business_type == 'CONTRACT_EXECUTION':
                    execution = ContractExecution.objects.get(id=instance.business_id)
                else:
                    from apps.purchase.contract_execution import PaymentRecord

                    payment = PaymentRecord.objects.get(id=instance.business_id)
                    execution = payment.execution
                if execution.contract and execution.contract.project:
                    return execution.contract.project.manager

            # 外协/售后/OA模块没有项目经理
            elif instance.business_type in [
                'OUTSOURCE_MATERIAL_ISSUE',
                'OUTSOURCE_RECEIPT',
                'SERVICE_REQUEST',
                'LEAVE_REQUEST',
                'OVERTIME_REQUEST',
                'VEHICLE_REQUEST',
                'ASSET_BORROW',
            ]:
                return None

        except Exception as e:
            logger.error(f'Error getting project manager: {e}')

        return None

    @classmethod
    def approve_task(cls, task, user, comment='', skip_assignee_check=False):
        """
        Approve a workflow task.

        Args:
            skip_assignee_check: Deprecated compatibility argument. Assignment
                remains authoritative for non-superusers.

        For a COUNTERSIGN (会签) step the instance advances to the next step
        only once EVERY sibling task of the step is approved; an approval that
        still leaves pending countersigners returns success but keeps the
        instance on the current step.

        For an OR_SIGN (或签) step the FIRST approval satisfies the step: it
        advances the instance and auto-closes (marks SKIPPED) the sibling
        PENDING tasks so they don't linger. The instance-row lock plus the
        refresh_from_db re-check serialize concurrent approvals so only the
        first one advances.
        """
        try:
            with transaction.atomic():
                instance = WorkflowInstance.objects.select_for_update().get(id=task.instance_id)
                task = WorkflowTask.objects.select_related('step', 'assignee').get(id=task.id)

                if instance.status != 'PENDING':
                    return False, '该审批流程已结束'
                if task.status != 'PENDING':
                    return False, '该任务已处理'
                if task.assignee != user and not user.is_superuser:
                    return False, '您没有权限处理此任务'
                # 职责分离:提交人不得审批自己提交的单据,即使被解析成了审批人
                # (_get_step_assignee 已对部门经理/上级做 escalate,这里是纵深防御,
                #  兜住 ROLE/USER 步骤恰好把审批人配成提交人本人的情形)。审计 batch1 #5。
                if instance.submitter_id == user.id and not user.is_superuser:
                    return False, '提交人不能审批自己提交的单据(职责分离)'

                task.status = 'APPROVED'
                task.action_time = timezone.now()
                task.comment = comment
                task.updated_by = user
                task.save()

                step = task.step
                if step.action_type == 'COUNTERSIGN':
                    has_pending_sibling = instance.tasks.filter(
                        step=step,
                        status='PENDING',
                        is_deleted=False,
                    ).exists()
                    if has_pending_sibling:
                        cls._record_event(
                            instance,
                            'APPROVED',
                            user,
                            task=task,
                            from_status='PENDING',
                            to_status='PENDING',
                            comment=comment,
                        )
                        return True, '会签通过，等待其他会签人审批'
                elif step.action_type == 'OR_SIGN':
                    instance.tasks.filter(
                        step=step,
                        status='PENDING',
                        is_deleted=False,
                    ).exclude(id=task.id).update(
                        status='SKIPPED',
                        action_time=timezone.now(),
                    )

                instance.current_step = step.step_order + 1
                instance.updated_by = user
                instance.save()
                cls._create_next_task(instance)
                cls._record_event(
                    instance,
                    'APPROVED',
                    user,
                    task=task,
                    from_status='PENDING',
                    to_status=instance.status,
                    comment=comment,
                )
                transaction.on_commit(lambda step=step, instance=instance: cls._notify_cc(step, instance, 'APPROVED'))
        except WorkflowConfigurationError as exc:
            return False, f'审批流程配置错误：{exc}'
        except Exception:
            logger.exception('Workflow approval rolled back because business synchronization failed')
            return False, '业务状态同步失败，审批操作已回滚'

        return True, '审批通过'

    @classmethod
    def reject_task(cls, task, user, comment='', skip_assignee_check=False):
        """
        Reject a workflow task.

        Args:
            skip_assignee_check: Deprecated compatibility argument. Assignment
                remains authoritative for non-superusers.

        For a single-approver step, or a COUNTERSIGN (会签) step, a single
        rejection rejects the whole instance: any one countersigner's rejection
        fails the step, and the remaining pending sibling tasks are cancelled
        (marked SKIPPED).

        For an OR_SIGN (或签) step the semantics are the mirror image: a single
        rejection does NOT fail the step while other approvers can still
        approve. Only that one task is marked REJECTED and its sibling PENDING
        tasks are left untouched. The instance is rejected only once EVERY
        assignee has rejected — i.e. when the last PENDING sibling is rejected
        and no pending sibling remains.
        """
        try:
            with transaction.atomic():
                instance = WorkflowInstance.objects.select_for_update().get(id=task.instance_id)
                task = WorkflowTask.objects.select_related('step', 'assignee').get(id=task.id)

                if instance.status != 'PENDING':
                    return False, '该审批流程已结束'
                if task.status != 'PENDING':
                    return False, '该任务已处理'
                if task.assignee != user and not user.is_superuser:
                    return False, '您没有权限处理此任务'
                if not task.step.can_reject:
                    return False, '当前审批步骤不允许拒绝'

                task.status = 'REJECTED'
                task.action_time = timezone.now()
                task.comment = comment
                task.updated_by = user
                task.save()

                step = task.step
                if step.action_type == 'OR_SIGN':
                    has_pending_sibling = instance.tasks.filter(
                        step=step,
                        status='PENDING',
                        is_deleted=False,
                    ).exists()
                    if has_pending_sibling:
                        cls._record_event(
                            instance,
                            'REJECTED',
                            user,
                            task=task,
                            from_status='PENDING',
                            to_status='PENDING',
                            comment=comment,
                        )
                        return True, '已拒绝，等待其他审批人处理'

                instance.tasks.filter(
                    status='PENDING',
                    is_deleted=False,
                ).exclude(id=task.id).update(
                    status='SKIPPED',
                    action_time=timezone.now(),
                )
                instance.status = 'REJECTED'
                instance.completed_at = timezone.now()
                instance.updated_by = user
                instance.save()
                cls._on_workflow_complete(instance, 'REJECTED')
                cls._record_event(
                    instance,
                    'REJECTED',
                    user,
                    task=task,
                    from_status='PENDING',
                    to_status='REJECTED',
                    comment=comment,
                )
                transaction.on_commit(lambda step=step, instance=instance: cls._notify_cc(step, instance, 'REJECTED'))
        except Exception:
            logger.exception('Workflow rejection rolled back because business synchronization failed')
            return False, '业务状态同步失败，拒绝操作已回滚'

        return True, '已拒绝'

    @classmethod
    def reject_to_step(cls, task, target_step_order, user, comment='', skip_assignee_check=False):
        """
        Return (退回) an approval task to an EARLIER step instead of rejecting
        the whole instance.

        Contrast with :meth:`reject_task`, which fails the entire instance
        (``status='REJECTED'``, workflow ends). ``reject_to_step`` keeps the
        instance IN PROGRESS (``status`` stays ``'PENDING'``) and merely rewinds
        ``instance.current_step`` back to an earlier real step so that step is
        re-approved:

          * the current task is marked ``RETURNED`` with the comment;
          * any still-pending sibling tasks of the current step (the other
            countersigners / or-signers) are cancelled (``SKIPPED``) so they do
            not linger after the rewind;
          * fresh task(s) for the target step are created via the normal
            ``_create_next_task`` assignee resolution, exactly as if the flow had
            just arrived at that step.

        Args:
            target_step_order: the ``step_order`` to rewind to. Must be a real,
                non-deleted step of the instance's workflow, ``>= 1`` and
                strictly earlier than the task's current step (you can only send
                a document backward, never sideways or forward).
            skip_assignee_check: deprecated compatibility argument. Assignment
                remains authoritative for non-superusers.

        Returns:
            tuple: (success: bool, message: str)
        """
        # Validate the target step number up front (cheap guards before locking).
        try:
            target_step_order = int(target_step_order)
        except (TypeError, ValueError):
            return False, '退回目标步骤无效'

        if target_step_order < 1:
            return False, '退回目标步骤无效'

        with transaction.atomic():
            # Lock the instance so a concurrent approve/reject cannot advance or
            # fail the step while we rewind it (same discipline as countersign).
            instance = WorkflowInstance.objects.select_for_update().get(id=task.instance_id)
            task = WorkflowTask.objects.select_related('step', 'assignee').get(id=task.id)

            # Only an in-progress instance can be returned.
            if instance.status != 'PENDING':
                return False, '该审批流程已结束，无法退回'

            if task.status != 'PENDING':
                return False, '该任务已处理'
            if task.assignee != user and not user.is_superuser:
                return False, '您没有权限处理此任务'
            if not task.step.can_reject:
                return False, '当前审批步骤不允许退回'

            current_order = task.step.step_order
            if target_step_order >= current_order:
                return False, '只能退回到当前步骤之前的步骤'

            target_step = instance.workflow.steps.filter(
                step_order=target_step_order,
                is_deleted=False,
            ).first()
            if not target_step:
                return False, '退回目标步骤不存在'

            # Mark the current task RETURNED (not REJECTED — the instance lives on).
            task.status = 'RETURNED'
            task.action_time = timezone.now()
            task.comment = comment
            task.updated_by = user
            task.save()

            # Cancel any still-pending sibling tasks (e.g. the other
            # countersigners / or-signers of this step) so they don't linger
            # after the rewind. Only current-step tasks are ever PENDING, so a
            # broad PENDING filter is safe and mirrors reject_task.
            instance.tasks.filter(
                status='PENDING',
                is_deleted=False,
            ).exclude(id=task.id).update(
                status='SKIPPED',
                action_time=timezone.now(),
            )

            # Rewind to the target step; the instance stays IN PROGRESS
            # (status PENDING, NOT REJECTED) and re-creates that step's task(s).
            instance.current_step = target_step_order
            instance.updated_by = user
            instance.save()

            cls._create_next_task(instance)
            cls._record_event(
                instance,
                'RETURNED',
                user,
                task=task,
                from_status='PENDING',
                to_status='PENDING',
                comment=comment,
                metadata={'target_step_order': target_step_order},
            )
            transaction.on_commit(lambda: cls._notify_cc(task.step, instance, 'RETURNED'))

        return True, f'已退回至第 {target_step_order} 步'

    @classmethod
    def withdraw_workflow(cls, instance, user):
        """
        Withdraw a workflow instance (by submitter).
        """
        try:
            with transaction.atomic():
                instance = WorkflowInstance.objects.select_for_update().select_related('submitter').get(pk=instance.pk)
                if instance.status != 'PENDING':
                    return False, '只能撤回进行中的审批'
                if instance.submitter != user and not user.is_superuser:
                    return False, '只有提交人可以撤回'

                instance.tasks.filter(status='PENDING', is_deleted=False).update(
                    status='SKIPPED',
                    action_time=timezone.now(),
                )
                instance.status = 'WITHDRAWN'
                instance.completed_at = timezone.now()
                instance.updated_by = user
                instance.save()
                cls._on_workflow_complete(instance, 'WITHDRAWN')
                cls._record_event(
                    instance,
                    'WITHDRAWN',
                    user,
                    from_status='PENDING',
                    to_status='WITHDRAWN',
                )
        except Exception:
            logger.exception('Workflow withdrawal rolled back because business synchronization failed')
            return False, '业务状态同步失败，撤回操作已回滚'

        return True, '已撤回'

    @classmethod
    def cancel_workflow(cls, business_type, business_id, user=None):
        """Idempotently cancel the pending workflow for a business object."""
        with transaction.atomic():
            instance = (
                WorkflowInstance.objects.select_for_update()
                .filter(
                    business_type=business_type,
                    business_id=business_id,
                    is_deleted=False,
                )
                .order_by('-submit_time', '-id')
                .first()
            )
            if not instance:
                return True, '该单据没有审批流程'
            if instance.status == 'CANCELLED':
                return True, '审批流程已取消'
            if instance.status != 'PENDING':
                return False, '只能取消进行中的审批流程'

            instance.tasks.filter(status='PENDING', is_deleted=False).update(
                status='SKIPPED',
                action_time=timezone.now(),
            )
            instance.status = 'CANCELLED'
            instance.completed_at = timezone.now()
            if user is not None:
                instance.updated_by = user
            instance.save()
            cls._record_event(
                instance,
                'CANCELLED',
                user,
                from_status='PENDING',
                to_status='CANCELLED',
            )
            return True, '审批流程已取消'

    @classmethod
    def _on_workflow_complete(cls, instance, result):
        """
        Callback when workflow is completed.
        Updates the business object status.
        """
        try:
            if instance.business_type == 'PURCHASE_REQUEST':
                from apps.purchase.models import PurchaseRequest

                pr = PurchaseRequest.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    pr.status = 'APPROVED'
                    # 更新BOM状态：PR_PENDING -> PR_APPROVED
                    from apps.projects.models import ProjectBOM

                    ProjectBOM.objects.filter(purchase_request=pr, is_deleted=False, order_status='PR_PENDING').update(
                        order_status='PR_APPROVED'
                    )
                elif result == 'REJECTED':
                    pr.status = 'REJECTED'
                elif result == 'WITHDRAWN':
                    pr.status = 'DRAFT'
                pr.save()

            elif instance.business_type == 'EXPENSE':
                from apps.finance.models import Expense

                expense = Expense.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    expense.status = 'APPROVED'
                elif result == 'REJECTED':
                    expense.status = 'REJECTED'
                elif result == 'WITHDRAWN':
                    expense.status = 'DRAFT'
                expense.save()

            elif instance.business_type == 'DELIVERY_ORDER':
                from apps.sales.models import DeliveryOrder

                delivery = DeliveryOrder.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    # 审批通过，进入备货环节
                    delivery.status = 'PREPARING'
                    delivery.save()
                    logger.info(f'Delivery order {delivery.delivery_no} approved, entering PREPARING status')
                elif result == 'REJECTED':
                    delivery.status = 'REJECTED'
                    delivery.save()
                elif result == 'WITHDRAWN':
                    delivery.status = 'DRAFT'
                    delivery.save()

            elif instance.business_type == 'SALES_ORDER':
                from apps.sales.models import SalesOrder

                so = SalesOrder.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    # 与直接确认路径 (_do_confirm) 一致的信用/客户状态校验：
                    # 停用、冻结、黑名单、超额时不得确认订单，避免审批确认绕过信用管控。
                    from apps.masterdata.credit_management import check_customer_credit_for_order

                    order_amount = so.total_with_tax or so.total_amount or 0
                    passed, message = check_customer_credit_for_order(so.customer, order_amount)
                    if not passed:
                        raise RuntimeError(f'销售订单信用校验未通过：{message}')
                    else:
                        so.status = 'CONFIRMED'  # 审批通过后确认订单
                        so.save()
                        # 与直接确认路径一致：生成应收账款与付款计划，避免审批确认的订单漏记 AR
                        try:
                            from apps.sales.services import create_sales_order_receivables

                            create_sales_order_receivables(so, getattr(instance, 'submitter', None) or so.created_by)
                        except Exception as e:
                            raise RuntimeError(f'销售订单创建应收/付款计划失败：{e}') from e
                        logger.info(f'Sales order {so.order_no} approved, status changed to CONFIRMED')
                elif result == 'REJECTED':
                    so.status = 'REJECTED'
                    so.save()
                elif result == 'WITHDRAWN':
                    so.status = 'DRAFT'
                    so.save()

            elif instance.business_type == 'PROJECT':
                from apps.projects.models import Project

                project = Project.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    project.status = 'IN_PROGRESS'  # 审批通过后项目开始
                    project.save()
                    logger.info(f'Project {project.code} approved, status changed to IN_PROGRESS')
                elif result == 'REJECTED':
                    project.status = 'REJECTED'  # 审批拒绝，可重新提交
                    project.save()
                    logger.info(f'Project {project.code} rejected, status changed to REJECTED')
                elif result == 'WITHDRAWN':
                    project.status = 'DRAFT'  # 撤回后回到草稿状态
                    project.save()

            elif instance.business_type == 'STOCK_ADJUSTMENT':
                from apps.inventory.models import StockAdjustment

                adjustment = StockAdjustment.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    adjustment.status = 'APPROVED'
                    adjustment.save()
                    # 执行库存调整
                    adjustment.apply_adjustment()
                    logger.info(f'Stock adjustment {adjustment.id} approved and applied')
                elif result == 'REJECTED':
                    adjustment.status = 'REJECTED'
                    adjustment.save()
                elif result == 'WITHDRAWN':
                    adjustment.status = 'DRAFT'
                    adjustment.save()

            elif instance.business_type == 'ECN':
                from apps.projects.models import ECN, ECNApproval

                ecn = ECN.objects.get(id=instance.business_id)

                # 获取最后一个审批任务的审批人（而非提交人）
                last_task = instance.tasks.filter(status__in=['APPROVED', 'REJECTED']).order_by('-action_time').first()
                approver = last_task.assignee if last_task else instance.submitter

                if result == 'APPROVED':
                    ecn.status = 'APPROVED'
                    ecn.approved_date = timezone.now().date()
                    ecn.save()
                    # 记录审批历史
                    ECNApproval.objects.create(
                        ecn=ecn, approver=approver, action='APPROVE', comment='审批流程通过', created_by=approver
                    )
                    logger.info(f'ECN {ecn.ecn_no} approved via workflow')
                elif result == 'REJECTED':
                    ecn.status = 'REJECTED'
                    ecn.save()
                    ECNApproval.objects.create(
                        ecn=ecn, approver=approver, action='REJECT', comment='审批流程拒绝', created_by=approver
                    )
                elif result == 'WITHDRAWN':
                    ecn.status = 'DRAFT'
                    ecn.save()

            # ============ 新增业务类型处理 ============

            elif instance.business_type == 'PURCHASE_ORDER':
                from apps.purchase.models import PurchaseOrder

                po = PurchaseOrder.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    po.status = 'APPROVED'
                    po.save()
                    logger.info(f'Purchase order {po.order_no} approved, waiting for confirmation')
                elif result == 'REJECTED':
                    po.status = 'REJECTED'
                    po.save()
                elif result == 'WITHDRAWN':
                    po.status = 'DRAFT'
                    po.save()

            elif instance.business_type == 'QUOTATION':
                from apps.sales.models import SalesQuotation

                quot = SalesQuotation.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    quot.status = 'APPROVED'
                    quot.save()
                    logger.info(f'Quotation {quot.quote_no} approved')
                elif result == 'REJECTED':
                    quot.status = 'REJECTED'
                    quot.save()
                elif result == 'WITHDRAWN':
                    quot.status = 'DRAFT'
                    quot.save()

            elif instance.business_type == 'SALES_CONTRACT':
                from apps.sales.models import SalesContract

                contract = SalesContract.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    contract.status = 'APPROVED'  # 审批通过
                    contract.save()
                    logger.info(f'Sales contract {contract.contract_no} approved')
                elif result == 'REJECTED':
                    contract.status = 'REJECTED'
                    contract.save()
                elif result == 'WITHDRAWN':
                    contract.status = 'DRAFT'
                    contract.save()

            elif instance.business_type == 'PAYMENT':
                from apps.finance.models import PaymentRequest

                payment_req = PaymentRequest.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    payment_req.status = 'APPROVED'
                    payment_req.save()
                    logger.info(f'Payment request {payment_req.request_no} approved')
                elif result == 'REJECTED':
                    payment_req.status = 'REJECTED'
                    payment_req.save()
                elif result == 'WITHDRAWN':
                    payment_req.status = 'DRAFT'
                    payment_req.save()

            elif instance.business_type == 'LEAVE_REQUEST':
                from apps.accounts.attendance import LeaveRequest

                leave = LeaveRequest.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    leave.status = 'APPROVED'
                    leave.save()
                    logger.info(f'Leave request {leave.id} approved')
                elif result == 'REJECTED':
                    leave.status = 'REJECTED'
                    leave.save()
                elif result == 'WITHDRAWN':
                    leave.status = 'DRAFT'
                    leave.save()

            elif instance.business_type == 'OVERTIME_REQUEST':
                from apps.accounts.attendance import OvertimeRequest

                overtime = OvertimeRequest.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    overtime.status = 'APPROVED'
                    overtime.save()
                    logger.info(f'Overtime request {overtime.id} approved')
                elif result == 'REJECTED':
                    overtime.status = 'REJECTED'
                    overtime.save()
                elif result == 'WITHDRAWN':
                    overtime.status = 'DRAFT'
                    overtime.save()

            elif instance.business_type == 'VEHICLE_REQUEST':
                from apps.oa.vehicle import VehicleRequest

                vehicle_req = VehicleRequest.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    vehicle_req.status = 'APPROVED'
                    vehicle_req.save()
                    logger.info(f'Vehicle request {vehicle_req.id} approved')
                elif result == 'REJECTED':
                    vehicle_req.status = 'REJECTED'
                    vehicle_req.save()
                elif result == 'WITHDRAWN':
                    vehicle_req.status = 'PENDING'
                    vehicle_req.save()

            elif instance.business_type == 'ASSET_BORROW':
                from apps.oa.asset import AssetBorrow

                borrow = AssetBorrow.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    borrow.status = 'APPROVED'
                    borrow.save()
                    logger.info(f'Asset borrow {borrow.id} approved')
                elif result == 'REJECTED':
                    borrow.status = 'REJECTED'
                    borrow.save()
                elif result == 'WITHDRAWN':
                    borrow.status = 'PENDING'
                    borrow.save()

            elif instance.business_type == 'PURCHASE_CONTRACT':
                from apps.purchase.models import PurchaseContract

                contract = PurchaseContract.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    contract.status = 'APPROVED'
                    contract.save()
                    logger.info(f'Purchase contract {contract.contract_no} approved')
                elif result == 'REJECTED':
                    contract.status = 'REJECTED'
                    contract.save()
                elif result == 'WITHDRAWN':
                    contract.status = 'DRAFT'
                    contract.save()

            elif instance.business_type == 'OUTSOURCE_MATERIAL_ISSUE':
                from apps.purchase.outsource_models import OutsourceMaterialIssue

                issue = OutsourceMaterialIssue.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    issue.status = 'CONFIRMED'
                    issue.save()
                    logger.info(f'Outsource material issue {issue.issue_no} approved')
                elif result in ('REJECTED', 'WITHDRAWN'):
                    issue.status = 'DRAFT'
                    issue.save()

            elif instance.business_type == 'OUTSOURCE_RECEIPT':
                from apps.purchase.outsource_models import OutsourceReceipt

                receipt = OutsourceReceipt.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    receipt.status = 'CONFIRMED'
                    receipt.save()
                    logger.info(f'Outsource receipt {receipt.receipt_no} approved')
                elif result in ('REJECTED', 'WITHDRAWN'):
                    receipt.status = 'DRAFT'
                    receipt.save()

            elif instance.business_type == 'CONTRACT_EXECUTION':
                from apps.purchase.contract_execution import ContractExecution

                execution = ContractExecution.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    execution.status = 'IN_PROGRESS'
                    if not execution.actual_start_date:
                        from datetime import date

                        execution.actual_start_date = date.today()
                    execution.save()
                    logger.info(f'Contract execution {execution.id} approved, now IN_PROGRESS')
                elif result in ('REJECTED', 'WITHDRAWN'):
                    execution.status = 'NOT_STARTED'
                    execution.save()

            elif instance.business_type == 'PAYMENT_RECORD':
                from apps.purchase.contract_execution import PaymentRecord

                payment = PaymentRecord.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    payment.status = 'APPROVED'
                    payment.approved_at = timezone.now()
                    payment.save()
                    logger.info(f'Payment record {payment.payment_no} approved')
                elif result == 'REJECTED':
                    payment.status = 'CANCELLED'
                    payment.save()
                elif result == 'WITHDRAWN':
                    payment.status = 'PENDING'
                    payment.save()

            elif instance.business_type == 'SERVICE_REQUEST':
                from apps.sales.after_sales_service import ServiceRequest

                sr = ServiceRequest.objects.get(id=instance.business_id)
                if result == 'APPROVED':
                    sr.status = 'ACKNOWLEDGED'
                    sr.acknowledged_at = timezone.now()
                    sr.save()
                    logger.info(f'Service request {sr.request_no} approved/acknowledged')
                elif result in ('REJECTED', 'WITHDRAWN'):
                    sr.status = 'NEW'
                    sr.save()

            transaction.on_commit(lambda instance=instance, result=result: cls._notify_submitter(instance, result))

        except Exception as e:
            logger.exception('Error updating business object: %s', e)
            raise

    @classmethod
    def _notify_assignee(cls, task):
        """
        Send notification to task assignee.
        """
        from apps.core.models import SystemNotification
        from apps.core.notification_service import NotificationService

        try:
            # Create system notification
            SystemNotification.objects.create(
                user=task.assignee,
                type='INFO',
                title='您有新的审批任务',
                message=f'单据 {task.instance.business_no} 等待您审批。',
            )

            # Send external notification (DingTalk/WeChat)
            NotificationService.send_approval_notification(task)

        except Exception as e:
            logger.error(f'Error sending notification: {e}')

    @classmethod
    def _notify_submitter(cls, instance, result):
        """
        Notify submitter about workflow result.
        """
        from apps.core.models import SystemNotification
        from apps.core.notification_service import NotificationService

        result_text = {'APPROVED': '已通过', 'REJECTED': '已拒绝', 'WITHDRAWN': '已撤回'}.get(result, result)

        try:
            SystemNotification.objects.create(
                user=instance.submitter,
                type='SUCCESS' if result == 'APPROVED' else 'WARNING',
                title=f'审批{result_text}',
                message=f'您提交的单据 {instance.business_no} {result_text}。',
            )

            # Send external notification
            NotificationService.send_workflow_result_notification(instance, result)

        except Exception as e:
            logger.error(f'Error sending notification: {e}')

    @classmethod
    def _notify_cc(cls, step, instance, result):
        """Notify configured CC users once the surrounding transaction commits."""
        from apps.accounts.models import User
        from apps.core.models import SystemNotification

        role_ids = list(step.cc_roles.values_list('id', flat=True))
        user_ids = list(step.cc_users.values_list('id', flat=True))
        recipients = User.objects.filter(
            Q(id__in=user_ids) | Q(roles__id__in=role_ids),
            is_active=True,
            is_deleted=False,
        ).distinct()
        result_text = {'APPROVED': '通过', 'REJECTED': '拒绝', 'RETURNED': '退回'}.get(result, result)
        for recipient in recipients:
            SystemNotification.objects.create(
                user=recipient,
                type='INFO',
                title='审批步骤已完成',
                message=f'单据 {instance.business_no} 的步骤“{step.name}”已{result_text}。',
            )

    @classmethod
    def get_pending_tasks(cls, user):
        """
        Get all pending tasks for a user.
        """
        return (
            WorkflowTask.objects.filter(assignee=user, status='PENDING', is_deleted=False)
            # WorkflowTaskSerializer 还会读 assignee.get_full_name 与
            # instance.submitter.get_full_name，不预取则每条任务各多两次查询
            .select_related('instance', 'instance__workflow', 'instance__submitter', 'step', 'assignee')
            .order_by('-created_at')
        )

    @classmethod
    def get_submitted_workflows(cls, user):
        """
        Get all workflows submitted by a user.
        """
        return (
            WorkflowInstance.objects.filter(submitter=user, is_deleted=False)
            .select_related('workflow')
            .order_by('-submit_time')
        )

    @classmethod
    def get_workflow_history(cls, business_type, business_id):
        """
        Get workflow history for a business object.
        """
        return (
            WorkflowInstance.objects.filter(business_type=business_type, business_id=business_id, is_deleted=False)
            .prefetch_related('tasks', 'tasks__assignee', 'tasks__step')
            .order_by('-submit_time')
        )

    @classmethod
    def _record_event(
        cls,
        instance,
        event_type,
        actor,
        *,
        task=None,
        from_status='',
        to_status='',
        comment='',
        metadata=None,
    ):
        return WorkflowEvent.objects.create(
            instance=instance,
            task=task,
            actor=actor,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            comment=comment,
            metadata=metadata or {},
        )
