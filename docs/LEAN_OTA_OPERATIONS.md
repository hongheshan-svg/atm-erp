# Lean ERP 在线升级操作指南

[返回 README](../README.md#升级与备份)

## 在线升级（OTA）

管理员在左上角“版本与升级”查看当前版本、检查正式发布版本及更新内容。只允许向更高正式版本升级，不支持预发布版本或降级。点击“备份并升级”前需确认已通知使用者暂停业务操作。

安装器默认自动配置宿主机执行器，用户不需要单独运行启动命令。Docker 的 install.sh/install.ps1 在应用健康后注册服务并确认心跳；原生 start 在应用就绪后执行相同接入。安装时需要宿主机 Python 3.11；Docker 还需要 Docker/Compose，原生备份额外需要 PostgreSQL 15 的 pg_dump。应用容器不接触 Docker socket。

每套部署的私有状态默认保存在 `~/.local/share/atm-erp-ota/<部署标识>`，服务命令不包含密钥，配置、下载包、日志和备份保持独立。不要删除该目录或运行中的安装目录。Linux root 安装注册系统 systemd 服务，普通用户注册用户服务并启用 linger；macOS 注册 LaunchAgent，Windows 注册当前用户登录计划任务，并每分钟检查启动。服务异常退出后自动恢复。macOS/Windows 需安装用户的登录会话保持可用，与 Docker Desktop 相同；服务器无人登录运行请使用 Linux 系统服务。

旧版安装使用新版安装器重新安装并启动即可接入；缺少的升级密钥会自动生成，已有密钥和业务数据保留。仅隔离 CI 环境使用 `--no-ota` / PowerShell `-NoOta` 跳过宿主机服务注册，生产默认不跳过。

新安装生成的 .env.lean 中包含 LEAN_OTA_AGENT_TOKEN，原生 native-config.json 中包含 OTA_AGENT_TOKEN；新版安装器为缺少该字段的旧配置自动补充随机密钥，再启动应用。已有密钥不覆盖。该密钥仅供本机执行器使用，不在页面显示。

```bash
# macOS / Linux：Docker 部署，替换成自己的绝对路径与端口
python3.11 scripts/ota_runner.py --mode docker --config /absolute/path/.env.lean --state-dir /absolute/path/erp-ota --url http://127.0.0.1:8080

# 原生部署（先使用新的 install-native.sh start 启动应用）
python3.11 scripts/ota_runner.py --mode native --config /absolute/path/native-config.json --state-dir /absolute/path/erp-ota --url http://127.0.0.1:8080
```

```powershell
# Windows：Docker；原生部署将 mode 改为 native，并指向 native-config.json
py -3.11 scripts/ota_runner.py --mode docker --config C:/erp/.env.lean --state-dir C:/erp-ota --url http://127.0.0.1:8080
```

上述直接运行命令仅用于手动诊断，不要与安装器注册的服务同时运行。服务日志在状态目录的 `service.log`，macOS 可通过 launchctl、Linux 通过 systemctl、Windows 通过任务计划程序查看服务状态。页面按真实心跳显示连接，断连不能发起升级，不会伪造在线状态。非本机 API 必须使用 HTTPS，普通成员及其他角色无升级权限。

执行器只下载固定仓库 hongheshan-svg/atm-erp 中有 SHA256 的对应平台安装包，再次核对 GitHub 元数据、版本、压缩包路径和运行时版本。Docker 先校验并导入 GitHub 已构建镜像（精简包可拉取固定 GHCR digest），再停机备份；正式包没有预构建镜像则拒绝升级，不回退本地构建。原生先停止受控应用，再备份数据库、附件及配置，并从包内 wheelhouse 离线安装二进制依赖。备份成功才执行安装和前向迁移；新健康页返回目标版本后才记为完成。停机期间页面自动重试，状态报告在应用恢复后补交。

升级成功后，执行器状态文件记录新的源码/配置路径；之后手动管理或重启也应使用该路径。不要再从旧目录启动应用。发布新版本时，backend/apps/core/version.py 与发布 tag 必须一致，并发布对应平台安装 ZIP；没有运行时版本标识的旧包不会被用于 OTA。

如果备份前后但迁移尚未开始就失败，会尝试启动原应用。迁移开始后的失败不会自动回退数据库或将旧应用连接新 schema；查看执行器目录 job-*/upgrade.log 和 backup，按独立恢复流程处理。若应用无法启动，页面无法读取失败详情，但日志与待补交状态仍在宿主机保存。执行器中断后不会自动重复升级，应先人工核对日志和备份。
