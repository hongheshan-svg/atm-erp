# ATM-ERP

**English** ｜ [简体中文](./README.zh-CN.md)

> An enterprise-grade ERP for the **custom (non-standard) automation equipment
> industry**, built **around projects** — covering the full closed loop of
> Sales → Design → BOM → Procurement → Production → Delivery → Cost Accounting.
> Django REST Framework backend + Vue 3 frontend, with a WeChat Mini Program for
> mobile approvals.

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white">
  <img alt="Django" src="https://img.shields.io/badge/Django-4.2-092E20?logo=django&logoColor=white">
  <img alt="DRF" src="https://img.shields.io/badge/DRF-3.14-A30000">
  <img alt="Vue" src="https://img.shields.io/badge/Vue-3.4-4FC08D?logo=vuedotjs&logoColor=white">
  <img alt="Vite" src="https://img.shields.io/badge/Vite-5-646CFF?logo=vite&logoColor=white">
  <img alt="Element Plus" src="https://img.shields.io/badge/Element%20Plus-2.4-409EFF">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white">
</p>

---

## Table of Contents

- [Overview](#overview)
- [Core Features](#core-features)
- [Modules](#modules)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
  - [One-click install (Linux / macOS / Windows)](#one-click-install-linux--macos--windows)
  - [Option 1: Docker Compose (recommended)](#option-1-docker-compose-recommended)
  - [Option 2: One-click native deploy on Ubuntu](#option-2-one-click-native-deploy-on-ubuntu)
  - [Option 3: Manual local dev setup](#option-3-manual-local-dev-setup)
- [First-time Bootstrap](#first-time-bootstrap)
- [Default Ports](#default-ports)
- [Environment Variables](#environment-variables)
- [Common Commands](#common-commands)
- [Testing](#testing)
- [Code Style & Git Workflow](#code-style--git-workflow)
- [Project Structure](#project-structure)
- [Design Conventions](#design-conventions)
- [Remote Upgrade](#remote-upgrade)
- [WeChat Mini Program](#wechat-mini-program)
- [Documentation](#documentation)
- [License](#license)

---

## Overview

ATM-ERP is an integrated business platform purpose-built for **custom automation
equipment manufacturers**. Unlike generic ERPs, it is organized **around the
"project"** — every sales order, drawing, BOM, purchase order, work order, and
expense claim traces back to a specific project, enabling **project-level
lifecycle cost accounting and profit analysis**.

It spans the entire chain from lead/opportunity acquisition, through quotation,
order, engineering selection, BOM explosion, procurement, production scheduling
(APS/MES), inbound/outbound, and delivery, all the way to AR/AP and project
settlement — with a configurable approval workflow, fine-grained RBAC, data-scope
control, audit logging, real-time notifications, and WeCom (Enterprise WeChat)
integration built in.

## Core Features

- 🎯 **Project-centric** — sales orders must link to a project; cost, labor,
  expense, and procurement all roll up to the project dimension.
- 🔐 **Enterprise RBAC** — roles + permission tree + data scope (all / department /
  self / custom), with unified front-end and back-end permission keys.
- 🧩 **Configurable approval workflow** — enforced at the ViewSet layer, supporting
  multi-level approval and amount thresholds.
- 📦 **End-to-end inventory costing** — weighted-average cost on stock moves, with
  batches, spare parts, MRP, and low-stock alerts.
- 🏭 **Manufacturing execution (MES/APS)** — routings, capacity planning,
  scheduling, kanban, and Andon.
- 🧾 **Full finance suite** — AR/AP, expense reimbursement, tax, accounting,
  assets, bank reconciliation, and aging analysis.
- 🔔 **Real-time notifications + WeCom push** — approvals, goods arrival, delivery
  dates, and project deadlines pushed precisely to the responsible owner.
- 📱 **Mobile approval Mini Program** — approve and view dashboards anywhere via WeChat.
- 🔍 **Full-text search** — business-data search powered by Elasticsearch.
- 📊 **BI & reports** — dashboard widgets, project profit analysis (Pandas), and
  multi-dimensional report export.
- 🧱 **Soft delete + audit log** — all business models inherit `BaseModel`; changes
  are tracked automatically.
- 🐳 **Ready-to-run deployment** — one-command Docker Compose or a one-click native
  Ubuntu script.

## Modules

The backend is split into 12 Django apps (under `backend/apps/`):

| App | Domain | Key capabilities |
|-----|--------|------------------|
| `core` | Platform core | BaseModel, audit log, attachments, notifications, permissions, code rules, workflow engine |
| `accounts` | Org & auth | Users, roles, departments, attendance (ZKTeco device integration) |
| `masterdata` | Master data | Items, customers, suppliers, warehouses, categories, credit management |
| `projects` | Projects | Projects/budget, BOM, drawings (PLM), tasks (WBS), timesheets, equipment records |
| `sales` | Sales & CRM | Quotes, sales orders (must link to a project), delivery, leads/opportunities |
| `purchase` | Procurement | Purchase requests (PR), RFQ, purchase orders (PO), receiving, subcontracting |
| `inventory` | Inventory | Stock, stock moves (weighted-average), MRP, batches, alerts, spare parts |
| `finance` | Finance | AR/AP, expenses, tax, accounting, assets, bank reconciliation, aging |
| `production` | Production | MES, APS scheduling, kanban, Andon, routings, capacity planning |
| `oa` | Office automation | Vehicles, assets, records, instant messaging, knowledge base |
| `reports` | Reports | Project profit analysis, multi-dimensional reports, Excel/PDF export |
| `analytics` | Analytics | Dashboard widgets, data visualization |

Frontend views (`frontend/src/views/`) map one-to-one to these modules, plus
dedicated pages for after-sales, equipment records, knowledge base, PLM, MES,
workflow, and system settings.

## Tech Stack

### Backend

| Category | Technology |
|----------|------------|
| Language / Framework | Python 3.10+ · Django 4.2 · Django REST Framework 3.14 |
| Async / Realtime | ASGI (Daphne) · Django Channels 4 · WebSocket |
| Database | PostgreSQL 15 |
| Cache / Broker | Redis 7 (cache + Celery broker) · django-redis |
| Async tasks | Celery 5.3 + Celery Beat |
| Search | Elasticsearch 7.17 + django-elasticsearch-dsl |
| Auth | JWT (simplejwt) · RBAC |
| Data processing | Pandas · NumPy |
| Import / Export | openpyxl · xlrd · xlsxwriter · reportlab (PDF) · qrcode / python-barcode |
| API docs | drf-spectacular (Swagger / OpenAPI) |
| Config | python-decouple (`.env`) |
| Hardware | pyzk (ZKTeco attendance device) |

### Frontend

| Category | Technology |
|----------|------------|
| Framework | Vue 3 (Composition API) · TypeScript |
| Build | Vite 5 |
| UI | Element Plus · @element-plus/icons-vue |
| Visualization | ECharts / vue-echarts · vue-ganttastic (Gantt) · Three.js (3D) |
| State | Pinia |
| Router | Vue Router 4 (lazy load + permission guard) |
| HTTP | Axios (JWT refresh, 401 queued retry) |
| Utils | dayjs · xlsx |
| Testing | Vitest · @vue/test-utils · Playwright |
| Quality | ESLint (flat config) · vue-tsc type check |

### Infrastructure

Docker Compose orchestrates 7 services: `postgres`, `redis`, `elasticsearch`,
`backend`, `celery`, `celery-beat`, and `nginx`.

## Architecture

```
                          ┌─────────────────────────┐
   Web Browser ──────────►│  Nginx (8080/8443)       │
   Mini Program ─────────►│  Reverse proxy / static  │
                          └───────────┬─────────────┘
                                      │ /api  /ws
                          ┌───────────▼─────────────┐
                          │  Backend (Daphne/ASGI)   │
                          │  Django REST + Channels  │
                          │  JWT · RBAC · Workflow   │
                          └──┬─────────┬─────────┬───┘
                             │         │         │
                ┌────────────▼──┐ ┌────▼────┐ ┌──▼──────────────┐
                │ PostgreSQL 15 │ │ Redis 7 │ │ Elasticsearch   │
                │  business data│ │ cache/MQ│ │  full-text      │
                └───────────────┘ └────┬────┘ └─────────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │ Celery Worker / Beat     │
                          │ async tasks · reminders  │
                          │ (host net → LAN devices) │
                          └──────────────────────────┘
```

- **Decoupled front/back end** — the frontend is served under `base: '/erp/'`; all
  routes are prefixed with `/erp/`, matching the Nginx routing.
- **API entry** — REST under `/api/`, WebSocket under `/ws/`.
- **Celery Worker** runs in host network mode to reach LAN devices such as the
  ZKTeco attendance terminal.

## Quick Start

### One-click install (Linux / macOS / Windows)

Pre-built multi-arch images are published to GHCR; the installer detects Docker,
generates a `.env`, pulls images, starts the stack, and prints the admin login.

**Linux / macOS:**

```bash
curl -fsSL https://github.com/hongheshan-svg/atm-erp/releases/latest/download/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://github.com/hongheshan-svg/atm-erp/releases/latest/download/install.ps1 | iex
```

Pin a version with `--tag 0.2.0` (Linux/macOS) or `-Tag 0.2.0` (Windows). To build
from source instead of pulling images, see [Option 1](#option-1-docker-compose-recommended)
with the `docker-compose.build.yml` override.

> After installation, open **`http://localhost/erp/`** in your browser (the SPA is
> served under `/erp/`; the root `/` returns 404). The first run pulls images and
> runs a multi-minute first-boot bootstrap; the admin username and generated password
> are printed to the console at the end.

### Option 1: Docker Compose (recommended)

Best for spinning up the full stack quickly. Requires Docker and Docker Compose.

```bash
# 1. Clone
git clone <repo-url> atm-erp && cd atm-erp

# 2. Prepare the env file
cp .env.docker.example .env.docker
# Edit secrets, DB password, domain, etc.

# 3. Start all services
docker compose up -d

# 4. Tail logs
docker compose logs -f backend

# 5. First-time bootstrap (see below)
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py init_permissions
docker compose exec backend python manage.py init_roles --force
docker compose exec backend python manage.py init_dashboard_widgets
docker compose exec backend python manage.py createsuperuser
```

Then open:

- Frontend: `http://localhost:8080/erp/`
- API docs (Swagger): `http://localhost:8080/api/docs/`

> ⚠️ **Port offset** — to avoid clashing with existing host services, the
> host-exposed ports are offset (PostgreSQL `5433`, Redis `6380`, Elasticsearch
> `9201`). Connect from the **host** via the offset ports, but
> **container-to-container** traffic still uses the standard ports (5432/6379/9200).

Ops commands:

```bash
docker compose logs -f celery              # Celery logs
docker compose up -d --build backend       # Rebuild & restart backend
docker compose restart celery celery-beat  # Required after changing Celery tasks
docker compose down                        # Stop all services
```

### Option 2: One-click native deploy on Ubuntu

For (pre-)production servers without Docker. The script installs and configures
PostgreSQL, Redis, Node.js 18, a Python venv, Gunicorn, Celery, Nginx, and systemd
units. Supports **Ubuntu 20.04 / 22.04 / 24.04 and Debian 11 / 12**.

```bash
sudo bash install.sh
```

Main steps (`scripts/deploy-native-ubuntu.sh`):

1. Install system dependencies (Python, Node.js 18, Nginx, …)
2. Set up and start PostgreSQL (create database & user)
3. Set up and start Redis
4. Create a Python venv and install dependencies (incl. gunicorn)
5. Run migrations and init (`migrate`, `init_workflows`, `init_dashboard_widgets`, `collectstatic`)
6. Build the frontend (`npm install && npm run build`)
7. Configure Gunicorn + Daphne and register systemd units
8. Configure the Nginx reverse proxy and start it

Service management (systemd):

```bash
sudo systemctl start   erp-backend erp-celery erp-celery-beat
sudo systemctl stop    erp-backend erp-celery erp-celery-beat
sudo systemctl restart erp-backend erp-celery erp-celery-beat
```

### Option 3: Manual local dev setup

For development. Provide your own PostgreSQL 15 and Redis 7 (Elasticsearch optional).

**Backend (`backend/`):**

```bash
cd backend

# 1. venv + dependencies
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. env vars
cp ../.env.example ../.env
# Edit DB host/port etc. (local is usually 127.0.0.1:5432)

# 3. migrate
python manage.py migrate

# 4. bootstrap (see below)
python manage.py init_permissions
python manage.py init_roles --force
python manage.py init_dashboard_widgets
python manage.py createsuperuser

# 5. run
python manage.py runserver 0.0.0.0:8000
```

**Frontend (`frontend/`):**

```bash
cd frontend

# 1. install deps
npm install

# 2. point to the backend (local, non-Docker)
export VITE_API_BASE_URL=http://localhost:8000

# 3. dev server (port 3000, base path /erp/)
npm run dev
# open http://localhost:3000/erp/
```

> Vite proxies `/api` and `/ws` to `http://backend:8000` (inside Docker) or to
> `VITE_API_BASE_URL` (local).

## First-time Bootstrap

These commands are **order-sensitive** — run them in sequence on first deploy
(in `backend/` or inside the container):

```bash
python manage.py migrate                  # database migrations
python manage.py init_permissions         # permission tree seed
python manage.py init_roles --force       # roles + permission assignment + data scope
python manage.py init_dashboard_widgets   # dashboard widgets
python manage.py seed_data                # optional: sample data
python manage.py createsuperuser          # admin superuser
python manage.py collectstatic --noinput  # collect static files (production)
```

## Default Ports

| Service | In-container | Host mapping | Note |
|---------|--------------|--------------|------|
| Nginx | 80 / 443 | **8080 / 8443** | Web entry |
| Backend (Daphne) | 8000 | — | Behind Nginx |
| PostgreSQL | 5432 | **5433** | Use 5433 from the host |
| Redis | 6379 | **6380** | Use 6380 from the host |
| Elasticsearch | 9200 | **9201** | Use 9201 from the host |
| Frontend dev | — | **3000** | Local dev only |

## Environment Variables

Env vars are read from `.env` via `python-decouple`. See the templates
`.env.example` (local) and `.env.docker.example` (Docker).

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key; **must be random in production** |
| `DEBUG` | Debug flag; `False` in production |
| `ALLOWED_HOSTS` | Allowed hosts / IPs |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | PostgreSQL settings |
| `REDIS_HOST` / `REDIS_URL` | Redis settings |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Celery settings |
| `ELASTICSEARCH_HOST` | Elasticsearch host |
| `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` | CORS & CSRF allowlist |
| `FRONTEND_URL` | Frontend URL |
| `JWT_ACCESS_LIFETIME_MINUTES` / `JWT_REFRESH_LIFETIME_DAYS` | JWT lifetimes |
| `SECURE_SSL_REDIRECT` / `SECURE_HSTS_SECONDS` / `*_COOKIE_SECURE` | HTTPS hardening (enable in production) |

## Common Commands

### Backend (`backend/`)

```bash
python manage.py makemigrations
python manage.py migrate

ruff check . --fix     # lint (line-length 120, single quotes)
ruff format .          # format
python manage.py shell_plus   # requires django-extensions
```

### Frontend (`frontend/`)

```bash
npm run dev            # dev server
npm run build          # production build
npm run preview        # preview the build
npm run lint           # ESLint check
npm run lint:fix       # auto-fix
npm run typecheck      # vue-tsc type check
```

### Celery

```bash
celery -A config worker -l info --concurrency=2
celery -A config beat -l info
```

## Testing

### Backend unit tests (`backend/`)

```bash
python manage.py test                                  # all
python manage.py test apps.core                        # single app
python manage.py test apps.core.tests.test_permission_service  # single file
```

### Frontend tests (`frontend/`)

```bash
npm run test           # single run
npm run test:ui        # interactive
npm run test:coverage  # coverage
```

### Integration / browser / permission tests

Run from the repo root; requires Docker running.

```bash
python run_all_tests.py              # auto bootstrap (migrate + init_roles) + full suite
python test_browser_simulation.py    # frontend smoke test
python test_browser_deep.py          # deep interaction test
python test_vue_runtime.py           # Vue runtime error detection

# Run these when touching RBAC / data scope
python test_permissions.py
python test_comprehensive_permissions.py
python test_frontend_permissions.py

# pytest integration (backend/, needs Docker)
cd backend && pip install -r requirements-dev.txt
pytest tests/integration -v --tb=short
```

## Code Style & Git Workflow

- **Backend** — Ruff (pycodestyle/pyflakes/isort/bugbear/django), line-length 120,
  single quotes, migrations excluded. Config in `backend/pyproject.toml`.
- **Frontend** — ESLint flat config (`frontend/eslint.config.js`) + vue-tsc type checks.
- **Pre-commit hooks** — Ruff, ESLint, a guard against committing to `main`, plus
  trailing-whitespace / end-of-file-fixer / check-yaml / check-added-large-files (500KB).

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

> Direct commits to `main` are blocked — use a feature branch + PR.

## Project Structure

```
atm-erp/
├── backend/              # Django REST Framework backend
│   ├── apps/             # 12 business apps (see Modules)
│   ├── config/           # settings.py / urls.py / asgi.py
│   └── requirements.txt
├── frontend/             # Vue 3 + Vite + TypeScript frontend
│   └── src/
│       ├── api/          # API wrappers per module (.ts)
│       ├── stores/       # Pinia (user / permission / websocket / companyConfig)
│       ├── router/       # routes + permission guard
│       ├── utils/        # request.ts (JWT refresh, 401 retry)
│       └── views/        # 19+ business module views
├── miniprogram/          # WeChat Mini Program (mobile approval)
├── nginx/                # Nginx reverse-proxy config
├── docker/               # Dockerfiles & build config
├── scripts/              # deploy & ops scripts (native deploy, packaging, SSL…)
├── docs/                 # requirements, dev guide, business processes, manuals
├── docker-compose.yml    # 7-service orchestration
├── install.sh            # native deploy entry (Ubuntu)
└── CLAUDE.md             # engineering conventions for AI agents
```

## Design Conventions

> Follow these when extending the system; see `CLAUDE.md` for full details.

- **BaseModel** — all business models inherit `apps.core.models.BaseModel`, which
  provides `created_at/updated_at/created_by/updated_by` timestamps and
  `is_deleted/deleted_at` soft-delete fields.
- **Soft delete** — the default `objects` manager filters `is_deleted=False`; use
  `all_objects` to bypass, and delete via `instance.soft_delete()`.
- **Unified permission mixin** — `apps.core.permission_mixin.PermissionMixin` is the
  current approach; configure `permission_module` / `permission_resource` /
  `context_role_fields`.
- **Standard ViewSet mixins** — compose `UserTrackingMixin` / `SoftDeleteMixin` /
  `DataScopeMixin` (all in `apps.core.mixins`).
- **Approval workflow** — `WorkflowEnforcementMixin` (`apps.core.workflow.mixins`);
  set `workflow_business_type` / `workflow_amount_field` / `workflow_no_field`.
- **Audit log** — `AuditLogMiddleware` records all changes automatically.
- **Code rules** — business numbers are generated dynamically via `CodeRule`; never
  hard-code prefixes or sequence formats.
- **Frontend permission trio** — route `meta.permission`,
  `usePermissionStore().hasPermission()`, and the `v-permission` directive must use
  identical permission keys.
- **Frontend networking** — all HTTP goes through `frontend/src/utils/request.ts`;
  add new endpoints under `frontend/src/api/<module>.ts`, organized per module.
  **Never `import axios` directly in view components.**

## Remote Upgrade

From the admin panel under **System Settings → System Upgrade**, super-administrators can:

1. **Check for updates** — the system fetches the public release manifest from
   [hongheshan-svg/atm-erp-release](https://github.com/hongheshan-svg/atm-erp-release)
   and compares the latest version against the running version reported by
   `GET /api/v1/health/`.
2. **One-click upgrade** — clicking "Upgrade" queues the job; the `erp-updater`
   service then:
   - takes an automatic PostgreSQL snapshot (rollback safety net),
   - pulls the new images (Docker) or downloads and verifies the signed tar.gz (native),
   - restarts the stack and waits for the health gate to pass,
   - auto-rolls back to the previous version if the health gate fails within 60 s.
3. **Live progress** — real-time step updates stream to the browser via WebSocket;
   progress is also persisted so the UI can resume after a backend restart.

Requires the `system:upgrade` permission (super-admin only by default).
See [`docs/REMOTE_UPGRADE.md`](docs/REMOTE_UPGRADE.md) for the full architecture,
manifest format, security design, and a step-by-step manual test procedure.

## WeChat Mini Program

`miniprogram/` is a standalone WeChat client (independent from the Vue frontend),
focused on **mobile approvals**:

- 📋 **Mobile approval** — to-do list, detail view, one-tap approve/reject, comments,
  and withdrawal.
- 📁 **Projects** — list/detail, budget usage, task progress.
- 📊 **Dashboard** — finance overview, project stats, inventory overview, cash-flow forecast.

> When the API contract changes, also update `miniprogram/pages/` and
> `miniprogram/utils/request.js`.

## Documentation

Full docs live under `docs/`:

| Document | Description |
|----------|-------------|
| `docs/DEVELOPMENT_GUIDE.md` | Environment & deployment guide |
| `docs/REQUIREMENTS-PRD.md` | Product requirements (PRD) |
| `docs/REQUIREMENTS-IMPLEMENTATION-MAPPING.md` | Requirement-to-implementation mapping |
| `docs/业务流程手册.md` | Business process handbook |
| `docs/USER_MANUAL.md` | User manual |
| `docs/SYSTEM_REQUIREMENTS.md` | System requirements |
| `docs/REMOTE_UPGRADE.md` | Remote upgrade architecture, manifest format, security, and manual test procedure |

Live API docs:

- Swagger UI: `/api/docs/`
- OpenAPI schema: `/api/schema/`

## License

This is an internal enterprise system; all rights reserved by the respective owners.
Add an appropriate license here if you intend to open-source or distribute it.
