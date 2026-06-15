"""
Integration tests for RBAC data scope filtering.

Tests verify that the PermissionMixin + resolve_data_scope pipeline correctly
restricts which records a user can see when listing projects.

Scope rules implemented in apps/core/permission_service.py:
- 'all'  → superuser or role with DataScope(scope_type='all') → unrestricted
- 'self' → DataScope(scope_type='self') → filters by created_by=user
- 'dept' → DataScope(scope_type='dept') → filters by department; Project has
           no department field, so queryset returns none for this scope type

API target: GET /api/projects/projects/
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role
from apps.core.permission_models_new import DataScope, Permission, RolePermission

pytestmark = pytest.mark.django_db

PROJECTS_URL = '/api/projects/projects/'

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_jwt_client(user) -> APIClient:
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


def _make_user_with_scope(username: str, scope_type: str, admin_user) -> User:
    """Create a user + role + DataScope(projects, scope_type)."""
    user = User.objects.create_user(
        username=username,
        password='ci-test-pw',
        is_active=True,
        employee_id=f'EMP-{username}',
    )

    role = Role.objects.create(
        name=f'Role-{username}',
        code=f'role-{username}',
        data_scope='SELF',  # legacy field; actual scope comes from DataScope
    )
    user.roles.add(role)

    # Grant permission to view projects
    perm, _ = Permission.objects.get_or_create(
        code='projects:project:view',
        defaults={
            'name': 'View Project (CI test)',
            'type': 'operation',
            'resource': 'project',
        },
    )
    RolePermission.objects.get_or_create(role=role, permission=perm)

    # Configure data scope for the 'projects' module
    DataScope.objects.create(
        role=role,
        module='projects',
        scope_type=scope_type,
    )

    return user


# ---------------------------------------------------------------------------
# Test 1 – superuser ('all' scope) sees everything
# ---------------------------------------------------------------------------

def test_scope_all_sees_everything(api_client_admin, make_project):
    """Superuser (is_superuser=True → scope='all') can see all projects."""
    # Create two projects by admin
    p1 = make_project(name='Scope-All-P1')
    p2 = make_project(name='Scope-All-P2')

    resp = api_client_admin.get(PROJECTS_URL)
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.data}"

    ids_returned = {item['id'] for item in resp.data.get('results', resp.data)}
    assert p1.id in ids_returned
    assert p2.id in ids_returned


# ---------------------------------------------------------------------------
# Test 2 – 'self' scope user only sees their own records
# ---------------------------------------------------------------------------

def test_scope_self_filters(admin_user, make_customer):
    """User with scope='self' on projects module only sees records they created."""
    user_self = _make_user_with_scope('ci_self_user', 'self', admin_user)
    client_self = _make_jwt_client(user_self)

    # Create one project as admin (created_by=admin_user)
    from apps.projects.models import Project
    other_project = Project.objects.create(
        code='PRJ-SCOPE-OTHER',
        name='Other user project',
        customer=_ensure_customer(admin_user),
        manager=admin_user,
        start_date=datetime.date.today(),
        end_date=datetime.date.today() + datetime.timedelta(days=30),
        created_by=admin_user,
    )

    # Create one project as the self-scope user (created_by=user_self)
    own_project = Project.objects.create(
        code='PRJ-SCOPE-OWN',
        name='Own project',
        customer=_ensure_customer(admin_user),
        manager=admin_user,
        start_date=datetime.date.today(),
        end_date=datetime.date.today() + datetime.timedelta(days=30),
        created_by=user_self,
    )

    resp = client_self.get(PROJECTS_URL)
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.data}"

    ids_returned = {item['id'] for item in resp.data.get('results', resp.data)}
    assert own_project.id in ids_returned, "Own project should be visible"
    assert other_project.id not in ids_returned, "Other user's project should be hidden"


# ---------------------------------------------------------------------------
# Test 3 – 'dept' scope user sees nothing for projects (no department field)
# ---------------------------------------------------------------------------

def test_scope_department_filters(admin_user):
    """User with scope='dept' on projects module sees empty list.

    Project has no 'department' FK, so apply_scope_filter returns queryset.none()
    for the 'dept' scope type (documented behaviour in permission_service.py).
    """
    user_dept = _make_user_with_scope('ci_dept_user', 'dept', admin_user)
    client_dept = _make_jwt_client(user_dept)

    # Create a project as admin
    from apps.projects.models import Project
    Project.objects.create(
        code='PRJ-SCOPE-DEPT',
        name='Department scope test project',
        customer=_ensure_customer(admin_user),
        manager=admin_user,
        start_date=datetime.date.today(),
        end_date=datetime.date.today() + datetime.timedelta(days=30),
        created_by=admin_user,
    )

    resp = client_dept.get(PROJECTS_URL)
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.data}"

    results = resp.data.get('results', resp.data)
    # Project model has no 'department' field → scope filter returns queryset.none()
    assert len(results) == 0, (
        f"Expected 0 results for 'dept' scope on projects (no department field), "
        f"got {len(results)}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_customer_cache: dict = {}


def _ensure_customer(admin_user):
    """Return (or create) a reusable test customer."""
    from apps.masterdata.models import Customer
    obj, _ = Customer.objects.get_or_create(
        code='CUST-SCOPE-TEST',
        defaults={'name': 'Scope Test Customer', 'created_by': admin_user},
    )
    return obj
