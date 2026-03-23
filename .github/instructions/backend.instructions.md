---
description: "Use when editing Django models, serializers, viewsets, permissions, workflows, or tests in backend/. Covers BaseModel, soft delete, RBAC, data scope, and API contract changes."
name: "ERP Backend Guidelines"
applyTo: "backend/**/*.py"
---

# Backend Guidelines

- Keep backend changes inside the owning app under `backend/apps/` unless the pattern already belongs in `backend/apps/core/`.
- New business models should inherit `apps.core.models.BaseModel`; preserve `is_deleted` behavior and prefer existing soft delete flows over raw `delete()`.
- When editing ViewSets, serializers, filters, or query logic, preserve RBAC, data-permission filtering, workflow enforcement, and audit expectations already used by the module.
- Reuse existing core patterns for pagination, permission mixins, workflow mixins, and code generation before introducing new helpers.
- Keep API routes consistent with the existing `/api/` prefix and current app URL structure in `backend/config/urls.py` and app-level `urls.py` files.
- If a serializer or list endpoint expands related objects, check whether `select_related` or `prefetch_related` is needed to avoid N+1 queries.
- Prefer focused validation first: `cd backend && python manage.py test <app_or_test>`; use root-level permission scripts when the change affects roles, menus, or data-scope behavior.
- If a backend API contract changes, update the matching frontend API wrapper under `frontend/src/api/` in the same task when feasible.
- For permission-sensitive changes, review existing scripts such as `test_permissions.py`, `test_comprehensive_permissions.py`, and `run_all_tests.py` before adding new test entry points.
