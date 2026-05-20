"""
Bug跟踪系统序列化器
"""
from django.utils import timezone
from rest_framework import serializers

from .bug_models import Bug, BugAttachment, BugComment, BugHistory


class BugAttachmentSerializer(serializers.ModelSerializer):
    """Bug附件序列化器"""
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = BugAttachment
        fields = [
            'id', 'bug', 'file', 'filename', 'file_size',
            'uploaded_by', 'uploaded_by_name', 'created_at'
        ]
        read_only_fields = ['uploaded_by', 'file_size', 'created_at']

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return f"{obj.uploaded_by.last_name}{obj.uploaded_by.first_name}" or obj.uploaded_by.username
        return ''

    def create(self, validated_data):
        validated_data['uploaded_by'] = self.context['request'].user
        if 'file' in validated_data:
            validated_data['file_size'] = validated_data['file'].size
            if not validated_data.get('filename'):
                validated_data['filename'] = validated_data['file'].name
        return super().create(validated_data)


class BugCommentSerializer(serializers.ModelSerializer):
    """Bug评论序列化器"""
    user_name = serializers.SerializerMethodField()
    user_avatar = serializers.SerializerMethodField()

    class Meta:
        model = BugComment
        fields = [
            'id', 'bug', 'user', 'user_name', 'user_avatar',
            'content', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        if obj.user:
            name = f"{obj.user.last_name}{obj.user.first_name}"
            return name if name else obj.user.username
        return ''

    def get_user_avatar(self, obj):
        if obj.user and obj.user.avatar:
            return obj.user.avatar.url
        return None

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class BugHistorySerializer(serializers.ModelSerializer):
    """Bug变更历史序列化器"""
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = BugHistory
        fields = [
            'id', 'bug', 'user', 'user_name',
            'field_name', 'field_label', 'old_value', 'new_value',
            'created_at'
        ]
        read_only_fields = ['created_at']

    def get_user_name(self, obj):
        if obj.user:
            name = f"{obj.user.last_name}{obj.user.first_name}"
            return name if name else obj.user.username
        return ''


class BugListSerializer(serializers.ModelSerializer):
    """Bug列表序列化器（简化版）"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    task_name = serializers.CharField(source='task.name', read_only=True)
    reporter_name = serializers.SerializerMethodField()
    assignee_name = serializers.SerializerMethodField()
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    bug_type_display = serializers.CharField(source='get_bug_type_display', read_only=True)
    comment_count = serializers.SerializerMethodField()
    attachment_count = serializers.SerializerMethodField()

    class Meta:
        model = Bug
        fields = [
            'id', 'bug_number', 'title', 'project', 'project_name',
            'task', 'task_name', 'module',
            'severity', 'severity_display',
            'priority', 'priority_display',
            'status', 'status_display',
            'bug_type', 'bug_type_display',
            'reporter', 'reporter_name',
            'assignee', 'assignee_name',
            'comment_count', 'attachment_count',
            'created_at', 'updated_at'
        ]

    def get_reporter_name(self, obj):
        if obj.reporter:
            name = f"{obj.reporter.last_name}{obj.reporter.first_name}"
            return name if name else obj.reporter.username
        return ''

    def get_assignee_name(self, obj):
        if obj.assignee:
            name = f"{obj.assignee.last_name}{obj.assignee.first_name}"
            return name if name else obj.assignee.username
        return ''

    def get_comment_count(self, obj):
        return obj.comments.count()

    def get_attachment_count(self, obj):
        return obj.attachments.count()


class BugDetailSerializer(serializers.ModelSerializer):
    """Bug详情序列化器（完整版）"""
    project_name = serializers.CharField(source='project.name', read_only=True)
    task_name = serializers.CharField(source='task.name', read_only=True)
    reporter_name = serializers.SerializerMethodField()
    assignee_name = serializers.SerializerMethodField()
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    bug_type_display = serializers.CharField(source='get_bug_type_display', read_only=True)
    resolution_display = serializers.CharField(source='get_resolution_display', read_only=True)
    comments = BugCommentSerializer(many=True, read_only=True)
    attachments = BugAttachmentSerializer(many=True, read_only=True)
    histories = BugHistorySerializer(many=True, read_only=True)
    duplicate_of_number = serializers.CharField(source='duplicate_of.bug_number', read_only=True)

    class Meta:
        model = Bug
        fields = [
            'id', 'bug_number', 'title', 'description',
            'project', 'project_name', 'task', 'task_name', 'module',
            'severity', 'severity_display',
            'priority', 'priority_display',
            'status', 'status_display',
            'bug_type', 'bug_type_display',
            'reporter', 'reporter_name',
            'assignee', 'assignee_name',
            'resolution', 'resolution_display', 'solution',
            'resolved_at', 'closed_at',
            'environment', 'version',
            'duplicate_of', 'duplicate_of_number',
            'comments', 'attachments', 'histories',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['bug_number', 'reporter', 'resolved_at', 'closed_at', 'created_at', 'updated_at']

    def get_reporter_name(self, obj):
        if obj.reporter:
            name = f"{obj.reporter.last_name}{obj.reporter.first_name}"
            return name if name else obj.reporter.username
        return ''

    def get_assignee_name(self, obj):
        if obj.assignee:
            name = f"{obj.assignee.last_name}{obj.assignee.first_name}"
            return name if name else obj.assignee.username
        return ''


class BugCreateUpdateSerializer(serializers.ModelSerializer):
    """Bug创建/更新序列化器"""

    class Meta:
        model = Bug
        fields = [
            'title', 'description', 'project', 'task', 'module',
            'severity', 'priority', 'bug_type', 'status',
            'assignee', 'resolution', 'solution',
            'environment', 'version', 'duplicate_of'
        ]

    def create(self, validated_data):
        validated_data['reporter'] = self.context['request'].user
        bug = super().create(validated_data)

        # 记录创建历史
        BugHistory.objects.create(
            bug=bug,
            user=self.context['request'].user,
            field_name='status',
            field_label='状态',
            old_value='',
            new_value='新建'
        )

        return bug

    def update(self, instance, validated_data):
        user = self.context['request'].user

        # 记录字段变更
        field_labels = {
            'title': '标题',
            'description': '描述',
            'severity': '严重程度',
            'priority': '优先级',
            'status': '状态',
            'bug_type': 'Bug类型',
            'assignee': '处理人',
            'resolution': '解决方式',
            'solution': '解决说明',
            'module': '模块',
            'environment': '环境',
            'version': '版本',
        }

        for field, label in field_labels.items():
            if field in validated_data:
                old_value = getattr(instance, field)
                new_value = validated_data[field]

                if old_value != new_value:
                    # 转换显示值
                    if field == 'assignee':
                        old_display = f"{old_value.last_name}{old_value.first_name}" if old_value else '未分配'
                        new_display = f"{new_value.last_name}{new_value.first_name}" if new_value else '未分配'
                    elif hasattr(instance, f'get_{field}_display'):
                        old_display = dict(getattr(Bug, f'{field.upper()}_CHOICES', [])).get(old_value, old_value) if old_value else ''
                        new_display = dict(getattr(Bug, f'{field.upper()}_CHOICES', [])).get(new_value, new_value) if new_value else ''
                    else:
                        old_display = str(old_value) if old_value else ''
                        new_display = str(new_value) if new_value else ''

                    BugHistory.objects.create(
                        bug=instance,
                        user=user,
                        field_name=field,
                        field_label=label,
                        old_value=old_display,
                        new_value=new_display
                    )

        # 状态变更时更新时间
        if 'status' in validated_data:
            new_status = validated_data['status']
            if new_status == 'RESOLVED' and instance.status != 'RESOLVED':
                validated_data['resolved_at'] = timezone.now()
            elif new_status == 'CLOSED' and instance.status != 'CLOSED':
                validated_data['closed_at'] = timezone.now()

        return super().update(instance, validated_data)


class BugStatisticsSerializer(serializers.Serializer):
    """Bug统计序列化器"""
    total = serializers.IntegerField()
    by_status = serializers.DictField()
    by_severity = serializers.DictField()
    by_priority = serializers.DictField()
    open_count = serializers.IntegerField()
    closed_count = serializers.IntegerField()
    resolved_today = serializers.IntegerField()
    created_today = serializers.IntegerField()

