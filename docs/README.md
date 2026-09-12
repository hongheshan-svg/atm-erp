# Lean ERP 文档

当前系统使用 Django REST Framework、Vue 3、PostgreSQL 和 Redis，只维护 `core/accounts/business` 三个后端应用。旧框架及其数据库不提供迁移兼容；安装使用独立新数据库。

## 使用与部署

- [安装、首次启用、升级与备份](../README.md)
- [日常使用](LEAN_USER_GUIDE.md)
- [自动化设备行业表单填写](AUTOMATION_FORM_GUIDE.md)
- [BOM 与产品编码](BOM_PRODUCT_CODING.md)
- [银行流水导入](BANK_IMPORT.md)
- [升级执行器运维](LEAN_OTA_OPERATIONS.md)
- [试运行与运维](OPERATIONS_AND_PILOT.md)

## 开发与验证

- [仓库开发约束](../AGENTS.md)
- [功能范围](CORE_ERP_SCOPE.md)
- [接口与业务约定](LEAN_REBUILD_CONTRACT.md)
- [模块边界](MODULE_BOUNDARIES.md)
- [验证记录](SIMPLIFICATION_EVIDENCE.md)
- [CI 工作流](CI_OPERATIONS.md)
- [发布说明模板](releases/TEMPLATE.md)

原始需求、旧架构审计报告、`superpowers/` 设计记录及 `screenshots/`、`output/` 内的旧版资料仅保留作历史参考，不代表当前功能或验收结果。旧版截图和手册生成脚本已移除；当前浏览器验证使用 `frontend/e2e/`，须显式指定隔离环境的 URL 和测试凭据。
