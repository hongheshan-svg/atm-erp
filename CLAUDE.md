# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

面向非标自动化行业的企业级 ERP 系统，采用 Django REST Framework 后端 + Vue 3 前端的前后端分离架构。以项目为核心，贯穿销售→设计→BOM→采购→生产→交付→成本核算全流程。

## Common Commands

### Backend (Django)

```bash
# 启动开发服务器（在 backend/ 目录下）
cd /home/administrator/erp/backend
python manage.py runserver 0.0.0.0:8000

# 数据库迁移
python manage.py makemigrations
python manage.py migrate

# 首次启动需要的 bootstrap 命令（顺序敏感）
python manage.py init_permissions     # 权限树种子数据
python manage.py init_roles --force   # 角色+权限分配+数据范围
python manage.py seed_data            # 可选：示例数据
python manage.py init_dashboard_widgets

# 创建超级用户
python manage.py createsuperuser

# 收集静态文件
python manage.py collectstatic --noinput

# Django shell
python manage.py shell_plus  # 需要 django-extensions
```

### Linting

```bash
# 后端 — Ruff (lint + format)，在 backend/ 目录下
cd /home/administrator/erp/backend
ruff check . --fix          # lint with auto-fix
ruff format .               # format (single quotes, line-length=120)

# 前端 — ESLint，在 frontend/ 目录下
cd /home/administrator/erp/frontend
npm run lint                # check
npm run lint:fix            # auto-fix
npm run typecheck           # vue-tsc --noEmit
```

Ruff 配置在 `backend/pyproject.toml`，规则含 pycodestyle/pyflakes/isort/bugbear/django-specific，line-length 120，排除 migrations。ESLint flat config 在 `frontend/eslint.config.js`。

### Tests

```bash
# 后端 Django 单元测试（在 backend/ 目录下）
python manage.py test                                   # 全量
python manage.py test apps.core                         # 单个 app
python manage.py test apps.core.tests.test_permission_service  # 单个文件
python manage.py test apps.core.tests.test_permission_service.PermissionServiceTest.test_xxx  # 单个用例

# 前端 Vitest（在 frontend/ 目录下）
npm run test                # vitest run (单次)
npm run test:ui             # vitest --ui (交互)
npm run test:coverage       # vitest run --coverage

# 集成 / 浏览器测试（仓库根目录，依赖 Docker 已启动）
python run_all_tests.py                                  # 自动 migrate + init_roles + 跑全套测试
python test_browser_simulation.py                        # 前端页面冒烟
python test_browser_deep.py                              # 深度交互测试
python test_vue_runtime.py                               # Vue 运行时报错检测

# 权限相关的根目录脚本（改动 RBAC / 数据范围时必跑）
python test_permissions.py
python test_comprehensive_permissions.py
python test_frontend_permissions.py
```

### Frontend (Vue 3 + Vite + TypeScript)

```bash
# 安装依赖（在 frontend/ 目录下）
cd /home/administrator/erp/frontend
npm install

# 开发服务器 (端口 3000，base path 为 /erp/，启动后访问 http://localhost:3000/erp/)
npm run dev

# 生产构建
npm run build

# 预览构建产物
npm run preview
```

Vite 已配置 `/api` 与 `/ws` 反向代理到 `http://backend:8000`（Docker 内）或 `VITE_API_BASE_URL`（本地需 export）。前端 `base: '/erp/'` 与 nginx 路由一致，**所有路由路径需带 `/erp/` 前缀**。

### Docker (完整环境)

```bash
# 启动所有服务
docker compose up -d

# 查看日志
docker compose logs -f backend
docker compose logs -f celery

# 重建后端
docker compose up -d --build backend
```

### Pre-commit Hooks

```bash
# 安装 pre-commit（首次）
pip install pre-commit
pre-commit install

# 手动运行所有 hooks
pre-commit run --all-files
```

Hooks 内容：Ruff (lint+format) on `backend/`、ESLint on `frontend/src/`、禁止直接提交到 main 分支、trailing-whitespace/end-of-file-fixer/check-yaml/check-added-large-files(500KB)。

### Integration Tests (pytest)

```bash
# 在 backend/ 目录下，需要 Docker 服务运行中
cd /home/administrator/erp/backend
pip install -r requirements-dev.txt
pytest tests/integration -v --tb=short
```

### Celery (异步任务)

```bash
celery -A config worker -l info --concurrency=2
celery -A config beat -l info
```

## Architecture

### Backend (`backend/`)

- **Framework**: Django 4.2 + DRF 3.14, ASGI via Daphne + Channels
- **Database**: PostgreSQL 15, Redis 7 (缓存/消息队列), Elasticsearch 7.17 (搜索)
- **Auth**: JWT (simplejwt), Bearer token, RBAC 权限控制
- **Settings**: `backend/config/settings.py`, 环境变量通过 `python-decouple` 读取
- **URL 入口**: `backend/config/urls.py`, 所有 API 前缀 `/api/`

15 个 Django App 位于 `backend/apps/`:

| App | 职责 |
|-----|------|
| `core` | BaseModel、审计日志、附件、通知、权限、编码规则、工作流 |
| `accounts` | 用户、角色、部门、考勤 |
| `masterdata` | 物料、客户、供应商、仓库、信用管理 |
| `projects` | 项目管理、BOM、图纸、任务、设备档案 |
| `sales` | 报价、销售订单、发货、CRM (线索/商机) |
| `purchase` | 采购申请、询价(RFQ)、采购订单、收货、委外 |
| `inventory` | 库存、库存移动、MRP、批次管理、库存预警、备件 |
| `finance` | 应收/应付、费用、税务、会计、资产、银行对账 |
| `production` | MES、APS排程、看板、Andon、工艺路线、产能规划 |
| `oa` | 办公自动化、车辆管理、资产管理、档案管理、即时通讯 |
| `reports` | 报表与分析 |
| `analytics` | BI 仪表盘 |

### Frontend (`frontend/`)

- **Framework**: Vue 3 (Composition API) + TypeScript + Vite 5
- **UI**: Element Plus, ECharts, vue-ganttastic
- **State**: Pinia (`stores/` 下 user、permission、websocket、companyConfig)
- **HTTP**: Axios，封装在 `src/utils/request.ts`，自动刷新 JWT、401 排队重试
- **路由**: `src/router/index.js` (懒加载)，权限通过 `usePermissionStore().hasPermission()` 控制
- **路径别名**: `@` → `frontend/src/`

视图按业务模块组织在 `src/views/` 下，API 调用封装在 `src/api/` 下（已部分迁移到 TypeScript）。

### Key Patterns

- **BaseModel**: 所有业务模型继承自 `apps.core.models.BaseModel`，自带 `created_at`/`updated_at`/`created_by`/`updated_by` 时间戳和 `is_deleted`/`deleted_at` 软删除
- **软删除**: `objects` 管理器默认过滤 `is_deleted=False`，绕过用 `all_objects`。删除调用 `instance.soft_delete()`
- **审计日志**: `AuditLogMiddleware` 自动记录所有变更
- **附件**: 通用 `Attachment` 模型，通过 `related_model` + `related_id` 关联任意业务对象
- **工作流**: 可配置审批流，`WorkflowEnforcementMixin`（在 `apps.core.workflow.mixins`）用于 ViewSet 级别的审批控制，需设置 `workflow_business_type`/`workflow_amount_field`/`workflow_no_field`
- **统一权限 Mixin**: `apps.core.permission_mixin.PermissionMixin` 是最新的权限方案（替代旧的 DataPermissionMixin/FinanceDataMixin/OperationPermissionMixin/SensitiveFieldMixin），配置 `permission_module`/`permission_resource`/`context_role_fields` 三个类属性即可
- **ViewSet 标准 Mixins**: 新 ViewSet 应组合 `UserTrackingMixin`（自动设 created_by/updated_by）、`SoftDeleteMixin`（perform_destroy 走软删除）、`DataScopeMixin`（按角色数据范围过滤）——均在 `apps.core.mixins`
- **分页**: `StandardPagination` 默认 20 条/页
- **编码规则**: `CodeRule` 模型支持自动生成业务编号
- **前端权限三件套**: 路由 `meta.permission` 控制页面访问、`usePermissionStore().hasPermission()` 用于逻辑判断、`v-permission` 指令控制元素可见性——三者权限标识必须一致

### Infrastructure

- **Docker Compose**: 7 个服务 (postgres:5433, redis:6380, elasticsearch:9201, backend:8000, celery, celery-beat, nginx:8080/8443)。**端口偏移是为避开宿主机已有服务**，从宿主机连接数据库时请用 `5433/6380/9201`，从容器内仍用 `5432/6379/9200`。
- **Celery Worker**: 使用 host 网络模式以访问局域网设备（如考勤机）。修改 Celery 任务后需 `docker compose restart celery celery-beat`，否则旧 worker 仍持有旧任务定义。
- **环境变量**: `.env` (本地开发), `.env.docker` (Docker), `.env.example` (模板)
- **API 文档**: Swagger UI 在 `/api/docs/`, OpenAPI schema 在 `/api/schema/`

## Other Codebases in the Repo

- `miniprogram/` — 微信小程序客户端（独立于 Vue 前端），改动 API 契约时需同步该目录下 `pages/`、`utils/request.js`。
- `nginx/`、`docker/` — 部署配置；改动反向代理或 Dockerfile 后必须 `docker compose build` 重新构建对应服务。
- `docs/` — 项目文档。重点参考：
  - `docs/DEVELOPMENT_GUIDE.md` — 环境与部署详解
  - `docs/REQUIREMENTS-PRD.md` / `docs/REQUIREMENTS-IMPLEMENTATION-MAPPING.md` — 需求与实现映射
  - `docs/业务流程手册.md` — 业务流程参考

## Conventions Worth Knowing

- 新业务模型继承 `apps.core.models.BaseModel`，删除调用 `instance.soft_delete()`，查询走默认 `objects` 管理器（已过滤软删除），绕过用 `all_objects`。
- ViewSet 修改时保留权限 Mixin（优先用 `PermissionMixin`，旧代码可能还用 `DataPermissionMixin`）、`WorkflowEnforcementMixin` 审批联动与审计日志中间件的预期，不要手写一套替代逻辑。
- 前端网络调用统一走 `frontend/src/utils/request.ts`（封装 JWT 刷新、401 排队重试、错误码提示），新接口在 `frontend/src/api/<module>.ts` 中按模块组织，**不要在视图组件里直接 `import axios`**。
- 前端权限：路由 `meta.permission`、`usePermissionStore().hasPermission()` 与 `v-permission` 指令三者权限标识保持一致；后端 API 契约变化要同步前端 API 封装与权限测试。
- 业务编号通过 `CodeRule` 模型动态生成，不要硬编码前缀/序号格式。
- 前端已迁移至 TypeScript，新文件用 `.ts`/`.vue`（script lang="ts"），遵循已有类型定义。
- Git 工作流：pre-commit 禁止直接提交 main，使用 feature branch。
