# Lean ERP 在线升级操作指南

[返回 README](../README.md#升级与备份)

## 在线升级（OTA）

管理员在左上角“版本与升级”查看当前版本、检查正式发布版本及更新内容。只允许向更高正式版本升级，不支持预发布版本或降级。默认 Docker 分“立即更新”和“重启服务”两步；下载准备不停机，重启前需确认已通知使用者暂停业务操作。兼容 host/原生模式保留“备份并升级”的自动执行流程。

版本入口及交互参考 [sub2api 的 VersionBadge](https://github.com/Wei-Shaw/sub2api/blob/7c700729c23187d31ed320f6b19c790e2f194826/frontend/src/components/common/VersionBadge.vue)：当前/最新版本、新版圆点、发布说明、下载准备、待重启与重连。管理员进入页面即复用20分钟发布信息缓存检查，“检查新版本”强制刷新。检查失败保留上次说明并明确警告，不显示“已是最新版”；提交下载仍重新校验 GitHub 发布信息。准备后的重启使用已固定校验的包，不要求再次联网检查发布。

重启接口只能确认已准备的任务，不能任意重启应用或跳过备份；等待重启状态保存在服务端和 runtime 卷，刷新页面或重建容器不丢失。ERP 在确认重启后停止业务、备份、迁移，不照搬 Go 二进制直接覆盖或降级。当前页面发起重启后，只有任务成功且运行版本达标才进入8秒刷新倒计时；断连时持续重试，不按固定等待时间猜测成功。其他管理员查看历史成功任务仍提供手动刷新。已经达到目标版本的旧失败折叠为历史，原记录不篡改。

## Docker 默认：容器内 OTA

新版镜像默认 `LEAN_OTA_MODE=container`，配置 `.env` 后直接 `docker compose up -d`，容器启动器自动派生内部认证并启动升级进程，不需要宿主机 Python、服务注册或 docker.sock。页面收到真实心跳后显示“容器内升级已就绪”。只支持一套应用实例挂载该 runtime 卷，不共享给多副本。旧宿主机执行器与容器模式互斥。

执行过程：下载固定仓库 Linux/native 发布包并验证 SHA256 → 验证 container_runtime=1 兼容声明及匹配架构 wheelhouse → 离线创建独立 venv → 等待管理员确认重启 → 停止容器内 Daphne → 备份 → 前向迁移 → 原子切换 active.json 与前端目录 → 启动并核对健康版本。下载、依赖预备失败不停止业务；完整备份之前绝不迁移。这里更新的是应用程序，不改变 Docker 镜像标签；系统库、Python、Nginx 或启动器协议改变需手动换基础镜像。

`lean_runtime` 挂载 `/app/runtime`：`job-<id>/upgrade.log` 保存详细日志，`job-<id>/backup/` 包含 PostgreSQL 15 自定义格式 `database.dump`、`uploads.tar`、私有 `config.json` 及 SHA256 清单；`active.json` 指向持久化版本和 venv。配置备份有敏感密钥，不公开分享。重建容器保留新版本；不可删除 runtime 卷或挂到其他部署。原宿主机 `.env` 不在容器内，仍需自行安全保存，以便重建 Compose。

备份格式不是旧 `scripts/backup.py` 的 ZIP，不能直接交给该脚本 restore。恢复应在独立空数据库、附件卷和匹配版本程序上操作：先校验清单，再用 PostgreSQL 15 `pg_restore --no-owner --no-acl` 恢复数据库，安全解包附件并对照私有配置恢复连接。不要覆盖当前库、密钥或运行时目录。

升级进程中断时按持久阶段恢复：backup 阶段先恢复原业务进程，再上报失败并解除维护；启动失败保留标记供 Supervisor 下次重试。verifying 阶段只允许启动并检查已切换的目标版本，成功后补齐状态，失败进入 blocked。容器启动时保留 verifying 标记交给升级服务核验，避免把已完成切换误报为失败。恢复日志在 runtime/recovery.log。

迁移失败或断电会留下 `maintenance.json` 的 migrating/blocked 状态，启动器拒绝运行旧代码；页面可能无法连接，日志与备份仍保留。此时禁止删除标记强行启动，先检查日志，再用独立备份恢复或经确认的前向修复。容器日志用 `docker compose logs --tail 100 app` 查看；升级成功无需重建容器，页面提供刷新按钮。

空间保护：下载前要求发布包大小加3 GiB余量；停机前按当前数据库物理大小的两倍、附件大小及512 MiB余量再次估算。预检不是磁盘空间预留，其他进程仍可能耗尽磁盘。备份文件刷盘后才写完成清单和开始迁移。正常升级成功自动清理该任务的 package.zip 下载缓存；运行程序、venv、失败现场、所有备份和日志保留，不按 sub2api 的单二进制 `.backup` 策略直接删除数据库备份。需定期监控 runtime 卷容量，备份外存及保留周期由管理员决定。

OTA 后执行管理命令应通过当前版本入口，例如 `docker compose exec app python /opt/erp/container_runtime.py manage changepassword admin`。不要在镜像旧源码目录直接运行 manage.py。切换旧 host 模式前须确保没有活动升级任务，且镜像版本与当前程序一致。

## 兼容模式：原生 / 旧宿主机执行器

以下仅适用于原生部署或显式 `LEAN_OTA_MODE=host` 的旧 Docker 方案。Docker 使用 `install.sh --with-ota` / `install.ps1 -WithOta` 会切换 host 模式并注册服务；原生在配置非空 OTA_AGENT_TOKEN 后启动时接入。宿主机需要 Python 3.11；原生备份额外需要 PostgreSQL 15 的 pg_dump。此方案不与默认容器执行器同时使用。

每套部署的私有状态默认保存在 `~/.local/share/atm-erp-ota/<部署标识>`，服务命令不包含密钥，配置、下载包、日志和备份保持独立。不要删除该目录或运行中的安装目录。Linux root 安装注册系统 systemd 服务，普通用户注册用户服务并启用 linger；macOS 注册 LaunchAgent，Windows 注册当前用户登录计划任务，并每分钟检查启动。服务异常退出后自动恢复。macOS/Windows 需安装用户的登录会话保持可用，与 Docker Desktop 相同；服务器无人登录运行请使用 Linux 系统服务。

旧版 Docker 安装使用新版安装器并显式指定原配置及 --with-ota 接入；缺少的升级密钥会生成，已有密钥和数据保留。默认不注册；--no-ota / -NoOta 仍兼容，但不会停止此前已启用的服务。

host/原生模式的 LEAN_OTA_AGENT_TOKEN / OTA_AGENT_TOKEN 留空时，页面显示“网页一键升级未启用”，不是断连故障。启用时设置至少32字符随机密钥并同步到应用，已有密钥不覆盖、不在页面显示。默认 container 模式不需要该配置。旧版 .env.lean 必须显式沿用，避免连接错误的数据卷。

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
