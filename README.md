# 项目 ERP · 精简版

面向约 50 人非标自动化公司，以项目串联销售、采购、交付和收付款。

[下载最新版本及版本说明](https://github.com/hongheshan-svg/atm-erp/releases/latest) · [历史版本](https://github.com/hongheshan-svg/atm-erp/releases)（当前版本以发布页为准，本页不写固定版本号）

[系统概览](#系统概览) · [安装](#安装) · [首次启用](#首次启用) · [日常使用](#日常使用) · [升级与备份](#升级与备份) · [常见问题](#常见问题) · [开发与验证](#开发与验证)

## 系统概览

业务主线：**需求 → 报价签约 → 项目与 BOM → 采购收货 → 设计装配调试 → 分批交付验收 → 售后与结算**。

| 模块 | 主要用途 |
| --- | --- |
| 工作台、经营报表 | 个人待办、项目经营数据与风险 |
| 销售 | 需求、报价、合同、签约交接及交付回款进度 |
| 项目、BOM | 任务工时、材料清单、预算成本、交付与售后 |
| 采购、库存 | 按 BOM 多选下单、采购合同、收货、领退料与盘点 |
| 收付款 | 应收应付、对账、收付款、退款与冲销 |
| 基础资料、设置 | 物料、客户供应商、用户岗位、编号与启用配置 |

十一种固定岗位：管理员、项目经理、销售经理、采购员、仓管、财务、普通成员、采购经理、机械工程师、电气工程师、生产经理。**一个账号可兼任多个岗位**，菜单按权限显示；各岗位职责、数据范围及总经理报表授权见[岗位职责与权限](docs/ROLE_RESPONSIBILITIES.md)。

金额采用 **CNY 含税经营口径**，不替代法定会计账。不包含 OA、复杂 MES/APS、可配置审批流或报表构建器。完整边界见 [系统范围](docs/CORE_ERP_SCOPE.md)。

## 安装

### 选择安装方式与下载包

| 方式 | 适合场景 | 需要提前准备 |
| --- | --- | --- |
| **Docker（推荐）** | 三平台快速部署，由 Compose 管理应用和数据服务 | Docker Engine / Docker Desktop、Compose v2、Linux 容器模式 |
| 原生 | 已有数据库及 Redis，由运维管理运行环境 | Python 3.11（3.11.3 及以上）、Nginx、PostgreSQL 15、Redis 7 |

在[发布页面](https://github.com/hongheshan-svg/atm-erp/releases/latest)的 **Assets** 下载 `atm-erp-v版本号-平台-方式.zip`。平台为 `macos` / `linux` / `windows`，方式为 `docker` / `native`，每版共 6 个安装包。请选择对应附件，GitHub 自动生成的 **Source code** 压缩包不等同于安装包。

这些是正式安装包，包含源码和预构建前端。Docker 包携带预构建镜像归档，并在 Compose 中固定该版本的多架构镜像摘要；原生包携带预编译 wheelhouse。包内 `INSTALL-MANIFEST.json` 记录来源。以下直接 Compose 入口适用于包含 `.env.example` 和固定摘要的新版安装包；v1.8.8 及之前的包仍按各自说明使用安装器。

> 全新部署必须使用独立数据库，不兼容早期非 Lean ERP 的表或迁移。系统发现旧表或回滚会拒绝启动；不要清库或绕过 schema guard。已有 Lean 数据库只能正常前向迁移。

<details>
<summary>下载校验（SHA256）</summary>

同时下载发布页的 `atm-erp-v<版本>-SHA256SUMS.txt`，在安装包目录执行；命令中的 `<版本>` 换成所下载的实际版本号。

```bash
# Linux
sha256sum -c atm-erp-v<版本>-SHA256SUMS.txt
# macOS
shasum -a 256 -c atm-erp-v<版本>-SHA256SUMS.txt
```

```powershell
# Windows：将输出与清单中对应文件的哈希比较
Get-FileHash .\atm-erp-v<版本>-windows-native.zip -Algorithm SHA256
```

仅下载一个包时，其他未下载文件会提示不存在，核对所下载包的哈希即可。

</details>

### Docker 安装

启动 Docker，确认使用 Linux 容器与 Compose v2。全新部署解压正式 Docker 包后，复制 `.env.example` 为 `.env`，设置互不相同的随机 `LEAN_DB_PASSWORD`、`LEAN_SECRET_KEY`（至少32字符）、`LEAN_ADMIN_PASSWORD`（至少12字符，避免常见密码）。`LEAN_IMAGE` 留空沿用包内固定摘要。默认 `LEAN_OTA_MODE=container`，启动后自动接入网页升级，`LEAN_OTA_AGENT_TOKEN` 留空即可。**直接启动只需 Docker，不需要宿主机 Python、Node、安装脚本或 Docker socket。**

```bash
# macOS / Linux，仅全新目录执行复制，不覆盖旧配置
cp .env.example .env
chmod 600 .env
# 编辑 .env 并填写上述必填值后：
docker compose up -d
docker compose ps
docker compose logs --tail 100 app
```

```powershell
# Windows PowerShell，复制前确认没有已有 .env
Copy-Item .env.example .env
# 编辑 .env 并填写上述必填值后：
docker compose up -d
```

镜像从发布仓库按摘要拉取，需能访问 GHCR；若需校验导入随包镜像，可使用兼容安装器 `bash install.sh` / `.\install.ps1`（需要 Python 3.11），它也可自动生成密钥，但默认不注册网页升级服务。不要在已有实例上重新生成配置。

安装完成后打开 **http://127.0.0.1:8080/erp/**，用户名为 `admin`，初始密码为 `.env` 中的 `LEAN_ADMIN_PASSWORD`。首次向导会要求修改密码；重复启动不会重置已有账户。

| 常用配置（`.env`，旧安装为 `.env.lean`） | 用途 |
| --- | --- |
| `LEAN_HTTP_PORT` | 访问端口，默认 8080 |
| `LEAN_BIND_ADDRESS`、`LEAN_ALLOWED_HOSTS` | 默认仅本机访问；局域网部署时显式配置 |
| `LEAN_ENVIRONMENT` | 正式部署保持 `production`（默认） |

修改配置后执行 `docker compose up -d`。已有 `.env.lean` 的部署必须显式使用 `docker compose --env-file .env.lean up -d`，不要新建 `.env` 丢失原项目名或密钥；兼容安装器优先使用已有 `.env`，否则沿用 `.env.lean`。保留配置和数据卷，多实例须分别设置项目名和端口。升级前备份，不能把本命令当成自动备份流程，步骤见下文“手动升级”。

### 原生安装

Docker 编排、原生配置字段和 Linux 升级服务诊断见 [部署配置说明](deploy/README.md)。原生沿用 JSON 私有配置，示例不能直接覆盖已有密钥或数据目录。

应用直接运行 Python/Daphne 和 Nginx，无需 Docker。前置依赖由管理员预先准备：

| 平台 | 应用运行依赖 | 数据服务 |
| --- | --- | --- |
| macOS | Python 3.11.3 及以上的 3.11（含 venv/pip）、Nginx，原生 CPU 架构 | PostgreSQL 15、Redis 7，可本机或独立服务器 |
| Linux | Python 3.11.3 及以上的 3.11（含 venv/pip）、Nginx，原生 CPU 架构 | PostgreSQL 15、Redis 7，可本机或独立服务器 |
| Windows | Python 3.11.3 及以上的 3.11 x64（含 py 启动器）、Windows Nginx，PowerShell | PostgreSQL 15；Redis 7 使用已有可连接服务（例如独立 Linux 服务器） |

Windows 包不包含官方 Windows Redis 7 服务。需要全套本机数据服务时使用 Docker 包。原生安装器不会安装操作系统软件、创建数据库用户或开启防火墙；Linux 推荐通过下方 systemd 入口托管应用，网页升级服务单独选择启用。发布包已有前端产物，无需 Node.js；从 Git 源码运行则先用 Node.js 22 执行 `cd frontend && npm ci && npm run build`。

#### 1. 准备独立数据库

由数据库管理员创建新的独立库及专用用户，不连接旧 ERP 库。例如 PostgreSQL 管理终端中执行（自行替换密码）：

```sql
CREATE ROLE atm_erp_lean LOGIN PASSWORD '替换成随机强密码';
CREATE DATABASE atm_erp_lean OWNER atm_erp_lean;
```

Redis 7 使用独立服务或分配独立逻辑库；如有密码/TLS，在 REDIS_URL 中配置。数据库和 Redis 不直接向公网开放。

#### 2. 生成配置

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

#### 3. 安装并启动

```bash
# Linux：安装后注册开机启动和失败重启；用同一专用部署账户执行
bash install-native.sh install
bash install-native.sh service-install
bash install-native.sh service-status
# macOS：前台运行
# bash install-native.sh install
bash install-native.sh start
```

```powershell
# Windows
.\install-native.ps1 install
.\install-native.ps1 start
```

安装会创建独立 Python 虚拟环境，从发布包的 wheelhouse 校验并离线安装全部锁定依赖，检查 PostgreSQL/Redis 连接、执行 schema guard/迁移及初始化、配置 Nginx，不下载源码依赖或现场编译。包内预编译依赖支持 Linux x86_64/aarch64（glibc 2.28+）、macOS Intel 12+ / Apple Silicon 14+、Windows x64；其他宿主机优先使用 Docker。仍需事先准备 Python 3.11（3.11.3 及以上）、Nginx、PostgreSQL 15 与 Redis 7。任何失败立即退出，不清库、不绕过保护。全新安装的初始管理员密码见 `native-config.json` 的 `ADMIN_PASSWORD`，用户名为 `admin`；完成安装向导修改密码后该值即失效，已有账户保持不变。

Linux `service-install` 注册并启动 systemd 应用服务：普通用户使用用户服务及 linger，root 使用系统服务。先保证该账户拥有安装目录、DATA_DIR、Nginx 及数据库访问权限；推荐专用非管理员账户。之后 `start` / `stop` 管理已注册服务，`service-status` 查看状态，终端关闭不停止服务。应用升级成功安装后更新持久启动入口，系统重启不会回到旧版本目录。切换现有前台实例前先 `stop`，不要同时启动两套进程。

macOS / Windows 仍前台运行，Ctrl+C 停止 Daphne 与 Nginx；本次未增加这两种系统的应用服务管理。应用日志在 DATA_DIR/logs，Linux 启动器日志另见 journal；`check` 检查依赖连接。服务启动后确认 `/erp/` 可用，不能只以 unit 已注册认定应用健康。

可用 `--config /absolute/path/config.json`（sh）或 `-Config C:/path/config.json`（PowerShell）指定持久配置；可通过 PYTHON 环境变量指定 Python 3.11 可执行文件。

## 首次启用

Docker 与三平台原生安装启动后共用网页向导，无需在网页填写数据库参数。用安装器生成的 admin 初始密码登录，自动进入五步配置：

1. **管理员账号**：填写姓名、初始密码和新的登录密码（至少12位）。
2. **公司资料**：填写实际公司名称、地址和联系电话，用于采购合同。
3. **人员与兼岗**：可选添加人员、独立密码和一个或多个岗位；也可留空，稍后在用户管理中维护。总经理报表需明确授权。
4. **编号规则**：默认规则可直接使用，也可调整前缀、日期、流水位数和重置周期。物料仍支持手工编码。
5. **确认启用**：核对后一次性保存，使用新密码重新登录，即可进入工作台并开单。

校验失败不会保存半套配置。填写期间密码只在当前页面内存中，刷新或退出需重新填写；若提交时断网，请用新密码重新登录核对完成状态，未完成时仍使用初始密码。完成后的初始密码不再有效，重复运行安装器也不会重置密码。

向导不生成虚构客户、库存或订单。进入“设置 → 启用指南”可直达客户供应商、物料导入、人员管理及销售开单。已有系统升级保留现状，不强制重新初始化；业务期初及生产备份仍按实际资料配置。

## 日常使用

1. **基础资料**：维护客户供应商、物料和人员；可下载模板、预览校验后批量导入。
2. **销售交接**：录入需求、报价、合同及收款节点，签约时指定项目经理，生成执行项目和应收。
3. **项目采购**：设置材料、人工、费用预算，维护 BOM；按品牌、单元、标准件/非标件筛选并多选采购。
4. **生产交付**：审批采购、分批收货、项目领料、任务工时、分批发货、安装验收和售后。
5. **财务结算**：按业务规则完成对账、收付款及纠错，处理任务、采购与余额后结项。

物料编码可手工填写，留空自动生成；合同编号可独立填写。列表支持每页 10/20/50/100 条，销售、采购及项目附件通过鉴权下载。

详细操作、导入导出限制及成本口径见 [日常使用说明](docs/LEAN_USER_GUIDE.md)；设备需求、图纸版本、BOM、验收及付款依据的填写口径见 [自动化设备表单指南](docs/AUTOMATION_FORM_GUIDE.md)；对账、锁账等固定管控见 [业务管控说明](docs/OPERATIONAL_HARDENING.md)。

## 升级与备份

### 服务状态与日志（Docker）

```bash
docker compose --env-file .env ps
docker compose --env-file .env logs --tail 100 app
docker compose --env-file .env stop
docker compose --env-file .env start
```

旧安装沿用 `.env.lean` 时，把本节及下文命令中的 `--env-file .env` 换成 `--env-file .env.lean`，不要另建 `.env`。**不要使用 `down -v`，它会删除数据卷。** 原生运行方式、日志目录和开机自启要求见上方原生安装步骤。

### 备份与恢复

以下脚本面向 Docker/Compose 部署；原生部署按上文备份 PostgreSQL、附件及配置。

Python 3.11+：

```bash
python3 scripts/backup.py backup --env-file .env --archive backups/erp-20260909.zip
```

省略 `--env-file` 时默认读取 `.env`，不存在时沿用旧 `.env.lean`。

备份短暂停止应用写入，一起保存数据库和附件，完成后恢复服务。归档有校验和，Unix 系统中备份文件默认仅当前用户可读，**不包含 `.env`（或旧 `.env.lean`）密钥**。另行安全保存环境配置。

归档清单同时记录备份时实际运行的程序版本，完成时一并显示；网页升级过的部署记录的是 `lean_runtime` 卷中已升级程序的版本，而不是原安装包镜像的版本。备份**不包含 `lean_runtime` 卷**（网页升级安装的程序、离线依赖、升级日志及升级前备份），恢复时这些内容不会随归档迁移，由目标镜像或发布包提供程序。

恢复必须使用新的 Compose 项目名、端口、数据库卷与附件卷。准备目标配置但不要先初始化应用，然后运行：

```bash
python3 scripts/backup.py restore --env-file .env.restore --archive backups/erp-20260909.zip
```

**恢复需使用不低于备份程序版本的 Docker 包或镜像**：在该版本或更新版本发布包的目录中运行上述命令（`LEAN_IMAGE` 留空即使用包内固定摘要），或用 `LEAN_IMAGE` 指定该版本或更新的镜像；镜像须已在本机，可先执行 `docker compose --env-file .env.restore pull app`（不要用安装器准备恢复目标，它会启动并初始化应用）。目标程序较旧时，脚本在写入数据库和附件之前拒绝，否则还原后应用会以“旧迁移历史”拒绝启动。网页升级过的部署通常比原安装包新，须按备份显示的版本准备发布包。没有版本记录的早期备份不做此核对；无法确认目标程序版本时（如没有版本文件的早期镜像）只打印警告并继续，须自行核对版本。恢复拒绝非空数据库、非空附件卷和正在运行的应用，绝不覆盖现有业务数据。原账户密码保持备份时的值。

### 手动升级

原生升级：先停止应用，备份 PostgreSQL（pg_dump 自定义格式）、DATA_DIR/uploads 附件及私有配置。新目录解压新版本，沿用原 native-config.json 和 DATA_DIR，执行 install，再 start。

Docker 升级：在旧目录执行 `docker compose --env-file .env stop app`（旧安装为 `.env.lean`），保留数据库服务供备份脚本使用。备份完成后，将原配置文件私密复制到新版本目录，保留项目名、密钥、数据库密码和原数据卷，再运行新目录的 install.sh 或 install.ps1（优先使用 `.env`，否则沿用 `.env.lean`）校验导入随包镜像、重建应用容器并前向迁移，不在本机编译。`LEAN_IMAGE` 留空的配置也可在新目录直接 `docker compose --env-file .env up -d`，按新包固定摘要拉取镜像；安装器写入过 `LEAN_IMAGE` 的配置会继续指向旧镜像，须走安装器。

直接 Compose 部署（`.env` 加 `docker compose up -d`，未用安装器）手动换包时同样先备份再启动新版本：新版本应用启动即前向迁移数据库，**不会自动备份**，不能解压新包后直接 `up -d`。网页升级（OTA）由升级流程自动先备份，不需要以下步骤。

```bash
# 1. 旧版本目录：停止应用写入，再完整备份数据库与附件（需要宿主机 Python 3.11+；Windows 用 py -3.11 运行同一脚本）
docker compose --env-file .env stop app
python3 scripts/backup.py backup --env-file .env --archive "backups/erp-before-upgrade-$(date +%Y%m%d-%H%M).zip"
# 2. 看到“备份完成”后，把原配置私密复制到新版本目录（保留项目名、密钥、数据库密码和 LEAN_IMAGE 留空）
NEW=/path/to/新版本目录
cp -p .env "$NEW/.env"
# 3. 新版本目录：启动后自动前向迁移，确认健康
cd "$NEW"
docker compose --env-file .env up -d
docker compose --env-file .env ps
docker compose --env-file .env logs --tail 100 app
```

备份失败时不要在新目录启动；此时数据库尚未迁移，可在旧目录执行 `docker compose --env-file .env start app` 恢复原服务。备份归档留在旧目录的 `backups/`，升级后不要随旧目录删除，并另行异地保存。新版本启动后数据库即已迁移，不能再回到旧目录启动。

禁止将已升级的数据库交给旧版本运行；回退只能恢复匹配旧版本的独立备份库与附件。不要覆盖密钥或生成新配置替代原配置。

Docker 可继续使用版本源码中的 `scripts/backup.py`；原生 PostgreSQL 和附件须一起备份，定期在独立数据库演练恢复。原生安装不复用仅面向 Compose 的备份脚本。

### 在线升级（OTA）

管理员在页面左上角“版本与升级”检查并安装正式版本。**新版 Docker 配置后直接 up，网页升级默认可用**，须看到“容器内升级已就绪”的真实心跳；“立即更新”只下载并准备，业务继续运行，管理员确认“重启服务”后才完整备份、前向迁移并切换程序。程序、依赖、日志和升级备份保存在 `lean_runtime` 卷，**禁止删除该卷或执行 `down -v`**。

升级步骤、空间要求、恢复格式、旧宿主机/原生执行器接入及故障排查只维护在 [OTA 操作指南](docs/LEAN_OTA_OPERATIONS.md)。

首次上线和升级后，应检查登录、角色权限、附件下载及备份恢复，不能仅以健康页作为业务验收结果。

## 常见问题

### Docker

- Docker 连接失败：确认 Docker 已启动，Windows/macOS 的 Docker Desktop 使用 Linux 容器模式。
- 镜像拉取失败：直接 Compose 按固定摘要从 GHCR 拉取，请检查镜像仓库网络连接；正式 Docker 包携带离线镜像归档，无法访问 GHCR 时用兼容安装器 `bash install.sh` / `.\install.ps1`（需要 Python 3.11）校验并导入随包镜像。仅从源码构建时才需检查 npm、PyPI 连接。
- 端口被占用：修改 `.env`（旧安装为 `.env.lean`）的 LEAN_HTTP_PORT 后执行 `docker compose --env-file .env up -d`。
- 默认仅能在本机打开；局域网部署需显式设置 LEAN_BIND_ADDRESS 和 LEAN_ALLOWED_HOSTS。两者只改其一时安装器会在结尾提示：
  只开放端口而未放行主机名，真实 IP 访问会被服务端拒绝（HTTP 400）；只放行主机名而未开放端口，局域网仍然连不上。
- 初始密码见 `.env`（旧安装为 `.env.lean`）的 LEAN_ADMIN_PASSWORD，仅在完成安装向导前有效；向导要求修改初始密码，之后请使用新密码。重新安装不会重置已有用户密码。
- 忘记管理员密码：新版 Docker 用 `docker compose --env-file .env -f docker-compose.yml exec app python /opt/erp/container_runtime.py manage changepassword admin`（旧安装用 `.env.lean`；自动选中 OTA 后的实际程序），
  原生安装用 `bash install-native.sh reset-password`（Windows 为 `.\install-native.ps1 reset-password`），重设其他账户加 `--user 用户名`（Windows 为 `-User 用户名`）。

### 原生安装

- Python 版本不符：使用 Python 3.11，可通过 PYTHON 环境变量指定完整可执行文件路径。
- 找不到 Nginx：确认已安装，并设置 NGINX_EXECUTABLE 为完整路径。
- 数据库或 Redis 连接失败：核对配置、专用数据库、账号、密码和服务监听地址。
- 端口占用：停止已有应用，或为 HTTP_PORT 与 APP_PORT 分别设置空闲端口。
- 配置文件已存在：configure 不覆盖既有配置，直接编辑原文件后运行 install。
- 终端关闭后应用停止：Linux 用 `service-install` 注册 systemd 服务后终端关闭不停止、开机自动启动；macOS / Windows 的 start 仍为前台进程，开机自启需运维使用操作系统服务管理器配置。

## 开发与验证

### 本地开发与检查

开发环境、本地端口、独立测试库（`PG_TEST_*`）与分阶段检查命令只维护在 [AGENTS.md](AGENTS.md#开发与测试)；后端测试目标唯一登记在 `scripts/ci/backend_test_matrix.py`。浏览器用例必须指向独立测试安装（显式设置 `E2E_BASE_URL`、`E2E_ADMIN_PASSWORD`），会创建模拟业务数据。

当前范围见 [CORE_ERP_SCOPE](docs/CORE_ERP_SCOPE.md)，接口见 [LEAN_REBUILD_CONTRACT](docs/LEAN_REBUILD_CONTRACT.md)，本轮验证进度见 [SIMPLIFICATION_EVIDENCE](docs/SIMPLIFICATION_EVIDENCE.md)。员工填写表格前请阅读 [导入模板填写说明](docs/IMPORT_TEMPLATES.md)，各模板下载旁也可取得独立说明文档。已完成的验收与审计记录在 [docs/archive](docs/archive/README.md)，不作为本版安装或模块清单。

### GitHub CI 与发布

进入 [GitHub Actions](https://github.com/hongheshan-svg/atm-erp/actions)，选择工作流后点击 **Run workflow**（需登录有权限的账号）。Fast checks 与 Browser validation 是可复用子流程，没有独立的 Run workflow 入口，只能经 Lean ERP CI 运行：

| 工作流 | 手动运行内容 |
| --- | --- |
| Lean ERP CI | 全量、单项，或 `custom` 勾选组合 |
| Fast checks | 前后端快速检查：在 Lean ERP CI 选 `suite=fast` |
| Browser validation | 桌面、手机或两端并行：在 Lean ERP CI 选 `suite=browser` 及 `browser_projects` |
| OTA validation | Docker 与原生升级演练 |
| Installer validation | 三平台安装器验证 |
| Release | 已存在 tag 的验证、打包及草稿/正式发布 |

PR 按变动选择任务，合并不重复启动全套验证；发版本必须通过发版验证。参数、运行范围、凭据复用和发布流程见 [CI 与发布操作指南](docs/CI_OPERATIONS.md)。
