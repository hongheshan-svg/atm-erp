"""
编码规则序列化器
"""
from rest_framework import serializers
from .code_rule_models import CodeRule, CodeHistory


class CodeRuleSerializer(serializers.ModelSerializer):
    """编码规则序列化器"""
    rule_type_display = serializers.CharField(source='get_rule_type_display', read_only=True)
    reset_mode_display = serializers.CharField(source='get_reset_mode_display', read_only=True)
    
    class Meta:
        model = CodeRule
        fields = [
            'id', 'rule_type', 'rule_type_display', 'rule_name', 'prefix',
            'date_format', 'seq_length', 'seq_start', 'current_seq',
            'reset_mode', 'reset_mode_display', 'separator', 'example',
            'is_active', 'description', 'last_reset_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['example', 'last_reset_date', 'created_at', 'updated_at']
    
    def validate_prefix(self, value):
        """验证前缀"""
        if value and len(value) > 20:
            raise serializers.ValidationError('前缀长度不能超过20个字符')
        return value
    
    def validate_seq_length(self, value):
        """验证序列号长度"""
        if value < 1 or value > 10:
            raise serializers.ValidationError('序列号长度必须在1-10之间')
        return value
    
    def validate_date_format(self, value):
        """验证日期格式"""
        if value:
            allowed_tokens = ['YYYY', 'YY', 'MM', 'DD']
            # 简单验证是否只包含允许的标记
            import re
            remaining = value
            for token in allowed_tokens:
                remaining = remaining.replace(token, '')
            # 移除可能的分隔符
            remaining = re.sub(r'[-_/.]', '', remaining)
            if remaining:
                raise serializers.ValidationError(
                    f'日期格式只能包含: {", ".join(allowed_tokens)} 以及分隔符'
                )
        return value


class CodeHistorySerializer(serializers.ModelSerializer):
    """编码历史序列化器"""
    rule_name = serializers.CharField(source='rule.rule_name', read_only=True)
    rule_type_display = serializers.CharField(source='rule.get_rule_type_display', read_only=True)
    generated_by_name = serializers.CharField(source='generated_by.username', read_only=True)
    
    class Meta:
        model = CodeHistory
        fields = [
            'id', 'rule', 'rule_name', 'rule_type_display',
            'generated_code', 'sequence_number', 'generated_by',
            'generated_by_name', 'generated_at', 'business_model', 'business_id'
        ]
        read_only_fields = ['generated_at']

