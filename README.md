# 项目 ERP · 精简版

面向约 50 人非标自动化公司，以项目串联销售、采购、交付和收付款。

**当前版本：v1.6.0** · [下载最新版本](https://github.com/hongheshan-svg/atm-erp/releases/latest) · [版本说明](docs/releases/v1.6.0.md) · [历史版本](https://github.com/hongheshan-svg/atm-erp/releases)

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

七种固定岗位：管理员、项目经理、销售经理、采购员、仓管、财务、成员。**一个账号可兼任多个岗位**，菜单按权限显示，销售负责人和项目成员的数据范围继续生效。经营报表向管理员开放；总经理使用经理角色，并由管理员单独开启“总经理报表权限”。

金额采用 **CNY 含税经营口径**，不替代法定会计账。不包含 OA、复杂 MES/APS、可配置审批流或报表构建器。完整边界见 [系统范围](docs/CORE_ERP_SCOPE.md)。

## 安装

### 选择安装方式与下载包

| 方式 | 适合场景 | 需要提前准备 |
| --- | --- | --- |
| **Docker（推荐）** | 三平台快速部署，由 Compose 管理应用和数据服务 | Docker Engine / Docker Desktop、Compose v2、Linux 容器模式 |
| 原生 | 已有数据库及 Redis，由运维管理运行环境 | Python 3.11、Nginx、PostgreSQL 15、Redis 7 |

在[发布页面](https://github.com/hongheshan-svg/atm-erp/releases/latest)的 **Assets** 下载 `atm-erp-v版本号-平台-方式.zip`。平台为 `macos` / `linux` / `windows`，方式为 `docker` / `native`，每版共 6 个安装包。请选择对应附件，GitHub 自动生成的 **Source code** 压缩包不等同于安装包。

这些是**联网安装包**，包含源码和预构建前端，不是离线镜像或桌面安装程序。Docker 镜像在本机构建，目前没有预制 GHCR 镜像拉取命令。包内 `INSTALL-MANIFEST.json` 记录源码和安装器来源；历史版本补包不改写原 tag。

> 全新部署必须使用独立数据库，不兼容早期非 Lean ERP 的表或迁移。系统发现旧表或回滚会拒绝启动；不要清库或绕过 schema guard。已有 Lean 数据库只能正常前向迁移。

<details>
<summary>下载校验（SHA256）</summary>

同时下载发布页的 `atm-erp-v1.6.0-SHA256SUMS.txt`，在安装包目录执行。其他版本请替换版本号。

```bash
# Linux
sha256sum -c atm-erp-v1.6.0-SHA256SUMS.txt
# macOS
shasum -a 256 -c atm-erp-v1.6.0-SHA256SUMS.txt
```

```powershell
# Windows：将输出与清单中对应文件的哈希比较
Get-FileHash .\atm-erp-v1.6.0-windows-native.zip -Algorithm SHA256
```

仅下载一个包时，其他未下载文件会提示不存在，核对所下载包的哈希即可。

</details>

### Docker 安装

启动 Docker，确认使用 Linux 容器与 Compose v2。安装过程需要访问 Docker 镜像仓库、npm 和 PyPI。解压安装包，进入解压目录后执行：

```bash
# macOS / Linux
bash install.sh
```

```powershell
# Windows PowerShell，按组织脚本执行策略运行
.\install.ps1
```

安装完成后打开 **http://127.0.0.1:8080/erp/**，用户名为 `admin`，首次密码在 `.env.lean` 的 `LEAN_ADMIN_PASSWORD`。登录后完成下方[首次启用](#首次启用)。重复安装不会重置已有账号密码。

| 常用配置（`.env.lean`） | 用途 |
| --- | --- |
| `LEAN_HTTP_PORT` | 访问端口，默认 8080 |
| `LEAN_BIND_ADDRESS`、`LEAN_ALLOWED_HOSTS` | 默认仅本机访问；局域网部署时显式配置 |
| `LEAN_ENVIRONMENT` | 正式部署保持 `production`（默认） |

修改配置后重新运行安装脚本使其生效；无需重新构建时可使用 `--skip-build`。保留配置和数据卷，同时部署多个环境须分别设置 `LEAN_PROJECT_NAME`、`LEAN_IMAGE`、`LEAN_HTTP_PORT`，不能共用数据卷。

### 原生安装

应用直接运行 Python/Daphne 和 Nginx，无需 Docker。前置依赖由管理员预先准备：

| 平台 | 应用运行依赖 | 数据服务 |
| --- | --- | --- |
| macOS | Python 3.11（含 venv/pip）、Nginx，原生 CPU 架构 | PostgreSQL 15、Redis 7，可本机或独立服务器 |
| Linux | Python 3.11（含 venv/pip）、Nginx，原生 CPU 架构 | PostgreSQL 15、Redis 7，可本机或独立服务器 |
| Windows | Python 3.11 x64（含 py 启动器）、Windows Nginx，PowerShell | PostgreSQL 15；Redis 7 使用已有可连接服务（例如独立 Linux 服务器） |

Windows 包不包含、不冒充提供官方 Windows Redis 7 服务。需要全套本机管理的数据服务时使用 Docker 包。原生安装器不会安装操作系统软件、创建数据库用户、开启防火墙或注册开机自启。发布包已有前端产物，无需 Node.js；从 Git 源码运行则先用 Node.js 22 执行 `cd frontend && npm ci && npm run build`。

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
# macOS / Linux
bash install-native.sh install
bash install-native.sh start
```

```powershell
# Windows
.\install-native.ps1 install
.\install-native.ps1 start
```

安装会创建独立 Python 虚拟环境、下载锁定依赖、检查 PostgreSQL/Redis 连接、执行原版 schema guard/迁移及初始化、配置 Nginx。任何失败立即退出，不清库、不绕过保护。首次管理员密码见 `native-config.json` 的 `ADMIN_PASSWORD`，用户名为 `admin`；已有账户保持不变。

看到“已启动”后访问 http://127.0.0.1:8080/erp/。启动器前台监控两个子进程；终端需保持打开，Ctrl+C 同时停止 Daphne 与 Nginx。进程异常退出时启动器非零退出。日志在 DATA_DIR/logs，诊断依赖连接用 `check`。需要开机自启时，由运维用本平台服务管理器运行相同 `start` 命令，工作目录设为解压目录，使用非管理员专用账户，保持配置私有。

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
docker compose --env-file .env.lean ps
docker compose --env-file .env.lean logs --tail 100 app
docker compose --env-file .env.lean stop
docker compose --env-file .env.lean start
```

**不要使用 `down -v`，它会删除数据卷。** 原生运行方式、日志目录和开机自启要求见上方原生安装步骤。

### 备份与恢复

以下脚本面向 Docker/Compose 部署；原生部署按上文备份 PostgreSQL、附件及配置。

Python 3.11+：

```bash
python3 scripts/backup.py backup --env-file .env.lean --archive backups/erp-20260909.zip
```

备份短暂停止应用写入，一起保存数据库和附件，完成后恢复服务。归档有校验和，Unix 系统中备份文件默认仅当前用户可读，**不包含 `.env.lean` 密钥**。另行安全保存环境配置。

恢复必须使用新的 Compose 项目名、端口、数据库卷与附件卷。准备目标配置但不要先初始化应用，然后运行：

```bash
python3 scripts/backup.py restore --env-file .env.restore --archive backups/erp-20260909.zip
```

目标环境需使用已构建的当前应用镜像；若镜像标签不同，设置 `LEAN_IMAGE`。恢复拒绝非空数据库、非空附件卷和正在运行的应用，绝不覆盖现有业务数据。原账户密码保持备份时的值。

### 手动升级

原生升级：先停止应用，备份 PostgreSQL（pg_dump 自定义格式）、DATA_DIR/uploads 附件及私有配置。新目录解压新版本，沿用原 native-config.json 和 DATA_DIR，执行 install，再 start。

Docker 升级：在旧目录执行 `docker compose --env-file .env.lean stop app`，保留数据库服务供备份脚本使用。备份完成后，将原 .env.lean 私密复制到新版本目录，保留项目名、密钥、数据库密码和原数据卷，再运行新目录的 install.sh 或 install.ps1 重建应用并前向迁移。

禁止将已升级的数据库交给旧版本运行；回退只能恢复匹配旧版本的独立备份库与附件。不要覆盖密钥或生成新配置替代原配置。

Docker 可继续使用版本源码中的 `scripts/backup.py`；原生 PostgreSQL 和附件须一起备份，定期在独立数据库演练恢复。原生安装不复用仅面向 Compose 的备份脚本。

### 在线升级（OTA）

管理员通过页面左上角“版本与升级”检查正式版本。启用宿主机执行器后，可发起“备份并升级”；执行器校验安装包 SHA256，备份成功才迁移，完成后核对运行版本。不支持降级，迁移失败后不会自动回退数据库。

执行器安装、三平台启动命令、密钥配置和故障处理见 [OTA 操作指南](docs/LEAN_OTA_OPERATIONS.md)。应用容器不挂载 Docker socket。

首次上线和升级后，应检查登录、角色权限、附件下载及备份恢复，不能仅以健康页作为业务验收结果。

## 常见问题

### Docker

- Docker 连接失败：确认 Docker 已启动，Windows/macOS 的 Docker Desktop 使用 Linux 容器模式。
- 拉取或构建失败：检查镜像仓库、npm、PyPI 网络连接；本包不含离线镜像。
- 端口被占用：修改 .env.lean 的 LEAN_HTTP_PORT 后重跑安装器。
- 默认仅能在本机打开；局域网部署需显式设置 LEAN_BIND_ADDRESS 和 LEAN_ALLOWED_HOSTS。
- 密码见 .env.lean；重新安装不会重置已有用户密码。

### 原生安装

- Python 版本不符：使用 Python 3.11，可通过 PYTHON 环境变量指定完整可执行文件路径。
- 找不到 Nginx：确认已安装，并设置 NGINX_EXECUTABLE 为完整路径。
- 数据库或 Redis 连接失败：核对配置、专用数据库、账号、密码和服务监听地址。
- 端口占用：停止已有应用，或为 HTTP_PORT 与 APP_PORT 分别设置空闲端口。
- 配置文件已存在：configure 不覆盖既有配置，直接编辑原文件后运行 install。
- 终端关闭后应用停止：start 为前台进程；开机自启需运维使用操作系统服务管理器配置。

## 开发与验证

### 本地检查

后端：Django REST Framework，三个本地 app `core/accounts/business`。前端：Vue 3、TypeScript、Element Plus，网络统一经过 `src/utils/request.ts`。

```bash
# Docker 中的临时 PostgreSQL 测试，自动清理测试容器
bash scripts/precheck-tests.sh --all

cd frontend
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
# 必须指向独立测试安装，会创建完整模拟业务数据
E2E_BASE_URL=http://127.0.0.1:18320 E2E_ADMIN_PASSWORD=测试管理员密码 npm run test:e2e
```

本地前端 `npm run dev`，默认端口 18310，API 代理默认 `127.0.0.1:18301`，可用 `VITE_API_BASE_URL` 修改。后端显式设置 `SECRET_KEY`、`DB_*`、`REDIS_URL` 后运行 `migrate`、`init_system`、`runserver`；它不读取旧 `.env`。

测试分组唯一维护在 `scripts/ci/backend_test_matrix.py`。`python run_all_tests.py --stage checks|backend|platform|business|concurrency|frontend|browser` 提供分阶段入口。后端测试需独立 `PG_TEST_HOST/USER/PASSWORD`，不使用业务库凭据。

当前范围见 [CORE_ERP_SCOPE](docs/CORE_ERP_SCOPE.md)，接口见 [LEAN_REBUILD_CONTRACT](docs/LEAN_REBUILD_CONTRACT.md)，本轮验证进度见 [SIMPLIFICATION_EVIDENCE](docs/SIMPLIFICATION_EVIDENCE.md)。其他历史文档不作为本版安装或模块清单。

开发环境可设置 `LEAN_ENVIRONMENT=development` 关闭登录限流；直接运行后端时对应 `APP_ENVIRONMENT=development`。开发标记不会开启 DEBUG。发布安装保持 `production`，登录限制为 10 次/分钟；原生发布安装器强制检查该配置。

### GitHub CI 与发布

进入 [GitHub Actions](https://github.com/hongheshan-svg/atm-erp/actions)，选择工作流后点击 **Run workflow**（需登录有权限的账号）：

| 工作流 | 手动运行内容 |
| --- | --- |
| Lean ERP CI | 全量、单项，或 `custom` 勾选组合 |
| Fast checks | 前后端快速检查 |
| Browser validation | 桌面、手机或两端并行 |
| OTA validation | Docker 与原生升级演练 |
| Installer validation | 三平台安装器验证 |
| Release | 已存在 tag 的验证、打包及草稿/正式发布 |

PR 按变动选择任务，合并不重复启动全套验证。Release 仅复用代码内容完全一致的全量通过记录，否则先补跑验证。参数、命令和发布流程见 [CI 与发布操作指南](docs/CI_OPERATIONS.md)。
