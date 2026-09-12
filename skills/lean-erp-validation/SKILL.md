---
name: lean-erp-validation
description: 修改 Lean ERP 业务写入、权限、金额、库存或跨角色操作链，以及验收这些行为时使用；纯文案、静态样式和只读说明不触发。
---

# Lean ERP 业务变更验证

仅适用于 `backend/apps/business` 的 Lean 实现；不加载旧版分散业务 app 的验证技能。

## 按任务读取

- 已加载且未变化的 AGENTS.md 不重复读取。范围变化查 `docs/CORE_ERP_SCOPE.md`；接口、字段和业务动作变化查 `docs/LEAN_REBUILD_CONTRACT.md` 对应章节；模块边界变化查 `docs/MODULE_BOUNDARIES.md`。
- 涉及业务写入、金额、库存、权限、工程变更或预算时，读取 [业务检查](references/business-checks.md) 对应段落；完整业务验收读取全部。保留原约束，不复制测试目标清单。

## 验证与完成

- 后端测试目标唯一来源为 `scripts/ci/backend_test_matrix.py`；按影响选择 `python run_all_tests.py --stage checks/platform/business/concurrency`。发布、全系统验收或广泛业务变更执行 `bash scripts/precheck-tests.sh --all`（独立 PostgreSQL）；发布仍需完整 GitHub CI 通过、合并 main 后打 tag。
- 前端按影响运行 lint、typecheck、test、build 和相关 e2e；完整验收运行全部。依赖缺失、锁文件变化、依赖异常或干净CI环境才需 `npm ci`。构建体积警告须调查，不能调高阈值冒充优化。
- 浏览器显式给出隔离安装的 `E2E_BASE_URL` 和 `E2E_ADMIN_PASSWORD`，不从生产配置推测。完整链路 `frontend/e2e/full-chain.spec.ts`；核对断言和实际业务结果，ORM夹具不能证明页面链可操作。
- 同一源码、依赖、配置和目标镜像已有成功证据可复用；新变更、失败、环境变化或未解决风险才重跑相应检查。发布复用须由 `scripts/ci/release_gate.py` 核验。
- 在已授权且目标明确的隔离环境完成实现、启动、检查、修复和受影响复验，不在初版后自行停止等确认；不扩展到生产、其他实例、外部消息或绕过权限审批。
- 源码、浏览器镜像和证据须对应；实际看过截图后才能声称视觉通过。某项验证受阻时继续独立的已授权工作，明确未覆盖项，不伪造通过、不绕过发布门禁。
- 部署及供用户检查的预览站点使用安装流程，独立项目、新卷并确认真实升级执行器心跳；仅隔离CI可显式跳过服务注册。schema guard拒绝时不得清库或绕过；恢复用 `scripts/backup.py`，目标须独立且符合空库检查。
- 业务变更和正式验收在 `docs/SIMPLIFICATION_EVIDENCE.md` 记录结果及未覆盖项；纯说明/文案任务无需新增验收流水。局部通过不代表全系统完成，不为技能新增常驻服务。
