"""PDF rendering for project acceptance reports."""

import io
from xml.sax.saxutils import escape


def build_acceptance_report_pdf(report_data):
    """Build a printable PDF from the data returned by the report endpoint."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

    font_name = 'STSong-Light'
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'AcceptanceReportTitle',
        parent=styles['Title'],
        fontName=font_name,
        fontSize=18,
        leading=24,
        alignment=1,
        spaceAfter=8 * mm,
    )
    heading_style = ParagraphStyle(
        'AcceptanceReportHeading',
        parent=styles['Heading2'],
        fontName=font_name,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1f2937'),
        spaceBefore=5 * mm,
        spaceAfter=2 * mm,
    )
    body_style = ParagraphStyle(
        'AcceptanceReportBody',
        parent=styles['BodyText'],
        fontName=font_name,
        fontSize=9,
        leading=13,
    )
    header_style = ParagraphStyle(
        'AcceptanceReportHeader',
        parent=body_style,
        textColor=colors.white,
        alignment=1,
    )

    def paragraph(value, style=body_style):
        text = '-' if value in (None, '') else str(value)
        return Paragraph(escape(text).replace('\n', '<br/>'), style)

    def styled_table(rows, widths, repeat_rows=0):
        table = LongTable(rows, colWidths=widths, repeatRows=repeat_rows, hAlign='LEFT')
        commands = [
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#cbd5e1')),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]
        if repeat_rows:
            commands.extend(
                [
                    ('BACKGROUND', (0, 0), (-1, repeat_rows - 1), colors.HexColor('#334155')),
                    ('TEXTCOLOR', (0, 0), (-1, repeat_rows - 1), colors.white),
                ]
            )
        table.setStyle(TableStyle(commands))
        return table

    acceptance = report_data['acceptance']
    statistics = report_data['statistics']
    issue_statistics = report_data['issues']
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f'验收报告 {acceptance.get("acceptance_no", "")}',
        author='ATM ERP',
    )

    elements = [
        Paragraph('设备验收报告', title_style),
        styled_table(
            [
                [paragraph('验收单号'), paragraph(acceptance.get('acceptance_no'))],
                [paragraph('验收名称'), paragraph(acceptance.get('name'))],
                [paragraph('项目'), paragraph(acceptance.get('project_name'))],
                [paragraph('客户'), paragraph(acceptance.get('customer_name'))],
                [paragraph('设备'), paragraph(acceptance.get('equipment_name') or acceptance.get('equipment_no'))],
                [paragraph('验收类型'), paragraph(acceptance.get('type_display'))],
                [
                    paragraph('状态 / 结果'),
                    paragraph(f'{acceptance.get("status_display") or "-"} / {acceptance.get("result_display") or "-"}'),
                ],
                [
                    paragraph('计划 / 实际日期'),
                    paragraph(f'{acceptance.get("planned_date") or "-"} / {acceptance.get("actual_date") or "-"}'),
                ],
                [paragraph('地点'), paragraph(acceptance.get('location'))],
            ],
            [38 * mm, 142 * mm],
        ),
        Paragraph('验收统计', heading_style),
        styled_table(
            [
                [
                    paragraph('检查项', header_style),
                    paragraph('通过', header_style),
                    paragraph('失败', header_style),
                    paragraph('不适用', header_style),
                    paragraph('待检查', header_style),
                    paragraph('通过率', header_style),
                ],
                [
                    paragraph(statistics['total_items']),
                    paragraph(statistics['passed_items']),
                    paragraph(statistics['failed_items']),
                    paragraph(statistics['na_items']),
                    paragraph(statistics['pending_items']),
                    paragraph(f'{statistics["pass_rate"]}%'),
                ],
            ],
            [30 * mm] * 6,
            repeat_rows=1,
        ),
    ]

    category_rows = [
        [
            paragraph('类别', header_style),
            paragraph('检查项', header_style),
            paragraph('通过', header_style),
            paragraph('失败', header_style),
        ]
    ]
    category_rows.extend(
        [
            paragraph(category or '未分类'),
            paragraph(values['total']),
            paragraph(values['passed']),
            paragraph(values['failed']),
        ]
        for category, values in report_data['categories'].items()
    )
    if len(category_rows) > 1:
        elements.extend(
            [
                Paragraph('分类统计', heading_style),
                styled_table(category_rows, [90 * mm, 30 * mm, 30 * mm, 30 * mm], repeat_rows=1),
            ]
        )

    check_item_rows = [
        [
            paragraph('序号', header_style),
            paragraph('类别', header_style),
            paragraph('检查项', header_style),
            paragraph('判定标准', header_style),
            paragraph('结果', header_style),
        ]
    ]
    for index, item in enumerate(acceptance.get('check_items', []), start=1):
        check_item_rows.append(
            [
                paragraph(item.get('sequence') or index),
                paragraph(item.get('category')),
                paragraph(item.get('name')),
                paragraph(item.get('criteria')),
                paragraph(item.get('result_display') or item.get('result')),
            ]
        )
    if len(check_item_rows) > 1:
        elements.extend(
            [
                Paragraph('检查明细', heading_style),
                styled_table(
                    check_item_rows,
                    [12 * mm, 30 * mm, 48 * mm, 68 * mm, 22 * mm],
                    repeat_rows=1,
                ),
            ]
        )

    elements.extend(
        [
            Paragraph('问题统计', heading_style),
            styled_table(
                [
                    [
                        paragraph('问题总数', header_style),
                        paragraph('待处理', header_style),
                        paragraph('严重', header_style),
                        paragraph('主要', header_style),
                        paragraph('次要', header_style),
                    ],
                    [
                        paragraph(issue_statistics['total']),
                        paragraph(issue_statistics['open']),
                        paragraph(issue_statistics['critical']),
                        paragraph(issue_statistics['major']),
                        paragraph(issue_statistics['minor']),
                    ],
                ],
                [36 * mm] * 5,
                repeat_rows=1,
            ),
            Spacer(1, 6 * mm),
            styled_table(
                [
                    [paragraph('我方意见'), paragraph(acceptance.get('our_opinion'))],
                    [paragraph('客户意见'), paragraph(acceptance.get('customer_opinion'))],
                    [paragraph('遗留问题'), paragraph(acceptance.get('pending_issues'))],
                    [paragraph('客户签字'), paragraph(acceptance.get('customer_signer'))],
                    [paragraph('我方签字'), paragraph(acceptance.get('our_signer_name'))],
                ],
                [38 * mm, 142 * mm],
            ),
        ]
    )

    document.build(elements)
    return output.getvalue()
