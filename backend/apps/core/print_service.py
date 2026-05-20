"""
批量打印服务
Print Service for generating printable documents
"""

from django.apps import apps
from django.http import HttpResponse
from django.template import Context, Template
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class PrintTemplate:
    """
    打印模板配置
    """
    TEMPLATES = {
        # 采购订单打印模板
        'purchase_order': {
            'title': '采购订单',
            'model': ('purchase', 'PurchaseOrder'),
            'template': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>采购订单 - {{ order.order_no }}</title>
    <style>
        body { font-family: "Microsoft YaHei", Arial, sans-serif; margin: 20px; }
        .header { text-align: center; margin-bottom: 20px; }
        .title { font-size: 24px; font-weight: bold; }
        .info-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        .info-table td { padding: 8px; border: 1px solid #ddd; }
        .info-table th { background: #f5f5f5; padding: 8px; border: 1px solid #ddd; }
        .items-table { width: 100%; border-collapse: collapse; }
        .items-table th, .items-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        .items-table th { background: #f5f5f5; }
        .footer { margin-top: 30px; }
        .signature { display: flex; justify-content: space-between; margin-top: 50px; }
        .signature div { width: 30%; }
        @media print { .no-print { display: none; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">采购订单</div>
    </div>
    <table class="info-table">
        <tr>
            <td width="15%"><strong>订单编号:</strong></td>
            <td width="35%">{{ order.order_no }}</td>
            <td width="15%"><strong>订单日期:</strong></td>
            <td width="35%">{{ order.order_date }}</td>
        </tr>
        <tr>
            <td><strong>供应商:</strong></td>
            <td>{{ order.supplier.name }}</td>
            <td><strong>联系人:</strong></td>
            <td>{{ order.supplier.contact_person }}</td>
        </tr>
        <tr>
            <td><strong>交货日期:</strong></td>
            <td>{{ order.expected_delivery_date }}</td>
            <td><strong>付款方式:</strong></td>
            <td>{{ order.payment_terms }}</td>
        </tr>
    </table>
    
    <table class="items-table">
        <thead>
            <tr>
                <th>序号</th>
                <th>物料编码</th>
                <th>物料名称</th>
                <th>规格型号</th>
                <th>数量</th>
                <th>单价</th>
                <th>金额</th>
            </tr>
        </thead>
        <tbody>
            {% for line in order.lines.all %}
            <tr>
                <td>{{ forloop.counter }}</td>
                <td>{{ line.item.item_code }}</td>
                <td>{{ line.item.name }}</td>
                <td>{{ line.item.specification }}</td>
                <td>{{ line.quantity }}</td>
                <td>{{ line.unit_price }}</td>
                <td>{{ line.line_total }}</td>
            </tr>
            {% endfor %}
        </tbody>
        <tfoot>
            <tr>
                <td colspan="6" align="right"><strong>合计金额:</strong></td>
                <td><strong>{{ order.total_amount }}</strong></td>
            </tr>
        </tfoot>
    </table>
    
    <div class="footer">
        <p><strong>备注:</strong> {{ order.notes }}</p>
    </div>
    
    <div class="signature">
        <div>制单人: ________</div>
        <div>审核人: ________</div>
        <div>供应商确认: ________</div>
    </div>
    
    <div class="no-print" style="margin-top: 30px; text-align: center;">
        <button onclick="window.print()">打印</button>
    </div>
</body>
</html>
            '''
        },

        # 销售订单打印模板
        'sales_order': {
            'title': '销售订单',
            'model': ('sales', 'SalesOrder'),
            'template': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>销售订单 - {{ order.order_no }}</title>
    <style>
        body { font-family: "Microsoft YaHei", Arial, sans-serif; margin: 20px; }
        .header { text-align: center; margin-bottom: 20px; }
        .title { font-size: 24px; font-weight: bold; }
        .info-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        .info-table td { padding: 8px; border: 1px solid #ddd; }
        .info-table th { background: #f5f5f5; padding: 8px; border: 1px solid #ddd; }
        .items-table { width: 100%; border-collapse: collapse; }
        .items-table th, .items-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        .items-table th { background: #f5f5f5; }
        .footer { margin-top: 30px; }
        .signature { display: flex; justify-content: space-between; margin-top: 50px; }
        .signature div { width: 30%; }
        @media print { .no-print { display: none; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">销售订单</div>
    </div>
    <table class="info-table">
        <tr>
            <td width="15%"><strong>订单编号:</strong></td>
            <td width="35%">{{ order.order_no }}</td>
            <td width="15%"><strong>订单日期:</strong></td>
            <td width="35%">{{ order.order_date }}</td>
        </tr>
        <tr>
            <td><strong>客户名称:</strong></td>
            <td>{{ order.customer.name }}</td>
            <td><strong>联系人:</strong></td>
            <td>{{ order.customer.contact_person }}</td>
        </tr>
        <tr>
            <td><strong>交货日期:</strong></td>
            <td>{{ order.delivery_date }}</td>
            <td><strong>付款方式:</strong></td>
            <td>{{ order.payment_terms }}</td>
        </tr>
    </table>
    
    <table class="items-table">
        <thead>
            <tr>
                <th>序号</th>
                <th>产品名称</th>
                <th>规格型号</th>
                <th>数量</th>
                <th>单价</th>
                <th>金额</th>
            </tr>
        </thead>
        <tbody>
            {% for line in order.lines.all %}
            <tr>
                <td>{{ forloop.counter }}</td>
                <td>{{ line.item.name }}</td>
                <td>{{ line.item.specification }}</td>
                <td>{{ line.quantity }}</td>
                <td>{{ line.unit_price }}</td>
                <td>{{ line.line_total }}</td>
            </tr>
            {% endfor %}
        </tbody>
        <tfoot>
            <tr>
                <td colspan="5" align="right"><strong>合计金额:</strong></td>
                <td><strong>¥{{ order.total_amount }}</strong></td>
            </tr>
        </tfoot>
    </table>
    
    <div class="footer">
        <p><strong>备注:</strong> {{ order.notes }}</p>
    </div>
    
    <div class="signature">
        <div>销售代表: ________</div>
        <div>审核人: ________</div>
        <div>客户确认: ________</div>
    </div>
</body>
</html>
            '''
        },

        # 领料单打印模板
        'requisition': {
            'title': '领料单',
            'model': ('inventory', 'Requisition'),
            'template': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>领料单 - {{ requisition.requisition_no }}</title>
    <style>
        body { font-family: "Microsoft YaHei", Arial, sans-serif; margin: 20px; }
        .header { text-align: center; margin-bottom: 20px; }
        .title { font-size: 24px; font-weight: bold; }
        .info-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        .info-table td { padding: 8px; border: 1px solid #ddd; }
        .items-table { width: 100%; border-collapse: collapse; }
        .items-table th, .items-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        .items-table th { background: #f5f5f5; }
        .signature { display: flex; justify-content: space-between; margin-top: 50px; }
        .signature div { width: 25%; }
        @media print { .no-print { display: none; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">领料单</div>
    </div>
    <table class="info-table">
        <tr>
            <td><strong>领料单号:</strong> {{ requisition.requisition_no }}</td>
            <td><strong>项目:</strong> {{ requisition.project.name }}</td>
            <td><strong>日期:</strong> {{ requisition.requisition_date }}</td>
        </tr>
        <tr>
            <td><strong>申请人:</strong> {{ requisition.requester.username }}</td>
            <td><strong>领料仓库:</strong> {{ requisition.warehouse.name }}</td>
            <td><strong>状态:</strong> {{ requisition.get_status_display }}</td>
        </tr>
    </table>
    
    <table class="items-table">
        <thead>
            <tr>
                <th>序号</th>
                <th>物料编码</th>
                <th>物料名称</th>
                <th>规格型号</th>
                <th>申请数量</th>
                <th>实发数量</th>
                <th>备注</th>
            </tr>
        </thead>
        <tbody>
            {% for line in requisition.lines.all %}
            <tr>
                <td>{{ forloop.counter }}</td>
                <td>{{ line.item.item_code }}</td>
                <td>{{ line.item.name }}</td>
                <td>{{ line.item.specification }}</td>
                <td>{{ line.requested_quantity }}</td>
                <td>{{ line.issued_quantity }}</td>
                <td>{{ line.notes }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    
    <div class="signature">
        <div>申请人: ________</div>
        <div>审核人: ________</div>
        <div>发料人: ________</div>
        <div>领料人: ________</div>
    </div>
</body>
</html>
            '''
        },

        # 设备台账打印模板
        'equipment': {
            'title': '设备台账',
            'model': ('projects', 'Equipment'),
            'template': '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>设备台账 - {{ equipment.equipment_no }}</title>
    <style>
        body { font-family: "Microsoft YaHei", Arial, sans-serif; margin: 20px; }
        .header { text-align: center; margin-bottom: 20px; }
        .title { font-size: 24px; font-weight: bold; }
        .info-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        .info-table td { padding: 10px; border: 1px solid #ddd; }
        .section-title { background: #f5f5f5; font-weight: bold; }
        @media print { .no-print { display: none; } }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">设备台账</div>
    </div>
    <table class="info-table">
        <tr class="section-title">
            <td colspan="4">基本信息</td>
        </tr>
        <tr>
            <td width="15%"><strong>设备编号:</strong></td>
            <td width="35%">{{ equipment.equipment_no }}</td>
            <td width="15%"><strong>设备名称:</strong></td>
            <td width="35%">{{ equipment.name }}</td>
        </tr>
        <tr>
            <td><strong>设备型号:</strong></td>
            <td>{{ equipment.model }}</td>
            <td><strong>序列号:</strong></td>
            <td>{{ equipment.serial_no }}</td>
        </tr>
        <tr>
            <td><strong>所属项目:</strong></td>
            <td>{{ equipment.project.name }}</td>
            <td><strong>客户:</strong></td>
            <td>{{ equipment.customer.name }}</td>
        </tr>
        <tr>
            <td><strong>状态:</strong></td>
            <td>{{ equipment.get_status_display }}</td>
            <td><strong>软件版本:</strong></td>
            <td>{{ equipment.software_version }}</td>
        </tr>
        <tr class="section-title">
            <td colspan="4">时间节点</td>
        </tr>
        <tr>
            <td><strong>生产完成日期:</strong></td>
            <td>{{ equipment.production_date }}</td>
            <td><strong>发货日期:</strong></td>
            <td>{{ equipment.shipping_date }}</td>
        </tr>
        <tr>
            <td><strong>安装完成日期:</strong></td>
            <td>{{ equipment.installation_date }}</td>
            <td><strong>验收日期:</strong></td>
            <td>{{ equipment.acceptance_date }}</td>
        </tr>
        <tr class="section-title">
            <td colspan="4">质保信息</td>
        </tr>
        <tr>
            <td><strong>质保期:</strong></td>
            <td>{{ equipment.warranty_months }} 个月</td>
            <td><strong>质保开始:</strong></td>
            <td>{{ equipment.warranty_start_date }}</td>
        </tr>
        <tr>
            <td><strong>质保结束:</strong></td>
            <td>{{ equipment.warranty_end_date }}</td>
            <td><strong>延保:</strong></td>
            <td>{% if equipment.extended_warranty %}是 ({{ equipment.extended_warranty_months }}个月){% else %}否{% endif %}</td>
        </tr>
        <tr class="section-title">
            <td colspan="4">安装信息</td>
        </tr>
        <tr>
            <td><strong>安装地址:</strong></td>
            <td colspan="3">{{ equipment.installation_address }}</td>
        </tr>
        <tr>
            <td><strong>联系人:</strong></td>
            <td>{{ equipment.installation_contact }}</td>
            <td><strong>联系电话:</strong></td>
            <td>{{ equipment.installation_phone }}</td>
        </tr>
    </table>
    
    <p><strong>备注:</strong> {{ equipment.notes }}</p>
</body>
</html>
            '''
        }
    }

    @classmethod
    def get_template(cls, template_name):
        return cls.TEMPLATES.get(template_name)

    @classmethod
    def list_templates(cls):
        return [
            {'key': k, 'title': v['title']}
            for k, v in cls.TEMPLATES.items()
        ]


class PrintView(APIView):
    """打印服务API"""
    permission_classes = [IsAuthenticated]

    def get(self, request, template_name, pk):
        """获取打印预览HTML"""
        template_config = PrintTemplate.get_template(template_name)
        if not template_config:
            return Response({'error': '模板不存在'}, status=400)

        # 获取数据
        app_label, model_name = template_config['model']
        try:
            model = apps.get_model(app_label, model_name)
            obj = model.objects.get(pk=pk)
        except Exception as e:
            return Response({'error': f'获取数据失败: {str(e)}'}, status=400)

        # 渲染模板
        template = Template(template_config['template'])
        context = Context({
            template_name.split('_')[-1] if '_' in template_name else template_name: obj,
            'order': obj,
            'requisition': obj,
            'equipment': obj,
        })

        html = template.render(context)

        return HttpResponse(html, content_type='text/html')


class BatchPrintView(APIView):
    """批量打印服务API"""
    permission_classes = [IsAuthenticated]

    def post(self, request, template_name):
        """批量打印多个文档"""
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请选择要打印的记录'}, status=400)

        template_config = PrintTemplate.get_template(template_name)
        if not template_config:
            return Response({'error': '模板不存在'}, status=400)

        # 获取数据
        app_label, model_name = template_config['model']
        try:
            model = apps.get_model(app_label, model_name)
            objects = model.objects.filter(pk__in=ids)
        except Exception as e:
            return Response({'error': f'获取数据失败: {str(e)}'}, status=400)

        # 渲染所有模板
        template = Template(template_config['template'])
        html_parts = []

        for obj in objects:
            context = Context({
                template_name.split('_')[-1] if '_' in template_name else template_name: obj,
                'order': obj,
                'requisition': obj,
                'equipment': obj,
            })
            html_parts.append(template.render(context))

        # 合并为一个HTML页面，添加分页符
        combined_html = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>批量打印</title>
    <style>
        @media print {
            .page-break { page-break-after: always; }
        }
    </style>
</head>
<body>
''' + '<div class="page-break"></div>'.join([
            # 提取body内容
            part.split('<body>')[1].split('</body>')[0] if '<body>' in part else part
            for part in html_parts
        ]) + '''
</body>
</html>
'''

        return HttpResponse(combined_html, content_type='text/html')


class PrintTemplateListView(APIView):
    """打印模板列表API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取可用的打印模板列表"""
        templates = PrintTemplate.list_templates()
        return Response(templates)
