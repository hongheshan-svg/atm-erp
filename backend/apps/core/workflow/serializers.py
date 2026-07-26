"""
Workflow serializers.
"""

from rest_framework import serializers

from .models import WorkflowDefinition, WorkflowEvent, WorkflowInstance, WorkflowStep, WorkflowTask


class WorkflowStepSerializer(serializers.ModelSerializer):
    """Serializer for WorkflowStep."""

    approver_type_display = serializers.CharField(source='get_approver_type_display', read_only=True)
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)
    approver_user_name = serializers.CharField(source='approver_user.get_full_name', read_only=True)
    approver_role_name = serializers.CharField(source='approver_role.name', read_only=True)
    cc_users_detail = serializers.SerializerMethodField(read_only=True)
    cc_roles_detail = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = WorkflowStep
        fields = [
            'id',
            'workflow',
            'step_order',
            'name',
            'approver_type',
            'approver_type_display',
            'approver_user',
            'approver_user_name',
            'approver_role',
            'approver_role_name',
            'action_type',
            'action_type_display',
            'timeout_hours',
            'skip_amount_threshold',
            'cc_users',
            'cc_users_detail',
            'cc_roles',
            'cc_roles_detail',
            'can_reject',
            'created_at',
            'updated_at',
        ]

    def validate(self, attrs):
        errors = {}
        workflow = attrs.get('workflow') or getattr(self.instance, 'workflow', None)
        if workflow and workflow.is_active:
            errors['workflow'] = '已发布的审批流程不可修改，请先停用流程'
        elif workflow and workflow.instances.filter(is_deleted=False).exists():
            errors['workflow'] = '已有审批实例的流程步骤不可修改，请创建新流程版本'

        step_order = attrs.get('step_order', getattr(self.instance, 'step_order', None))
        if step_order is None or step_order < 1:
            errors['step_order'] = '步骤顺序必须大于等于 1'

        timeout_hours = attrs.get('timeout_hours', getattr(self.instance, 'timeout_hours', None))
        if timeout_hours is None or timeout_hours <= 0:
            errors['timeout_hours'] = '超时时间必须大于 0'

        skip_threshold = attrs.get(
            'skip_amount_threshold',
            getattr(self.instance, 'skip_amount_threshold', None),
        )
        if skip_threshold is not None and skip_threshold < 0:
            errors['skip_amount_threshold'] = '跳过金额阈值不能小于 0'

        approver_type = attrs.get('approver_type', getattr(self.instance, 'approver_type', None))
        approver_user = attrs.get('approver_user', getattr(self.instance, 'approver_user', None))
        approver_role = attrs.get('approver_role', getattr(self.instance, 'approver_role', None))
        if approver_type == 'USER' and not approver_user:
            errors['approver_user'] = '指定用户审批必须配置审批人'
        if approver_type == 'ROLE' and not approver_role:
            errors['approver_role'] = '指定角色审批必须配置审批角色'

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def get_cc_users_detail(self, obj) -> list[dict]:
        return [{'id': u.id, 'name': u.get_full_name() or u.username} for u in obj.cc_users.all()]

    def get_cc_roles_detail(self, obj) -> list[dict]:
        return [{'id': r.id, 'name': r.name} for r in obj.cc_roles.all()]


class WorkflowDefinitionSerializer(serializers.ModelSerializer):
    """Serializer for WorkflowDefinition."""

    business_type_display = serializers.CharField(source='get_business_type_display', read_only=True)
    steps = WorkflowStepSerializer(many=True, read_only=True)

    class Meta:
        model = WorkflowDefinition
        fields = [
            'id',
            'name',
            'code',
            'business_type',
            'business_type_display',
            'description',
            'is_active',
            'amount_threshold',
            'steps',
            'created_at',
            'updated_at',
        ]

    def validate(self, attrs):
        errors = {}
        is_active = attrs.get('is_active', getattr(self.instance, 'is_active', False))
        if self.instance is None and is_active:
            attrs['is_active'] = False
            is_active = False
        elif is_active and not self.instance.steps.filter(is_deleted=False).exists():
            errors['is_active'] = '流程至少配置一个有效审批步骤后才能发布'

        if self.instance:
            route_fields = ('code', 'business_type', 'amount_threshold')
            changed_routes = [
                field for field in route_fields if field in attrs and attrs[field] != getattr(self.instance, field)
            ]
            if self.instance.is_active and changed_routes:
                errors.update({field: '已发布流程的路由不可修改，请先停用流程' for field in changed_routes})

            if self.instance.instances.filter(is_deleted=False).exists():
                historical_fields = ('name', 'code', 'business_type', 'amount_threshold', 'description')
                changed_history = [
                    field
                    for field in historical_fields
                    if field in attrs and attrs[field] != getattr(self.instance, field)
                ]
                errors.update({field: '已有审批实例的流程定义不可修改，请创建新流程版本' for field in changed_history})

        if is_active:
            business_type = attrs.get('business_type', self.instance.business_type)
            threshold = attrs.get('amount_threshold', self.instance.amount_threshold)
            conflicts = WorkflowDefinition.objects.filter(
                business_type=business_type,
                is_active=True,
                is_deleted=False,
            ).exclude(pk=self.instance.pk)
            if threshold is None:
                conflicts = conflicts.filter(amount_threshold__isnull=True)
            else:
                conflicts = conflicts.filter(amount_threshold=threshold)
            if conflicts.exists():
                errors['is_active'] = '相同业务类型和金额门槛已有已发布流程'

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class WorkflowTaskSerializer(serializers.ModelSerializer):
    """Serializer for WorkflowTask."""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    step_name = serializers.CharField(source='step.name', read_only=True)
    step_order = serializers.IntegerField(source='step.step_order', read_only=True)
    assignee_name = serializers.CharField(source='assignee.get_full_name', read_only=True)
    business_no = serializers.CharField(source='instance.business_no', read_only=True)
    business_id = serializers.IntegerField(source='instance.business_id', read_only=True)
    business_type = serializers.CharField(source='instance.business_type', read_only=True)
    business_type_display = serializers.CharField(source='instance.workflow.get_business_type_display', read_only=True)
    workflow_name = serializers.CharField(source='instance.workflow.name', read_only=True)
    submitter_name = serializers.CharField(source='instance.submitter.get_full_name', read_only=True)
    amount = serializers.DecimalField(source='instance.amount', max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = WorkflowTask
        fields = [
            'id',
            'instance',
            'step',
            'step_name',
            'step_order',
            'assignee',
            'assignee_name',
            'status',
            'status_display',
            'action_time',
            'comment',
            'deadline',
            'business_no',
            'business_id',
            'business_type',
            'business_type_display',
            'workflow_name',
            'submitter_name',
            'amount',
            'created_at',
            'updated_at',
        ]


class WorkflowEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)

    class Meta:
        model = WorkflowEvent
        fields = [
            'id',
            'task',
            'actor',
            'actor_name',
            'event_type',
            'event_type_display',
            'from_status',
            'to_status',
            'comment',
            'metadata',
            'created_at',
        ]
        read_only_fields = fields


class WorkflowInstanceSerializer(serializers.ModelSerializer):
    """Serializer for WorkflowInstance."""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    workflow_name = serializers.CharField(source='workflow.name', read_only=True)
    business_type_display = serializers.CharField(source='workflow.get_business_type_display', read_only=True)
    submitter_name = serializers.CharField(source='submitter.get_full_name', read_only=True)
    tasks = WorkflowTaskSerializer(many=True, read_only=True)
    events = WorkflowEventSerializer(many=True, read_only=True)
    total_steps = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowInstance
        fields = [
            'id',
            'workflow',
            'workflow_name',
            'business_type',
            'business_type_display',
            'business_id',
            'business_no',
            'submitter',
            'submitter_name',
            'submit_time',
            'status',
            'status_display',
            'current_step',
            'total_steps',
            'amount',
            'completed_at',
            'tasks',
            'events',
            'created_at',
            'updated_at',
        ]

    def get_total_steps(self, obj) -> int:
        return obj.workflow.steps.filter(is_deleted=False).count()
