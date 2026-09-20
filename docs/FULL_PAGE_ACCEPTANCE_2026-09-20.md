# ERP 全流程与全页面验收（2026-09-20）

## 范围与环境

本次按用户明确要求验证全部页面及业务主链，不进行版本发布。应用源码为 v1.8.7、提交 `bff91a4494400dbb70934bfe8f51f67e89982c0f`；分支 `test/full-page-validation-20260920`。本轮补充测试覆盖，应用实现未改动。

结论：681 项自动测试通过，全部 14 个页面及内部业务页签已覆盖；截图复核发现 1 处非阻断的 BOM 长名称排版问题，尚未修复，见下文。

- 桌面：`http://127.0.0.1:18571`，独立项目 `erp-validation-20260920-desktop`。
- 手机视口：`http://127.0.0.1:18572`，独立项目 `erp-validation-20260920-mobile`。
- 两套安装分别使用新的 PostgreSQL、Redis、附件卷与显式测试凭据；现有 8080 实例未作为测试目标。
- 安装器正常注册两个宿主机升级执行器，服务端返回真实心跳。镜像 `atm-erp-validation:20260920-bff91a44`，镜像 ID 为 `sha256:68dc88e866253fbee7854e93a934b878c9f3217f80950f5b102098cb6770e4ea`。每套运行环境的 164 个后端源码/前端产物与工作区 SHA256 一致。
- 浏览器为 Playwright Chromium，桌面 1440×1000、手机 390×844；另有登录 1280×720、360×640、短屏表单和 768/1024 像素平板布局检查。前端检查使用本机 Node.js 26.9.0；后端测试镜像使用 Python 3.11、PostgreSQL 15。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| 后端静态检查、格式、Django 配置、迁移漂移 | 通过 |
| 后端平台 / 业务 / PostgreSQL 并发 | 59 / 223 / 25，共 307 项通过 |
| 前端 lint、typecheck、Vitest、build | 通过；26 文件、197 项单元测试通过，无构建体积警告 |
| 安装、升级、备份等运维单元测试 | 63 项通过 |
| 桌面 / 手机首次安装五步向导 | 各 1 项通过 |
| 桌面 / 手机完整浏览器套件 | 各 56 项通过，分别耗时 8.9 / 8.7 分钟；加首次向导共 114 项，无跳过、失败或重试 |
| 实际截图复核 | 已查看全部 14 个页面的两端截图及 BOM、结项预算等重点操作；发现 1 处非阻断排版问题 |

首次浏览器启动及一个本地监听端口测试受到 macOS 沙箱限制；获准执行后通过，未修改产品行为或放宽断言。测试期间开发配置仅用于这两套隔离环境。

## 页面覆盖

路由中的 14 个实际页面均列入验收；`/` 和未知路径属于重定向，不计为独立页面。以下路径省略 `/erp` 前缀。

| 页面 | 路径 | 检查内容及主要用例 |
| --- | --- | --- |
| 登录 | `/login` | 空凭据、停用账号、改密、可视范围；login、account-masterdata-audit |
| 首次启用 / 启用指南 | `/setup` | 五步初始化、兼岗、编号、重新登录及禁止重复初始化；setup |
| 工作台 | `/workbench` | 按岗位待办、审批、销售/生产入口；eight-role-audit、cancel-actions-audit、production-role |
| 经营报表 | `/reports` | 独立授权及撤销、筛选、汇总、只读明细、导出；reports、transfers、hardening-ui |
| 销售 | `/sales` | 需求修订、重新报价、签约、项目交接、补充协议、附件、交付回款；full-chain、sales-role、review-remediation |
| 项目列表 | `/projects` | 项目/任务/工时三个页签、范围、筛选、取消/重开；eight-role-audit、state-actions-audit |
| 项目详情 | `/projects/:id` | 任务/工时、BOM/明细、采购、交付/售后、款项/对账/流水、预算/成本、附件；full-chain、ui-concepts |
| BOM | `/bom` | 自动物料编码、版本、同料多单元、缺料与同屏采购；product-coding、bom-selection、bom-purchase-layout |
| 采购 | `/purchases` | 单据、本人自批拒绝、预算、退回、收货隔离、余量取消、账期与质保；full-chain、specialist-roles、payment-terms、state-actions-audit |
| 采购合同 | `/purchases/:id/contract` | 打印/附件、签署归档与原资料保留、响应式；hardening-ui、ui-concepts |
| 库存 | `/inventory` | 库存/移动流水、领退料、盘点冲突、退货金额、超退回滚；full-chain、state-actions-audit |
| 收付款 | `/finance` | 应收应付/费用、业务/月度对账、收付流水、银行到账认领与匹配、退款冲销；reconciliation、bank-review-audit、full-chain |
| 基础资料 | `/masterdata` | 物料/客户供应商、新增/编辑/停用、历史关联、导入导出；account-masterdata-audit、product-coding、transfers |
| 设置 | `/settings` | 用户/兼岗、公司、编号、审计、我的账户、密码、锁账；settings、multi-role、coding-rules、state-actions-audit |

通用检查包括无权限直达、分页、搜索与刷新、表单必填拒绝、键盘切换、详情关闭、内部横向滚动及浏览器控制台异常。`ui-concepts` 另外对各内部页签、合同、详情抽屉及表单逐个留图；纯页面访问不代替业务链写入验收。

逐岗巡检共 24 个两端身份用例、664 次页面/子页检查（包括重复访问）；这些访问次数不等同于 664 个独立页面。主套件保存桌面 198 张、手机 188 张截图，另有向导截图及问题复现图；自动覆盖不等同于每张截图均经人工视觉复核。

## 岗位与完整业务链

将 `frontend/e2e/eight-role-audit.spec.ts` 的历史八身份巡检补齐为十一岗位加单独授权的总经理，共 12 种身份；补充采购经理、机械工程师、电气工程师、生产经理的全部可见主页面、项目子页、越权入口回退和项目隔离。仍保留专门岗位的真实写入用例。

完整业务链在桌面和手机端均通过，分别覆盖独立七角色与项目经理兼采购员：销售交接、BOM、采购批准及禁止自批、收货/领退料、设计→装配→调试、工时更正、分批交付验收、免费/收费售后、对账、结清、结项/重开。各链最终核对材料 500.00、人工 400.00、费用 50.00、退货价差 0.00、总成本 950.00；预算与实际一致，采购净额 500.00、在途承诺 0.00，合同及收费售后收款合计 10,300.00。兼岗链的五条款项余额均为零，最终再次结项。

## 发现的问题

### BOM 采购草稿的长物料名称覆盖数量标签（非阻断）

1440×1000 桌面下，选择名称含连续英文/数字的物料（本轮样本为 `测试件BOM1789868410808-0`），草稿左侧名称文本越过其网格列，覆盖右侧“数量”标签。截图和 DOM 尺寸复核均可重现：文本右缘 1146.47px，数量列左缘 1105.27px，水平方向重叠约 41.2px。

定位：`frontend/src/components/BOMPurchasePicker.vue` 的 `.draft-item-title strong` 缺少连续长文本换行约束；旁边编码的 `small` 已使用 `overflow-wrap: anywhere`。建议修正名称换行或草稿列布局，并补长名称矩形不重叠的浏览器回归。

证据：[复现截图](../frontend/test-results/full-page-20260920/bom-long-name.png)、[尺寸测量](../frontend/test-results/full-page-20260920/bom-long-name.json)、本地证据中的 `check_bom_long_name.mjs`。复核只在原测试项目勾选草稿，未保存订单；同屏采购的金额和保存用例已通过。该问题作为验收发现保留，本轮未修改应用实现，不能将业务自动测试通过表述为界面无缺陷。

## 证据与限制

持久本地证据已复制到 `frontend/test-results/full-page-20260920/`（被 Git 忽略，不随提交上传）：[统计及覆盖明细](../frontend/test-results/full-page-20260920/summary.json)、[运行文件与心跳](../frontend/test-results/full-page-20260920/runtime-parity.json)、`desktop.json`、`mobile.json`、安装/测试日志及两端截图。

原始证据和隔离配置保存在 `/private/tmp/erp-full-page-20260920-sW67uk/`。后端与前端完整检查日志也已复制到上述仓库证据目录；临时目录另保留首次沙箱启动失败的记录。

本次为隔离模拟业务及桌面/手机视口验收，不是手机真机或企业生产数据验收；未发起在线升级、跨版本迁移、实际备份恢复或 GitHub 发布 CI，运维单元测试不能代替这些演练。

验收后已停止本次两套容器和升级执行器，两个 LaunchAgent 启动项移至临时证据目录的 `disabled-launchagents/` 留存，测试数据卷和附件保留；未清库、未删除业务数据。改动未提交、未推送。
