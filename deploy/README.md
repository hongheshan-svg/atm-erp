# 部署配置

参考 sub2api 的 [Compose](https://github.com/Wei-Shaw/sub2api/blob/main/deploy/docker-compose.local.yml)、[原生配置分区](https://github.com/Wei-Shaw/sub2api/blob/main/deploy/config.example.yaml) 和 systemd 管理方式；不复制其产品专用参数、可变镜像标签或降级策略。

## Docker

根目录 `docker-compose.yml` 是唯一编排入口。全新正式包复制 `.env.example` 为 `.env`，填好密钥后直接 `docker compose up -d`；无需宿主机 Python。包内默认镜像由 CI 写入真实固定摘要，不使用 latest，不现场构建；源码开发仍需先构建本地镜像。旧 `.env.lean` 用 --env-file 显式沿用，项目名与数据卷保持不变。三个容器日志最多3份、每份10MB，应用 init 处理信号和子进程。数据库和 Redis 不暴露端口，默认回环访问，公网另配反向代理和允许的域名。

## 原生配置

Docker 网页升级随 up 自动接入，使用容器内执行器和持久化 lean_runtime 卷，无需宿主机服务或 Docker socket。模式、兼容包及恢复格式见 [OTA 指南](../docs/LEAN_OTA_OPERATIONS.md)。下述独立服务诊断仅用于原生或显式 host 兼容模式。

`native-config.example.json` 是字段参考，不是可直接运行的配置。继续使用现有 JSON 格式，避免给宿主机安装器增加 YAML 解析依赖。先运行 `bash install-native.sh configure` 生成私有配置与随机密钥，再编辑生成的 `native-config.json`；不要用示例覆盖已有配置。

- 服务：`BIND_ADDRESS`、`HTTP_PORT` 为访问入口；`APP_PORT` 只供本机 Nginx 代理，两端口不能相同。
- 数据：`DB_*`、`REDIS_URL` 指向独立配置的 PostgreSQL / Redis；`DATA_DIR` 必须是可写的绝对路径，升级沿用原目录。
- 安全：保留 `SECRET_KEY` 与 `OTA_AGENT_TOKEN`，不在重新安装时轮换；管理员初始化不会重置已有密码。配置文件权限为 600，不提交 Git。
- 运行：保持 `APP_ENVIRONMENT=production`；`NGINX_EXECUTABLE` 可填写完整路径。Linux 执行 configure/install/service-install 后由 systemd 管理应用，start/stop/service-status 操作对应服务；macOS/Windows 保持前台 start。持久应用启动描述位于 DATA_DIR/application-service.json，成功安装新版本后更新路径，不随系统重启回到旧目录。
- 网页升级：OTA_AGENT_TOKEN 默认空，不要求执行器在线；需要时才配置密钥并注册独立服务。应用服务和升级执行器是两个不同服务，不把进程运行等同于心跳正常。

## Linux 升级服务诊断

执行器独立于应用运行。root 安装注册系统级服务，启动目标为 `multi-user.target`；普通用户注册用户服务，目标为 `default.target`，并启用 linger。使用安装服务的同一用户检查，不能混用 root 与普通用户的状态目录。

```bash
python3.11 scripts/ota_service.py status --state-dir /实际安装用户的状态目录
```

状态目录为安装日志中的升级日志所在目录。命令只读检查心跳、实际脚本/配置是否存在、未完成任务及 systemd 状态，不输出密钥，不会启动升级。退出码 1 表示未收到有效心跳，并不等同于进程未启动。`service.log` 区分 HTTP 401/403 认证或代理拒绝、404 路径错误、409 执行器/任务冲突及网络错误。

修复服务前核对未完成任务和备份；不要删除状态目录、任务记录或数据卷。服务运行并不等于心跳正常，必须看到真实心跳才能确认接入恢复。
