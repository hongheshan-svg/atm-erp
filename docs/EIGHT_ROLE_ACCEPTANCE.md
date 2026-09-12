# 八身份业务与页面验收（2026-09-12）

本次按用户明确要求执行完整业务验收。范围为当前 Lean ERP 的十个业务入口、项目详情子页、首次安装向导与合同预览。代码基于 `ce051d6c`，包含本报告所列未提交修复。

## 身份与环境

| 测试身份 | 权限重点 |
| --- | --- |
| 管理员 admin | 账户、公司、编号、审计；全模块操作与管理例外留痕 |
| 总经理 | manager 加显式 management_reports 授权，独立验证报表访问 |
| 项目经理 manager | 所管项目、任务、采购审批与成本；普通经理无经营报表 |
| 销售经理 sales_manager | 本人销售、报价、签约交接；他人销售和项目范围受限 |
| 采购 purchaser | 物料、供应商、BOM 多选下单；不得代替审批或收付款 |
| 仓管 warehouse | 收货、隔离品、领退料、盘点、采购退货；敏感金额过滤 |
| 财务 finance | 对账、收付款、退款、冲销、银行核对；业务金额只读边界 |
| 成员 member | 参与项目、本人任务和工时；不可见其他项目及敏感金额 |

仍为七个固定角色；总经理是单独验收的授权身份。另有兼岗及权限撤销测试。

- 桌面：`http://127.0.0.1:18506`，独立 Docker 项目 `atm-eight-role-qa`。
- 移动视口：`http://127.0.0.1:18507`，独立 Docker 项目 `atm-eight-mobile-setup`。
- 两端使用独立 PostgreSQL、Redis 和上传卷；整套测试镜像 `atm-eight-role-qa:final`，最后采购参数修复使用 `atm-eight-role-qa:final-2` 并重验采购/BOM及完整业务链。锁账用例单进程单 worker，结束后恢复原设置。
- 后端使用专用测试 PostgreSQL 与 `config.test_settings`。未清空数据库，未操作 18360/18496 用户站点，也未发起版本升级。

## 页面与业务覆盖

| 页面 | 本次执行内容 | 主要浏览器用例 |
| --- | --- | --- |
| 登录、首次向导 | 空表单、账号停用、改密旧密码失效、五步初始化、完成后禁止重复初始化 | login、setup、account-masterdata-audit |
| 工作台 | 八身份菜单和待办、页面跳转、销售单号定位、关注事项 | eight-role-audit、cancel-actions-audit、sales-role |
| 经营报表 | 管理员/授权总经理、普通经理拒绝、授权撤销、筛选、分页、汇总与明细、导出、只读关注展开 | reports、eight-role-audit、transfers、hardening-ui |
| 销售 | 需求、编辑、报价、签约指定项目经理、交接项目、附件、补充协议、取消并保留原单 | full-chain、sales-role、attachments、review-remediation、cancel-actions-audit |
| 项目 | 列表筛选、详情各页签、编辑、取消/重开、成员范围、附件 | eight-role-audit、cancel-actions-audit、attachments |
| 任务与工时 | 创建、分配、改派、取消、重开、完成、登记工时、工时更正、跨期阻断和补录 | full-chain、state-actions-audit |
| BOM | 缺料与行明细、维护/变更预览、自动物料编码、单元/品牌/类别组合、跨页多选、移除保留依据 | product-coding、bom-selection、review-remediation、cancel-actions-audit |
| 采购、合同 | 新建/提交/审批、超预算、退回修改、部分收货、隔离品、取消余量、账期、合同打印归档、质保登记/维修/关闭 | full-chain、review-remediation、payment-terms、hardening-ui、state-actions-audit |
| 库存 | 当前库存/移动流水、领退料、采购退货、超退失败、盘点并发快照冲突和重试、数量与金额核对 | full-chain、state-actions-audit、eight-role-audit |
| 项目成本 | 材料/人工/费用预算，超预算采购拦截及确认，实际成本、已承诺采购、剩余成本估算、来源明细 | full-chain、review-remediation |
| 应收应付/费用 | 款项明细、收付流水、已付款费用取消保留付款与退款余额 | full-chain、cancel-actions-audit |
| 业务/月度对账 | 差异阻断、作废、合同预付款核准、月结分次付款、原业务变化后的额度复核 | reconciliation、payment-terms、full-chain |
| 收付流水 | 收款、付款、退款、冲销、凭证补录/鉴权下载，银行匹配后不重复记账 | full-chain、attachments、review-remediation、reconciliation |
| 银行到账 | 认领、匹配、撤销匹配、多汇退回、撤销关联、误录作废；原生 XLSX 导入、缺户名阻断、核实、重复导入 | reconciliation、bank-review-audit |
| 基础资料 | 物料/客户供应商新增、编辑、停用，新单选择过滤、历史采购保留，编码规则与重复物料处理 | account-masterdata-audit、product-coding、transfers |
| 设置 | 用户管理、兼岗、权限撤销、本人改密、公司/编号/审计页签，锁账和重开 | settings、multi-role、reports、coding-rules、state-actions-audit |
| 通用操作 | 10主入口及项目子页逐岗访问、无权限直达回退、搜索/刷新、分页大小、必填校验、键盘页签/弹窗、响应式溢出、控制台错误 | eight-role-audit、navigation-dialog、module-tabs、pagination-layout、industry-forms |
| 导入导出 | 12类模板表头与页面说明逐列对应、错误文件阻断、取消重开清预览、非法类型逐行报错与整批回滚；物料CSV、BOM、原生银行XLSX实际确认与重复提交 | import-surface-audit、transfers、product-coding、bank-review-audit |

上述为明确执行的行为，模板下载/错误文件测试与成功入库测试分别记录。后端补充金额、库存、角色、并发、幂等、导入全部资源与异常数据的断言。

## 发现与修复

| 问题 | 修改与回归 |
| --- | --- |
| 关闭未确认导入后重新打开仍保留旧预览 | 重开时清空预览和页码；确认按钮禁用，旧文件未写入 |
| 选中项目后仍提示未选项目 | 提示随选中/清空同步；BOM及收付款页面回归 |
| 工作台销售链接被旧搜索覆盖 | 路由单号优先，同页链接更新；分页保留当前筛选，真实工作台点击回归 |
| 项目失败后刷新成功仍显示旧错误 | 重试清除旧错误；先失败再恢复单测 |
| 部分导入模型校验丢失行号及后续行错误 | 捕获模型校验并显示行号；错误间夹有效行仍整批回滚，不留编号/凭据/审计 |
| 对账类型传数组/对象触发500 | 写入前类型校验，返回400，失败不留原单及幂等凭据 |
| 质保处理状态传数组/对象触发500 | 写入前类型校验，返回400，质保与关联业务保持原状 |
| 采购BOM行关联传数组/对象触发500 | 复用identity校验后再作为字典键，合法字符串ID正常取号；非法请求不改变已有采购及明细、编号、凭据或审计 |

新增用例初跑还发现只读表格选择器和菜单退出动画同步错误，已作为测试问题修正；未计为产品缺陷，也未放宽业务断言。

## 验证记录

- 后端：260项通过（平台53、业务182、并发25）；Ruff、格式、Django系统检查、迁移一致性通过。日志 `/private/tmp/erp-eight-backend-final.log`。
- 前端：65项单测通过；lint、typecheck、build通过。构建日志 `/private/tmp/erp-eight-final-build.log`。
- 首次安装：桌面、移动各1项独立向导验证通过。日志 `/private/tmp/erp-eight-setup.log`、`/private/tmp/erp-eight-mobile-setup.log`。
- 新增状态动作桌面首轮：11项通过。日志 `/private/tmp/erp-eight-actions-final.log`。
- 双端整套：每端43项通过、1项首次安装按场景跳过、2项新增测试断言失败；保留原始失败记录。日志 `/private/tmp/erp-eight-final-desktop.log`、`/private/tmp/erp-eight-final-mobile.log`。
- 最后采购修复后的定向复验：每端账号/资料3项、BOM多选1项、完整业务链1项通过（同时运行的银行用例提示定位仍需修正）；日志 `/private/tmp/erp-eight-verified-desktop.log`、`/private/tmp/erp-eight-verified-mobile.log`。
- 银行原生导入最终单项补验：桌面/移动各1项通过；桌面键盘关闭菜单、移动触摸关闭，核实及重复导入均不增加收付款或匹配记录。日志 `/private/tmp/erp-eight-bank-verified-desktop.log`、`/private/tmp/erp-eight-bank-verified-mobile.log`。
- 合并整套与定向复验后的有效结果：每端45项通过，共90项浏览器用例；2项首次安装场景已另行验证通过，当前已安装实例按场景跳过。无已复现但未修复的业务失败。逐用例最终结果 `/private/tmp/erp-eight-final-verdicts.json`，保留各轮原始日志，不把失败轮写成全绿。
- 八身份逐页证据含每端222次页面/子页访问检查（含重复访问），合计444次。每端管理员42、总经理37、项目经理36、销售经理6、采购23、仓管23、财务37、成员18。每例附带 `page-operation-inventory` 和各主页面截图。

## 项目经理兼采购员完整链补验（2026-09-12）

按用户追加要求，管理员从用户管理页面创建同时具有 `manager` 和 `purchaser` 的单一账号。项目与采购使用该账号的两个独立浏览器会话，登录后通过 `/auth/me/` 核对相同用户 ID、两项角色及关闭的经营报表授权。销售、审批、仓库、财务及成员操作继续由相应人员交接完成。

- 真实页面链：销售需求与重报价 → 签约交接 → 双岗经理设置预算、导入BOM、多选下单并提交 → 本人超预算审批拒绝 → 管理员批准 → 预付款核准、付款冲销与重录 → 部分收货、取消余量及退款 → 双岗补购、本人预算内审批拒绝、管理员批准 → 收货领料 → 任务与工时更正 → 两批安装验收 → 免费/收费售后 → 费用及对账结算 → 结项、重开、再次结项。
- 两类自批均收到明确的申请人身份拒绝，采购原单和项目款项前后不变；未领料发货与未结清款项结项均被阻断。兼岗不获得仓管/财务写权限、默认经营报表授权，也不扩大其他项目的审批、预算、任务和取消权限。
- 补强旧仓管金额断言：检查实际只读表格无单价列，接口采购明细也不含 `unit_price`，避免仅查找不存在的输入框导致虚假通过。

| 最终核对项 | 桌面与移动结果 |
| --- | --- |
| 项目状态 | 已结项；两批设备均已验收 |
| 材料 / 人工 / 费用实际成本 | 500.00 / 400.00 / 50.00 元，合计950.00元 |
| 预算 / 已承诺采购 / 累计采购净额 | 950.00 / 0.00 / 500.00 元，无超预算 |
| 合同与售后回款 | 10000.00 + 300.00 = 10300.00 元 |
| 款项余额 | 2笔应收、2笔采购应付、1笔费用，5笔余额均为0 |

本轮使用已有 `atm-eight-role-qa:final-2` 镜像，新增和补强测试，未修改业务实现或迁移。桌面使用隔离18507（最终双岗项目 `ATM2626`，ID28），移动视口使用隔离18506（`ATM2679`，ID85），各自数据库独立。未操作用户站点或真实企业单据。

- 后端：hardening与reports两个模块19项通过，含新增2条本项目双岗身份隔离及其他项目管理范围回归。日志 `/private/tmp/erp-manager-purchaser-backend.log`。未重复执行全部后端套件。
- 最终浏览器：桌面2项通过（双岗完整链＋原七角色完整链），移动双岗1项通过；无跳过或重试。日志 `/private/tmp/erp-manager-purchaser-desktop-final.log`、`/private/tmp/erp-manager-purchaser-mobile-final.log`。每条完整链约1.2–1.3分钟。
- 初次桌面新增断言因超预算警告与权限错误同时存在而发生定位冲突，已精确定位错误框；原始失败日志保留在 `/private/tmp/erp-manager-purchaser-desktop.log`，不计为产品缺陷。
- 前端lint、typecheck、后端Ruff与格式检查、`git diff --check`通过。业务镜像未变化，沿用上一轮单测和构建证据。
- 最终账号/项目/采购/成本/款项与销售进度原始结果：`/private/tmp/erp-manager-purchaser-desktop-result.json`、`/private/tmp/erp-manager-purchaser-mobile-result.json`；截图位于对应 `*-final/` 输出目录，包含普通/超预算自批拒绝及结项成本页面。已查看桌面和移动截图。

## 验收边界

移动端使用 Chromium 390×844 触摸视口；桌面使用 Chromium 1440×1000 并补短窗口/键盘操作。未使用真实手机软键盘、纸质打印机、真实银行账户或生产企业数据；本轮未运行实际版本升级、外网中断、长期大数据压力和所有输入组合。业务测试完成不等于可以保证没有任何潜在缺陷。正式发布仍需执行发布门禁和安装/OTA全套检查。
