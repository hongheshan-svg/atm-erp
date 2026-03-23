# Project Guidelines

## Architecture

- This workspace is a split ERP monorepo: Django REST backend in `backend/`, Vue 3 frontend in `frontend/`, and a separate mini program in `miniprogram/`.
- Backend business code lives under `backend/apps/`; shared patterns such as base models, permissions, workflows, pagination, and audit behavior live in `backend/apps/core/`.
- Backend entry points are `backend/config/settings.py`, `backend/config/urls.py`, and `backend/manage.py`. Keep API changes consistent with the `/api/` prefix.
- Frontend app code lives under `frontend/src/`; follow the existing separation between `api/`, `stores/`, `router/`, `layout/`, `components/`, and `views/`.
- Prefer targeted module changes over introducing new cross-cutting abstractions unless the same pattern already exists in both backend and frontend.

## Build and Test

- Backend setup and runtime: `cd backend && pip install -r requirements.txt`, `python manage.py migrate`, `python manage.py runserver 0.0.0.0:8000`.
- Frontend setup and runtime: `cd frontend && npm install`, `npm run dev`, `npm run build`.
- Infra-sensitive backend work may depend on PostgreSQL, Redis, Elasticsearch, and Celery; avoid assuming features work without those services when touching related code.
- Use the smallest relevant validation first: `cd backend && python manage.py test <app_or_test>` for focused backend changes, then broader root-level scripts only when the change affects integration flows.
- Permission, menu, or data-scope changes should be checked against the existing root scripts such as `test_permissions.py`, `test_comprehensive_permissions.py`, `test_frontend_permissions.py`, or `run_all_tests.py`.

## Conventions

- New backend business models should inherit `apps.core.models.BaseModel`; prefer soft delete flows over raw `delete()`, and preserve `is_deleted` filtering semantics.
- When editing ViewSets, serializers, or query logic, preserve RBAC, data-scope filtering, workflow enforcement, and audit-log expectations already used by the module.
- Reuse existing code-generation, pagination, and permission patterns from `backend/apps/core/` before adding new utilities.
- Frontend network calls should stay in `frontend/src/api/` and use the shared request wrapper in `frontend/src/utils/request.js`; avoid calling raw axios directly from page components.
- Frontend route, menu, and action changes must preserve the existing permission model built around route metadata, `hasMenuAccess()`, and `v-permission`.
- Use the `@` alias for frontend imports from `frontend/src/`.
- When backend API contracts change, update the matching frontend API wrapper and any affected permission or integration tests in the same task.

## References

- See `CLAUDE.md` for the high-level architecture and service map.
- See `docs/DEVELOPMENT_GUIDE.md` for environment requirements and deployment context.