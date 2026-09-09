# Repository Guidance: Lean ERP

面向约 50 人非标自动化公司，只保留工作台、销售、项目、BOM、采购、库存、收付款、基础资料和设置。范围以 docs/CORE_ERP_SCOPE.md 为准，接口以 docs/LEAN_REBUILD_CONTRACT.md 为准；不要重新引入已删除扩展。

- Django REST Framework 后端，Vue 3 + TypeScript + Element Plus 前端，PostgreSQL 15 + Redis 7。
- 本地 app 仅 core/accounts/business。只支持独立新数据库，schema guard 拒绝旧表、旧迁移和回滚；禁止清库或绕过保护。
- 固定 admin/manager/purchaser/warehouse/finance/member 六角色，无 Role 表、权限树或可配置工作流。通过 core.permissions/PermissionMixin 授权，成员项目范围与敏感金额过滤不可省略。
- BaseModel 提供审计和软删除；业务查询用 objects，删除用 soft_delete。金额流水不能物理删除，纠错保留原记录。
- 编号用 CodeRule.generate_code；采购、库存、收付款必须事务加锁与服务端校验，重复提交用 ActionReceipt，不信任前端金额。
- 金额为 CNY 含税经营口径，不替代法定会计账。一个事实一处维护；见 docs/SIMPLIFICATION_EVIDENCE.md 三条复用规则。
- 前端统一走 src/utils/request.ts 和 src/api；页面不直接 import axios。主路径 /erp/，业务 API /api/business/。附件只走鉴权下载。
- 全新安装用 install.sh/install.ps1，默认独立 atm-erp-lean 项目和新卷，服务仅 postgres/redis/app；app 只运行 Daphne、Nginx，无 Celery、WebSocket、updater、docker.sock。
- 后端检查：bash scripts/precheck-tests.sh --all（独立 PostgreSQL）；也可 python run_all_tests.py --stage checks/platform/business/concurrency。测试目标只维护在 scripts/ci/backend_test_matrix.py，不复制名单。
- 前端检查在 frontend：npm ci、npm run lint、npm run typecheck、npm run test、npm run build、npm run test:e2e。浏览器必须显式指定隔离测试 URL 和管理员密码，不读取生产配置。
- 使用 feature branch，不直接提交 main；保留用户未提交改动。使用 apply_patch 修改源码，按实际行为补测试。
- 历史 docs/superpowers、审计报告与旧部署文档仅作参考，不是现行要求。
