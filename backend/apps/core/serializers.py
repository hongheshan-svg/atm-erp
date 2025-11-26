"""
Serializers for core app.
"""
from rest_framework import serializers
from .models import AuditLog, SystemNotification, Attachment


class AuditLogSerializer(serializers.ModelSerializer):
    """审计日志序列化器"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'action', 'action_display',
            'model_name', 'object_id', 'object_repr', 'changes',
            'ip_address', 'timestamp'
        ]
        read_only_fields = fields


class SystemNotificationSerializer(serializers.ModelSerializer):
    """系统通知序列化器"""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    class Meta:
        model = SystemNotification
        fields = [
            'id', 'user', 'type', 'type_display', 'title', 'message',
            'is_read', 'created_at', 'read_at'
        ]
        read_only_fields = ['id', 'created_at', 'read_at']


class AttachmentSerializer(serializers.ModelSerializer):
    """附件序列化器"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Attachment
        fields = [
            'id', 'related_model', 'related_id', 'file', 'file_url',
            'original_name', 'file_size', 'file_size_display', 'file_type',
            'category', 'category_display', 'description',
            'uploaded_by', 'uploaded_by_name', 'uploaded_at'
        ]
        read_only_fields = ['id', 'file_size', 'file_type', 'uploaded_by', 'uploaded_at']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None
    
    def get_file_size_display(self, obj):
        """将文件大小转换为人类可读格式"""
        size = obj.file_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"


class AttachmentUploadSerializer(serializers.Serializer):
    """附件上传序列化器"""
    file = serializers.FileField()
    related_model = serializers.CharField(max_length=100)
    related_id = serializers.IntegerField()
    category = serializers.ChoiceField(choices=Attachment.CATEGORY_CHOICES, default='OTHER')
    description = serializers.CharField(required=False, allow_blank=True, default='')
    
    def create(self, validated_data):
        file = validated_data['file']
        attachment = Attachment.objects.create(
            file=file,
            original_name=file.name,
            related_model=validated_data['related_model'],
            related_id=validated_data['related_id'],
            category=validated_data.get('category', 'OTHER'),
            description=validated_data.get('description', ''),
            uploaded_by=self.context['request'].user
        )
        return attachment

