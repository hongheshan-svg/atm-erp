"""
邮件通知模板管理
Email Notification Template Management
"""

import re

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.template import Context, Template
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel


class EmailTemplate(BaseModel):
    """
    邮件模板
    """

    TEMPLATE_TYPES = [
        ('APPROVAL_PENDING', '审批待处理'),
        ('APPROVAL_APPROVED', '审批通过'),
        ('APPROVAL_REJECTED', '审批驳回'),
        ('ORDER_CREATED', '订单创建'),
        ('ORDER_SHIPPED', '订单发货'),
        ('PAYMENT_RECEIVED', '收款确认'),
        ('PAYMENT_REMINDER', '付款提醒'),
        ('CONTRACT_EXPIRY', '合同到期'),
        ('PROJECT_STATUS', '项目状态变更'),
        ('TASK_ASSIGNED', '任务分配'),
        ('MAINTENANCE_DUE', '设备维保到期'),
        ('SYSTEM_ALERT', '系统告警'),
        ('WELCOME', '欢迎邮件'),
        ('PASSWORD_RESET', '密码重置'),
        ('CUSTOM', '自定义'),
    ]

    code = models.CharField(max_length=50, unique=True, verbose_name='模板编码')
    name = models.CharField(max_length=100, verbose_name='模板名称')
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES, default='CUSTOM', verbose_name='模板类型')
    subject = models.CharField(max_length=200, verbose_name='邮件主题')
    body_html = models.TextField(verbose_name='HTML内容')
    body_text = models.TextField(blank=True, verbose_name='纯文本内容')
    variables = models.JSONField(default=list, blank=True, verbose_name='可用变量', help_text='模板中可使用的变量列表')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')
    is_system = models.BooleanField(default=False, verbose_name='系统模板')
    description = models.TextField(blank=True, verbose_name='模板说明')

    class Meta:
        db_table = 'core_email_template'
        verbose_name = '邮件模板'
        verbose_name_plural = verbose_name
        ordering = ['template_type', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'

    def render(self, context_data: dict) -> tuple:
        """
        渲染模板
        返回 (subject, html_body, text_body)
        """
        # 渲染主题
        subject_template = Template(self.subject)
        rendered_subject = subject_template.render(Context(context_data))

        # 渲染HTML内容
        html_template = Template(self.body_html)
        rendered_html = html_template.render(Context(context_data))

        # 渲染纯文本内容
        text_body = ''
        if self.body_text:
            text_template = Template(self.body_text)
            text_body = text_template.render(Context(context_data))

        return rendered_subject, rendered_html, text_body

    def extract_variables(self) -> list:
        """从模板内容中提取变量"""
        # 匹配 {{ variable }} 格式
        pattern = r'\{\{\s*(\w+(?:\.\w+)*)\s*\}\}'
        all_vars = set()

        for text in [self.subject, self.body_html, self.body_text]:
            if text:
                matches = re.findall(pattern, text)
                all_vars.update(matches)

        return list(all_vars)


class EmailLog(BaseModel):
    """
    邮件发送日志
    """

    STATUS_CHOICES = [
        ('PENDING', '待发送'),
        ('SENT', '已发送'),
        ('FAILED', '发送失败'),
    ]

    template = models.ForeignKey(
        EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs', verbose_name='邮件模板'
    )
    recipient_email = models.EmailField(verbose_name='收件人邮箱')
    recipient_name = models.CharField(max_length=100, blank=True, verbose_name='收件人名称')
    subject = models.CharField(max_length=200, verbose_name='邮件主题')
    body_html = models.TextField(verbose_name='HTML内容')
    body_text = models.TextField(blank=True, verbose_name='纯文本内容')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='发送状态')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    context_data = models.JSONField(default=dict, blank=True, verbose_name='上下文数据')

    class Meta:
        db_table = 'core_email_log'
        verbose_name = '邮件日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.recipient_email} - {self.subject}'


# =====================
# Serializers
# =====================


class EmailTemplateSerializer(serializers.ModelSerializer):
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    extracted_variables = serializers.SerializerMethodField()

    class Meta:
        model = EmailTemplate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

    def get_extracted_variables(self, obj):
        return obj.extract_variables()


class EmailTemplateListSerializer(serializers.ModelSerializer):
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)

    class Meta:
        model = EmailTemplate
        fields = [
            'id',
            'code',
            'name',
            'template_type',
            'template_type_display',
            'subject',
            'is_enabled',
            'is_system',
            'created_at',
        ]


class EmailLogSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = EmailLog
        fields = '__all__'


# =====================
# Email Service
# =====================


class EmailService:
    """邮件服务"""

    @staticmethod
    def send_by_template(
        template_code: str, recipient_email: str, context_data: dict, recipient_name: str = '', created_by=None
    ) -> EmailLog:
        """
        使用模板发送邮件
        """
        from django.utils import timezone

        try:
            template = EmailTemplate.objects.get(code=template_code, is_enabled=True, is_deleted=False)
        except EmailTemplate.DoesNotExist:
            # 模板不存在，记录错误日志
            log = EmailLog.objects.create(
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                subject=f'Template not found: {template_code}',
                body_html='',
                status='FAILED',
                error_message=f'邮件模板 {template_code} 不存在或已禁用',
                context_data=context_data,
                created_by=created_by,
            )
            return log

        # 渲染模板
        subject, html_body, text_body = template.render(context_data)

        # 创建日志记录
        log = EmailLog.objects.create(
            template=template,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
            body_html=html_body,
            body_text=text_body,
            status='PENDING',
            context_data=context_data,
            created_by=created_by,
        )

        # 尝试发送邮件
        try:
            send_mail(
                subject=subject,
                message=text_body or '',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                html_message=html_body,
                fail_silently=False,
            )
            log.status = 'SENT'
            log.sent_at = timezone.now()
            log.save()
        except Exception as e:
            log.status = 'FAILED'
            log.error_message = str(e)
            log.save()

        return log

    @staticmethod
    def send_direct(
        recipient_email: str,
        subject: str,
        body_html: str,
        body_text: str = '',
        recipient_name: str = '',
        created_by=None,
    ) -> EmailLog:
        """
        直接发送邮件（不使用模板）
        """
        from django.utils import timezone

        log = EmailLog.objects.create(
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            status='PENDING',
            created_by=created_by,
        )

        try:
            send_mail(
                subject=subject,
                message=body_text or '',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                html_message=body_html,
                fail_silently=False,
            )
            log.status = 'SENT'
            log.sent_at = timezone.now()
            log.save()
        except Exception as e:
            log.status = 'FAILED'
            log.error_message = str(e)
            log.save()

        return log


# =====================
# ViewSets
# =====================


class EmailTemplateViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """
    邮件模板管理
    """

    queryset = EmailTemplate.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['template_type', 'is_enabled', 'is_system']
    search_fields = ['code', 'name', 'subject', 'description']
    ordering_fields = ['template_type', 'code', 'name']

    def get_serializer_class(self):
        if self.action == 'list':
            return EmailTemplateListSerializer
        return EmailTemplateSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_system:
            return Response({'error': '系统模板不能删除'}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def toggle_enable(self, request, pk=None):
        """切换启用状态"""
        instance = self.get_object()
        instance.is_enabled = not instance.is_enabled
        instance.save()
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """预览模板渲染结果"""
        instance = self.get_object()
        context_data = request.data.get('context', {})

        try:
            subject, html_body, text_body = instance.render(context_data)
            return Response(
                {
                    'subject': subject,
                    'html_body': html_body,
                    'text_body': text_body,
                    'variables_used': instance.extract_variables(),
                }
            )
        except Exception as e:
            return Response({'error': f'模板渲染失败: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def test_send(self, request, pk=None):
        """发送测试邮件"""
        instance = self.get_object()
        recipient_email = request.data.get('email')
        context_data = request.data.get('context', {})

        if not recipient_email:
            return Response({'error': '请提供收件人邮箱'}, status=status.HTTP_400_BAD_REQUEST)

        log = EmailService.send_by_template(
            template_code=instance.code,
            recipient_email=recipient_email,
            context_data=context_data,
            created_by=request.user,
        )

        return Response({'status': log.status, 'message': '发送成功' if log.status == 'SENT' else log.error_message})

    @action(detail=False, methods=['get'])
    def template_types(self, request):
        """获取所有模板类型"""
        return Response([{'value': choice[0], 'label': choice[1]} for choice in EmailTemplate.TEMPLATE_TYPES])

    @action(detail=False, methods=['post'])
    def init_system_templates(self, request):
        """初始化系统模板"""
        if not request.user.is_superuser:
            return Response({'error': '仅超级管理员可执行此操作'}, status=403)

        base_style = """
<style>
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }
.container { max-width: 600px; margin: 0 auto; padding: 20px; }
.header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
.content { background: #fff; padding: 30px; border: 1px solid #e0e0e0; }
.footer { background: #f5f5f5; padding: 15px; text-align: center; font-size: 12px; color: #888; border-radius: 0 0 8px 8px; }
.btn { display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 15px 0; }
.info-table { width: 100%; border-collapse: collapse; margin: 15px 0; }
.info-table td { padding: 10px; border-bottom: 1px solid #eee; }
.info-table td:first-child { font-weight: bold; width: 120px; color: #666; }
</style>
"""

        system_templates = [
            {
                'code': 'APPROVAL_PENDING',
                'name': '审批待处理通知',
                'template_type': 'APPROVAL_PENDING',
                'subject': '[待审批] {{ title }}',
                'body_html': f"""
{base_style}
<div class="container">
    <div class="header">
        <h1>⏳ 审批通知</h1>
    </div>
    <div class="content">
        <p>尊敬的 {{{{ recipient_name }}}}：</p>
        <p>您有一个新的审批待处理：</p>
        <table class="info-table">
            <tr><td>审批类型</td><td>{{{{ approval_type }}}}</td></tr>
            <tr><td>标题</td><td>{{{{ title }}}}</td></tr>
            <tr><td>申请人</td><td>{{{{ applicant }}}}</td></tr>
            <tr><td>申请时间</td><td>{{{{ apply_time }}}}</td></tr>
        </table>
        <p>请及时登录系统处理。</p>
        <a href="{{{{ link }}}}" class="btn">立即处理</a>
    </div>
    <div class="footer">
        此邮件由系统自动发送，请勿回复
    </div>
</div>
""",
                'variables': ['recipient_name', 'approval_type', 'title', 'applicant', 'apply_time', 'link'],
            },
            {
                'code': 'APPROVAL_APPROVED',
                'name': '审批通过通知',
                'template_type': 'APPROVAL_APPROVED',
                'subject': '[已通过] {{ title }}',
                'body_html': f"""
{base_style}
<div class="container">
    <div class="header" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);">
        <h1>✅ 审批通过</h1>
    </div>
    <div class="content">
        <p>尊敬的 {{{{ recipient_name }}}}：</p>
        <p>您提交的申请已审批通过：</p>
        <table class="info-table">
            <tr><td>审批类型</td><td>{{{{ approval_type }}}}</td></tr>
            <tr><td>标题</td><td>{{{{ title }}}}</td></tr>
            <tr><td>审批人</td><td>{{{{ approver }}}}</td></tr>
            <tr><td>审批时间</td><td>{{{{ approve_time }}}}</td></tr>
            <tr><td>审批意见</td><td>{{{{ comments }}}}</td></tr>
        </table>
        <a href="{{{{ link }}}}" class="btn" style="background: #11998e;">查看详情</a>
    </div>
    <div class="footer">
        此邮件由系统自动发送，请勿回复
    </div>
</div>
""",
                'variables': [
                    'recipient_name',
                    'approval_type',
                    'title',
                    'approver',
                    'approve_time',
                    'comments',
                    'link',
                ],
            },
            {
                'code': 'PAYMENT_REMINDER',
                'name': '付款提醒',
                'template_type': 'PAYMENT_REMINDER',
                'subject': '[付款提醒] {{ customer_name }} - {{ contract_no }}',
                'body_html': f"""
{base_style}
<div class="container">
    <div class="header" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
        <h1>💰 付款提醒</h1>
    </div>
    <div class="content">
        <p>尊敬的 {{{{ recipient_name }}}}：</p>
        <p>以下付款即将到期，请及时跟进：</p>
        <table class="info-table">
            <tr><td>客户名称</td><td>{{{{ customer_name }}}}</td></tr>
            <tr><td>合同编号</td><td>{{{{ contract_no }}}}</td></tr>
            <tr><td>应付金额</td><td style="color: #f5576c; font-weight: bold;">¥{{{{ amount }}}}</td></tr>
            <tr><td>到期日期</td><td>{{{{ due_date }}}}</td></tr>
            <tr><td>距今天数</td><td>{{{{ days_left }}}} 天</td></tr>
        </table>
        <a href="{{{{ link }}}}" class="btn" style="background: #f5576c;">查看详情</a>
    </div>
    <div class="footer">
        此邮件由系统自动发送，请勿回复
    </div>
</div>
""",
                'variables': [
                    'recipient_name',
                    'customer_name',
                    'contract_no',
                    'amount',
                    'due_date',
                    'days_left',
                    'link',
                ],
            },
        ]

        created_count = 0
        for tpl_data in system_templates:
            _, created = EmailTemplate.objects.update_or_create(
                code=tpl_data['code'],
                defaults={
                    'name': tpl_data['name'],
                    'template_type': tpl_data['template_type'],
                    'subject': tpl_data['subject'],
                    'body_html': tpl_data['body_html'],
                    'variables': tpl_data['variables'],
                    'is_system': True,
                    'created_by': request.user,
                },
            )
            if created:
                created_count += 1

        return Response({'message': f'初始化完成，创建了 {created_count} 个新模板'})


class EmailLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    邮件日志（只读）
    """

    queryset = EmailLog.objects.all()
    serializer_class = EmailLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'template']
    search_fields = ['recipient_email', 'recipient_name', 'subject']
    ordering_fields = ['created_at', 'sent_at']

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """邮件发送统计"""
        from datetime import timedelta

        from django.db.models import Count
        from django.utils import timezone

        today = timezone.now().date()
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)

        total = self.get_queryset().count()
        total_sent = self.get_queryset().filter(status='SENT').count()
        total_failed = self.get_queryset().filter(status='FAILED').count()

        today_count = self.get_queryset().filter(created_at__date=today).count()

        last_7_days_count = self.get_queryset().filter(created_at__date__gte=last_7_days).count()

        last_30_days_count = self.get_queryset().filter(created_at__date__gte=last_30_days).count()

        by_template = self.get_queryset().values('template__name').annotate(count=Count('id')).order_by('-count')[:10]

        return Response(
            {
                'total': total,
                'total_sent': total_sent,
                'total_failed': total_failed,
                'success_rate': round(total_sent / total * 100, 2) if total > 0 else 0,
                'today': today_count,
                'last_7_days': last_7_days_count,
                'last_30_days': last_30_days_count,
                'by_template': list(by_template),
            }
        )

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """重试发送失败的邮件"""
        log = self.get_object()
        if log.status != 'FAILED':
            return Response({'error': '只能重试发送失败的邮件'}, status=status.HTTP_400_BAD_REQUEST)

        from django.utils import timezone

        try:
            send_mail(
                subject=log.subject,
                message=log.body_text or '',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[log.recipient_email],
                html_message=log.body_html,
                fail_silently=False,
            )
            log.status = 'SENT'
            log.sent_at = timezone.now()
            log.error_message = ''
            log.save()
            return Response({'message': '发送成功'})
        except Exception as e:
            log.error_message = str(e)
            log.save()
            return Response({'error': f'发送失败: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
