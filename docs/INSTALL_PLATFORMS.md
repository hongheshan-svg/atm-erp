# macOS / Linux / Windows 安装

完整步骤统一维护在 [README](../README.md#安装)，字段说明见 [部署配置](../deploy/README.md)，网页升级见 [OTA 操作指南](LEAN_OTA_OPERATIONS.md)。不要套用其他项目的 YAML、密钥或数据库。

## Docker（三平台推荐）

新版正式包包含固定摘要的多架构 Compose 镜像配置与 `.env.example`。全新目录复制为 `.env` 并填写随机数据库密码、SECRET_KEY、管理员初始密码，然后执行 `docker compose up -d`。只需 Docker Engine / Desktop（Linux 容器）及 Compose v2，不需要宿主机 Python 或 Node。

旧 `.env.lean` 必须用 `--env-file .env.lean` 显式沿用，保留项目名、数据卷、密钥。v1.8.8 及更早安装包仍按各自说明使用安装器。新版镜像 up 后默认容器内 OTA，无需宿主机服务；运行目录及备份持久化到 lean_runtime 卷，不得删除。--with-ota / -WithOta 仅用于显式切换旧宿主机模式，不是网页升级前置步骤。

## 原生

准备 Python 3.11、Nginx、独立 PostgreSQL 15、Redis 7。Windows 的 Redis 使用独立服务器，不提供虚构的 Windows Redis 服务。包内 wheelhouse 校验后离线安装依赖，不现场编译；数据库用户及防火墙由管理员管理。

1. `bash install-native.sh configure`，编辑生成的私有 JSON。
2. `bash install-native.sh install`。
3. Linux：`bash install-native.sh service-install` 注册并启动 systemd，`service-status` 查看状态，后续 start/stop 管理该服务。使用同一部署账户；切换现有前台实例前先停止，不能双开。
4. macOS：前台 `bash install-native.sh start`。Windows 用 `install-native.ps1` 的 configure/install/start。二者需保持启动会话，本次未提供应用后台服务注册。

DATA_DIR 必须为持久绝对路径；Linux 应用服务在其中保存启动入口，成功安装新版本后更新目录。网页升级密钥默认留空，应用服务与可选升级执行器分别管理。

## 升级与备份

升级前完整备份数据库、附件和配置。保留原项目、密钥及 DATA_DIR；不重置已有账号，不清库、不降级、不绕过 schema guard。Docker 用 `scripts/backup.py`，原生按 README 配套备份 PostgreSQL 与附件；不要将只支持 Compose 的恢复命令套到原生部署。

安装包核对同版本 SHA256SUMS 清单。禁止用 `docker compose down -v` 修复或升级现有实例。健康检查、安装测试和业务验收分别记录，局部通过不宣称全业务通过。
