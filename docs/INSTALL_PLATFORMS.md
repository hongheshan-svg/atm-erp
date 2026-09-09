# macOS / Linux / Windows 安装

v1.0.0、v1.1.0 各提供 6 个 ZIP 附件：平台 `macos`、`linux`、`windows` × 方式 `native`、`docker`。均为**联网安装包**，不是离线安装镜像、签名桌面 App、MSI 或内置数据库的一键安装器。ZIP 已包含对应 tag 的完整源码与预构建前端；各平台共用同一业务实现。无需购买软件许可证；使用自己的 PostgreSQL / Redis / Nginx 服务。

原 tag 保持不变。`INSTALL-MANIFEST.json` 记录业务源码提交与补充安装器提交，补充文件清单独立列出。GitHub 自动生成的 Source code ZIP 不含补充安装器，请下载带平台和安装方式的附件。校验文件为 `atm-erp-vX.Y.Z-SHA256SUMS.txt`。

## Docker 安装（三平台推荐）

前提：已安装并启动 Docker Engine / Docker Desktop，支持 **Linux 容器**及 Compose v2。Windows 使用 Docker Desktop Linux 容器模式；macOS 使用 Docker Desktop；Linux 使用 Docker Engine + Compose 插件。需能联网拉取 postgres:15-alpine、redis:7-alpine、node:22-alpine、python:3.11-slim，以及 npm / PyPI 依赖。镜像按主机架构本地构建，不宣称提供预制多架构镜像。

解压到独立目录，进入该目录：

```bash
# macOS / Linux
bash install.sh
```

```powershell
# Windows PowerShell，按组织脚本执行策略允许本目录脚本
.\install.ps1
```

默认访问 http://127.0.0.1:8080/erp/，账户 admin，首次密码在 `.env.lean` 的 LEAN_ADMIN_PASSWORD。保留配置及 Docker 卷；重复安装不会重置账户。应用、PostgreSQL、Redis 均由 Compose 管理。

```bash
docker compose --env-file .env.lean ps
docker compose --env-file .env.lean logs --tail 100 app
docker compose --env-file .env.lean stop
docker compose --env-file .env.lean start
```

不要使用 `down -v`，它会删除数据卷。同时试用两个版本时，分别指定不同 LEAN_PROJECT_NAME、LEAN_IMAGE 和 LEAN_HTTP_PORT，不能复用另一版本的数据库卷。发布环境保持 LEAN_ENVIRONMENT=production（默认），登录限流开启。

## 原生安装（三平台）

应用直接运行 Python/Daphne 和 Nginx，无需 Docker。前置依赖由管理员预先准备：

| 平台 | 应用运行依赖 | 数据服务 |
| --- | --- | --- |
| macOS | Python 3.11（含 venv/pip）、Nginx，原生 CPU 架构 | PostgreSQL 15、Redis 7，可本机或独立服务器 |
| Linux | Python 3.11（含 venv/pip）、Nginx，原生 CPU 架构 | PostgreSQL 15、Redis 7，可本机或独立服务器 |
| Windows | Python 3.11 x64（含 py 启动器）、Windows Nginx，PowerShell | PostgreSQL 15；Redis 7 使用已有可连接服务（例如独立 Linux 服务器） |

Windows 包不包含、不冒充提供官方 Windows Redis 7 服务。需要全套本机管理的数据服务时使用 Docker 包。原生安装器不会安装操作系统软件、创建数据库用户、开启防火墙或注册开机自启。发布包已有前端产物，无需 Node.js；从 Git 源码运行则先用 Node.js 22 执行 `cd frontend && npm ci && npm run build`。

### 1. 准备独立数据库

由数据库管理员创建新的独立库及专用用户，不连接旧 ERP 库。例如 PostgreSQL 管理终端中执行（自行替换密码）：

```sql
CREATE ROLE atm_erp_lean LOGIN PASSWORD '替换成随机强密码';
CREATE DATABASE atm_erp_lean OWNER atm_erp_lean;
```

Redis 7 使用独立服务或分配独立逻辑库；如有密码/TLS，在 REDIS_URL 中配置。数据库和 Redis 不直接向公网开放。

### 2. 生成配置

```bash
# macOS / Linux
bash install-native.sh configure
```

```powershell
# Windows
.\install-native.ps1 configure
```

编辑生成的 `native-config.json`，填写 DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD、REDIS_URL。NGINX_EXECUTABLE 填 Nginx 命令或完整可执行文件路径。Windows JSON 路径推荐使用 `/`，例如 `C:/nginx/nginx.exe`。配置文件包含密钥与首次管理员密码，只供部署账户访问；生成时设置私有权限。

DATA_DIR 为虚拟环境、附件、前端、日志与 Nginx 配置的绝对路径，默认安装目录下 `.native`。HTTP_PORT 默认 8080，APP_PORT 默认 18001（Daphne 仅监听本机）。默认只允许本机访问；局域网部署需配置 BIND_ADDRESS 和 ALLOWED_HOSTS。保持 APP_ENVIRONMENT=production，安装器强制 DEBUG=false。

### 3. 安装并启动

```bash
# macOS / Linux
bash install-native.sh install
bash install-native.sh start
```

```powershell
# Windows
.\install-native.ps1 install
.\install-native.ps1 start
```

安装会创建独立 Python 虚拟环境、下载锁定依赖、检查 PostgreSQL/Redis 连接、执行原版 schema guard/迁移及初始化、配置 Nginx。任何失败立即退出，不清库、不绕过保护。首次管理员密码见配置，已有账户保持不变。

看到“已启动”后访问 http://127.0.0.1:8080/erp/。启动器前台监控两个子进程；终端需保持打开，Ctrl+C 同时停止 Daphne 与 Nginx。进程异常退出时启动器非零退出。日志在 DATA_DIR/logs，诊断依赖连接用 `check`。需要开机自启时，由运维用本平台服务管理器运行相同 `start` 命令，工作目录设为解压目录，使用非管理员专用账户，保持配置私有。

可用 `--config /absolute/path/config.json`（sh）或 `-Config C:/path/config.json`（PowerShell）指定持久配置；可通过 PYTHON 环境变量指定 Python 3.11 可执行文件。

## 升级、备份与校验

升级前停止应用，备份 PostgreSQL（pg_dump 自定义格式）、附件 DATA_DIR/uploads（Docker 为上传卷）及私有配置。新目录解压新版本，沿用配置与 DATA_DIR，执行 install，再 start。禁止把 v1.1.0 库交给 v1.0.0 运行；回退只能恢复匹配旧版本的独立备份库与附件。不要覆盖密钥或生成新配置替代原配置。

Docker 可继续使用版本源码中的 `scripts/backup.py`；原生 PostgreSQL 和附件须一起备份，定期在独立数据库演练恢复。原生安装不复用仅面向 Compose 的备份脚本。

```bash
# Linux
sha256sum -c atm-erp-v1.1.0-SHA256SUMS.txt
# macOS
shasum -a 256 -c atm-erp-v1.1.0-SHA256SUMS.txt
```

```powershell
# Windows：输出应与 SHA256SUMS 文件对应行一致
Get-FileHash .\atm-erp-v1.1.0-windows-native.zip -Algorithm SHA256
```

仅下载单个包时，校验文件内其他未下载包会提示不存在；核对自己下载包的对应哈希即可。首次上线后检查登录、角色权限、附件下载及备份恢复，不以健康页替代完整业务验收。
