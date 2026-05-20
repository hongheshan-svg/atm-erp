"""
合同模板管理
Contract Template Management
支持销售合同、采购合同等多种合同模板配置和生成
"""

from datetime import datetime
from decimal import Decimal

from django.db import models
from django.template import Context, Template
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel


class ContractTemplate(BaseModel):
    """
    合同模板
    """

    CONTRACT_TYPES = [
        ('SALES', '销售合同'),
        ('PURCHASE', '采购合同'),
        ('SERVICE', '服务合同'),
        ('NDA', '保密协议'),
        ('FRAMEWORK', '框架协议'),
        ('OUTSOURCE', '外协加工合同'),
        ('MAINTENANCE', '维保合同'),
        ('OTHER', '其他'),
    ]

    TEMPLATE_FORMATS = [
        ('WORD', 'Word文档'),
        ('HTML', 'HTML模板'),
        ('PDF', 'PDF模板'),
    ]

    code = models.CharField(max_length=50, unique=True, verbose_name='模板编码')
    name = models.CharField(max_length=200, verbose_name='模板名称')
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPES, default='SALES', verbose_name='合同类型')
    format = models.CharField(max_length=20, choices=TEMPLATE_FORMATS, default='HTML', verbose_name='模板格式')
    template_file = models.FileField(upload_to='templates/contracts/', blank=True, null=True, verbose_name='模板文件')
    html_content = models.TextField(blank=True, verbose_name='HTML模板内容')

    # 合同条款配置
    party_a_config = models.JSONField(default=dict, blank=True, verbose_name='甲方信息配置')
    party_b_config = models.JSONField(default=dict, blank=True, verbose_name='乙方信息配置')
    terms_config = models.JSONField(default=list, blank=True, verbose_name='合同条款配置')
    payment_terms = models.JSONField(default=list, blank=True, verbose_name='付款条款')
    warranty_terms = models.JSONField(default=dict, blank=True, verbose_name='质保条款')

    # 可用变量
    available_variables = models.JSONField(default=list, blank=True, verbose_name='可用变量列表')

    is_default = models.BooleanField(default=False, verbose_name='默认模板')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本号')
    description = models.TextField(blank=True, verbose_name='模板说明')

    class Meta:
        db_table = 'sales_contract_template'
        verbose_name = '合同模板'
        verbose_name_plural = verbose_name
        ordering = ['contract_type', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'

    def save(self, *args, **kwargs):
        if self.is_default:
            ContractTemplate.objects.filter(contract_type=self.contract_type, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)


class ContractClause(BaseModel):
    """
    合同条款库
    """

    CLAUSE_TYPES = [
        ('GENERAL', '通用条款'),
        ('PAYMENT', '付款条款'),
        ('DELIVERY', '交付条款'),
        ('WARRANTY', '质保条款'),
        ('LIABILITY', '责任条款'),
        ('CONFIDENTIAL', '保密条款'),
        ('TERMINATION', '终止条款'),
        ('DISPUTE', '争议解决'),
        ('OTHER', '其他'),
    ]

    code = models.CharField(max_length=50, unique=True, verbose_name='条款编码')
    name = models.CharField(max_length=200, verbose_name='条款名称')
    clause_type = models.CharField(max_length=20, choices=CLAUSE_TYPES, default='GENERAL', verbose_name='条款类型')
    content = models.TextField(verbose_name='条款内容')
    is_required = models.BooleanField(default=False, verbose_name='必选条款')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    applicable_types = models.JSONField(
        default=list, blank=True, verbose_name='适用合同类型', help_text='留空表示适用所有类型'
    )

    class Meta:
        db_table = 'sales_contract_clause'
        verbose_name = '合同条款'
        verbose_name_plural = verbose_name
        ordering = ['clause_type', 'sort_order']

    def __str__(self):
        return f'{self.code} - {self.name}'


class GeneratedContract(BaseModel):
    """
    生成的合同记录
    """

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待审批'),
        ('APPROVED', '已审批'),
        ('SIGNED', '已签署'),
        ('EFFECTIVE', '已生效'),
        ('EXPIRED', '已过期'),
        ('TERMINATED', '已终止'),
    ]

    template = models.ForeignKey(
        ContractTemplate,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_contracts',
        verbose_name='使用模板',
    )
    contract_no = models.CharField(max_length=50, unique=True, verbose_name='合同编号')
    contract_name = models.CharField(max_length=200, verbose_name='合同名称')
    contract_type = models.CharField(max_length=20, choices=ContractTemplate.CONTRACT_TYPES, verbose_name='合同类型')

    # 甲方信息
    party_a_name = models.CharField(max_length=200, verbose_name='甲方名称')
    party_a_address = models.CharField(max_length=500, blank=True, verbose_name='甲方地址')
    party_a_contact = models.CharField(max_length=100, blank=True, verbose_name='甲方联系人')
    party_a_phone = models.CharField(max_length=50, blank=True, verbose_name='甲方电话')
    party_a_bank = models.CharField(max_length=200, blank=True, verbose_name='甲方开户行')
    party_a_account = models.CharField(max_length=100, blank=True, verbose_name='甲方账号')

    # 乙方信息
    party_b_name = models.CharField(max_length=200, verbose_name='乙方名称')
    party_b_address = models.CharField(max_length=500, blank=True, verbose_name='乙方地址')
    party_b_contact = models.CharField(max_length=100, blank=True, verbose_name='乙方联系人')
    party_b_phone = models.CharField(max_length=50, blank=True, verbose_name='乙方电话')
    party_b_bank = models.CharField(max_length=200, blank=True, verbose_name='乙方开户行')
    party_b_account = models.CharField(max_length=100, blank=True, verbose_name='乙方账号')

    # 合同金额
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='合同金额')
    currency = models.CharField(max_length=10, default='CNY', verbose_name='币种')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=13, verbose_name='税率(%)')

    # 日期
    sign_date = models.DateField(null=True, blank=True, verbose_name='签订日期')
    effective_date = models.DateField(null=True, blank=True, verbose_name='生效日期')
    expiry_date = models.DateField(null=True, blank=True, verbose_name='到期日期')

    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 内容
    contract_content = models.TextField(blank=True, verbose_name='合同内容')
    selected_clauses = models.JSONField(default=list, blank=True, verbose_name='选用条款')
    custom_terms = models.TextField(blank=True, verbose_name='自定义条款')

    # 附件
    generated_file = models.FileField(
        upload_to='contracts/generated/', blank=True, null=True, verbose_name='生成的文件'
    )
    signed_file = models.FileField(upload_to='contracts/signed/', blank=True, null=True, verbose_name='签署的文件')

    # 关联
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contracts_generated',
        verbose_name='关联项目',
    )
    sales_order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contracts_generated',
        verbose_name='关联销售订单',
    )

    class Meta:
        db_table = 'sales_generated_contract'
        verbose_name = '生成的合同'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.contract_no} - {self.contract_name}'


# =====================
# Contract Generation Service
# =====================


class ContractGenerationService:
    """合同生成服务"""

    def __init__(self, template: ContractTemplate):
        self.template = template

    def generate_html(self, contract_data: dict) -> str:
        """生成HTML合同"""
        if self.template.html_content:
            tpl = Template(self.template.html_content)
        else:
            tpl = Template(self._get_default_html_template())

        # 获取适用的条款
        clauses = (
            ContractClause.objects.filter(is_enabled=True, is_deleted=False)
            .filter(models.Q(applicable_types=[]) | models.Q(applicable_types__contains=[self.template.contract_type]))
            .order_by('clause_type', 'sort_order')
        )

        # 分组条款
        grouped_clauses = {}
        for clause in clauses:
            clause_type = clause.get_clause_type_display()
            if clause_type not in grouped_clauses:
                grouped_clauses[clause_type] = []
            grouped_clauses[clause_type].append(clause)

        context = Context(
            {
                'contract': contract_data,
                'template': self.template,
                'clauses': grouped_clauses,
                'generated_at': datetime.now(),
                'party_a': self.template.party_a_config or {},
                'party_b': self.template.party_b_config or {},
                'payment_terms': self.template.payment_terms or [],
                'warranty_terms': self.template.warranty_terms or {},
            }
        )

        return tpl.render(context)

    def _get_default_html_template(self) -> str:
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ contract.contract_name }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: "SimSun", "Microsoft YaHei", serif; padding: 50px; line-height: 1.8; color: #333; }
        .contract-container { max-width: 800px; margin: 0 auto; background: white; }
        .contract-header { text-align: center; margin-bottom: 40px; }
        .contract-title { font-size: 26px; font-weight: bold; letter-spacing: 8px; margin-bottom: 20px; }
        .contract-no { font-size: 14px; color: #666; }
        .section { margin-bottom: 30px; }
        .section-title { font-size: 16px; font-weight: bold; margin-bottom: 15px; padding-left: 10px; border-left: 4px solid #333; }
        .party-info { display: flex; gap: 40px; margin-bottom: 30px; }
        .party-box { flex: 1; padding: 20px; background: #f9f9f9; border-radius: 4px; }
        .party-box h4 { margin-bottom: 15px; font-size: 15px; }
        .party-box p { font-size: 14px; margin: 5px 0; }
        .party-box .label { color: #666; display: inline-block; width: 80px; }
        .article { margin-bottom: 20px; }
        .article-title { font-weight: bold; margin-bottom: 10px; }
        .article-content { text-indent: 2em; text-align: justify; }
        .amount-highlight { font-size: 18px; color: #c00; font-weight: bold; }
        .signature-area { display: flex; justify-content: space-between; margin-top: 60px; padding-top: 30px; border-top: 1px solid #ddd; }
        .signature-box { width: 45%; }
        .signature-box h4 { margin-bottom: 30px; }
        .signature-line { border-bottom: 1px solid #333; margin-bottom: 10px; padding-bottom: 40px; }
        .date-line { margin-top: 20px; }
        @media print { body { padding: 20px; } .contract-container { box-shadow: none; } }
    </style>
</head>
<body>
    <div class="contract-container">
        <div class="contract-header">
            <h1 class="contract-title">{{ contract.contract_name }}</h1>
            <p class="contract-no">合同编号：{{ contract.contract_no }}</p>
        </div>
        
        <div class="section">
            <div class="party-info">
                <div class="party-box">
                    <h4>甲方（购买方）</h4>
                    <p><span class="label">单位名称：</span>{{ contract.party_a_name }}</p>
                    <p><span class="label">地址：</span>{{ contract.party_a_address }}</p>
                    <p><span class="label">联系人：</span>{{ contract.party_a_contact }}</p>
                    <p><span class="label">电话：</span>{{ contract.party_a_phone }}</p>
                </div>
                <div class="party-box">
                    <h4>乙方（供应方）</h4>
                    <p><span class="label">单位名称：</span>{{ contract.party_b_name }}</p>
                    <p><span class="label">地址：</span>{{ contract.party_b_address }}</p>
                    <p><span class="label">联系人：</span>{{ contract.party_b_contact }}</p>
                    <p><span class="label">电话：</span>{{ contract.party_b_phone }}</p>
                </div>
            </div>
        </div>
        
        <div class="section">
            <p style="text-indent: 2em;">
                甲乙双方本着平等互利、诚实信用的原则，经友好协商，就甲方向乙方采购非标自动化设备事宜达成如下协议：
            </p>
        </div>
        
        <div class="section">
            <h3 class="section-title">第一条 合同标的</h3>
            <div class="article">
                <p class="article-content">
                    甲方向乙方采购{{ contract.project_name|default:"非标自动化设备" }}，
                    合同总金额为人民币 <span class="amount-highlight">￥{{ contract.total_amount }}</span> 元
                    （大写：{{ contract.amount_in_words|default:"" }}）。
                </p>
            </div>
        </div>
        
        <div class="section">
            <h3 class="section-title">第二条 付款方式</h3>
            {% for term in payment_terms %}
            <div class="article">
                <p class="article-content">{{ forloop.counter }}. {{ term }}</p>
            </div>
            {% empty %}
            <div class="article">
                <p class="article-content">1. 合同签订后3个工作日内，甲方向乙方支付合同总额30%作为预付款；</p>
                <p class="article-content">2. 设备发货前，甲方向乙方支付合同总额60%；</p>
                <p class="article-content">3. 设备验收合格后7个工作日内，甲方向乙方支付合同总额10%作为质保金。</p>
            </div>
            {% endfor %}
        </div>
        
        <div class="section">
            <h3 class="section-title">第三条 交货期限</h3>
            <div class="article">
                <p class="article-content">
                    乙方应在收到甲方预付款后{{ contract.delivery_days|default:"45" }}个工作日内完成设备制造并发货。
                </p>
            </div>
        </div>
        
        <div class="section">
            <h3 class="section-title">第四条 质量保证</h3>
            <div class="article">
                <p class="article-content">
                    {{ warranty_terms.content|default:"乙方保证设备符合技术协议约定的技术指标和性能要求。设备验收合格后，乙方提供12个月质保期。质保期内，因设备本身质量问题导致的故障，乙方负责免费维修或更换。" }}
                </p>
            </div>
        </div>
        
        {% for clause_type, clause_list in clauses.items %}
        <div class="section">
            <h3 class="section-title">{{ clause_type }}</h3>
            {% for clause in clause_list %}
            <div class="article">
                <p class="article-content">{{ clause.content }}</p>
            </div>
            {% endfor %}
        </div>
        {% endfor %}
        
        <div class="section">
            <h3 class="section-title">其他约定</h3>
            <div class="article">
                <p class="article-content">
                    {{ contract.custom_terms|default:"本合同一式两份，甲乙双方各执一份，具有同等法律效力。本合同自双方签字盖章之日起生效。" }}
                </p>
            </div>
        </div>
        
        <div class="signature-area">
            <div class="signature-box">
                <h4>甲方（盖章）：</h4>
                <div class="signature-line"></div>
                <p>法定代表人或授权代表：</p>
                <div class="signature-line"></div>
                <p class="date-line">日期：______年______月______日</p>
            </div>
            <div class="signature-box">
                <h4>乙方（盖章）：</h4>
                <div class="signature-line"></div>
                <p>法定代表人或授权代表：</p>
                <div class="signature-line"></div>
                <p class="date-line">日期：______年______月______日</p>
            </div>
        </div>
    </div>
</body>
</html>
"""


# =====================
# Serializers
# =====================


class ContractTemplateSerializer(serializers.ModelSerializer):
    contract_type_display = serializers.CharField(source='get_contract_type_display', read_only=True)
    format_display = serializers.CharField(source='get_format_display', read_only=True)

    class Meta:
        model = ContractTemplate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ContractTemplateListSerializer(serializers.ModelSerializer):
    contract_type_display = serializers.CharField(source='get_contract_type_display', read_only=True)
    format_display = serializers.CharField(source='get_format_display', read_only=True)

    class Meta:
        model = ContractTemplate
        fields = [
            'id',
            'code',
            'name',
            'contract_type',
            'contract_type_display',
            'format',
            'format_display',
            'is_default',
            'is_enabled',
            'version',
            'created_at',
        ]


class ContractClauseSerializer(serializers.ModelSerializer):
    clause_type_display = serializers.CharField(source='get_clause_type_display', read_only=True)

    class Meta:
        model = ContractClause
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class GeneratedContractSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    contract_type_display = serializers.CharField(source='get_contract_type_display', read_only=True)

    class Meta:
        model = GeneratedContract
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class GeneratedContractListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    contract_type_display = serializers.CharField(source='get_contract_type_display', read_only=True)

    class Meta:
        model = GeneratedContract
        fields = [
            'id',
            'contract_no',
            'contract_name',
            'contract_type',
            'contract_type_display',
            'party_a_name',
            'party_b_name',
            'total_amount',
            'status',
            'status_display',
            'sign_date',
            'effective_date',
            'expiry_date',
            'created_at',
        ]


# =====================
# ViewSets
# =====================


class ContractTemplateViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """合同模板管理"""

    queryset = ContractTemplate.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['contract_type', 'format', 'is_default', 'is_enabled']
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['contract_type', 'code', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return ContractTemplateListSerializer
        return ContractTemplateSerializer

    @action(detail=False, methods=['get'])
    def contract_types(self, request):
        """获取合同类型"""
        return Response([{'value': t[0], 'label': t[1]} for t in ContractTemplate.CONTRACT_TYPES])

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """设为默认模板"""
        instance = self.get_object()
        instance.is_default = True
        instance.save()
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """预览模板"""
        template = self.get_object()

        sample_data = {
            'contract_no': 'HT-2025-SAMPLE',
            'contract_name': '非标自动化设备采购合同',
            'party_a_name': '示例客户有限公司',
            'party_a_address': '广东省深圳市南山区科技园',
            'party_a_contact': '张先生',
            'party_a_phone': '13800138000',
            'party_b_name': '深圳市奥特迈智能装备有限公司',
            'party_b_address': '广东省深圳市宝安区新安街道',
            'party_b_contact': '李经理',
            'party_b_phone': '13900139000',
            'total_amount': '500,000.00',
            'amount_in_words': '伍拾万元整',
            'project_name': '自动化装配线',
            'delivery_days': 45,
        }

        service = ContractGenerationService(template)
        html_content = service.generate_html(sample_data)

        return Response({'html_content': html_content})

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """生成合同"""
        data = request.data
        template_id = data.get('template_id')

        if template_id:
            try:
                template = ContractTemplate.objects.get(id=template_id, is_enabled=True, is_deleted=False)
            except ContractTemplate.DoesNotExist:
                return Response({'error': '模板不存在'}, status=404)
        else:
            contract_type = data.get('contract_type', 'SALES')
            template = ContractTemplate.objects.filter(
                contract_type=contract_type, is_default=True, is_enabled=True, is_deleted=False
            ).first()

            if not template:
                template = ContractTemplate.objects.create(
                    code=f'DEFAULT_{contract_type}',
                    name=f'默认{dict(ContractTemplate.CONTRACT_TYPES).get(contract_type, "")}模板',
                    contract_type=contract_type,
                    is_default=True,
                    payment_terms=[
                        '合同签订后3个工作日内，甲方向乙方支付合同总额30%作为预付款',
                        '设备发货前，甲方向乙方支付合同总额60%',
                        '设备验收合格后7个工作日内，甲方向乙方支付合同总额10%作为质保金',
                    ],
                    warranty_terms={
                        'content': '乙方保证设备符合技术协议约定的技术指标和性能要求。设备验收合格后，乙方提供12个月质保期。'
                    },
                    created_by=request.user,
                )

        contract_data = {
            'contract_no': data.get('contract_no'),
            'contract_name': data.get('contract_name'),
            'party_a_name': data.get('party_a_name'),
            'party_a_address': data.get('party_a_address', ''),
            'party_a_contact': data.get('party_a_contact', ''),
            'party_a_phone': data.get('party_a_phone', ''),
            'party_b_name': data.get('party_b_name'),
            'party_b_address': data.get('party_b_address', ''),
            'party_b_contact': data.get('party_b_contact', ''),
            'party_b_phone': data.get('party_b_phone', ''),
            'total_amount': data.get('total_amount', 0),
            'project_name': data.get('project_name', ''),
            'delivery_days': data.get('delivery_days', 45),
            'custom_terms': data.get('custom_terms', ''),
        }

        service = ContractGenerationService(template)
        html_content = service.generate_html(contract_data)

        # 保存生成的合同
        contract = GeneratedContract.objects.create(
            template=template,
            contract_no=contract_data['contract_no'],
            contract_name=contract_data['contract_name'],
            contract_type=template.contract_type,
            party_a_name=contract_data['party_a_name'],
            party_a_address=contract_data['party_a_address'],
            party_a_contact=contract_data['party_a_contact'],
            party_a_phone=contract_data['party_a_phone'],
            party_b_name=contract_data['party_b_name'],
            party_b_address=contract_data['party_b_address'],
            party_b_contact=contract_data['party_b_contact'],
            party_b_phone=contract_data['party_b_phone'],
            total_amount=Decimal(str(contract_data['total_amount'])) if contract_data['total_amount'] else 0,
            contract_content=html_content,
            custom_terms=contract_data.get('custom_terms', ''),
            created_by=request.user,
        )

        return Response({'success': True, 'contract_id': contract.id, 'html_content': html_content})


class ContractClauseViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """合同条款管理"""

    queryset = ContractClause.objects.filter(is_deleted=False)
    serializer_class = ContractClauseSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['clause_type', 'is_required', 'is_enabled']
    search_fields = ['code', 'name', 'content']
    ordering_fields = ['clause_type', 'sort_order', 'code']

    @action(detail=False, methods=['get'])
    def clause_types(self, request):
        """获取条款类型"""
        return Response([{'value': t[0], 'label': t[1]} for t in ContractClause.CLAUSE_TYPES])

    @action(detail=False, methods=['get'])
    def by_contract_type(self, request):
        """根据合同类型获取适用条款"""
        contract_type = request.query_params.get('contract_type')

        queryset = self.get_queryset().filter(is_enabled=True)
        if contract_type:
            queryset = queryset.filter(
                models.Q(applicable_types=[]) | models.Q(applicable_types__contains=[contract_type])
            )

        return Response(self.get_serializer(queryset, many=True).data)


class GeneratedContractViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """生成的合同管理"""

    queryset = GeneratedContract.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['contract_type', 'status']
    search_fields = ['contract_no', 'contract_name', 'party_a_name', 'party_b_name']
    ordering_fields = ['created_at', 'sign_date', 'total_amount']

    def get_serializer_class(self):
        if self.action == 'list':
            return GeneratedContractListSerializer
        return GeneratedContractSerializer

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """更新合同状态"""
        contract = self.get_object()
        new_status = request.data.get('status')

        if new_status not in dict(GeneratedContract.STATUS_CHOICES):
            return Response({'error': '无效的状态'}, status=400)

        contract.status = new_status

        if new_status == 'SIGNED' and not contract.sign_date:
            contract.sign_date = datetime.now().date()

        contract.save()
        return Response(self.get_serializer(contract).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """合同统计"""
        from django.db.models import Count, Sum
        from django.db.models.functions import TruncMonth

        qs = self.get_queryset()

        # 按状态统计
        by_status = qs.values('status').annotate(count=Count('id'), total=Sum('total_amount'))

        # 按类型统计
        by_type = qs.values('contract_type').annotate(count=Count('id'), total=Sum('total_amount'))

        # 按月统计
        by_month = (
            qs.annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'), total=Sum('total_amount'))
            .order_by('month')
        )

        return Response(
            {
                'total_count': qs.count(),
                'total_amount': qs.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
                'by_status': list(by_status),
                'by_type': list(by_type),
                'by_month': list(by_month),
            }
        )
