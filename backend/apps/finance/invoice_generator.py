"""
PDF Invoice Generator using ReportLab
"""
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime


class InvoiceGenerator:
    """Generate PDF invoices from sales orders"""
    
    def __init__(self, sales_order):
        self.sales_order = sales_order
        self.buffer = BytesIO()
        self.doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        self.elements = []
        self.styles = getSampleStyleSheet()
    
    def generate(self):
        """Generate the PDF invoice"""
        self._add_header()
        self._add_company_info()
        self._add_invoice_details()
        self._add_line_items()
        self._add_totals()
        self._add_footer()
        
        self.doc.build(self.elements)
        self.buffer.seek(0)
        return self.buffer
    
    def _add_header(self):
        """Add invoice header"""
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        title = Paragraph('INVOICE', title_style)
        self.elements.append(title)
        self.elements.append(Spacer(1, 0.2 * inch))
    
    def _add_company_info(self):
        """Add company and customer information"""
        data = [
            ['Company Name', '', 'Bill To:'],
            ['123 Business Street', '', self.sales_order.customer.name],
            ['City, State 12345', '', self.sales_order.customer.address or ''],
            ['Phone: (555) 123-4567', '', f'Phone: {self.sales_order.customer.phone or ""}'],
            ['Email: info@company.com', '', f'Email: {self.sales_order.customer.email or ""}'],
        ]
        
        table = Table(data, colWidths=[3*inch, 1*inch, 3*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        
        self.elements.append(table)
        self.elements.append(Spacer(1, 0.3 * inch))
    
    def _add_invoice_details(self):
        """Add invoice details"""
        data = [
            ['Invoice #:', self.sales_order.order_no],
            ['Date:', self.sales_order.order_date.strftime('%Y-%m-%d')],
            ['Due Date:', self.sales_order.delivery_date.strftime('%Y-%m-%d')],
            ['Status:', self.sales_order.status],
        ]
        
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        self.elements.append(table)
        self.elements.append(Spacer(1, 0.3 * inch))
    
    def _add_line_items(self):
        """Add line items table"""
        headers = ['#', 'Item', 'Quantity', 'Unit Price', 'Amount']
        data = [headers]
        
        for idx, line in enumerate(self.sales_order.lines.all(), 1):
            row = [
                str(idx),
                line.item.name,
                str(line.qty),
                f'${line.unit_price:,.2f}',
                f'${line.qty * line.unit_price:,.2f}'
            ]
            data.append(row)
        
        table = Table(data, colWidths=[0.5*inch, 3*inch, 1*inch, 1.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),
        ]))
        
        self.elements.append(table)
        self.elements.append(Spacer(1, 0.3 * inch))
    
    def _add_totals(self):
        """Add totals section"""
        total = self.sales_order.total_amount
        
        data = [
            ['Subtotal:', f'${total:,.2f}'],
            ['Tax (0%):', '$0.00'],
            ['Total:', f'${total:,.2f}'],
        ]
        
        table = Table(data, colWidths=[5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#3498db')),
        ]))
        
        self.elements.append(table)
        self.elements.append(Spacer(1, 0.5 * inch))
    
    def _add_footer(self):
        """Add invoice footer"""
        footer_style = ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        
        footer_text = Paragraph(
            'Thank you for your business!<br/>For questions, contact: support@company.com',
            footer_style
        )
        self.elements.append(footer_text)
    
    @classmethod
    def generate_invoice(cls, sales_order):
        """Class method to generate invoice"""
        generator = cls(sales_order)
        return generator.generate()

