# CLAUDE.md

# 项目约束

遵循根目录 [AGENTS.md](AGENTS.md)，按任务需要读取其中引用的文档。当前系统只维护 Lean ERP，旧架构文档不作为现行要求。

## 常用命令速查

后端测试使用 `config.test_settings`，必须显式提供独立库的 `PG_TEST_HOST`、`PG_TEST_USER`、`PG_TEST_PASSWORD`，不读取 `DB_*`：

```bash
# 在 backend/ 下运行单个测试模块、类或用例（Django 测试标签）
python manage.py test apps.business.tests.test_inventory --noinput --settings=config.test_settings
python manage.py test apps.business.tests.test_inventory.SomeTestCase.test_method --noinput --settings=config.test_settings

# 在仓库根目录运行静态检查（矩阵登记校验、Ruff check/format、manage.py check、迁移检查）
python run_all_tests.py --stage checks
python run_all_tests.py --stage business --plan-only   # 只打印阶段命令
```

- 模块 → 测试的映射只维护在 `scripts/ci/backend_test_matrix.py` 的 `MODULE_TESTS`/`TARGETS`；新增 `test_*.py` 必须登记，否则 checks 阶段的 `validate_coverage` 会失败。

## 架构要点

- 后端请求路径：`business/urls.py` → `business/api/<领域>.py`（DRF 视图、权限、范围过滤）→ `business/services/<领域>.py`（状态校验、加锁事务、ActionReceipt 去重）→ `business/models.py`（`BaseModel` 提供审计和软删除）。跨领域的写入逻辑放在 services，不写在视图或序列化器里。
- 权限按用户所有角色的并集判断，统一走 `apps/core/permissions.py` 的 `has_role`/`PermissionMixin`。前端导航和动作按钮只做展示层过滤，必须与后端角色一致。
- 前端：`src/business.ts` 只按资源分发到 `src/modules/<领域>.ts`（表单、动作定义）；HTTP 请求一律经过 `src/api/` 和 `src/utils/request.ts`。
- CI 按影响范围挑选测试：`scripts/ci/impact.py`、`select_suites.py` 计算要跑的模块，发版本强制发版验证，由 `release_gate.py` 核验能否复用同一代码树的结果。详见 `docs/CI_OPERATIONS.md`。
