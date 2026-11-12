# 自动化公司模拟业务验收

本次使用隔离安装 `http://127.0.0.1:18360`，模拟两台自动化设备订单。所有浏览器业务写入通过实际页面完成；接口只用于核对事实及权限，不直接修改数据库推进流程。模拟数据不代替企业真实订单试运行。

## 场景与验收点

| 范围 | 实际验证内容 | 验证入口 |
| --- | --- | --- |
| 基础资料与人员 | 七角色账户、客户、供应商、物料及自定义编码 | full-chain、sales-role；后端 commercial_chain、sales |
| 销售 | 需求变更使报价失效，重新报价，销售经理签约并指定项目经理 | full-chain、sales-role |
| 项目与 BOM | 成员分配、版本导入、品牌/单元/类别多选采购、同料多单元 | full-chain、bom-selection、review-remediation |
| 采购与预算 | 提交、普通/超预算批准、退回修改、取消未收余量、预算调整人复核限制 | full-chain、review-remediation；后端 budgets、concurrency |
| 仓库 | 部分收货、领料、隔离品复检及退回；库存成本与采购退款区分 | full-chain、review-remediation；后端 inventory |
| 生产 | 设计、装配、调试、本人登记工时、更正保留冲销记录 | full-chain；后端 execution |
| 分批交付 | 未领料拒绝发货，两批各一台，安装与验收顺序 | full-chain；后端 execution、operational_review |
| 售后 | 质保内免费换件、质保外收费、材料及工时计成本 | full-chain |
| 收付款 | 采购付款、冲销重付、取消余量退款、费用、合同与售后回款、欠款拒绝结项 | full-chain；后端 commercial_chain |
| 成本管控 | 材料/人工/费用预算、实际与在途、剩余成本预测、成本来源 | full-chain、review-remediation；后端 budgets、operational_review |
| 附件与协议 | 销售/采购上传、鉴权下载、项目汇总、补充协议、财务凭证追加 | sales-role、attachments、review-remediation |
| 经营报表 | 管理员授权总经理、查询导出、撤权后拒绝、实际与承诺及逾期计算 | reports、transfers；后端 reports |
| 导入导出 | 模板、预览、整批确认、筛选全量导出、错误回滚、重复确认和权限 | transfers；后端 transfers、import_documents |
| UI 与权限 | 页签直达/记忆、分页、短屏操作、桌面键盘与窄屏滚动、角色菜单及接口隔离 | settings、module-tabs、pagination-layout、navigation-dialog；后端角色测试 |

## 七角色闭环核对

销售经理创建并签约 10,000 元订单，项目经理负责执行，采购员下单，管理员复核超预算采购，仓库收领料，成员执行任务并登记工时，财务登记收付。两批验收后另有 300 元收费售后。

测试要求最终应收净回款 10,300 元、所有应收余额为零；材料成本 500 元、人工 400 元、费用 50 元，总成本 950 元，已承诺在途为零。结项后销售经理能查看验收及回款，无成本字段或财务写入入口；重新打开保留原事实。

## 当前验证记录（2026-09-10）

- 后端完整检查 179 项通过（平台 38、业务 120、并发 21），包括静态检查及迁移一致性：`/private/tmp/erp-goal-backend-final.log`。
- 发现并修复报表测试的固定日期夹具失效：将该用例采购应付设为当天到期，验证当天不逾期、昨天到期的费用计入逾期；没有改变正确的报表计算。
- 前端 lint、typecheck、31 项单元测试及生产构建通过。
- 部署一致性核对：82 个后端 Python 文件与当前工作区一致，28 个前端构建文件与本次 dist 一致；哈希清单在 `/private/tmp/erp-goal-runtime-hashes.json`、`/private/tmp/erp-goal-frontend-hashes.json`。
- 七角色浏览器专项桌面、移动端 2 项通过，日志 `/private/tmp/erp-seven-role-chain.log`；最终完整回归 26 项全部通过（桌面 13、移动端 13，7.3 分钟，无重试），日志 `/private/tmp/erp-goal-browser-all.log`，截图在 `/private/tmp/erp-goal-browser-results/`。
- 已查看最终桌面和移动端销售结项回款截图；两批验收、合同及售后款余额为零，移动端底部操作保持可见。最终异常链也通过项目刷新后的父子页签可见性断言，覆盖先前该处的超时/滚动问题。
- 本次模拟业务链及上述范围验收通过，未发现仍待修复的本次复现问题。代码保留在功能分支，未提交、推送或发布；没有操作生产数据。

测试注册表仍仅由 `scripts/ci/backend_test_matrix.py` 维护；上表用于说明业务覆盖，不作为第二份执行清单。安装、备份恢复及 OTA 历史专项见 SIMPLIFICATION_EVIDENCE.md，本次业务测试不将其重新声称为当日实机演练。
