# macOS / Linux / Windows 安装检查清单

安装步骤只维护在 [README 安装](../README.md#安装)，配置字段见 [部署配置](../deploy/README.md)，网页升级见 [OTA 操作指南](LEAN_OTA_OPERATIONS.md)。本页只列安装前后的核对项，不重复步骤；不要套用其他项目的 YAML、密钥或数据库。

## 安装前

- [ ] 下载发布页 Assets 中对应平台与方式的安装包（不是 Source code），并按 `SHA256SUMS` 清单核对哈希。
- [ ] Docker：Docker Engine / Desktop 使用 Linux 容器，Compose v2；无需宿主机 Python 或 Node。
- [ ] 原生：Python 3.11（3.11.3 及以上）、Nginx、独立的 PostgreSQL 15 与 Redis 7 已由管理员准备；Windows 的 Redis 使用独立服务器。
- [ ] 使用全新独立数据库，不连接旧 ERP 库，不清库、不绕过 schema guard。

## 配置与启动

- [ ] Docker 全新目录：`.env.example` 复制为 `.env`，填写互不相同的随机数据库密码、SECRET_KEY 和管理员初始密码。
- [ ] 旧安装沿用 `.env.lean`：始终用 `--env-file .env.lean`，保留项目名、数据卷和密钥，不新建 `.env`。
- [ ] 原生：先 `configure` 生成私有 JSON 再编辑，不用示例覆盖已有配置；DATA_DIR 为持久绝对路径。
- [ ] Linux 原生用 `service-install` 交给 systemd，切换现有前台实例前先停止，不能双开；macOS / Windows 前台运行。

## 升级与验收

- [ ] 升级前完整备份数据库、附件和配置；Docker 用 `scripts/backup.py`，原生按 README 配套备份 PostgreSQL 与附件。
- [ ] 不重置已有账号、不降级、不清库；禁止用 `docker compose down -v` 修复或升级现有实例，不删除 `lean_runtime` 卷。
- [ ] 健康检查、安装测试和业务验收分别记录，局部通过不宣称全业务通过。
