"""
Data export service for Excel/PDF generation.
"""
import io
import logging

from django.http import HttpResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class ExcelExportService:
    """
    Service for exporting data to Excel format.
    """

    @classmethod
    def export_queryset(cls, queryset, columns, filename, sheet_name='Sheet1'):
        """
        Export a queryset to Excel file.
        
        Args:
            queryset: Django QuerySet or list of dicts
            columns: List of dicts with 'field', 'header', 'width' keys
            filename: Output filename (without extension)
            sheet_name: Excel sheet name
        
        Returns:
            HttpResponse with Excel file
        """
        import pandas as pd

        # Convert queryset to list of dicts
        if hasattr(queryset, 'values'):
            data = list(queryset.values(*[col['field'] for col in columns]))
        else:
            data = list(queryset)

        # Create DataFrame
        df = pd.DataFrame(data)

        # Rename columns to headers
        column_mapping = {col['field']: col['header'] for col in columns}
        df = df.rename(columns=column_mapping)

        # Reorder columns
        headers = [col['header'] for col in columns]
        df = df[[h for h in headers if h in df.columns]]

        # Create Excel file
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)

            workbook = writer.book
            worksheet = writer.sheets[sheet_name]

            # Set column widths
            for i, col in enumerate(columns):
                width = col.get('width', 15)
                worksheet.set_column(i, i, width)

            # Add header format
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1,
                'align': 'center'
            })

            for col_num, header in enumerate(headers):
                if col_num < len(df.columns):
                    worksheet.write(0, col_num, header, header_format)

        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename={filename}_{timezone.now().strftime("%Y%m%d")}.xlsx'
        return response

    @classmethod
    def export_report(cls, title, data_sections, filename):
        """
        Export a multi-section report to Excel.
        
        Args:
            title: Report title
            data_sections: List of dicts with 'name', 'data', 'columns' keys
            filename: Output filename
        
        Returns:
            HttpResponse with Excel file
        """
        import pandas as pd

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book

            # Title format
            title_format = workbook.add_format({
                'bold': True,
                'font_size': 16,
                'align': 'center'
            })

            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1
            })

            for section in data_sections:
                sheet_name = section['name'][:31]  # Excel sheet name limit
                df = pd.DataFrame(section['data'])

                if section.get('columns'):
                    column_mapping = {col['field']: col['header'] for col in section['columns']}
                    df = df.rename(columns=column_mapping)

                df.to_excel(writer, index=False, sheet_name=sheet_name, startrow=2)

                worksheet = writer.sheets[sheet_name]

                # Write title
                worksheet.merge_range(0, 0, 0, len(df.columns) - 1, title, title_format)

                # Set column widths
                for i, col in enumerate(df.columns):
                    worksheet.set_column(i, i, 15)

        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename={filename}_{timezone.now().strftime("%Y%m%d")}.xlsx'
        return response


class PDFExportService:
    """
    Service for exporting data to PDF format.
    """

    @classmethod
    def export_report(cls, title, content, filename):
        """
        Export report to PDF.
        
        Args:
            title: Report title
            content: HTML content or structured data
            filename: Output filename
        
        Returns:
            HttpResponse with PDF file
        """
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

            output = io.BytesIO()
            doc = SimpleDocTemplate(output, pagesize=A4)

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'Title',
                parent=styles['Heading1'],
                fontSize=18,
                alignment=1  # Center
            )

            elements = []

            # Add title
            elements.append(Paragraph(title, title_style))
            elements.append(Spacer(1, 0.5 * inch))

            # Add content
            if isinstance(content, list) and len(content) > 0:
                # Assume it's table data
                if isinstance(content[0], dict):
                    headers = list(content[0].keys())
                    data = [headers]
                    for row in content:
                        data.append([str(row.get(h, '')) for h in headers])
                else:
                    data = content

                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)

            doc.build(elements)
            output.seek(0)

            response = HttpResponse(output.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename={filename}_{timezone.now().strftime("%Y%m%d")}.pdf'
            return response

        except ImportError:
            logger.warning("reportlab not installed, PDF export unavailable")
            return HttpResponse("PDF export requires reportlab library", status=501)


# Export column definitions for common models
EXPORT_COLUMNS = {
    'project': [
        {'field': 'code', 'header': '项目编号', 'width': 15},
        {'field': 'name', 'header': '项目名称', 'width': 30},
        {'field': 'customer__name', 'header': '客户', 'width': 20},
        {'field': 'manager__username', 'header': '项目经理', 'width': 15},
        {'field': 'status', 'header': '状态', 'width': 10},
        {'field': 'budget_total', 'header': '总预算', 'width': 15},
        {'field': 'start_date', 'header': '开始日期', 'width': 12},
        {'field': 'end_date', 'header': '结束日期', 'width': 12},
    ],
    'sales_order': [
        {'field': 'order_no', 'header': '订单号', 'width': 15},
        {'field': 'customer__name', 'header': '客户', 'width': 20},
        {'field': 'project__name', 'header': '项目', 'width': 20},
        {'field': 'total_amount', 'header': '金额', 'width': 15},
        {'field': 'status', 'header': '状态', 'width': 10},
        {'field': 'order_date', 'header': '订单日期', 'width': 12},
    ],
    'purchase_order': [
        {'field': 'order_no', 'header': '订单号', 'width': 15},
        {'field': 'supplier__name', 'header': '供应商', 'width': 20},
        {'field': 'project__name', 'header': '项目', 'width': 20},
        {'field': 'total_amount', 'header': '金额', 'width': 15},
        {'field': 'status', 'header': '状态', 'width': 10},
        {'field': 'order_date', 'header': '订单日期', 'width': 12},
    ],
    'stock': [
        {'field': 'warehouse__name', 'header': '仓库', 'width': 15},
        {'field': 'item__sku', 'header': 'SKU', 'width': 15},
        {'field': 'item__name', 'header': '物料名称', 'width': 25},
        {'field': 'qty_on_hand', 'header': '库存数量', 'width': 12},
        {'field': 'qty_reserved', 'header': '预留数量', 'width': 12},
        {'field': 'weighted_avg_cost', 'header': '平均成本', 'width': 12},
    ],
    'expense': [
        {'field': 'expense_no', 'header': '费用编号', 'width': 15},
        {'field': 'user__username', 'header': '申请人', 'width': 12},
        {'field': 'project__name', 'header': '项目', 'width': 20},
        {'field': 'category', 'header': '类别', 'width': 10},
        {'field': 'amount', 'header': '金额', 'width': 12},
        {'field': 'status', 'header': '状态', 'width': 10},
        {'field': 'expense_date', 'header': '日期', 'width': 12},
    ],
    'ar': [
        {'field': 'ar_no', 'header': '应收单号', 'width': 15},
        {'field': 'customer__name', 'header': '客户', 'width': 25},
        {'field': 'so__order_no', 'header': '销售订单', 'width': 15},
        {'field': 'project__name', 'header': '项目', 'width': 20},
        {'field': 'invoice_no', 'header': '发票号', 'width': 15},
        {'field': 'invoice_date', 'header': '发票日期', 'width': 12},
        {'field': 'amount_due', 'header': '应收金额', 'width': 15},
        {'field': 'amount_paid', 'header': '已收金额', 'width': 15},
        {'field': 'due_date', 'header': '到期日', 'width': 12},
        {'field': 'status', 'header': '状态', 'width': 10},
        {'field': 'created_at', 'header': '创建时间', 'width': 18},
    ],
    'ap': [
        {'field': 'ap_no', 'header': '应付单号', 'width': 15},
        {'field': 'supplier__name', 'header': '供应商', 'width': 20},
        {'field': 'amount_due', 'header': '应付金额', 'width': 15},
        {'field': 'amount_paid', 'header': '已付金额', 'width': 15},
        {'field': 'due_date', 'header': '到期日', 'width': 12},
        {'field': 'status', 'header': '状态', 'width': 10},
    ],
}
