# 项目 ERP · 精简版

当前版本：**v1.1.0**。查看[发布说明](docs/releases/v1.1.0.md)及旧版数据库兼容性限制。

面向约 50 人非标自动化公司，以项目串联 **需求 → 报价签约 → BOM → 采购收货 → 设计装配调试 → 分批发货安装验收 → 售后 → 收付款与成本**。

十个入口：工作台、经营报表、销售、项目、BOM、采购、库存、收付款、基础资料、设置，按权限显示。固定管理员、项目经理、采购员、仓管、财务、成员六角色。没有 OA、复杂 MES/APS、可配置审批流、报表构建器、会计总账或小程序。

经营报表汇总当前筛选项目的合同、成本、在途采购、待收待付及风险；管理员默认可看。总经理使用经理角色账号，由管理员在“设置 → 用户管理”开启“总经理报表权限”，其他经理默认不可看。

管理员可在设置中配置六类自动编号的前缀、日期、流水位数及重置周期，仅影响新记录。物料新建支持手工编码（留空自动生成），销售签约支持填写独立合同编号；编码唯一，历史编号保留。

业务列表、经营报表及 BOM 支持每页 10/20/50/100 条，默认 10 条，选择在当前浏览器保存并跨页面复用；长表格在内部滚动。

采购列表“从 BOM 多选下单”及项目BOM“按缺料采购”支持按品牌、功能单元、标准件/非标件组合筛选，跨页勾选或全选筛选结果，再统一填写供应商、数量和单价。品牌和类别在物料资料维护，功能单元在项目BOM行维护；保存时重验实际缺口，订单仍需提交审批。

业务页面可选择 Excel/CSV 导出全部筛选结果，采购明细逐行展开，经营报表带合计。支持物料、客户供应商、销售和采购草稿、项目、任务、期初库存、领料、费用、收付款、工时及发货的模板下载和批量导入；BOM 保留原导入入口。操作顺序为下载模板 → 选择文件预览 → 修正行级错误 → 确认导入。单文件最多1000行/5MB，导出最多20000行；确认再次校验并整批保存，导入不覆盖原记录，签约、审批及流水纠错仍走原操作。

开发安装的配置文件可设置 `LEAN_ENVIRONMENT=development` 关闭登录限流；发布部署必须设置 `LEAN_ENVIRONMENT=production`，默认即为 production，启用 10 次/分钟登录限制。修改配置后重跑安装脚本（可用 `--skip-build`）使运行环境生效。原生后端使用对应的 `APP_ENVIRONMENT`，开发标记不会开启 DEBUG。

## 安装（macOS / Linux / Windows）

下载版本：[v1.1.0](https://github.com/hongheshan-svg/atm-erp/releases/tag/v1.1.0) · [v1.0.0](https://github.com/hongheshan-svg/atm-erp/releases/tag/v1.0.0)。安装说明统一在本 README 阅读，Release 页面保留版本变化和安装包下载。

v1.0.0、v1.1.0 各提供 6 个 ZIP 附件：平台 `macos`、`linux`、`windows` × 方式 `native`、`docker`。均为**联网安装包**，不是离线安装镜像、签名桌面 App、MSI 或内置数据库的一键安装器。ZIP 已包含对应 tag 的完整源码与预构建前端；各平台共用同一业务实现。使用自己配置的 PostgreSQL / Redis / Nginx 服务，第三方依赖按各自许可使用。

原 tag 保持不变。`INSTALL-MANIFEST.json` 记录业务源码提交与补充安装器提交，补充文件清单独立列出。GitHub 自动生成的 Source code ZIP 不含补充安装器，请下载带平台和安装方式的附件。校验文件为 `atm-erp-vX.Y.Z-SHA256SUMS.txt`。

**全新部署必须使用独立数据库，不兼容早期非 Lean ERP 的表或迁移。** 检测到旧表或回滚时会拒绝启动，不清库、不使用 fake migration、不绕过 schema guard。已有 Lean 数据库只允许正常前向迁移。

### Docker 安装（三平台推荐）

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

### 原生安装（三平台）

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

安装会创建独立 Python 虚拟环境、下载锁定依赖、检查 PostgreSQL/Redis 连接、执行原版 schema guard/迁移及初始化、配置 Nginx。任何失败立即退出，不清库、不绕过保护。首次管理员密码见配置，已有账户保持不变。

看到“已启动”后访问 http://127.0.0.1:8080/erp/。启动器前台监控两个子进程；终端需保持打开，Ctrl+C 同时停止 Daphne 与 Nginx。进程异常退出时启动器非零退出。日志在 DATA_DIR/logs，诊断依赖连接用 `check`。需要开机自启时，由运维用本平台服务管理器运行相同 `start` 命令，工作目录设为解压目录，使用非管理员专用账户，保持配置私有。

可用 `--config /absolute/path/config.json`（sh）或 `-Config C:/path/config.json`（PowerShell）指定持久配置；可通过 PYTHON 环境变量指定 Python 3.11 可执行文件。

### 升级、备份与校验

原生升级：先停止应用，备份 PostgreSQL（pg_dump 自定义格式）、DATA_DIR/uploads 附件及私有配置。新目录解压新版本，沿用原 native-config.json 和 DATA_DIR，执行 install，再 start。

Docker 升级：在旧目录执行 `docker compose --env-file .env.lean stop app`，保留数据库服务供下方备份脚本使用。备份完成后，将原 .env.lean 私密复制到新版本目录，保留项目名、密钥、数据库密码和原数据卷，再运行新目录的 install.sh 或 install.ps1 重建应用并前向迁移。

禁止把 v1.1.0 库交给 v1.0.0 运行；回退只能恢复匹配旧版本的独立备份库与附件。不要覆盖密钥或生成新配置替代原配置。

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

### 常见问题

#### Docker

- Docker 连接失败：确认 Docker 已启动，Windows/macOS 的 Docker Desktop 使用 Linux 容器模式。
- 拉取或构建失败：检查镜像仓库、npm、PyPI 网络连接；本包不含离线镜像。
- 端口被占用：修改 .env.lean 的 LEAN_HTTP_PORT 后重跑安装器。
- 默认仅能在本机打开；局域网部署需显式设置 LEAN_BIND_ADDRESS 和 LEAN_ALLOWED_HOSTS。
- 密码见 .env.lean；重新安装不会重置已有用户密码。

#### 原生安装

- Python 版本不符：使用 Python 3.11，可通过 PYTHON 环境变量指定完整可执行文件路径。
- 找不到 Nginx：确认已安装，并设置 NGINX_EXECUTABLE 为完整路径。
- 数据库或 Redis 连接失败：核对配置、专用数据库、账号、密码和服务监听地址。
- 端口占用：停止已有应用，或为 HTTP_PORT 与 APP_PORT 分别设置空闲端口。
- 配置文件已存在：configure 不覆盖既有配置，直接编辑原文件后运行 install。
- 终端关闭后应用停止：start 为前台进程；开机自启需运维使用操作系统服务管理器配置。

## 日常操作

1. 管理员在设置建立账户；采购员维护物料、客户和供应商。
2. 经理在销售中新建需求、报价及签约，签约时分配项目成员。收款节点合计必须等于最终报价，销售通过交接服务生成执行项目和应收；从销售单的执行项目链接进入后续工作。内部项目也可直接在项目模块创建。
3. 经理可先在项目“预算与成本管控”设置材料、人工、费用预算，再维护或导入 BOM。采购员按缺料建采购，提交后由经理批准，自动生成应付。超预算时需明确确认并填写原因，核算快照留在审计中；未设置预算的旧项目仅提示、不拦截。
4. 仓管分批收货、按项目领料。未收余量可取消，退货、盘点和退款保留历史。
5. 经理安排设计、装配、调试，成员完成任务并登记工时。发货前检查任务和对应领料量，支持多批设备交付。
6. 每批完成安装后由经理验收。售后关联验收批次：质保内免费，质保外登记收费。售后领料和工时纳入项目成本。
7. 财务登记费用、收付款、退款和冲销。任务、采购及余额全部处理后才能结项；需要继续售后时可重新打开项目。

合同/费用、采购/库存、工时各只维护一份业务事实。成本为 CNY 含税经营口径，不替代法定会计账。附件通过登录鉴权下载；成员仅可访问所属项目，敏感金额由后端按角色过滤。

## Docker 备份与恢复

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

## 开发与验证

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

测试分组唯一维护在 `scripts/ci/backend_test_matrix.py`。`python run_all_tests.py --stage checks|platform|business|concurrency|frontend|browser` 提供分阶段入口。后端测试需独立 `PG_TEST_HOST/USER/PASSWORD`，不使用业务库凭据。

当前范围见 [CORE_ERP_SCOPE](docs/CORE_ERP_SCOPE.md)，接口见 [LEAN_REBUILD_CONTRACT](docs/LEAN_REBUILD_CONTRACT.md)，本轮验证进度见 [SIMPLIFICATION_EVIDENCE](docs/SIMPLIFICATION_EVIDENCE.md)。其他历史文档不作为本版安装或模块清单。
