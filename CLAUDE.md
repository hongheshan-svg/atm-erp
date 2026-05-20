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

# 创建超级用户
python manage.py createsuperuser

# 收集静态文件
python manage.py collectstatic --noinput

# Django shell
python manage.py shell_plus  # 需要 django-extensions
```

### Frontend (Vue 3 + Vite)

```bash
# 安装依赖（在 frontend/ 目录下）
cd /home/administrator/erp/frontend
npm install

# 开发服务器 (端口 3000)
npm run dev

# 生产构建
npm run build
```

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

- **Framework**: Vue 3 (Composition API) + Vite 5
- **UI**: Element Plus, ECharts, vue-ganttastic
- **State**: Pinia (`stores/` 下 user、websocket、config)
- **HTTP**: Axios，封装在 `src/utils/request.js`，自动刷新 JWT
- **路由**: `src/router/index.js` (懒加载)，权限通过 `hasMenuAccess()` 控制
- **路径别名**: `@` → `frontend/src/`

视图按业务模块组织在 `src/views/` 下，API 调用封装在 `src/api/` 下。

### Key Patterns

- **BaseModel**: 所有业务模型继承自 `apps.core.models.BaseModel`，自带 `created_at`/`updated_at`/`created_by`/`updated_by` 时间戳和 `is_deleted`/`deleted_at` 软删除
- **软删除**: 查询时需过滤 `is_deleted=False`，删除调用 `soft_delete()` 方法
- **审计日志**: `AuditLogMiddleware` 自动记录所有变更
- **附件**: 通用 `Attachment` 模型，通过 `related_model` + `related_id` 关联任意业务对象
- **工作流**: 可配置审批流，`WorkflowEnforcementMixin` 用于 ViewSet 级别的审批控制
- **数据权限**: `DataPermissionMixin` 按角色数据范围过滤查询集
- **分页**: `StandardPagination` 默认 20 条/页
- **编码规则**: `CodeRule` 模型支持自动生成业务编号

### Infrastructure

- **Docker Compose**: 7 个服务 (postgres:5433, redis:6380, elasticsearch:9201, backend:8000, celery, celery-beat, nginx:8080/8443)
- **Celery Worker**: 使用 host 网络模式以访问局域网设备（如考勤机）
- **环境变量**: `.env` (本地开发), `.env.docker` (Docker), `.env.example` (模板)
- **API 文档**: Swagger UI 在 `/api/docs/`, OpenAPI schema 在 `/api/schema/`
