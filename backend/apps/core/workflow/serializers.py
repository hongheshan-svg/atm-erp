"""
Workflow serializers.
"""

from rest_framework import serializers

from .models import WorkflowDefinition, WorkflowInstance, WorkflowStep, WorkflowTask


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

    def get_cc_users_detail(self, obj):
        return [{'id': u.id, 'name': u.get_full_name() or u.username} for u in obj.cc_users.all()]

    def get_cc_roles_detail(self, obj):
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


class WorkflowInstanceSerializer(serializers.ModelSerializer):
    """Serializer for WorkflowInstance."""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    workflow_name = serializers.CharField(source='workflow.name', read_only=True)
    business_type_display = serializers.CharField(source='workflow.get_business_type_display', read_only=True)
    submitter_name = serializers.CharField(source='submitter.get_full_name', read_only=True)
    tasks = WorkflowTaskSerializer(many=True, read_only=True)
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
            'created_at',
            'updated_at',
        ]

    def get_total_steps(self, obj):
        return obj.workflow.steps.filter(is_deleted=False).count()
