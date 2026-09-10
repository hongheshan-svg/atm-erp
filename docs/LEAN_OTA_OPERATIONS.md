# Lean ERP 在线升级操作指南

[返回 README](../README.md#升级与备份)

## 在线升级（OTA）

管理员在左上角“版本与升级”查看当前版本、检查正式发布版本及更新内容。只允许向更高正式版本升级，不支持预发布版本或降级。点击“备份并升级”前需确认已通知使用者暂停业务操作。

首次使用需手动安装含 OTA 功能的代码，并在宿主机启用执行器；此前发布的 v1.0.0/v1.1.0 原始业务源码不会凭空获得此入口。应用容器本身不接触 Docker socket。执行器使用 Python 3.11，Docker 部署需宿主机 Docker/Compose，原生部署额外需要 PostgreSQL 15 的 pg_dump 客户端。执行器目录要放在安装目录外、空间充足的私有位置，保存下载包、日志、备份和当前安装路径，不能随旧版本目录一起删除。

新安装生成的 .env.lean 中包含 LEAN_OTA_AGENT_TOKEN，原生 native-config.json 中包含 OTA_AGENT_TOKEN；已有配置缺少时，生成至少 32 字符随机密钥填入对应字段，再重新运行安装器并启动应用。该密钥仅供本机执行器使用，不在页面显示。

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

保持执行器运行；如需开机自启，由运维在操作系统服务管理器配置上述命令。非本机 API 必须使用 HTTPS。页面显示执行器已连接后即可提交升级，普通成员及其他角色无此权限。

执行器只下载固定仓库 hongheshan-svg/atm-erp 中有 SHA256 的对应平台安装包，再次核对 GitHub 元数据、版本、压缩包路径和运行时版本。Docker 先构建新镜像，再停机备份；原生先停止受控应用，再备份数据库、附件及配置。备份成功才执行安装和前向迁移；新健康页返回目标版本后才记为完成。停机期间页面会自动重试，状态报告保存在宿主机并在应用恢复后补交。

升级成功后，执行器状态文件记录新的源码/配置路径；之后手动管理或重启也应使用该路径。不要再从旧目录启动应用。发布新版本时，backend/apps/core/version.py 与发布 tag 必须一致，并发布对应平台安装 ZIP；没有运行时版本标识的旧包不会被用于 OTA。

如果备份前后但迁移尚未开始就失败，会尝试启动原应用。迁移开始后的失败不会自动回退数据库或将旧应用连接新 schema；查看执行器目录 job-*/upgrade.log 和 backup，按独立恢复流程处理。若应用无法启动，页面无法读取失败详情，但日志与待补交状态仍在宿主机保存。执行器中断后不会自动重复升级，应先人工核对日志和备份。
