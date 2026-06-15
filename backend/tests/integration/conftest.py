"""Shared fixtures for integration tests.

These tests assume:
- postgres + redis services are up (CI uses docker sidecars; locally use docker compose)
- the DB has been bootstrapped with init_permissions / init_roles / init_industry_roles
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.masterdata.models import Customer, Item, ItemCategory, Supplier, Warehouse
from apps.projects.models import Project


@pytest.fixture
def admin_user(db):
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username='ci_admin',
        defaults={
            'is_superuser': True,
            'is_staff': True,
            'is_active': True,
        },
    )
    user.set_password('ci-test-pw')
    user.save()
    return user


@pytest.fixture
def api_client_admin(admin_user):
    client = APIClient()
    token = RefreshToken.for_user(admin_user).access_token
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


@pytest.fixture
def make_customer(db, admin_user):
    counter = {'n': 0}

    def _make(name='测试客户', **kwargs):
        counter['n'] += 1
        defaults = {
            'code': f'CUST-CI-{counter["n"]:04d}',
            'name': f'{name}-{counter["n"]}',
            'created_by': admin_user,
        }
        defaults.update(kwargs)
        return Customer.objects.create(**defaults)

    return _make


@pytest.fixture
def make_supplier(db, admin_user):
    counter = {'n': 0}

    def _make(name='测试供应商', **kwargs):
        counter['n'] += 1
        defaults = {
            'code': f'SUP-CI-{counter["n"]:04d}',
            'name': f'{name}-{counter["n"]}',
            'created_by': admin_user,
        }
        defaults.update(kwargs)
        return Supplier.objects.create(**defaults)

    return _make


@pytest.fixture
def make_project(db, admin_user, make_customer):
    import datetime

    counter = {'n': 0}

    def _make(name='测试项目', customer=None, **kwargs):
        counter['n'] += 1
        defaults = {
            'code': f'PRJ-CI-{counter["n"]:04d}',
            'name': f'{name}-{counter["n"]}',
            'customer': customer or make_customer(),
            # Project requires manager (FK, PROTECT), start_date and end_date.
            'manager': admin_user,
            'start_date': datetime.date.today(),
            'end_date': datetime.date.today() + datetime.timedelta(days=30),
            'created_by': admin_user,
        }
        defaults.update(kwargs)
        return Project.objects.create(**defaults)

    return _make


@pytest.fixture
def make_warehouse(db, admin_user):
    counter = {'n': 0}

    def _make(name='测试仓库', **kwargs):
        counter['n'] += 1
        defaults = {
            'code': f'WH-CI-{counter["n"]:04d}',
            'name': f'{name}-{counter["n"]}',
            'created_by': admin_user,
        }
        defaults.update(kwargs)
        return Warehouse.objects.create(**defaults)

    return _make


@pytest.fixture
def make_item(db, admin_user):
    counter = {'n': 0}
    category, _ = ItemCategory.objects.get_or_create(
        code='CI-CAT',
        defaults={'name': 'CI 测试分类', 'created_by': admin_user},
    )

    def _make(name='测试物料', standard_cost=Decimal('100.00'), **kwargs):
        counter['n'] += 1
        defaults = {
            # Item's unique code field is `sku` (not `code`); `unit` uses
            # UNIT_CHOICES keys ('PCS' == 个).
            'sku': f'ITEM-CI-{counter["n"]:04d}',
            'name': f'{name}-{counter["n"]}',
            'unit': 'PCS',
            'category': category,
            'standard_cost': standard_cost,
            'created_by': admin_user,
        }
        defaults.update(kwargs)
        return Item.objects.create(**defaults)

    return _make
