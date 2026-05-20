"""
批量导入模板服务
Import Template Service - Generate downloadable import templates
"""

from io import BytesIO

import pandas as pd
from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class ImportTemplateConfig:
    """
    导入模板配置
    """

    TEMPLATES = {
        'items': {
            'name': '物料导入模板',
            'filename': '物料导入模板.xlsx',
            'columns': [
                {'field': 'item_code', 'label': '物料编码', 'required': True, 'example': 'M001'},
                {'field': 'name', 'label': '物料名称', 'required': True, 'example': '螺丝M6x20'},
                {'field': 'specification', 'label': '规格型号', 'required': False, 'example': 'M6x20mm'},
                {'field': 'unit', 'label': '单位', 'required': True, 'example': '个'},
                {'field': 'category', 'label': '分类', 'required': False, 'example': '标准件'},
                {'field': 'brand', 'label': '品牌', 'required': False, 'example': 'ABC'},
                {'field': 'min_stock', 'label': '最低库存', 'required': False, 'example': '100'},
                {'field': 'max_stock', 'label': '最高库存', 'required': False, 'example': '1000'},
                {'field': 'purchase_price', 'label': '采购价', 'required': False, 'example': '0.5'},
                {'field': 'notes', 'label': '备注', 'required': False, 'example': '常用标准件'},
            ],
            'instructions': [
                '1. 物料编码和物料名称为必填项',
                '2. 物料编码不能重复',
                '3. 单位必须与系统中已有单位匹配',
                '4. 采购价请填写数字，无需货币符号',
            ],
        },
        'suppliers': {
            'name': '供应商导入模板',
            'filename': '供应商导入模板.xlsx',
            'columns': [
                {'field': 'code', 'label': '供应商编码', 'required': True, 'example': 'SUP001'},
                {'field': 'name', 'label': '供应商名称', 'required': True, 'example': '深圳XX公司'},
                {'field': 'short_name', 'label': '简称', 'required': False, 'example': 'XX公司'},
                {'field': 'contact_person', 'label': '联系人', 'required': False, 'example': '张三'},
                {'field': 'contact_phone', 'label': '联系电话', 'required': False, 'example': '13800138000'},
                {'field': 'email', 'label': '邮箱', 'required': False, 'example': 'zhangsan@xx.com'},
                {'field': 'address', 'label': '地址', 'required': False, 'example': '深圳市XX区XX路XX号'},
                {'field': 'bank_name', 'label': '开户银行', 'required': False, 'example': '中国银行'},
                {'field': 'bank_account', 'label': '银行账号', 'required': False, 'example': '6225xxxx'},
                {'field': 'tax_no', 'label': '税号', 'required': False, 'example': '91440300xxxx'},
                {'field': 'payment_terms', 'label': '付款条款', 'required': False, 'example': '月结30天'},
                {'field': 'notes', 'label': '备注', 'required': False, 'example': '主要供应标准件'},
            ],
            'instructions': [
                '1. 供应商编码和名称为必填项',
                '2. 供应商编码不能重复',
                '3. 联系电话请填写11位手机号或座机号',
            ],
        },
        'customers': {
            'name': '客户导入模板',
            'filename': '客户导入模板.xlsx',
            'columns': [
                {'field': 'code', 'label': '客户编码', 'required': True, 'example': 'CUS001'},
                {'field': 'name', 'label': '客户名称', 'required': True, 'example': '广州XX科技'},
                {'field': 'short_name', 'label': '简称', 'required': False, 'example': 'XX科技'},
                {'field': 'contact_person', 'label': '联系人', 'required': False, 'example': '李四'},
                {'field': 'contact_phone', 'label': '联系电话', 'required': False, 'example': '13900139000'},
                {'field': 'email', 'label': '邮箱', 'required': False, 'example': 'lisi@xx.com'},
                {'field': 'address', 'label': '地址', 'required': False, 'example': '广州市XX区'},
                {'field': 'industry', 'label': '行业', 'required': False, 'example': '新能源'},
                {'field': 'credit_limit', 'label': '信用额度', 'required': False, 'example': '100000'},
                {'field': 'payment_terms', 'label': '付款条款', 'required': False, 'example': '预付30%'},
                {'field': 'notes', 'label': '备注', 'required': False, 'example': '重点客户'},
            ],
            'instructions': [
                '1. 客户编码和名称为必填项',
                '2. 客户编码不能重复',
                '3. 信用额度请填写数字',
            ],
        },
        'bom': {
            'name': 'BOM导入模板',
            'filename': 'BOM导入模板.xlsx',
            'columns': [
                {'field': 'project_no', 'label': '项目编号', 'required': True, 'example': 'PRJ2025001'},
                {'field': 'parent_item_code', 'label': '父级物料编码', 'required': False, 'example': 'ASM001'},
                {'field': 'item_code', 'label': '物料编码', 'required': True, 'example': 'M001'},
                {'field': 'quantity', 'label': '数量', 'required': True, 'example': '10'},
                {'field': 'unit', 'label': '单位', 'required': False, 'example': '个'},
                {'field': 'process', 'label': '工序', 'required': False, 'example': '组装'},
                {'field': 'position', 'label': '位置号', 'required': False, 'example': 'A1-01'},
                {'field': 'notes', 'label': '备注', 'required': False, 'example': ''},
            ],
            'instructions': [
                '1. 项目编号和物料编码为必填项',
                '2. 项目编号必须与系统中已有项目匹配',
                '3. 物料编码必须与系统中已有物料匹配',
                '4. 父级物料编码留空表示顶层BOM',
            ],
        },
        'equipment': {
            'name': '设备台账导入模板',
            'filename': '设备台账导入模板.xlsx',
            'columns': [
                {'field': 'equipment_no', 'label': '设备编号', 'required': True, 'example': 'EQ2025001'},
                {'field': 'name', 'label': '设备名称', 'required': True, 'example': '自动组装设备'},
                {'field': 'model', 'label': '设备型号', 'required': False, 'example': 'ATM-001'},
                {'field': 'serial_no', 'label': '序列号', 'required': False, 'example': 'SN20250001'},
                {'field': 'project_no', 'label': '项目编号', 'required': True, 'example': 'PRJ2025001'},
                {'field': 'customer_code', 'label': '客户编码', 'required': True, 'example': 'CUS001'},
                {'field': 'production_date', 'label': '生产日期', 'required': False, 'example': '2025-01-01'},
                {'field': 'warranty_months', 'label': '质保月数', 'required': False, 'example': '12'},
                {'field': 'installation_address', 'label': '安装地址', 'required': False, 'example': '广州市XX区'},
                {'field': 'notes', 'label': '备注', 'required': False, 'example': ''},
            ],
            'instructions': [
                '1. 设备编号、名称、项目编号、客户编码为必填项',
                '2. 日期格式：YYYY-MM-DD',
                '3. 项目编号和客户编码必须与系统中已有数据匹配',
            ],
        },
    }

    @classmethod
    def get_template_config(cls, template_type):
        return cls.TEMPLATES.get(template_type)

    @classmethod
    def list_templates(cls):
        return [{'key': k, 'name': v['name'], 'filename': v['filename']} for k, v in cls.TEMPLATES.items()]


class ImportTemplateListView(APIView):
    """获取可用的导入模板列表"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        templates = ImportTemplateConfig.list_templates()
        return Response(templates)


class ImportTemplateDownloadView(APIView):
    """下载导入模板"""

    permission_classes = [IsAuthenticated]

    def get(self, request, template_type):
        config = ImportTemplateConfig.get_template_config(template_type)

        if not config:
            return Response({'error': '模板不存在'}, status=404)

        # 创建Excel文件
        output = BytesIO()

        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book

            # 数据Sheet
            columns = config['columns']
            headers = [c['label'] for c in columns]
            examples = [[c['example'] for c in columns]]

            df = pd.DataFrame(examples, columns=headers)
            df.to_excel(writer, sheet_name='数据', index=False, startrow=0)

            # 格式化数据Sheet
            worksheet = writer.sheets['数据']
            header_format = workbook.add_format(
                {'bold': True, 'bg_color': '#4472C4', 'font_color': 'white', 'border': 1}
            )
            required_format = workbook.add_format(
                {'bold': True, 'bg_color': '#FF6B6B', 'font_color': 'white', 'border': 1}
            )

            for col_num, column in enumerate(columns):
                if column['required']:
                    worksheet.write(0, col_num, column['label'], required_format)
                else:
                    worksheet.write(0, col_num, column['label'], header_format)
                worksheet.set_column(col_num, col_num, 15)

            # 说明Sheet
            instructions_df = pd.DataFrame({'填写说明': config['instructions']})
            instructions_df.to_excel(writer, sheet_name='填写说明', index=False)

            # 字段说明Sheet
            field_info = pd.DataFrame(
                {
                    '字段名': [c['label'] for c in columns],
                    '字段代码': [c['field'] for c in columns],
                    '是否必填': ['是' if c['required'] else '否' for c in columns],
                    '示例值': [c['example'] for c in columns],
                }
            )
            field_info.to_excel(writer, sheet_name='字段说明', index=False)

        output.seek(0)

        response = HttpResponse(
            output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{config["filename"]}"'

        return response
