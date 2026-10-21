# 32项审计整改与业务决策（2026-10-22）

本轮依据外部审计 `audit/MASTER.md` 的32个编号实施，继续使用分支 `fix/full-audit-2026-10-21`，保留已有提交和工作区改动。32项代码整改已完成，12个待确认事项均已处理（9项用户业务选择、3项技术调查）；以下结论以本轮实际验证为依据，不把历史报告中的“已提交”直接视为验收通过。

## 整改对照

| 编号 | 修正行为 | 主要验证位置 |
| --- | --- | --- |
| PA-01 | 金额读取按动作和项目范围计算，兼岗不能扩大完整金额、成本、款项及敏感项目附件范围；采购/财务合法读取保留 | `test_money_scope`、`test_hardening` |
| BP-01 | 多明细分次收货允许本次未到行填0，仅处理有效到货行，重复明细仍拒绝 | `test_audit_business`、`test_review_remediation` |
| BP-02 | 按BOM行ID修订时省略单元保留原单元 | `test_bom_selection`、`test_audit_business` |
| BP-03 | 前端留空不误建未分单元行；只有明确指定时才更改单元 | `audit-fixes.spec.ts`、`audit-business.spec.ts` |
| BP-05 | 采购草稿可修改账期，并按账期条件显示日期/天数 | `test_payment_terms`、`audit-fixes.spec.ts` |
| BP-08 | 合同页归档后不再显示重复归档操作 | `PurchaseContractPage.audit.spec.ts` |
| BP-09 | 未批准采购明确为整单作废；已批准采购按本次明细取消 | `audit-business.spec.ts` |
| UX-01 | 导入ID引用错误显示中文字段及文件行号，可定位单元格 | `test_import_feedback`、`import-audit-real.spec.ts` |
| UX-02 | 项目内工时、收付款等导入显示正确项目上下文 | `import-context.spec.ts`、`import-audit-real.spec.ts` |
| UX-03 | 确认阶段校验失败回填错误行、禁用旧凭据并提供标注文件 | `TransferTools.spec.ts`、`import-audit-real.spec.ts` |
| IF-01 | 对账授权只比较经济事实，改名/备注不使其失效；金额、主体、账期、库存及资金变化仍失效 | `test_reconciliation` |
| SP-01 | 仅更换负责人时同样检查遗留任务，需先改派或保留原负责人为成员 | `test_audit_business`、`test_operational_review` |
| SP-02 | 签约/协议日期不得晚于今天，失败不留下项目/应收等副作用 | `test_sales`、`test_audit_business` |
| IF-02 | 逾期汇总按整数分相加，避免浮点尾差 | `FinanceTotals.spec.ts` |
| TR-02 | 后端settings按共享核心映射选择检查，新增测试及导入辅助文件登记影响范围 | `test_ci_workflows.RoutingTests` |
| TR-03 | 附件超时重传复用操作标识，核对实际文件内容并隔离旧请求响应 | `InlineDocumentField.spec.ts` |
| TR-04 | 真实唯一约束冲突返回中文409；其他完整性错误不伪装成重复记录 | `test_platform` |
| TR-01 | 复用当前查询的成员预取与请求范围，列表20/200条查询数量一致，写入继续锁内重新授权 | `test_permission_queries`、`test_money_scope` |
| UX-10 | 规范化业务内容防重复导入，确认阶段跨用户串行复核，显式允许再次新增与网络重试分开 | `test_import_dedup`、`test_import_concurrency` |
| UX-09 | 成功后可直接打开实际导入结果，不把库存移动ID当库存ID | `import-context.spec.ts`、`import-audit-real.spec.ts` |
| UX-07 | 采购/BOM、期初、领料、退料及采购退货的正数量前端提前校验，服务端明细错误定位到行和字段；收货未到行、盘点仍允许0 | `test_audit_business`、`ActionDialog.audit.spec.ts`、`inventory.spec.ts` |
| IF-06 | 创建对账申请时即检查额度，确认时再次检查，超额不留申请及编号副作用 | `test_reconciliation`、`finance.spec.ts` |
| IF-07 | 收付款默认值受余额和所选对账剩余额度限制，手填金额不静默截断 | `finance.spec.ts`、`FinancePage.spec.ts`、资金并发用例 |
| SP-07 | 管理员、项目经理、财务可从已签约销售进入只读交付回款 | `audit-business.spec.ts` |
| SP-03 | 售后任务保留完整标题，应收摘要截取到字段长度并保留任务关联 | `test_audit_business` |
| SP-04 | 补充协议缺失/非法版本为字段400，版本过时仍409 | `test_audit_business` |
| UX-04 | 采购/往来单位账期示例一致，条件字段明确留空规则 | `test_transfers` |
| UX-05 | 费用模板明确金额为费用应付总额、导入不代表付款，原表头兼容 | `test_transfers`、`IMPORT_TEMPLATES.md` |
| UX-08 | 导出文件使用中文业务名称和日期 | `import-context.spec.ts`、`import-audit-real.spec.ts` |
| IF-08 | 仓管零库存盘盈仍拒绝，并明确联系管理员填写单位成本 | `test_inventory`、`inventory.spec.ts` |
| IF-09 | 金额统一两位小数，核准月份/额度错误使用正确字段，银行重复编号明确提示 | `test_payment_terms`、`test_reconciliation` |
| IF-05 | 复现多项目导入死锁后稳定排序预锁；交叉人员外键死锁通过批量与单笔工时一致的人员锁修复，等待后重新授权 | `test_import_concurrency` |

测试模块唯一登记位置仍为 `scripts/ci/backend_test_matrix.py`；此表只用于问题追踪，不替代测试矩阵。

## 已确认业务选择

以下九项由用户逐项选择后实施，不使用等待超时或默认选中代替确认。

| 编号 | 用户选择与实现边界 |
| --- | --- |
| BP-06 | 允许按明细取消未收数量，其他明细继续履约；所选隔离明细先处理，已收数量不能取消，应付按累计舍入差额冲减 |
| SP-05 | 客户付款期限独立于维修期限；新页面收费时单独填写，旧客户端缺省以售后业务日期兼容 |
| SP-02b | 允许合同收款节点早于签约日，保留真实约定日期并提醒，不修改逾期计算 |
| BP-04 | 允许补录早于采购单创建日期的实际收货，填写补录原因，锁账保护继续生效 |
| BP-07 | 全部到货待检时突出“已到货待检”和隔离数量，合格库存仍为0，不虚增库存 |
| UX-06 | 生产经理只导入参与项目的装配/调试任务，设计仍由项目经理操作；兼任采购不扩大范围 |
| IF-03 | 约定付款日与实际应付到期日分开显示；未收货不凭约定日期产生付款额度 |
| IF-04 | 可补录锁定期原始银行流水用于核对；生成付款、修改既有锁定期记录仍受截止保护 |
| SP-06 | 关联未签约销售的历史项目保持未签约；需求变更后重新报价，重开不得直接执行。直接创建的执行项目按原规则处理 |

## 技术调查结论

- **PA-02**：不依赖公司是否单出口IP即可修正。生产登录保持每IP 10次/分钟；有效刷新独立按账号30次/分钟，无效刷新独立按IP 10次/分钟。先验证签名、账号及撤销状态，再决定账号桶。
- **TR-05**：外网版本请求移出持锁事务，锁内仍复核管理员、活动任务、执行器及版本/资产；旧请求可离线重放。此改动不等同于真实执行器升级验收。
- **TR-06**：拒绝原报告“保留30天后直接删除回执”的建议。删除防重键会把旧付款/库存请求变成新操作；本轮长期保留键及结果，增加十年前凭据的回放、内容变化、撤权与停用验证。未引入清理任务，也未删除历史记录。

## 验证环境与完成边界

- 全新隔离 PostgreSQL 15 容器，端口55436；不同工作组使用各自 `test_atm_erp_lean_audit32_*` 测试库。预览使用独立开发配置、Redis及附件目录，不读取生产配置，不关闭schema guard。
- 浏览器预览为 `127.0.0.1:18330/erp/`，后端为18321。桌面与390px手机视口检查改动场景；模拟API的组件测试与真实API/事务验证分开记录。
- 按本次权限、导入、资金、采购及认证等共享改动的影响计划验证关联模块，不运行未获请求的完整销售到收款页面链。
- 后端最终按影响计划的34个测试模块共 **482项通过**，含真实PostgreSQL并发、权限拒绝、事务回滚、幂等及迁移相关接口；前端30个测试文件共 **268项通过**；CI影响计划与门禁规则 **35项通过**。
- 后端Ruff/格式、Django检查及真实隔离库迁移历史检查通过，模型无新迁移；前端ESLint、类型检查、构建通过。构建仍有既有ActionDialog静态/动态导入合并提示，不影响构建成功。
- 桌面与390px手机视口实际核验采购部分取消、历史补录、待检数量、售后双期限、提前节点签约；财务额度默认值、超额拒绝、重复流水号；库存四入口0值拦截/0.001保存、盘点0保存。均读取实际保存结果，代表截图已打开检查。手机为模拟视口，不代表手机真机验收。
- 导入页面使用真实API专项（两场景×桌面/手机），核对项目上下文、中文错误定位、确认失败整批回滚、重复确认、结果入口，以及生产经理任务范围和降权后旧凭据拒绝。最终后端重启后 **4项通过**，结果见 `imports-browser-integrated.log`。
- 临时证据目录：`/private/tmp/erp-audit32-handoff/`。主要日志为 `backend-integration-final.log`、`backend-checks-final.log`、`frontend-integration-final.log`、`frontend-lint-final.log`、`frontend-typecheck-final.log`、`frontend-build-final.log`、`ci-routing-final.log`、`imports-browser-integrated.log`、`business-browser-results.md`、`finance-browser-final.log`、`inventory-ux07-browser.log`。永久测试代码已纳入仓库，临时日志不是发版凭据。
- 上述记录属于发布前本地验证，未运行完整业务页面链或真实OTA升级演练，本地OTA证据限升级接口事务、权限和回放。后续v1.8.15正式发版另由GitHub Actions运行suite=release（含所选OTA演练），状态以工作流和发布页为准；不升级生产环境。

## 独立复核追加修正

- 发版CI额外发现跨时区默认日期不一致：UTC浏览器的“今天”比服务器上海业务日期早一天，导致正常收货误要求补录原因、采购报修被拒绝。`today()`统一使用Asia/Shanghai，保持用户填写日期与历史补录校验不变。新增15项午夜、跨年、闰日及业务默认日期回归；UTC环境77项、洛杉矶与UTC+14环境各24项通过，定向lint、类型检查与构建通过。真实UTC浏览器按原操作复验收货、质保、任务与锁账，桌面/手机共8项通过（`business-utc-e2e.log`）。修复后重新运行正式发版验证，之前失败的CI不作为发布凭据。

- **银行等价时间绕过防重**：真实复现同交易换时间写法可生成第二笔银行流水及收款后，改为完整规范化交易身份比较。新增8项银行回归覆盖旧指纹、旧凭据、锁账、等价格式并发、重复认领拒绝，以及不同交易不能误合并。不会自动删除或合并已存在的历史重复流水；遇到冲突须核对原始记录及认领。
- **交叉工时外键死锁与等待撤权**：新增7项持久化并发回归，覆盖导入↔导入、导入↔单笔、导入↔更正、每日24小时竞争、等待后撤权和最新费率。使用兼容外键引用的人员行锁，仍保持同一人员的工时/费率互斥，不通过重试吞掉数据库错误。
- 最后一次独立代码复核未发现新增可复现缺陷；最终测试结果以上述集成日志为准。
