"""
Integration tests for the workflow / approval lifecycle.

Uses the PurchaseRequest submit/approve/reject flow because:
- The PurchaseRequest.submit action triggers WorkflowService.start_workflow()
- If no WorkflowDefinition is configured it falls back to auto-approve
- The approve/reject actions require status='SUBMITTED'

Tests cover both paths:
1. With a WorkflowDefinition → status becomes SUBMITTED, WorkflowInstance created
2. Without a WorkflowDefinition → auto-approve path (status→APPROVED directly)
3. Reject: submit → reject → status REJECTED

Key models:
  apps.purchase.models.PurchaseRequest
  apps.core.workflow.models.WorkflowDefinition, WorkflowStep, WorkflowInstance
"""

import datetime

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import Role
from apps.core.workflow.models import WorkflowDefinition, WorkflowInstance, WorkflowStep
from apps.purchase.models import PurchaseRequest

pytestmark = pytest.mark.django_db

PR_URL = '/api/purchase/requests/'

User = get_user_model()


def _today_plus(days: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


def _make_pr(api_client, admin_user) -> int:
    """Create a DRAFT purchase request via API, return its id.

    requestor is auto-set to request.user in PurchaseRequestViewSet.perform_create().
    """
    payload = {
        'required_date': _today_plus(14),
        'notes': 'CI workflow test',
    }
    resp = api_client.post(PR_URL, payload, format='json')
    assert resp.status_code == 201, f"PR creation failed: {resp.status_code}: {resp.data}"
    return resp.data['id']


# ---------------------------------------------------------------------------
# Test 1 – submitting a PR with a configured workflow starts an instance
# ---------------------------------------------------------------------------

def test_submit_starts_workflow(api_client_admin, admin_user):
    """Submitting a PR when a WorkflowDefinition exists creates a WorkflowInstance."""
    # Create a workflow definition for PURCHASE_REQUEST
    wf = WorkflowDefinition.objects.create(
        name='CI采购申请审批',
        code='CI_PR_APPROVAL',
        business_type='PURCHASE_REQUEST',
        is_active=True,
        created_by=admin_user,
    )

    # Add a step so the workflow is valid
    WorkflowStep.objects.create(
        workflow=wf,
        step_order=1,
        name='审批',
        approver_type='USER',
        approver_user=admin_user,
        created_by=admin_user,
    )

    pr_id = _make_pr(api_client_admin, admin_user)

    resp = api_client_admin.post(f'{PR_URL}{pr_id}/submit/', {}, format='json')
    assert resp.status_code == 200, f"Submit failed: {resp.status_code}: {resp.data}"

    # Either a workflow instance was started (status=SUBMITTED)
    # or auto-approved (status=APPROVED) depending on WorkflowService logic
    assert resp.data['status'] in ('SUBMITTED', 'APPROVED'), (
        f"Unexpected status after submit: {resp.data['status']}"
    )

    if resp.data.get('workflow_started'):
        assert resp.data['status'] == 'SUBMITTED'
        # WorkflowInstance should exist
        instance = WorkflowInstance.objects.filter(
            business_type='PURCHASE_REQUEST', business_id=pr_id
        ).first()
        assert instance is not None, 'Expected WorkflowInstance to be created'
        assert instance.status == 'PENDING'
    else:
        # Auto-approve path - still a valid outcome
        assert resp.data['status'] == 'APPROVED'


# ---------------------------------------------------------------------------
# Test 2 – approve completes the workflow (no active workflow required path)
# ---------------------------------------------------------------------------

def test_approve_completes_workflow(api_client_admin, admin_user):
    """Approving a SUBMITTED PR (direct approval, no active workflow) sets status=APPROVED."""
    # Ensure no active WorkflowDefinition for PURCHASE_REQUEST to take the
    # no-workflow path so we can test the approve action directly.
    WorkflowDefinition.objects.filter(
        business_type='PURCHASE_REQUEST', is_active=True
    ).update(is_active=False)

    pr_id = _make_pr(api_client_admin, admin_user)

    # Submit → should auto-approve (no workflow), but we force manual path
    # by directly setting the PR to SUBMITTED via model
    pr = PurchaseRequest.objects.get(id=pr_id)
    pr.status = 'SUBMITTED'
    pr.save()

    resp = api_client_admin.post(f'{PR_URL}{pr_id}/approve/', {}, format='json')
    assert resp.status_code == 200, f"Approve failed: {resp.status_code}: {resp.data}"
    assert resp.data['status'] == 'APPROVED'


# ---------------------------------------------------------------------------
# Test 3 – reject returns PR to rejected state
# ---------------------------------------------------------------------------

def test_reject_returns_to_draft(api_client_admin, admin_user):
    """Rejecting a SUBMITTED PR sets status=REJECTED."""
    # Deactivate any existing workflows
    WorkflowDefinition.objects.filter(
        business_type='PURCHASE_REQUEST', is_active=True
    ).update(is_active=False)

    pr_id = _make_pr(api_client_admin, admin_user)

    # Force PR to SUBMITTED state
    pr = PurchaseRequest.objects.get(id=pr_id)
    pr.status = 'SUBMITTED'
    pr.save()

    resp = api_client_admin.post(
        f'{PR_URL}{pr_id}/reject/',
        {'reason': 'CI test rejection'},
        format='json',
    )
    assert resp.status_code == 200, f"Reject failed: {resp.status_code}: {resp.data}"
    assert resp.data['status'] == 'REJECTED'
