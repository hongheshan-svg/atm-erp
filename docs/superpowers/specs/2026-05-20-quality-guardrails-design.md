# Quality Guardrails for ERP

**Date:** 2026-05-20
**Status:** Draft, awaiting user approval
**Owner:** ERP maintainer

## 1. Background

The ERP system was largely written via Cursor in earlier iterations. Today's session uncovered the typical "AI big-edit" residue: a single multi-tool refactor catches "the happy path" but leaves syntactic / structural debt behind. In one ESLint pass we found and fixed **89 errors across 23 files**, including:

- 17 `error is not defined` (catch block closed too early, then a stray `console.error(..., error)` references the now-out-of-scope variable)
- 18 `request is not defined` (missing `import request from '@/utils/request'` in pages where `await request({...})` is called directly)
- 11 `selectedRows is not defined` (a rename was applied to the template/declaration but not to the handlers)
- 6 `data is not defined` (refactor renamed `response` to `data` in the body but left the `await` capturing it as `response`)
- 23 other miscellaneous missing imports / undefined function names

On the backend the same session found a "designed for one specific Excel file" bug in `bank_statement_views.py:107` where `header_row = 2` is hard-coded, causing imports to silently return all-zero counts when the user's Excel has the header on row 1.

There is currently **no CI**, **no pre-commit hook**, and **no integration tests** in the repository. Every Cursor-style bulk rewrite is shipped on trust.

This spec defines the smallest set of quality guardrails that would have prevented today's failures from reaching production, and that we can ship without changing application architecture.

## 2. Goals & Non-Goals

### Goals

1. **Catch the bug classes we hit today before they reach `main`** — undefined identifiers, dead code after malformed control flow, missing imports, type errors.
2. **Verify the six business-critical flows the user identified** — bank statement import, sales-order-to-project, stock_move + weighted average costing, RBAC data scope, workflow lifecycle, purchase chain.
3. **Run guardrails at two levels**: instant (pre-commit, < 5s) and thorough (云效 Flow CI, < 30 min).
4. **Make the first CI run green** by including baseline cleanup in the same delivery.

### Non-Goals

- TypeScript migration of the frontend (a separate sub-project)
- Refactoring large `views.py` / breaking up oversized files (a separate sub-project)
- Adding browser / E2E tests (Playwright, Cypress) — left for a future iteration
- Code coverage gating — would create an unreachable target given current test density
- Migrating off Cursor / changing primary editor

## 3. Architecture

```
                                   ┌──────────────────────────────────┐
                  本地 (开发者机)   │  pre-commit hook                  │
                                   │  ├─ ESLint  (frontend/**)         │
                                   │  ├─ ruff check + format (backend/**)│
                                   │  └─ no-commit-to-branch main       │
                                   └────────────┬─────────────────────┘
                                                │ commit / push
                                                ▼
                                   ┌──────────────────────────────────┐
                  阿里云云效 Flow  │  3 条独立流水线 (.workflow/*.yml) │
                  (Codeup origin)  │                                  │
                                   │  frontend.yml ← 触发: frontend/** │
                                   │    └─ npm ci + ESLint + vite build│
                                   │                                   │
                                   │  backend.yml  ← 触发: backend/**  │
                                   │    ├─ ruff (check + format --check)│
                                   │    ├─ pyright                      │
                                   │    └─ django unit tests           │
                                   │                                   │
                                   │  integration.yml ← 任一代码改动    │
                                   │    └─ pytest tests/integration/   │
                                   │       (六个核心业务流程)            │
                                   └──────────────────────────────────┘
```

### Why this split

| Decision | Reason |
|---|---|
| **3 条独立流水线** | 前端改动（多数情况）不应付出 7 分钟后端测试的代价。每条流水线可独立重跑。 |
| **pre-commit 只做 lint，不做类型检查 / 测试** | 慢于 5 秒的 hook 会被 `--no-verify` 绕过。pyright 启动就要 10-30 秒。 |
| **`no-commit-to-branch main`** | 强默认值: 强制 PR 评审，这是 ESLint / ruff / pyright / 集成测试集体把关 merge 的唯一地方。 |
| **集成测试独立一条流水线** | 后续添加每夜全量回归或其他重型作业时，不与 PR 反馈耦合。 |
| **阿里云云效 Flow，不是 GitHub Actions** | 服务器无法访问 GitHub。Codeup 已是主 origin，云效 Flow 与 Codeup 原生集成。 |

## 4. Component Design

### 4.1 pre-commit configuration

`.pre-commit-config.yaml` at repo root.

```yaml
repos:
  - repo: local
    hooks:
      - id: eslint
        name: ESLint (frontend)
        entry: bash -c 'cd frontend && npx eslint --max-warnings 0'
        language: system
        types_or: [javascript, vue]
        files: ^frontend/src/
        pass_filenames: true

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
        files: ^backend/
      - id: ruff-format
        files: ^backend/

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-merge-conflict
      - id: check-added-large-files
        args: [--maxkb=2000]
      - id: no-commit-to-branch
        args: [--branch, main]
```

> **关于 pre-commit 拉取 GitHub repos**: 服务器虽然 push 不到 GitHub，但 pre-commit 安装阶段（`pre-commit install`）仍要从 `github.com/astral-sh/ruff-pre-commit` 等仓库克隆 hook 实现。如果开发机有代理可访问 GitHub，正常工作。如果开发机也访问不了 GitHub，需要把这两个仓库改为本地 mirror（如 gitee 镜像），或将相应的 hook 实现内联为 `repo: local` 形式。**实施阶段需要确认开发机能否访问 github.com**，是 PR-2 的前置条件。

**Settings rationale:**

- `--max-warnings 0`: warnings accumulate if tolerated. Today's ESLint report had 0 errors / 124 warnings; if we accept warnings the count will silently grow back into bug territory.
- `pass_filenames: true`: only lints changed files, keeps the hook in 100ms territory.
- `--maxkb=2000`: large enough to allow the existing `BOM_import_template.xlsx` (~1.1 MB) at repo root, small enough to block accidental DB dumps.
- `no-commit-to-branch main`: behavioural change for the team — `main` becomes PR-only. Must be applied **after** PR-1 and PR-2 are merged, otherwise the hook would block the very PRs that install it.

### 4.2 frontend pipeline

`.workflow/frontend.yml`:

```yaml
name: frontend-ci
sources:
  repo:
    type: codeup
    name: erp
    endpoint: https://codeup.aliyun.com/68b3e811efefeec54ed61a32/erp.git
    branch: main
    triggerEvents:
      - push
      - merge_request
    # paths 过滤 — 仅当 frontend/ 改动时触发
    triggerFilters:
      paths:
        - frontend/**
        - .workflow/frontend.yml

stages:
  lint_and_build:
    name: ESLint and Build
    jobs:
      job:
        name: frontend-lint-build
        runsOn: public/cn-hangzhou       # 阿里云公共构建集群; 区域按需调整
        steps:
          install:
            step: NodeBuild
            name: install deps
            with:
              nodeVersion: '20'
              workingDir: frontend
              run: |
                npm ci --legacy-peer-deps
          eslint:
            step: Shell
            name: ESLint
            with:
              workingDir: frontend
              run: npx eslint src --max-warnings 0
          build:
            step: Shell
            name: Vite build
            with:
              workingDir: frontend
              run: npm run build
```

关键决策:

| Decision | Reason |
|---|---|
| **`npm ci` 而不是 `npm install`** | CI 必须用 lockfile，避免"我本机能跑 CI 跑不了"。今天已生成新 lockfile (含 eslint deps). |
| **`--legacy-peer-deps`** | Dockerfile 里就是这么装的（element-plus 等旧 peer dep 必需），保持一致。 |
| **跑 `npm run build`** | ESLint 是静态检查，build 才能验证 import 路径真实存在 / 编译能过。今天那 18 处 `request is not defined`，ESLint 拦得住，即使没拦住 build 也会失败。两道防线。 |
| **`triggerFilters.paths`** | 仅当 frontend 目录变化时触发，避免后端改动浪费构建资源。 |

> **云效 Flow 语法 caveat**: `triggerFilters.paths` 的精确字段名以及 `NodeBuild` step 是否原生支持 cache，本 spec 撰写时未经实机验证。实施阶段第一步是在云效控制台用图形向导建一条最简流水线，再导出 YAML 作为基线模板。本文档给出的是预期形态，**实施时以云效官方组件库为准**。

### 4.3 backend pipeline

`.workflow/backend.yml`:

```yaml
name: backend-ci
sources:
  repo:
    type: codeup
    name: erp
    endpoint: https://codeup.aliyun.com/68b3e811efefeec54ed61a32/erp.git
    branch: main
    triggerEvents:
      - push
      - merge_request
    triggerFilters:
      paths:
        - backend/**
        - .workflow/backend.yml

stages:
  lint_and_type:
    name: Lint and Type Check
    jobs:
      job:
        name: ruff-pyright
        runsOn: public/cn-hangzhou
        steps:
          setup:
            step: PythonBuild
            name: install deps
            with:
              pythonVersion: '3.11'
              workingDir: backend
              run: |
                pip install -r requirements.txt
                pip install -r requirements-dev.txt
          ruff_check:
            step: Shell
            name: Ruff check
            with:
              workingDir: backend
              run: ruff check .
          ruff_format:
            step: Shell
            name: Ruff format --check
            with:
              workingDir: backend
              run: ruff format --check .
          pyright:
            step: Shell
            name: Pyright
            with:
              workingDir: backend
              run: pyright

  unit_test:
    name: Django Unit Tests
    dependsOn: lint_and_type     # 节省构建集群: lint 通过后再跑测试
    jobs:
      job:
        name: django-test
        runsOn: public/cn-hangzhou
        # 关键: 该 step 需要 postgres + redis。云效 Flow 没有 GitHub Actions 那种
        # 原生 services 块，需要在 step 内通过 docker 命令启动 sidecar 容器。
        steps:
          start_services:
            step: Shell
            name: Start postgres and redis
            with:
              run: |
                docker run -d --name pg \
                  -e POSTGRES_DB=erp_test \
                  -e POSTGRES_USER=erp_user \
                  -e POSTGRES_PASSWORD=erp_password \
                  -p 5432:5432 postgres:15-alpine
                docker run -d --name redis -p 6379:6379 redis:7-alpine
                # 等待 postgres 就绪
                for i in $(seq 1 30); do
                  docker exec pg pg_isready -U erp_user && break
                  sleep 1
                done
          setup:
            step: PythonBuild
            with:
              pythonVersion: '3.11'
              workingDir: backend
              run: pip install -r requirements.txt
          django_check:
            step: Shell
            with:
              workingDir: backend
              run: python manage.py check
          tests:
            step: Shell
            with:
              workingDir: backend
              env:
                DB_HOST: localhost
                DB_PORT: '5432'
                DB_NAME: erp_test
                DB_USER: erp_user
                DB_PASSWORD: erp_password
                REDIS_URL: redis://localhost:6379/1
                CELERY_BROKER_URL: redis://localhost:6379/0
                SECRET_KEY: ci-test-key
                DEBUG: 'False'
              run: python manage.py test --verbosity 2
```

关键决策:

| Decision | Reason |
|---|---|
| **拆 2 个 stage (lint_and_type → unit_test)** | lint 不需要数据库，1-2 分钟出结果；unit_test 需要 postgres+redis，慢。串行依赖避免无效测试运行（lint 不过就没必要跑测试）。 |
| **`docker run` 启动 sidecar** | 云效 Flow YAML 没有 GitHub Actions 风格的 `services:` 顶层字段；通过 `runsOn` 的构建集群提供的 Docker daemon 启动容器是惯例。**实施阶段需在云效控制台确认 `public/cn-hangzhou` 镜像确实预装 docker**。 |
| **加 `ruff` / `pyright`，不加 `mypy`** | 一个类型检查工具就够。pyright 更快、Django/DRF 支持更好。 |
| **`ruff format --check`** | CI 只检查格式不动文件——格式化是 pre-commit 干的活。 |

### 4.4 integration pipeline

`.workflow/integration.yml`:

```yaml
name: integration-ci
sources:
  repo:
    type: codeup
    name: erp
    endpoint: https://codeup.aliyun.com/68b3e811efefeec54ed61a32/erp.git
    branch: main
    triggerEvents:
      - push
      - merge_request
    triggerFilters:
      paths:
        - backend/**
        - frontend/**
        - docker/**
        - docker-compose.yml
        - .workflow/integration.yml
        - backend/tests/integration/**

stages:
  integration:
    name: Integration Flows
    jobs:
      job:
        name: pytest-integration
        runsOn: public/cn-hangzhou
        steps:
          start_services:
            step: Shell
            name: Start postgres and redis
            with:
              run: |
                docker run -d --name pg \
                  -e POSTGRES_DB=erp_test \
                  -e POSTGRES_USER=erp_user \
                  -e POSTGRES_PASSWORD=erp_password \
                  -p 5432:5432 postgres:15-alpine
                docker run -d --name redis -p 6379:6379 redis:7-alpine
                for i in $(seq 1 30); do
                  docker exec pg pg_isready -U erp_user && break
                  sleep 1
                done
          setup:
            step: PythonBuild
            with:
              pythonVersion: '3.11'
              workingDir: backend
              run: |
                pip install -r requirements.txt
                pip install -r requirements-dev.txt
          bootstrap:
            step: Shell
            with:
              workingDir: backend
              env:
                DB_HOST: localhost
                DB_PORT: '5432'
                DB_NAME: erp_test
                DB_USER: erp_user
                DB_PASSWORD: erp_password
                REDIS_URL: redis://localhost:6379/1
                SECRET_KEY: ci-test-key
              run: |
                python manage.py migrate --noinput
                python manage.py init_permissions
                python manage.py init_roles --force
                python manage.py init_industry_roles --force
          tests:
            step: Shell
            with:
              workingDir: backend
              env:
                DB_HOST: localhost
                DB_PORT: '5432'
                DB_NAME: erp_test
                DB_USER: erp_user
                DB_PASSWORD: erp_password
                REDIS_URL: redis://localhost:6379/1
                SECRET_KEY: ci-test-key
              run: pytest tests/integration -v
```

**6 个流程的覆盖** — 与原方案一致，放在 `backend/tests/integration/`，目录布局和 `conftest.py` 见 §4.6。

### 4.5 Backend configuration files

**`backend/pyproject.toml`** (new):

```toml
[tool.ruff]
line-length = 120
target-version = "py311"
extend-exclude = ["migrations", "*/migrations/*"]

[tool.ruff.lint]
select = [
  "E",    # pycodestyle errors
  "F",    # pyflakes (undefined names, unused imports — same class as today's frontend bugs)
  "W",    # pycodestyle warnings
  "I",    # isort
  "B",    # bugbear (mutable default args, etc.)
  "DJ",   # django-specific
]
ignore = [
  "E501",  # line too long — keep as warn, but ruff format handles most
  "B008",  # function call in default argument (DRF/Django uses this idiom)
]

[tool.ruff.lint.per-file-ignores]
"settings.py" = ["F405", "F403"]  # star imports in settings
"*/migrations/*" = ["E501", "F401"]

[tool.ruff.format]
quote-style = "single"
```

**`backend/pyrightconfig.json`** (new):

```json
{
  "include": ["apps", "config"],
  "exclude": ["**/migrations", "**/__pycache__"],
  "venvPath": ".",
  "venv": "venv",
  "pythonVersion": "3.11",
  "typeCheckingMode": "basic",
  "reportMissingImports": "error",
  "reportUndefinedVariable": "error",
  "reportInvalidTypeForm": "error",
  "reportGeneralTypeIssues": "warning",
  "reportOptionalMemberAccess": "warning",
  "reportArgumentType": "none",
  "reportAttributeAccessIssue": "none"
}
```

Rationale: with Django ORM, `Model.objects.filter(...).first()` returns `Model | None`, and most existing code accesses fields without checking — turning `reportOptionalMemberAccess` to `error` would create ~500 false positives. We start with `basic` mode and only escalate the rules that correspond to today's bug classes (`reportUndefinedVariable`, `reportMissingImports`).

**`backend/requirements-dev.txt`** (new):

```
ruff==0.6.9
pyright==1.1.385
pytest==8.3.3
pytest-django==4.9.0
```

Kept separate from `requirements.txt` so the production Docker image doesn't ship lint tools.

**`backend/requirements.txt`**: no changes — pytest moves to dev-only.

### 4.6 Integration test layout

```
backend/tests/
  __init__.py
  integration/
    __init__.py
    conftest.py
    test_bank_statement_import.py
    test_sales_order_to_project.py
    test_stock_move_costing.py
    test_rbac_data_scope.py
    test_workflow_lifecycle.py
    test_purchase_chain.py
```

`conftest.py` provides shared fixtures:

- `admin_user` — `User` with `is_superuser=True`
- `api_client_admin` — `APIClient` with JWT bearer token
- `make_customer(name=...)`, `make_supplier(...)`, `make_project(...)`, `make_item(...)` — factory helpers that create minimal valid instances

**Per-file assertion sketches** (the *what*, not the *how* — implementation details belong in the writing-plans step):

| File | Covers |
|---|---|
| `test_bank_statement_import.py` | Header detection at row 1 / 3 / unrecognized; internal-fee skipping; duplicate skipping; auto-match supplier/customer at confidence ≥ 70 |
| `test_sales_order_to_project.py` | Posting `SalesOrder` to the DRF API without `project` returns 4xx; creating SO from accepted Quotation; project BOM creation hook |
| `test_stock_move_costing.py` | Two inbound moves at different prices yield correct weighted unit_cost; outbound consumes weighted price not last price |
| `test_rbac_data_scope.py` | Three roles (`scope=all/dept/own`) hitting `/api/masterdata/customers/` return correctly filtered counts |
| `test_workflow_lifecycle.py` | Submit → reject returns to DRAFT; submit → approve advances to APPROVED and triggers downstream state change |
| `test_purchase_chain.py` | PR approved → PO generated → goods receipt → stock quantity and weighted cost both updated |

Each file: 3–5 test functions. Target file size 100–150 lines.

## 5. Data Flow

There's no application data flow to describe — these are quality-control workflows, not features. The data flow is **commit/PR → guardrail → fail-or-merge**.

- A developer changes `frontend/src/foo.vue`
  → `.pre-commit-config.yaml` runs ESLint on that file in < 1s
  → if pass, commit succeeds and is pushed
  → `git push` to `origin` (Codeup) triggers `frontend-ci` pipeline in 云效 Flow
  → ESLint + vite build in ~4 min
  → branch protection on `main` blocks merge unless workflow is green

For backend the parallel path triggers `backend.yml` (lint+type+unit) and `integration.yml`.

## 6. Error Handling

### 6.1 What "error" means here

- Pre-commit hook failure → commit aborted, developer fixes locally
- 云效 Flow pipeline failure → MR can't merge (Codeup branch protection rule)
- A flaky integration test → re-run that workflow; if persistent, the test gets `@pytest.mark.flaky` with a TODO and a tracking issue

### 6.2 Baseline failure modes & mitigations

We **know** these will fail on first run, so we mitigate before merging PR-2:

| Failure | Mitigation |
|---|---|
| `ruff check .` finds hundreds of issues across `backend/` | PR-1 runs `ruff check --fix .` + `ruff format .` and commits the result before PR-2. Remaining style rules like `E501` (line too long) are listed in `pyproject.toml`'s `ignore` block so they do not block CI. |
| `pyright` reports false positives on Django ORM | `pyrightconfig.json` set to `typeCheckingMode: "basic"` with narrow rule overrides; `django-stubs` not added in this iteration (defer cost) |
| `python manage.py test` discovers broken `test_*.py` left from earlier work | Triage: working tests stay; broken ones get `@pytest.mark.skip("legacy, broken since YYYY")` with a tracking comment |
| `pre-commit no-commit-to-branch main` would block PR-1 / PR-2 from being merged into `main` | Install hook **after** PR-2 is merged, not before. The PR description includes the install step. |
| Codeup `origin` stays on its own branch while CI runs against `backup` | N/A: CI runs on the same Codeup origin. |
| 云效 Flow YAML 与 GitHub Actions 在 services / cache / matrix 上的语义差异 | 第一条流水线先用云效图形向导建出来导出 YAML 作为基线，再在 spec / writing-plans 中把握具体字段。本 spec 给出的 YAML 是预期形态，实施时以云效官方组件库为准。 |
| 云效构建集群是否预装 docker（用于 sidecar postgres/redis） | 实施第一步在云效控制台选 `runsOn` 时检查；若公共集群不行，切到「自有主机组」或换用云效 RDS / Redis 测试实例 |
| pre-commit 拉取 GitHub 的 hook 仓库 | 服务器访问不到 GitHub，但本地开发机大概率能访问。如果开发机也不行，spec 实施阶段把 `ruff-pre-commit` 和 `pre-commit-hooks` 改为本地内联或换 gitee 镜像 |

### 6.3 Test isolation

- All integration tests use `pytest.mark.django_db` for transaction rollback between tests
- No test depends on order with another
- No test depends on data outside fixtures or `init_permissions` / `init_roles` output

## 7. Testing Strategy

This spec **is** the testing strategy for the application; but the guardrails themselves also need verification:

| Layer | Verification |
|---|---|
| `.pre-commit-config.yaml` syntax | `pre-commit run --all-files` locally before pushing PR-2 |
| Pipeline YAML syntax | 在云效控制台用图形向导建一条最简流水线、导出 YAML，对照本 spec 校对字段名（云效官方组件库为准）。 |
| Workflow actually runs | After merging PR-2, push a test commit that touches `frontend/` only and confirm only `frontend.yml` runs |
| Integration test logic | Each test must be designed so that **reverting the fix would make it fail**. Bank statement test 1 specifically asserts `header_row == 1` — this would fail on the old `header_row = 2` hard-coded code. |

## 8. Delivery Plan

This spec ships as **two consecutive PRs**, both against `main`:

### PR-1: chore: baseline ruff cleanup

- Run `ruff check --fix . && ruff format .` in `backend/`
- Single commit with the result
- Title: `chore(backend): apply ruff --fix and format baseline`
- No behavioural code changes
- Must merge before PR-2

### PR-2: feat(ci): quality guardrailsAll other files listed in §4 plus:

- `.pre-commit-config.yaml`
- `.workflow/{frontend,backend,integration}.yml`
- `backend/pyproject.toml`, `backend/pyrightconfig.json`
- `backend/requirements-dev.txt`
- `backend/tests/integration/` (6 test files + conftest)
- `docs/superpowers/specs/2026-05-20-quality-guardrails-design.md` (this file)
- Update root `README.md` or `CLAUDE.md` with: "running tests" + "installing pre-commit"

Post-merge:
1. 在云效控制台导入 `.workflow/*.yml` 创建三条流水线，关联 Codeup origin 仓库
2. 配置 Codeup 分支保护：`main` 分支要求三条流水线（frontend-ci / backend-ci / integration-ci）全部成功才能 merge MR
3. 每位开发者本地执行：`pip install pre-commit && pre-commit install`
4. （可选）当服务器网络可访问 GitHub 时，把 backup remote 重新指向 `hongheshan-svg/atm-erp` 并 push，作为代码镜像

## 9. Open Questions

None at design time. Open items are listed as **risks** in §6.2, not unknowns.

## 10. Out of scope (future work)

- TypeScript migration of frontend
- `vue/no-mutating-props` is currently `warn` — escalate to `error` after the warning count drops below a threshold
- Backend hotspot refactoring (`views.py` 1000+ lines, ViewSet decomposition)
- Add `django-stubs` for accurate ORM type narrowing
- Coverage threshold gating
- Playwright / browser-level E2E
- Documenting which legacy `test_*.py` files were skipped, and resurrecting them
