# ATM-ERP

[English](./README.md) ｜ **简体中文**

> 面向**非标自动化行业**的企业级 ERP 系统，以**项目为核心**，贯穿
> 销售 → 设计 → BOM → 采购 → 生产 → 交付 → 成本核算 全流程闭环。
> 后端 Django REST Framework + 前端 Vue 3，配套微信小程序移动审批端。

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

## 目录

- [项目简介](#项目简介)
- [核心特性](#核心特性)
- [功能模块总览](#功能模块总览)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
  - [方式一：Docker Compose（推荐）](#方式一docker-compose推荐)
  - [方式二：Ubuntu 一键原生部署](#方式二ubuntu-一键原生部署)
  - [方式三：本地手动开发环境](#方式三本地手动开发环境)
- [首次启动初始化](#首次启动初始化)
- [默认端口一览](#默认端口一览)
- [环境变量配置](#环境变量配置)
- [常用命令](#常用命令)
- [测试](#测试)
- [代码规范与提交流程](#代码规范与提交流程)
- [项目结构](#项目结构)
- [核心设计约定](#核心设计约定)
- [微信小程序端](#微信小程序端)
- [文档索引](#文档索引)
- [License](#license)

---

## 项目简介

ATM-ERP 是为**非标自动化设备制造企业**量身打造的一体化业务管理平台。与通用 ERP 不同，
本系统以「**项目**」为业务主线 —— 每一个销售订单、设计图纸、BOM、采购单、生产工单、
费用报销都可追溯到具体项目，从而实现**项目级别的全生命周期成本核算与利润分析**。

系统覆盖从线索/商机的获取，到报价、签单、设计选型、BOM 拆解、物料采购、生产排程
（APS/MES）、入库出库、发货交付，直到应收应付与项目结算的完整业务链路，并内置可配置
审批工作流、RBAC 细粒度权限、数据范围控制、审计日志、实时通知与企业微信集成。

## 核心特性

- 🎯 **以项目为核心**：销售订单强制关联项目，成本/工时/费用/采购全部归集到项目维度。
- 🔐 **企业级 RBAC 权限**：角色 + 权限树 + 数据范围（全部/部门/本人/自定义），前后端权限标识统一。
- 🧩 **可配置审批工作流**：在 ViewSet 层联动审批，支持多级审批、金额阈值。
- 📦 **全链路库存核算**：库存移动采用加权平均成本法，支持批次、备件、MRP、库存预警。
- 🏭 **生产制造执行（MES/APS）**：工艺路线、产能规划、排程、看板、Andon 安灯。
- 🧾 **完整财务体系**：应收/应付、费用报销、税务、会计、资产、银行对账、账龄分析。
- 🔔 **实时通知 + 企业微信推送**：审批待办、采购到货、销售交期、项目截止精准推送到责任人。
- 📱 **移动审批小程序**：微信小程序端随时随地审批、查看看板。
- 🔍 **全文检索**：基于 Elasticsearch 的业务数据搜索。
- 📊 **BI 与报表**：仪表盘 Widget、项目利润分析（Pandas 驱动）、多维报表导出。
- 🧱 **软删除 + 审计日志**：所有业务模型继承 `BaseModel`，自动记录变更轨迹。
- 🐳 **开箱即用部署**：Docker Compose 一键拉起 / Ubuntu 一键原生部署脚本。

## 功能模块总览

后端按业务域划分为 12 个 Django App（位于 `backend/apps/`）：

| App | 职责 | 关键能力 |
|-----|------|----------|
| `core` | 系统底座 | BaseModel、审计日志、附件、通知、权限、编码规则、工作流引擎 |
| `accounts` | 组织与权限 | 用户、角色、部门、考勤（ZKTeco 考勤机集成） |
| `masterdata` | 主数据 | 物料、客户、供应商、仓库、物料分类、信用管理 |
| `projects` | 项目管理 | 项目/预算、BOM、图纸（PLM）、任务（WBS）、工时、设备档案 |
| `sales` | 销售与 CRM | 报价、销售订单（强制关联项目）、发货、线索/商机 |
| `purchase` | 采购管理 | 采购申请（PR）、询价（RFQ）、采购订单（PO）、收货、委外 |
| `inventory` | 库存管理 | 实时库存、库存移动（加权平均）、MRP、批次、库存预警、备件 |
| `finance` | 财务管理 | 应收/应付、费用报销、税务、会计、资产、银行对账、账龄分析 |
| `production` | 生产制造 | MES、APS 排程、生产看板、Andon、工艺路线、产能规划 |
| `oa` | 办公自动化 | 车辆管理、资产管理、档案管理、即时通讯、知识库 |
| `reports` | 报表中心 | 项目利润分析、多维报表、Excel/PDF 导出 |
| `analytics` | BI 分析 | 仪表盘 Widget、数据可视化 |

前端视图（`frontend/src/views/`）与上述模块一一对应，并额外包含售后（aftersales）、
设备档案（equipment）、知识库（knowledge）、PLM、MES、工作流（workflow）、
系统设置（settings/system）等专属页面。

## 技术栈

### 后端

| 类别 | 技术 |
|------|------|
| 语言/框架 | Python 3.10+ · Django 4.2 · Django REST Framework 3.14 |
| 异步/实时 | ASGI（Daphne）· Django Channels 4 · WebSocket |
| 数据库 | PostgreSQL 15 |
| 缓存/消息 | Redis 7（缓存 + Celery broker）· django-redis |
| 异步任务 | Celery 5.3 + Celery Beat |
| 搜索 | Elasticsearch 7.17 + django-elasticsearch-dsl |
| 认证 | JWT（simplejwt）· RBAC |
| 数据处理 | Pandas · NumPy |
| 导入导出 | openpyxl · xlrd · xlsxwriter · reportlab（PDF）· qrcode / python-barcode |
| API 文档 | drf-spectacular（Swagger / OpenAPI） |
| 配置 | python-decouple（`.env`） |
| 硬件集成 | pyzk（ZKTeco 考勤机） |

### 前端

| 类别 | 技术 |
|------|------|
| 框架 | Vue 3（Composition API）· TypeScript |
| 构建 | Vite 5 |
| UI | Element Plus · @element-plus/icons-vue |
| 可视化 | ECharts / vue-echarts · vue-ganttastic（甘特图）· Three.js（3D） |
| 状态管理 | Pinia |
| 路由 | Vue Router 4（懒加载 + 权限守卫） |
| HTTP | Axios（JWT 刷新、401 排队重试） |
| 工具 | dayjs · xlsx |
| 测试 | Vitest · @vue/test-utils · Playwright |
| 质量 | ESLint（flat config）· vue-tsc 类型检查 |

### 基础设施

Docker Compose 编排 7 个服务：`postgres` · `redis` · `elasticsearch` · `backend` ·
`celery` · `celery-beat` · `nginx`。

## 系统架构

```
                          ┌─────────────────────────┐
   Web 浏览器  ──────────►│  Nginx (8080/8443)       │
   微信小程序  ──────────►│  反向代理 / 静态资源     │
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
                │  业务数据      │ │ 缓存/MQ │ │  全文检索        │
                └───────────────┘ └────┬────┘ └─────────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │ Celery Worker / Beat     │
                          │ 异步任务 · 定时提醒推送  │
                          │ （host 网络访问考勤机）  │
                          └──────────────────────────┘
```

- **前后端分离**：前端 `base: '/erp/'`，所有路由带 `/erp/` 前缀，与 Nginx 路由一致。
- **API 入口**：接口前缀 `/api/`，WebSocket 前缀 `/ws/`。
- **Celery Worker** 使用 host 网络模式，以便访问局域网设备（如 ZKTeco 考勤机）。

## 快速开始

### 方式一：Docker Compose（推荐）

适合快速体验完整环境。需已安装 Docker 与 Docker Compose。

```bash
# 1. 克隆仓库
git clone <repo-url> atm-erp && cd atm-erp

# 2. 准备环境变量
cp .env.docker.example .env.docker
# 按需修改 .env.docker 中的密钥、数据库密码、域名等

# 3. 启动全部服务
docker compose up -d

# 4. 查看启动日志
docker compose logs -f backend

# 5. 首次启动需执行初始化（见下文）
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py init_permissions
docker compose exec backend python manage.py init_roles --force
docker compose exec backend python manage.py init_dashboard_widgets
docker compose exec backend python manage.py createsuperuser
```

启动完成后访问：

- 前端应用：`http://localhost:8080/erp/`
- API 文档（Swagger）：`http://localhost:8080/api/docs/`

> ⚠️ **端口偏移说明**：为避开宿主机已有服务，Compose 对外暴露的端口做了偏移
> （PostgreSQL `5433`、Redis `6380`、Elasticsearch `9201`）。**从宿主机连接**这些服务请用
> 偏移端口；**容器内部互联**仍用标准端口（5432/6379/9200）。

常用运维命令：

```bash
docker compose logs -f celery              # 查看 Celery 日志
docker compose up -d --build backend       # 重建并重启后端
docker compose restart celery celery-beat  # 修改 Celery 任务后必须重启
docker compose down                        # 停止全部服务
```

### 方式二：Ubuntu 一键原生部署

适合生产/准生产服务器（无 Docker）。脚本自动安装并配置 PostgreSQL、Redis、Node.js 18、
Python venv、Gunicorn、Celery、Nginx 与 systemd 服务。支持
**Ubuntu 20.04 / 22.04 / 24.04、Debian 11 / 12**。

```bash
sudo bash install.sh
```

脚本执行的主要步骤（`scripts/deploy-native-ubuntu.sh`）：

1. 安装系统依赖（Python、Node.js 18、Nginx 等）
2. 配置并启动 PostgreSQL（建库建用户）
3. 配置并启动 Redis
4. 创建 Python 虚拟环境并安装依赖（含 gunicorn）
5. 执行数据库迁移与初始化（`migrate`、`init_workflows`、`init_dashboard_widgets`、`collectstatic`）
6. 前端 `npm install && npm run build`
7. 配置 Gunicorn + Daphne，注册 systemd 服务
8. 配置 Nginx 反向代理并启动

服务管理（systemd）：

```bash
sudo systemctl start   erp-backend erp-celery erp-celery-beat
sudo systemctl stop    erp-backend erp-celery erp-celery-beat
sudo systemctl restart erp-backend erp-celery erp-celery-beat
```

### 方式三：本地手动开发环境

适合开发调试。需自行准备 PostgreSQL 15、Redis 7（Elasticsearch 可选）。

**后端（`backend/`）：**

```bash
cd backend

# 1. 创建虚拟环境并安装依赖
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. 配置环境变量
cp ../.env.example ../.env
# 根据本地实际修改 DB_HOST/DB_PORT 等（本地通常 127.0.0.1:5432）

# 3. 数据库迁移
python manage.py migrate

# 4. 初始化（见下文）
python manage.py init_permissions
python manage.py init_roles --force
python manage.py init_dashboard_widgets
python manage.py createsuperuser

# 5. 启动开发服务器
python manage.py runserver 0.0.0.0:8000
```

**前端（`frontend/`）：**

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 指定后端地址（本地开发，非 Docker 时需要）
export VITE_API_BASE_URL=http://localhost:8000

# 3. 启动开发服务器（端口 3000，base path 为 /erp/）
npm run dev
# 访问 http://localhost:3000/erp/
```

> Vite 已配置 `/api` 与 `/ws` 反向代理到 `http://backend:8000`（Docker 内）或
> `VITE_API_BASE_URL`（本地）。

## 首次启动初始化

以下 bootstrap 命令**顺序敏感**，首次部署务必按序执行（在 `backend/` 目录或容器内）：

```bash
python manage.py migrate                  # 数据库迁移
python manage.py init_permissions         # 权限树种子数据
python manage.py init_roles --force       # 角色 + 权限分配 + 数据范围
python manage.py init_dashboard_widgets   # 仪表盘 Widget
python manage.py seed_data                # 可选：示例数据
python manage.py createsuperuser          # 创建超级管理员
python manage.py collectstatic --noinput  # 收集静态文件（生产环境）
```

## 默认端口一览

| 服务 | 容器内端口 | 宿主机映射端口 | 说明 |
|------|-----------|---------------|------|
| Nginx | 80 / 443 | **8080 / 8443** | Web 入口 |
| Backend (Daphne) | 8000 | — | 经 Nginx 代理 |
| PostgreSQL | 5432 | **5433** | 宿主机连接用 5433 |
| Redis | 6379 | **6380** | 宿主机连接用 6380 |
| Elasticsearch | 9200 | **9201** | 宿主机连接用 9201 |
| 前端 Dev Server | — | **3000** | 仅本地开发 `npm run dev` |

## 环境变量配置

环境变量通过 `python-decouple` 从 `.env` 读取。模板见 `.env.example`（本地）与
`.env.docker.example`（Docker）。关键变量：

| 变量 | 说明 |
|------|------|
| `SECRET_KEY` | Django 密钥，**生产必须改为随机值** |
| `DEBUG` | 调试开关，生产置 `False` |
| `ALLOWED_HOSTS` | 允许的访问域名/IP |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | PostgreSQL 配置 |
| `REDIS_HOST` / `REDIS_URL` | Redis 配置 |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Celery 配置 |
| `ELASTICSEARCH_HOST` | Elasticsearch 地址 |
| `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` | 跨域与 CSRF 白名单 |
| `FRONTEND_URL` | 前端地址 |
| `JWT_ACCESS_LIFETIME_MINUTES` / `JWT_REFRESH_LIFETIME_DAYS` | JWT 有效期 |
| `SECURE_SSL_REDIRECT` / `SECURE_HSTS_SECONDS` / `*_COOKIE_SECURE` | HTTPS 安全项（生产启用） |

## 常用命令

### 后端（`backend/`）

```bash
python manage.py makemigrations
python manage.py migrate

ruff check . --fix     # Lint（line-length=120，单引号）
ruff format .          # Format
python manage.py shell_plus   # 需 django-extensions
```

### 前端（`frontend/`）

```bash
npm run dev            # 开发服务器
npm run build          # 生产构建
npm run preview        # 预览构建产物
npm run lint           # ESLint 检查
npm run lint:fix       # 自动修复
npm run typecheck      # vue-tsc 类型检查
```

### Celery

```bash
celery -A config worker -l info --concurrency=2
celery -A config beat -l info
```

## 测试

### 后端单元测试（`backend/`）

```bash
python manage.py test                                  # 全量
python manage.py test apps.core                        # 单个 app
python manage.py test apps.core.tests.test_permission_service  # 单个文件
```

### 前端测试（`frontend/`）

```bash
npm run test           # 单次运行
npm run test:ui        # 交互式
npm run test:coverage  # 覆盖率
```

### 集成 / 浏览器 / 权限测试

仓库根目录运行，依赖 Docker 运行中。

```bash
python run_all_tests.py              # 自动 migrate + init_roles + 跑全套
python test_browser_simulation.py    # 前端页面冒烟
python test_browser_deep.py          # 深度交互测试
python test_vue_runtime.py           # Vue 运行时报错检测

# RBAC / 数据范围改动时必跑
python test_permissions.py
python test_comprehensive_permissions.py
python test_frontend_permissions.py

# pytest 集成测试（backend/，需 Docker）
cd backend && pip install -r requirements-dev.txt
pytest tests/integration -v --tb=short
```

## 代码规范与提交流程

- **后端**：Ruff（pycodestyle/pyflakes/isort/bugbear/django），line-length 120，单引号，
  排除 migrations。配置见 `backend/pyproject.toml`。
- **前端**：ESLint flat config（`frontend/eslint.config.js`）+ vue-tsc 类型检查。
- **Pre-commit Hooks**：Ruff、ESLint、禁止直接提交 `main`、trailing-whitespace /
  end-of-file-fixer / check-yaml / check-added-large-files(500KB)。

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

> pre-commit **禁止直接提交 main**，请使用 feature branch + PR。

## 项目结构

```
atm-erp/
├── backend/              # Django REST Framework 后端
│   ├── apps/             # 12 个业务 App（见功能模块总览）
│   ├── config/           # settings.py / urls.py / asgi.py
│   └── requirements.txt
├── frontend/             # Vue 3 + Vite + TypeScript 前端
│   └── src/
│       ├── api/          # 按模块组织的 API 封装（.ts）
│       ├── stores/       # Pinia（user/permission/websocket/companyConfig）
│       ├── router/       # 路由 + 权限守卫
│       ├── utils/        # request.ts（JWT 刷新、401 重试）
│       └── views/        # 19+ 业务模块视图
├── miniprogram/          # 微信小程序（移动审批端）
├── nginx/                # Nginx 反向代理配置
├── docker/               # Dockerfile 与构建配置
├── scripts/              # 部署/运维脚本（原生部署、打包、SSL 等）
├── docs/                 # 需求、开发指南、业务流程、用户手册
├── docker-compose.yml    # 7 服务编排
├── install.sh            # Ubuntu 一键原生部署入口
└── CLAUDE.md             # 面向 AI 协作的工程约定
```

## 核心设计约定

> 二次开发请遵循以下约定，详见 `CLAUDE.md`。

- **BaseModel**：所有业务模型继承 `apps.core.models.BaseModel`，自带
  `created_at/updated_at/created_by/updated_by` 与 `is_deleted/deleted_at` 软删除字段。
- **软删除**：默认 `objects` 管理器过滤 `is_deleted=False`，绕过用 `all_objects`，
  删除调用 `instance.soft_delete()`。
- **统一权限 Mixin**：`apps.core.permission_mixin.PermissionMixin` 为最新方案，
  配置 `permission_module` / `permission_resource` / `context_role_fields` 即可。
- **ViewSet 标准 Mixins**：组合 `UserTrackingMixin` / `SoftDeleteMixin` / `DataScopeMixin`
  （均在 `apps.core.mixins`）。
- **审批工作流**：`WorkflowEnforcementMixin`（`apps.core.workflow.mixins`），
  设置 `workflow_business_type` / `workflow_amount_field` / `workflow_no_field`。
- **审计日志**：`AuditLogMiddleware` 自动记录所有变更。
- **编码规则**：业务编号通过 `CodeRule` 模型动态生成，不要硬编码前缀/序号格式。
- **前端权限三件套**：路由 `meta.permission`、`usePermissionStore().hasPermission()`、
  `v-permission` 指令——三者权限标识必须一致。
- **前端网络调用**：统一走 `frontend/src/utils/request.ts`，新接口在
  `frontend/src/api/<module>.ts` 按模块组织，**不要在视图组件里直接 `import axios`**。

## 微信小程序端

`miniprogram/` 是独立于 Vue 前端的微信小程序客户端，主打**移动审批**：

- 📋 移动审批：待办列表、详情、一键通过/拒绝、审批意见、撤回。
- 📁 项目管理：项目列表/详情、预算使用、任务进度。
- 📊 数据看板：财务概览、项目统计、库存概览、现金流预测。

> 改动 API 契约时需同步 `miniprogram/pages/` 与 `miniprogram/utils/request.js`。

## 文档索引

`docs/` 目录下提供完整文档：

| 文档 | 说明 |
|------|------|
| `docs/DEVELOPMENT_GUIDE.md` | 环境与部署详解 |
| `docs/REQUIREMENTS-PRD.md` | 原始需求规格说明书 |
| `docs/REQUIREMENTS-IMPLEMENTATION-MAPPING.md` | 需求-实现对照表 |
| `docs/业务流程手册.md` | 业务流程参考 |
| `docs/USER_MANUAL.md` | 用户操作手册 |
| `docs/SYSTEM_REQUIREMENTS.md` | 系统需求 |

在线 API 文档：

- Swagger UI：`/api/docs/`
- OpenAPI Schema：`/api/schema/`

## License

本项目为企业内部系统，版权归属相关权利人。如需开源或对外授权，请补充对应 License。
