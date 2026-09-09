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

## 全新安装

需要 Docker 与 Compose v2。从源码目录运行：

```bash
bash install.sh
```

Windows PowerShell：`./install.ps1`。安装构建 PostgreSQL 15、Redis 7、应用三个服务，应用包含 Daphne 与 Nginx。默认访问 **http://127.0.0.1:8080/erp/**，管理员用户名 `admin`，首次随机密码在 `.env.lean` 的 `LEAN_ADMIN_PASSWORD`。

首次安装可设置 `LEAN_HTTP_PORT` 改端口；局域网部署在 `.env.lean` 设置 `LEAN_BIND_ADDRESS=0.0.0.0`，并在 `LEAN_ALLOWED_HOSTS=localhost,127.0.0.1` 后追加实际 IP 或域名，再重跑安装。环境配置文件需单独保管。重复安装保留已有账户、密码和数据。源码变更后重跑安装会重新构建应用。

**此版只支持独立的新数据库，不兼容旧版表或迁移。** 默认项目名 `atm-erp-lean` 和独立卷避免复用旧部署。发现旧表会拒绝启动，不能通过清库、fake migration 或跳过保护安装。原有旧版系统应保持独立，需要的数据由业务人员确认后重新录入。

## 日常操作

1. 管理员在设置建立账户；采购员维护物料、客户和供应商。
2. 经理在销售中新建需求、报价及签约，签约时分配项目成员。收款节点合计必须等于最终报价，销售通过交接服务生成执行项目和应收；从销售单的执行项目链接进入后续工作。内部项目也可直接在项目模块创建。
3. 经理可先在项目“预算与成本管控”设置材料、人工、费用预算，再维护或导入 BOM。采购员按缺料建采购，提交后由经理批准，自动生成应付。超预算时需明确确认并填写原因，核算快照留在审计中；未设置预算的旧项目仅提示、不拦截。
4. 仓管分批收货、按项目领料。未收余量可取消，退货、盘点和退款保留历史。
5. 经理安排设计、装配、调试，成员完成任务并登记工时。发货前检查任务和对应领料量，支持多批设备交付。
6. 每批完成安装后由经理验收。售后关联验收批次：质保内免费，质保外登记收费。售后领料和工时纳入项目成本。
7. 财务登记费用、收付款、退款和冲销。任务、采购及余额全部处理后才能结项；需要继续售后时可重新打开项目。

合同/费用、采购/库存、工时各只维护一份业务事实。成本为 CNY 含税经营口径，不替代法定会计账。附件通过登录鉴权下载；成员仅可访问所属项目，敏感金额由后端按角色过滤。

## 备份与恢复

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
