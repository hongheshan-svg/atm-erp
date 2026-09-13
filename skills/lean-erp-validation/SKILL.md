---
name: lean-erp-validation
description: 修改 Lean ERP 业务写入、权限、金额、库存或跨角色操作链，以及验收这些行为时使用；纯文案、静态样式和只读说明不触发。
---

# Lean ERP 业务变更验证

适用于当前 `core/accounts/business` 架构及其 Vue 前端的业务行为验证，包含账号兼岗、共享授权与幂等机制变更；不加载旧版分散业务 app 的验证技能。纯文档技能维护只检查说明与引用，不启动业务验收。

## 按任务读取

- `docs/`、`backend/`、`frontend/`、`scripts/` 路径均相对仓库根目录；本技能的 Markdown 相对链接按技能文件所在目录解析。
- 已加载且未变化的 AGENTS.md 不重复读取。范围变化查 `docs/CORE_ERP_SCOPE.md`；接口、字段和业务动作变化查 `docs/LEAN_REBUILD_CONTRACT.md` 对应章节；模块边界变化查 `docs/MODULE_BOUNDARIES.md`。
- 涉及业务写入、金额、库存、权限、工程变更或预算时，读取 [业务检查](references/business-checks.md) 对应段落；完整业务验收读取全部。保留原约束，不复制测试目标清单。
- 角色或数据范围变化先查 `docs/ROLE_RESPONSIBILITIES.md`，再读业务检查的“岗位与兼岗”；BOM 选料、导入、编码或采购交互变化读“BOM、物料与同屏采购”。按实际动作选择用例，不用管理员成功代替岗位验证。

## 验证与完成

- 后端测试目标唯一来源为 `scripts/ci/backend_test_matrix.py`，新增测试模块只在此登记；在根目录用 `python run_all_tests.py --stage checks` 或选择 `platform`、`business`、`concurrency` 阶段，`--plan-only` 可先查看命令。执行数据库测试须显式配置独立 `PG_TEST_HOST/USER/PASSWORD`。仅打 tag 发版本时执行 `bash scripts/precheck-tests.sh --all`（独立 PostgreSQL）；发布仍需完整 GitHub CI 通过、合并 main 后打 tag。
- 前端按影响运行 lint、typecheck、test、build 和相关 e2e；日常只跑受影响用例，打 tag 发版本时运行全部。依赖缺失、锁文件变化、依赖异常或干净CI环境才需 `npm ci`。构建体积警告须调查，不能调高阈值冒充优化。
- 浏览器显式给出隔离安装的 `E2E_BASE_URL` 和 `E2E_ADMIN_PASSWORD`，不从生产配置推测。完整链路 `frontend/e2e/full-chain.spec.ts`；核对断言和实际业务结果，ORM夹具不能证明页面链可操作。
- 前端命令在 `frontend/` 执行；例如 `npm run test -- src/components/BOMPurchasePicker.spec.ts`，或在设置上述隔离凭据后执行 `npm run test:e2e -- e2e/bom-purchase-layout.spec.ts --project=desktop`。交互布局变化按影响覆盖 desktop/mobile；完整发布覆盖两端全部用例。这些是定位示例，不是第二份测试矩阵。
- 同一源码、依赖、配置和目标镜像已有成功证据可复用；新变更、失败、环境变化或未解决风险才重跑相应检查。发布复用须由 `scripts/ci/release_gate.py` 核验。
- 在已授权且目标明确的隔离环境完成实现、启动、检查、修复和受影响复验，不在初版后自行停止等确认；不扩展到生产、其他实例、外部消息或绕过权限审批。
- 源码、浏览器镜像和证据须对应；实际看过截图后才能声称视觉通过。某项验证受阻时继续独立的已授权工作，明确未覆盖项，不伪造通过、不绕过发布门禁。
- 部署及供用户检查的预览站点使用安装流程，独立项目、新卷并确认真实升级执行器心跳；仅隔离CI可显式跳过服务注册。schema guard拒绝时不得清库或绕过。Docker 恢复用 `scripts/backup.py`，目标须独立且符合空库检查；原生部署按 `README.md` 配套备份 PostgreSQL、附件和配置，不套用 Compose 恢复脚本。
- 安装器或 OTA 有变化时按影响检查 `scripts/tests/` 的对应测试与相关工作流；正式 Docker 包使用 CI 预构建镜像、校验后导入或锁定 digest，原生包使用已校验 wheelhouse 离线安装。不能以现场构建成功代替发布包验证，也不能用健康页代替执行器真实心跳。
- 业务变更和正式验收在 `docs/SIMPLIFICATION_EVIDENCE.md` 记录结果及未覆盖项；纯说明/文案任务无需新增验收流水。局部通过不代表全系统完成，不为技能新增常驻服务。
