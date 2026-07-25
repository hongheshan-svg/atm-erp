from django.test import SimpleTestCase

from apps.projects.acceptance_report import build_acceptance_report_pdf


class AcceptanceReportPDFTest(SimpleTestCase):
    def test_builds_valid_pdf_from_report_data(self):
        pdf = build_acceptance_report_pdf(
            {
                'acceptance': {
                    'acceptance_no': 'YS-001',
                    'name': '整机出厂验收',
                    'project_name': '自动化产线',
                    'customer_name': '示例客户',
                    'equipment_name': '装配设备',
                    'type_display': '出厂验收',
                    'status_display': '验收通过',
                    'result_display': '通过',
                    'planned_date': '2026-07-25',
                    'actual_date': '2026-07-25',
                    'location': '一号车间',
                    'check_items': [
                        {
                            'sequence': 1,
                            'category': '功能测试',
                            'name': '急停功能',
                            'criteria': '所有急停按钮有效',
                            'result_display': '通过',
                        }
                    ],
                    'our_opinion': '同意验收',
                    'customer_opinion': '设备符合要求',
                    'pending_issues': '',
                    'customer_signer': '客户代表',
                    'our_signer_name': '项目经理',
                },
                'statistics': {
                    'total_items': 1,
                    'passed_items': 1,
                    'failed_items': 0,
                    'na_items': 0,
                    'pending_items': 0,
                    'pass_rate': 100,
                },
                'categories': {'功能测试': {'total': 1, 'passed': 1, 'failed': 0}},
                'issues': {'total': 0, 'open': 0, 'critical': 0, 'major': 0, 'minor': 0},
            }
        )

        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertGreater(len(pdf), 1000)
