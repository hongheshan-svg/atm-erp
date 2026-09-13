# Repository Guidelines

## 项目范围与依据

面向约 50 人非标自动化公司，只保留工作台、经营报表、销售、项目、BOM、采购、库存、收付款、基础资料和设置；不要重新引入已删除扩展。范围变化查 docs/CORE_ERP_SCOPE.md，接口/字段/业务动作变化查 docs/LEAN_REBUILD_CONTRACT.md 对应章节，模块边界变化查 docs/MODULE_BOUNDARIES.md。引用文档不等于每次全文阅读；已加载且未变化的内容不重复读取。

## 目录与代码约定

- Python 3.11 / Django REST Framework 后端，Vue 3 + TypeScript + Element Plus 前端，Node.js 22，PostgreSQL 15 + Redis 7。
- `backend/apps/` 仅 `core/accounts/business`；领域接口在 `business/api/`，状态校验与事务写入在 `business/services/`。前端页面在 `frontend/src/views/`，模块表单与动作在 `src/modules/`，共享组件在 `src/components/`，静态资源在 `src/assets/`；`business.ts` 只分发资源。
- Python 使用四空格、snake_case，Ruff 配置见 `backend/pyproject.toml`（120 列、单引号）；Vue/TypeScript 沿用两空格、单引号、组件 PascalCase，使用 ESLint 和 vue-tsc，不为局部变更全库格式化。
- 前端统一走 `frontend/src/utils/request.ts` 和 `src/api/`；页面不直接 import axios。主路径 `/erp/`，业务 API `/api/business/`。附件只走鉴权下载。

## 业务与权限不变量

- 本地 app 仅 core/accounts/business。只支持独立新数据库，schema guard 拒绝旧表、旧迁移和回滚；禁止清库或绕过保护。
- 按用户新增要求固定 admin/manager/sales_manager/purchaser/warehouse/finance/member/purchase_manager/mechanical_engineer/electrical_engineer/production_manager 十一角色，允许一个账号兼任多个角色，无 Role 表、权限树或可配置工作流。岗位职责见 docs/ROLE_RESPONSIBILITIES.md。权限按业务取各岗位的并集，通过 core.permissions.has_role/PermissionMixin 授权，不按主角色判权。采购经理可跨项目采购审批，但不自动获得项目管理或完整成本权限；工程师仅在参与项目维护 BOM 和技术资料。生产经理仅管理参与项目的装配、调试、安装和售后任务及团队工时，保内免费售后可创建，收费确认及涉及账款的取消/重开由项目经理处理；不自动获得设计派工、发货验收、预算、BOM写入或资金权限。兼任采购不扩大工程或生产写入范围。仅销售经理权限时只操作本人销售单；兼任采购不扩大销售范围，兼任成员只开放参与项目，兼任财务可按财务权限读取销售但不能修改他人销售。签约指定具备 manager/admin 的项目经理。成员项目范围、敏感金额过滤、已有按人员身份的审批约束与总经理报表独立授权不可省略。
- 经营报表为固定只读页面，管理员默认可看；总经理沿用 manager 角色并由管理员显式设置 management_reports 授权，默认关闭，不向所有项目经理开放。
- BaseModel 提供审计和软删除；业务查询用 objects，删除用 soft_delete。金额流水不能物理删除，纠错保留原记录。
- 编号用 CodeRule.generate_code；采购、库存、收付款必须事务加锁与服务端校验，重复提交用 ActionReceipt，不信任前端金额。
- 金额为 CNY 含税经营口径，不替代法定会计账。一个事实一处维护；见 docs/SIMPLIFICATION_EVIDENCE.md 三条复用规则。
- BOM 与采购复用 `BOMPurchasePicker.vue`；以稳定 `bom_line` 关联明细，不按物料合并多单元行。前端金额只作预览，服务端锁内重验缺口与金额。工程权限、采购权限与项目管理权限分别判断。

## 安装与配置

- 全新安装用 install.sh/install.ps1，默认独立 atm-erp-lean 项目和新卷，服务仅 postgres/redis/app；app 只运行 Daphne、Nginx，无 Celery、WebSocket、docker.sock。按用户新增要求，安装器默认通过 scripts/ota_service.py 自动注册、启动并保活宿主机执行器 scripts/ota_runner.py，确认真实心跳；仅隔离 CI 可显式跳过服务注册。仅管理员发起固定仓库正式版升级，执行器校验 SHA256、先备份后迁移，不回退或清空数据库。
- Docker 开发配置 `LEAN_ENVIRONMENT=development`，直接运行后端用 `APP_ENVIRONMENT=development`，关闭登录限流；发布部署必须使用 production（默认值），恢复原10次/分钟限制，不能把开发配置直接沿用到发布环境。DEBUG 不随开发标记开启。密钥和账号配置不提交 Git。

## 开发与测试

- 后端在 `backend/` 安装 `requirements-dev.txt`，显式配置 `SECRET_KEY`、`DB_*`、`REDIS_URL`、`ADMIN_PASSWORD`，针对独立新库执行 `python manage.py migrate`、`python manage.py init_system`；本地启动用 `python manage.py runserver 127.0.0.1:18301`。初始化不重置已有密码。
- 前端在 `frontend/` 执行 `npm run dev`，默认 `127.0.0.1:18310/erp/`，API 代理默认 `127.0.0.1:18301`，可用 `VITE_API_BASE_URL` 指定后端。
- 后端 Django 测试放在 `backend/apps/*/tests/test_*.py`，新增模块登记到测试矩阵；Vitest 用例为 `frontend/src/**/*.spec.ts`，Playwright 用例在 `frontend/e2e/*.spec.ts`。按行为覆盖成功、拒绝、范围与回滚，不设虚构的覆盖率门槛。
- 全链条验证仅在用户要求打 tag 发版本时执行；普通提交、push 和合并 main 不自动触发全量，按影响补做针对性检查。发布仍须完整验证通过，不能以普通 PR 绿灯代替。
- 后端局部变更在根目录运行 `python run_all_tests.py --stage checks`（Ruff、Django 检查、迁移检查）或选择 `platform`、`business`、`concurrency` 阶段；测试显式提供独立 `PG_TEST_HOST/USER/PASSWORD`。用 `--plan-only` 查看命令而不执行。仅打 tag 发版本时执行 `bash scripts/precheck-tests.sh --all`（独立 PostgreSQL）。测试目标只维护在 `scripts/ci/backend_test_matrix.py`，不复制名单。纯文档改动检查内容一致性及链接，不无条件运行业务测试。
- 前端在 frontend 按影响运行 npm run lint、typecheck、test、build 及相关 test:e2e；日常只跑受影响用例，打 tag 发版本时运行全部。npm ci 用于依赖缺失、锁文件变化、依赖异常或干净CI环境。浏览器必须显式指定隔离测试 URL 和管理员密码，不读取生产配置。同一源码、依赖、配置和目标镜像的成功证据可复用；新变更、失败或未解决风险才重跑相应检查，发布CI复用由 scripts/ci/release_gate.py 核验。
- 已授权且目标明确的隔离测试可连续执行、修复并复验，无需逐步确认；实现任务完成所需启动、检查和修复后再交付，不在初版后自行暂停。不得扩大到生产、其他部署或外部消息，不绕过沙箱审批。某项验证受阻时继续独立工作并说明未覆盖项，不能声称通过或越过发布门禁。供用户检查的预览站点也须完成安装器的升级服务注册和真实心跳验证，不视作可跳过服务的隔离CI。

## Agent 与技能协作

- ERP业务验证使用 [skills/lean-erp-validation/SKILL.md](skills/lean-erp-validation/SKILL.md)；旧架构技能不适用。全局同名技能仅作定位入口，业务规则只在仓库版维护。纯文案、静态样式和只读说明不触发业务验证技能；其他专用技能仅在任务确实需要时使用，不因出现URL、文件名或技术关键词就加载。更新技能时同步核对其 references，避免复制岗位文档和测试矩阵。
- 用户明确要求先审阅方案时，停在审阅边界；已选定方案或已授权实现时，不重复请求同一确认。必要信息缺失时先完成不依赖它的工作，只询问仍然阻塞的事项。规则说明和测试结果如有差异应如实报告，不以修改说明代替修复行为。

## 提交、PR 与发布

- 使用 feature branch，不直接提交 main；保留用户未提交改动。使用 apply_patch 修改源码，按实际行为补测试。提交沿用 `feat:`、`fix:`、`chore:`、`ci:` 等前缀，文档使用 `docs:`。PR 说明实际变化、影响与验证结果，关联已有问题；界面变化附实际截图，未覆盖检查明确列出。
- 发布说明使用 docs/releases/TEMPLATE.md，在最下方保留 Installation 与 Documentation 区块，替换实际 tag 并核对附件名称。按用户新增要求，GitHub 预构建 Docker amd64/arm64 镜像，安装器仅拉取固定 digest 或校验导入随包镜像，不回退本地构建；原生包携带 CI 预编译 wheelhouse 离线安装依赖，不现场编译。不编造公开可用的 GHCR 地址，完整安装说明保留在 README。
- 日常发布默认只递增补丁号（如 1.0.0 → 1.0.1）；除非用户明确指定，不自行提升主版本号或次版本号。以后端、前端和 tag 一致的版本发布，并在完整 CI 通过、合并 main 后打 tag。
- 版本核对 `backend/apps/core/version.py`、`frontend/package.json` 及锁文件，不从 README 的旧版本横幅推断。CI 操作见 `docs/CI_OPERATIONS.md`；发布凭据须为同一 Git tree 的完整 `ci.yml` 成功记录（含 desktop/mobile），单项工作流和普通 PR 绿灯不能替代。
- 历史 docs/superpowers、审计报告与旧部署文档仅作参考，不是现行要求。
