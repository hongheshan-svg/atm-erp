# ERP 优化基线核对（2026-09-09）

## 范围已确认

用户随后明确要求“严格按 Lean ERP 约束重构”。下文为确认前的核对记录，阻塞已解除。

进一步检查 Git 未引用对象，找到完整候选源码树 `20d3ce96308c0c2d8d108a3e3ab1adfb6d8503d3`，包含与用户约束一致的 AGENTS、范围、接口及三条复用规则。已在 `codex/lean-rebuild-20260909` 通过源码补丁恢复，清理旧模块；恢复文件和历史验收文字均须重新验证。此前所说“未找到”仅指当时检查的分支，并非 Git 对象中完全没有成果。

完整旧版优化仍保存在 `cb762ed`，未应用。现存旧部署及其数据不参与 Lean 测试；新验证实例使用独立 `atm-erp-lean-rebuild-20260909` 项目和 18350 端口。

## 当前事实

- 当前工作分支为 `codex/remote-docker-20260909`，代码已按重新拉取请求恢复为 `origin/main` 的 `8fd47308ec6540471131e6ed86ffd70e4a91753e`。
- 本地 `codex/lean-erp` 也指向该提交；分支名称不能证明存在 Lean 实现。
- 当前远端分支为 `main`、`fix/workflow-approver-unresolved`；本轮未找到指定的 Lean 分支。
- `docs/CORE_ERP_SCOPE.md` 和 `docs/LEAN_REBUILD_CONTRACT.md` 在当前提交及本地 `codex/lean-erp` 中均不存在。
- 重置前的修改保存在 stash 提交 `cb762ed`，消息为 `backup-before-user-requested-remote-restore-20260909`。没有应用该备份，也没有删除备份。
- 本轮只做基线核对，没有重新部署、迁移数据库或运行业务验收。此前优化版的测试结果不适用于当前恢复后的源码。

## 与用户提供的仓库约束的差异

| 约束 | 当前源码证据 | 对后续工作的影响 |
| --- | --- | --- |
| 仅 core/accounts/business 三个业务 app | `backend/apps/` 包含 sales、purchase、inventory、finance、production、oa 等，缺少 business | 不能将本版本视为已完成模块收敛 |
| 固定六角色，无 Role 表和可配置工作流 | `backend/apps/accounts/models.py` 定义 Role；`backend/apps/core/workflow/` 存在 | 原有角色/审批修复不能直接作为 Lean 权限实现 |
| app 仅运行 Daphne、Nginx | `docker/app/supervisord.conf` 还运行 Celery worker、beat 和 upgrade-relay | 直接按远端启动不符合所给部署约束 |
| 无 updater、docker.sock | `docker-compose.yml` 定义 erp-updater 并挂载 Docker socket | 不应未经范围确认启动整套默认服务 |
| 无 WebSocket | `backend/config/asgi.py` 使用 Channels；settings 注册 channels | 保留现有代码不等于满足运行范围 |
| 按现行范围和接口文档验收 | 两份指定文档缺失 | 无法验证具体接口契约或宣称整体完成 |

## 备份中可供后续评估的工作

备份的 `docs/ERP_OPTIMIZATION_PROGRESS.md` 描述了菜单常用入口过滤、报价与订单写入复用、项目关联、BOM 到采购、分批收货、领料、交付、收付款及权限修复。它是历史记录，不是当前状态证明。

- 可优先复用设计与验证思路：保持 Element Plus 风格、获授权菜单过滤、明确的保存/提交动作、真实业务操作后的数量与金额核对、隔离测试地址与凭据。
- 需按最终模型重新评估实现：Role/工作流分派、分散业务 app 的服务、PaymentSchedule/CollectionPlan 等重叠事实、旧版字段权限。
- 不直接移植：旧部署编排、扩展模块及依赖、旧模型迁移和运行时服务。

## 后续验收边界

版本范围确认后，仍需逐项证明：界面风格保持；低频入口隐藏且权限不扩大；模块与接口符合范围；重复事实由单一服务维护；金额动作事务、加锁及幂等；软删除和审计；附件鉴权；销售至交付收款、BOM 至采购入库付款的真实操作链；异常与不同角色；可复用 skill；规定的前后端检查和 Docker 部署。

不能以恢复远端、单个样例跑通或历史测试通过代替整体完成。当前需要确定采用远端完整 ERP 范围，还是提供符合 Lean 约束的代码/契约；在此之前不恢复整份旧优化或执行改变数据库结构的部署。
