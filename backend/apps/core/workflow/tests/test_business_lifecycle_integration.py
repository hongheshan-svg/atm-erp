from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.workflow.models import WorkflowDefinition, WorkflowInstance, WorkflowStep
from apps.purchase.models import PurchaseRequest

User = get_user_model()


class PurchaseRequestWorkflowLifecycleIntegrationTest(TestCase):
    url = '/api/purchase/requests/'

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='workflow_integration_admin',
            password='x',
            employee_id='workflow_integration_admin',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _create_request(self):
        response = self.client.post(
            self.url,
            {
                'required_date': (date.today() + timedelta(days=14)).isoformat(),
                'notes': 'workflow integration test',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def test_submit_starts_configured_workflow(self):
        workflow = WorkflowDefinition.objects.create(
            name='采购申请集成审批',
            code='purchase_request_integration',
            business_type='PURCHASE_REQUEST',
            is_active=True,
            created_by=self.user,
        )
        WorkflowStep.objects.create(
            workflow=workflow,
            step_order=1,
            name='审批',
            approver_type='USER',
            approver_user=self.user,
            created_by=self.user,
        )
        request_id = self._create_request()

        response = self.client.post(f'{self.url}{request_id}/submit/', {}, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'SUBMITTED')
        self.assertTrue(response.data['workflow_started'])
        self.assertTrue(
            WorkflowInstance.objects.filter(
                business_type='PURCHASE_REQUEST',
                business_id=request_id,
                status='PENDING',
            ).exists()
        )

    def test_direct_approve_without_workflow(self):
        request_id = self._create_request()
        purchase_request = PurchaseRequest.objects.get(pk=request_id)
        purchase_request.status = 'SUBMITTED'
        purchase_request.save(update_fields=['status'])

        response = self.client.post(f'{self.url}{request_id}/approve/', {}, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'APPROVED')

    def test_direct_reject_without_workflow(self):
        request_id = self._create_request()
        purchase_request = PurchaseRequest.objects.get(pk=request_id)
        purchase_request.status = 'SUBMITTED'
        purchase_request.save(update_fields=['status'])

        response = self.client.post(
            f'{self.url}{request_id}/reject/',
            {'reason': 'workflow integration rejection'},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'REJECTED')
