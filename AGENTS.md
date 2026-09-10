# Repository Guidance: Lean ERP

面向约 50 人非标自动化公司，只保留工作台、经营报表、销售、项目、BOM、采购、库存、收付款、基础资料和设置。范围以 docs/CORE_ERP_SCOPE.md 为准，接口以 docs/LEAN_REBUILD_CONTRACT.md 为准；不要重新引入已删除扩展。

- Django REST Framework 后端，Vue 3 + TypeScript + Element Plus 前端，PostgreSQL 15 + Redis 7。
- 本地 app 仅 core/accounts/business。只支持独立新数据库，schema guard 拒绝旧表、旧迁移和回滚；禁止清库或绕过保护。
- 固定 admin/manager/sales_manager/purchaser/warehouse/finance/member 七角色，允许一个账号兼任多个角色，无 Role 表、权限树或可配置工作流。权限按业务取各岗位的并集，通过 core.permissions.has_role/PermissionMixin 授权，不按主角色判权。仅销售经理权限时只操作本人销售单；兼任采购不扩大销售范围，兼任成员只开放参与项目，兼任财务可按财务权限读取销售但不能修改他人销售。签约指定具备 manager/admin 的项目经理。成员项目范围、敏感金额过滤、已有按人员身份的审批约束与总经理报表独立授权不可省略。
- 经营报表为固定只读页面，管理员默认可看；总经理沿用 manager 角色并由管理员显式设置 management_reports 授权，默认关闭，不向所有项目经理开放。
- BaseModel 提供审计和软删除；业务查询用 objects，删除用 soft_delete。金额流水不能物理删除，纠错保留原记录。
- 编号用 CodeRule.generate_code；采购、库存、收付款必须事务加锁与服务端校验，重复提交用 ActionReceipt，不信任前端金额。
- 金额为 CNY 含税经营口径，不替代法定会计账。一个事实一处维护；见 docs/SIMPLIFICATION_EVIDENCE.md 三条复用规则。
- 前端统一走 src/utils/request.ts 和 src/api；页面不直接 import axios。主路径 /erp/，业务 API /api/business/。附件只走鉴权下载。
- 全新安装用 install.sh/install.ps1，默认独立 atm-erp-lean 项目和新卷，服务仅 postgres/redis/app；app 只运行 Daphne、Nginx，无 Celery、WebSocket、docker.sock。按用户新增要求，OTA 使用可选宿主机执行器 scripts/ota_runner.py；仅管理员发起固定仓库正式版升级，执行器校验 SHA256、先备份后迁移，不回退或清空数据库。
- 本地开发配置 LEAN_ENVIRONMENT=development 关闭登录限流；发布部署必须使用 production（默认值），恢复原10次/分钟限制，不能把开发配置直接沿用到发布环境。DEBUG 不随开发标记开启。
- 后端检查：bash scripts/precheck-tests.sh --all（独立 PostgreSQL）；也可 python run_all_tests.py --stage checks/platform/business/concurrency。测试目标只维护在 scripts/ci/backend_test_matrix.py，不复制名单。
- 前端检查在 frontend：npm ci、npm run lint、npm run typecheck、npm run test、npm run build、npm run test:e2e。浏览器必须显式指定隔离测试 URL 和管理员密码，不读取生产配置。
- 使用 feature branch，不直接提交 main；保留用户未提交改动。使用 apply_patch 修改源码，按实际行为补测试。
- 发布说明使用 docs/releases/TEMPLATE.md，在最下方保留 Installation 与 Documentation 区块，替换实际 tag 并核对附件名称。当前 Docker 安装包本地构建镜像，不编造 GHCR docker pull 地址；完整安装说明继续保留在 README。
- 日常发布默认只递增补丁号（如 1.0.0 → 1.0.1）；除非用户明确指定，不自行提升主版本号或次版本号。以后端、前端和 tag 一致的版本发布，并在完整 CI 通过、合并 main 后打 tag。
- 历史 docs/superpowers、审计报告与旧部署文档仅作参考，不是现行要求。
