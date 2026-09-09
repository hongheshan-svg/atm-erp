# 精简版接口契约

根路径 `/api/business/`；需要 Bearer JWT。列表采用 `count/next/previous/results`，默认 20、最大 200 条，使用 `page` 和 `page_size`。业务写入为 JSON 对象；除基础资料 PATCH 外均为 POST。所有业务写入提供 `Idempotency-Key`，相同键和相同数据回放一次结果；数据改变必须换键，每次回放重新授权。

日期 YYYY-MM-DD；金额两位小数、数量三位小数的十进制字符串。错误：400 输入校验、403 无权限、404 不存在或不在范围、409 状态/并发冲突。界面展示服务端原因，不自行算账作为事实。

## 表格导入导出

- 业务列表 `{resource}/export/?file_format=csv|xlsx` 使用原列表全部筛选结果，忽略分页，最多20000行；沿用 queryset 项目范围及序列化金额过滤。采购按明细展开。附件列表仅导出元数据，附件内容仍走独立鉴权下载。设置不属于业务表格导入范围。
- `reports/?file_format=csv|xlsx` 导出全部筛选项目明细与合计，沿用管理员/总经理报表授权。金额为 CNY 含税经营口径；XLSX数值使用文本单元格保存，CSV保存原始十进制字符串，避免服务端转换损失精度。Excel读取CSV时应按文本导入编码/大金额列，以免软件自动转换前导零或长数字。危险公式前缀转义为文本。
- items/partners/sales/projects/purchases/tasks/stocks/moves/entries/payments/time/deliveries 提供 `import-template/` GET（file_format同上）、`import-file/` POST multipart单个file、`import-confirm/` POST JSON `{token}`。CSV为UTF-8，XLSX仅一个工作表，禁止公式，文件5MB/1000行上限，严格使用模板列。关联使用编码或账号，标注ID的列从列表导出获取。
- 预览返回 count/rows/errors/can_import/token/note，在事务内调用现有服务校验后回滚；错误按文件行号展示。确认凭据绑定用户/模块、30分钟有效，确认重新授权和校验，任一行失败则全部回滚。同一token的重试或并发确认使用同一ActionReceipt，返回同一结果；新文件应重新预览。
- 物料/往来单位与采购由采购权限新增；销售/项目/任务/交付由经理权限新增；期初仅管理员；领料由仓库权限；费用和收付款由财务权限；工时保留本人任务和项目范围。采购同一分组号合为一张草稿，组内单据信息必须一致。销售/采购不自动审批签约；应收应付由原合同采购产生；退款、冲销、盘点、更正仍从原记录操作。预览不产生持久业务记录、审计或编号计数变更。

## 平台接口

`/api/auth/login/` 接收 username/password，返回 access/refresh；`refresh/` 接收 refresh；`me/` 返回 id、username、display_name、role、management_reports；`directory/` 返回启用人员 id/display_name 数组。`password/` 接收 old_password/new_password，修改后令牌撤销，重新登录。

`/api/auth/users/` 管理员 GET/POST，`users/{id}/` GET/PATCH：username、display_name、role、hourly_cost、is_active、password、management_reports。新增必填密码，至少 12 位；不可移除最后管理员。management_reports 默认为 false，仅 manager 角色允许设为 true；管理员自动可看经营报表。授权更正留审计，me 返回本人此开关，不接受用户自行更改。

登录及令牌刷新沿用 LoginThrottle：APP_ENVIRONMENT=production（默认）为10次/分钟，development关闭限流，其他值拒绝启动。Compose/安装器通过 LEAN_ENVIRONMENT 设置该值，默认 production；发布时不得沿用 development 配置。DEBUG 独立且默认关闭。

## 经营报表

`/api/business/reports/` GET，管理员或 management_reports=true 的 manager 可读，其余角色 403，每次请求核对当前授权。参数 search（项目名称/编号，最多150字符）、status（项目状态，留空全部）、risk（over_budget/overdue/unbudgeted，留空全部）、page（正整数）、page_size（1–200，接口默认20）。响应 summary/count/page/page_size/results/generated_at/filters；summary 汇总全部筛选结果，不仅当前页。前端统一默认每页10条，可选10/20/50/100并跨页面保存，调整大小回第一页。

全部为当前筛选项目的累计经营口径，包含已结项和已取消项目（可用状态筛选排除）；已签约合同额不作为会计收入。实际成本与项目页共用批量投影，在途承诺、累计采购预算校验复用预算服务。未设预算与零预算区分；交付逾期仅统计计划日期早于今天且执行中/交付中的项目，质保阶段不再算交付逾期。待收待付按原单金额减抵减、减净收付款求余额，逾期为期限早于今天；正向余额和负向退款分别汇总，取消项目退款仍显示。费用属于待付款，付款不重复计成本，冲销按原负向流水抵消。报表无写接口、无独立台账、无期间收入/完工利润推算。

## 公司与编号

`/api/core/company/` GET、`company/1/` 管理员 PATCH name/address/phone；`codes/`、`audit/` 管理员可读。`/api/health/` 返回 schema 版本。

`/api/core/codes/{id}/configure/` 管理员 POST，提供 Idempotency-Key，完整提交 prefix/date_format/padding/reset_cycle/reason/expected_revision。前缀为 1–10 位字母、数字、短横线或下划线；日期可为空或 YYYY/YYYYMM/YYYYMMDD；流水补零位数 1–10，超出位数自然增长；周期 never/year/month/day，日期必须覆盖重置周期。生成格式为前缀＋服务器本地日期＋流水；修改配置不回退现有序号，仅周期切换时从 1 起，已存在编码（含软删除）自动跳过。规则版本过期拒绝，修改原因及前后配置留审计；不允许编辑计数器、用途或历史业务编号。

## 销售

- `sales/` GET/POST：name/customer/manager/requirements/due_date/equipment_quantity/warranty_months。经理或管理员创建；管理员、经理、财务可读，其他角色禁止。
- `sales/{id}/quote/` POST amount/reason；需求中或已报价可报价。
- `sales/{id}/edit/` POST reason、expected_updated_at 与待修改的销售基础字段；仅未签约单可改。expected_updated_at 必须等于打开表单时的版本，过时返回 409；无实际修改返回 400。修改后清除当前报价并回到需求状态，必须重新报价，原报价及修改前后内容保留在审计中。
- `sales/{id}/sign/` POST date、contract_number?、manager?、members?、milestones[{title,amount,due_date}]；合同编号按实际签署合同填写，去首尾空格、最多 80 字符、全局唯一（含软删除），留空为 null；签约后不可直接覆盖，历史记录不自动补造编号。节点合计必须等于最终报价。单事务创建执行项目和应收，返回 id（销售）与 project。重复请求只回放，其他键再次签约拒绝。历史迁移的未签约项目保留原人员及编号。销售列表可按合同编号搜索。
- `sales/{id}/cancel/` POST reason；仅未签约单可取消。已签约合同保持历史，执行中止由项目处理，收款纠错由收付款处理。
- 销售独立存储报价、合同金额和签约日期；项目的同名字段为只读投影。项目执行数据在交接后独立维护。

## 项目与基础资料

- `items/`、`partners/` GET/POST/PATCH。编号自动生成；物料新建可选 code，留空自动生成，手填去首尾空格、最多 30 字符，全局唯一且包括停用/软删除；与自动取号共用锁，保存后不能编辑编码。物料其余字段 name/specification/unit/is_active/brand（80字符）/part_type（standard标准件、custom非标件或空）。往来单位 name/kind(customer/supplier/both)/contact/phone/address/is_active。采购员、经理、管理员维护。物料导入新增品牌/物料类别列，旧四列模板兼容；旧数据保持未分类。
- `projects/` GET/POST：name/customer/manager/members/requirements/due_date/equipment_quantity/warranty_months。经理或管理员创建，普通成员只看所属项目。
- `edit/`：reason 和待修改项目字段；签约或已有交付后不能直接改客户、设备数量、质保约定，包括无销售合同的独立项目；移除成员不能遗留待办。
- `cancel/`、`reopen/`、`close/`：reason。取消需要处理采购、退料和应付，原合同历史保留；结项需要全部设备验收、任务及采购完成、余额为零。
- `cost/` GET：materials、labor、expenses、purchase_return_variance、total。仅管理员、经理、财务可看。
- `cost-analysis/` GET：预算、实际、已承诺（在途）、实际＋在途、预算余量，以及累计采购净额和超额提示；仅管理员、经理、财务可看。材料实际含采购退货价差；在途仅为已批准未收货采购，按累计收货分角规则计算。人工、费用没有承诺计划，列为零，不代表完工预测；未付款费用已经计入实际，不重复计入承诺。
- `budget/` POST materials/labor/expenses/reason/expected_revision：管理员、经理在执行中/交付中/已验收项目设置或更正预算。三个金额非负，0 为零额度；版本必须等于查询时的 budget_revision，否则 409。旧项目默认为未设置预算（null），不启用拦截，不能用 0 代替未设置；设置后不支持清空，所有更正留审计。

## BOM 与采购

- `projects/{id}/demand/` GET：revision、lines[{bom_line,item,item_code,item_name,specification,brand,part_type,assembly_unit,unit,is_active,quantity,issued,incoming,available,shortage}]。品牌/类别读取物料事实，单元读取项目 BOM 行，共享库存不预留。关联采购优先计入原BOM行在途，其余在途、已领和共享库存按行顺序分摊一次；展示分摊不代表单元实际领料归属或保证可领。
- `revise-bom/`：必填 expected_revision、lines[{item,quantity,change_note,assembly_unit?}]，单元为100字符内的设备功能单元名称，显式空值可清空，省略保留旧值。版本取自 demand 或导入预览，缺失/格式错误返回 400，过时返回 409；数量不小于已领与在途，已有行修改需说明；同一物料在同一单元只有一条有效 BOM，同物料允许跨单元；不增加多层BOM或独立单元表。修订可带行id以更改单元，替换物料需新增行。总量不得低于物料已领与在途，单行数量不得低于其关联未收采购。
- `bom/{id}/remove/`：reason，仅无该行未收采购且其他单元总量足以覆盖物料已领与在途时可移除，保留软删除历史。
- `projects/bom-template/` CSV 模板为物料编码/数量/变更说明/单元，兼容旧三列模板（保留旧单元）；`projects/{id}/import-preview/` multipart 单个 file（CSV/XLSX，5MB、1000 行上限）。返回 expected_revision/lines/errors/can_import。确认时仅将 item/quantity/change_note/assembly_unit 提交 revise-bom；禁止直接提交预览中的行号或展示字段。
- 采购列表及项目BOM提供多选选料，品牌/单元/类别同一维度多值为或，维度之间为且；跨页及筛选变更保留勾选。无缺口或停用物料不能选择。生成采购表单时重新读取需求，仅带所选BOM行，随后通过原 purchases/ 的 from_demand/bom_line 校验保存，不能超额或重复占用缺口；订单仍为单供应商草稿，提交审批流程不变。
- `purchases/` POST：project/supplier/due_date/note/lines[{item,bom_line?,quantity,unit_price,due_date?}]/from_demand。按缺料采购必须关联 BOM 并在服务端重新检查缺口。
- `purchases/{id}/submit/`、`approve/`：空对象。采购员提交，经理批准，批准生成唯一应付。
- `purchases/{id}/budget-check/` GET：经理、管理员、财务读取待批准采购的批准后预算对比与 snapshot。`approve/` 在项目锁内重新核算；任一类别、总计实际＋在途超过预算，或累计采购净额超过材料预算，返回 409，不产生应付或防重复凭据。收货不释放累计采购额度，取消余量、供应商退货按应付冲减释放额度。
- `purchases/{id}/approve-over-budget/` POST reason/confirmed/expected_snapshot：经理或管理员明确批准超额，confirmed 必须为 true，reason 必填，snapshot 必须等于锁内实时核算结果，否则 409 要求重新查看。保存批准人、原因及完整预算检查快照，不自动增加项目预算。预算设置和超额批准沿用经理角色，但最近预算调整人不能自行批准超额采购（403）；其他经理复核，管理员例外也必须填原因。不增加独立审批角色或多级流程；审计保留两类动作。
- `receive/`：location/reason/lines[{line,quantity,pending_quantity?}]，line 是本单采购明细 id；quantity是合格入库数量，pending_quantity是隔离待处理数量（默认0），两者合计必须为正且不超过实际未到数量。隔离不计可用库存、不减少承诺或应付；仓管分批合格入库，累计金额保留分角差。
- `cancel-remainder/`：reason，取消未收数量并冲减应付，已付多出部分形成待退款余额。

## 库存与纠错

- `stocks/` GET；`stocks/opening/` 管理员 POST item/location/quantity/unit_cost/reason，只允许无历史库位。
- `stocks/issue/`：project/stock/task?/quantity/reason；生产领料受 BOM 上限约束，已验收项目必须关联未完成的售后任务。
- `stocks/{id}/count/`：quantity/expected_quantity/expected_updated_at/reason，拒绝过时盘点快照；只有零库存盘盈可由管理员额外给 unit_cost。
- `moves/` GET；`moves/{id}/return-material/`：quantity/reason，不能超原领料或退回已交付部分的必要材料。
- `return-purchase/`：quantity/reason，供应商冲减按原采购成本，库存按移动平均价值退出，价差单列。

## 任务、交付、售后

- `tasks/` POST：project/kind(design/assembly/test)/title/description/assignee/due_date；由经理创建。
- `tasks/{id}/complete/`：reason，执行人或经理完成，阶段顺序校验。`assign/`：assignee/reason；`cancel/`、`reopen/`：reason，由经理操作。安装与验收任务不可随意取消。
- `tasks/{id}/time/`：date/hours/reason/user?；本人登记，经理可代录。每日净工时≤24，按当时费率快照计成本。
- `time/{id}/amend/`：date/hours/reason，原人员或经理更正，hours=0 撤销。冲销+替代记录保留历史与原费率，重复更正拒绝。
- `projects/{id}/ship/`：quantity/date/installer/acceptor/note，生产阶段完成且累计领料覆盖本批数量后才可发货，创建安装与验收任务。
- `deliveries/{id}/accept/`：date/reason，经理确认安装完成后的验收；每批独立保修截止日。
- `projects/{id}/service/`：delivery/date/title/description/assignee/due_date/fee。质保截止日当天仍免费，期外收费必须为正数并生成应收。售后材料、工时纳入实际成本。

## 收付款与附件

- `entries/` GET（经理/财务/管理员）；`entries/expense/` 财务 POST project/title/amount/due_date。
- `entries/{id}/pay/`、`refund/`：amount/date/reason/method?/account?/reference?/document?，金额为正，由服务器检查余额和方向。
- `cancel-expense/`：reason；`payments/{id}/reverse/`：date/reason。通过冲减及冲销保留历史，不物理删除。
- `payments/` 与 `time/` 的 `reversed_by` 为关联冲销记录 id，未冲销为 null；与 `reversal_of` 一起供页面展示原记录、冲销记录及有效记录，后端仍独立校验重复操作。
- `documents/` multipart POST project/category/file（20MB 上限）。分类 drawing/contract/receipt/delivery/other；合同经理上传，凭据财务上传；敏感分类仅金额可见角色读取。
- `documents/{id}/download/`：鉴权下载，无公开 media 路由；返回附件流、private/no-store、nosniff。
- `workbench/` GET：tasks 与按角色可见 approvals/receipts/drafts/settlements，每组 count 和前 20 条 results；数量统计为全量，已取消项目的待退款仍保留。

## 评审整改补充契约

- `projects/{id}/bom-impact/` GET，经理/管理员可读。返回按物料汇总的需求、已领、在途、当前最低可改量和未完成采购链接；不创建新的变更台账。减少用量先取消采购余量、处理隔离品和退回未用材料；已交付所需材料不能退。
- `purchases/{id}/reject/` POST reason，经理将待批准采购退回草稿。`edit/` POST expected_updated_at/reason/due_date/note/lines[{id,quantity,unit_price,due_date}]，采购权限仅改草稿，保留原明细ID，重新校验BOM总缺口、金额及版本；不得漏行或重复行，重新提交后才可批准。
- `purchases/{id}/delivery-plan/` POST expected_updated_at/reason/lines[{id,due_date}]，采购权限维护已批准/部分收货的未完成明细承诺日期；不改变原应付期限。工作台为采购及仓库提供逾期未完成明细对应采购入口。
- `purchases/{id}/quality-accept/` POST location/reason/lines[{line,quantity}]，仓库将隔离数量转入合格库存，数量不能超过隔离余额。`quality-return/` POST reason/lines[{line,quantity}]，仓库将隔离品退回供应商，继续保留待补货数量及原应付；不再补货需采购另行取消余量。隔离余额未清不能取消余量。`handling-history/` GET 沿用采购可读角色，分页展示上述动作的人员、时间、原因，不向仓库暴露价格。
- `sales/{id}/amend/` POST expected_updated_at/reason/document/date/amount/equipment_quantity/warranty_months/milestones?/credits?。经理提交正式补充协议，document必须是同项目合同附件；amount为变更后总额。增额milestones[{title,amount,due_date}]合计必须等于差额；减额credits[{entry,amount}]必须指向同项目合同应收，合计等于减少金额且不超过原款项可抵减额。已收款抵减后保留负余额供财务退款。无金额差额时不允许节点或抵减。已发货不能改变总设备数；质保仅改变后续批次。原签约金额original_contract_amount保留，ContractAmendment不可变记录保存前后快照与附件，现行contract_amount作为协议后的事实投影。`amendments/` GET 返回协议记录，仅销售可读角色可访问。失败回滚全部应收、协议、审计及ActionReceipt。
- `projects/{id}/forecast/` POST remaining_labor/remaining_expenses/expected_revision/reason，经理维护非负的预计剩余人工与费用。`cost-analysis/`额外返回forecast_revision/remaining_labor/remaining_expenses/forecast_total；未填为null，0为已估算零额。forecast_total=实际+在途+剩余人工+剩余费用，不含未下单材料，不能解释成已确定的完工利润，不生成成本/付款流水。
- 结算method为bank/cash/other或空，account账户标识和reference银行流水号最长100字符；document为同项目receipt附件，可选且在登记前上传，不能关联其他项目或合同附件。付款流水不可覆盖；项目收付款页提供流水列表和鉴权凭证下载。
- 新采购导入模板末列增加“明细交期”（空时使用订单交期），兼容旧8列；收付款模板追加结算方式、账户标识、银行流水号、凭证ID，兼容旧4列。BOM旧3列遇到同物料多单元时拒绝并提示使用新模板；4列可按物料+单元重复物料编码。
- 项目概览支持折叠并记忆，标签支持query.tab并按项目记忆；工作台带resource/focus定位单据。列表搜索及模块项目筛选在当前浏览器会话保留。直达接口仍执行角色和项目权限。

过滤字段以各 View 的 filterset_fields 为准。列表与动作都由后端执行角色和项目范围校验。采购价格仓管不可见，普通成员不可访问采购、库存、收付款或成本接口。

## 第二轮经营与操作完善（优先于上述旧字段说明）

- `forecast/` 增加 remaining_materials。完整预测=实际+在途+剩余材料+剩余人工+剩余费用；缺任一值返回null。旧客户端不提交材料时保持未完整估算，不能默认为零。材料必须排除已计入实际及在途部分，并覆盖预期领用共享库存和未下单需求。返回forecast_at/forecast_by/forecast_stale；项目、BOM、采购、材料流水、工时、费用变化或超过30天提示复核。
- 采购新建及草稿修改增加payment_due_date；批准生成应付使用该日期。兼容旧单据留空沿用原订单交期，页面明确提示。交期调整不改变应付期限。新采购模板10列，末列付款到期日，兼容8/9列；同组付款期限必须一致。next_delivery_date为未完成明细最早到货日期，工作台使用该日期。
- `payments/{id}/attach-evidence/` 财务POST document/reason，项目锁及ActionReceipt保护，关联同项目receipt附件。重复关联拒绝；同键回放一次。PaymentEvidence追加不可变关系，原Payment及凭证不覆盖，闭项后允许补纸面证据。列表evidence返回文件名及补录原因、人员时间；下载仍经原鉴权接口。
- `ship/` 增加可选materials[{item,quantity}]。多单元必须明确本批配套；同配置可留空按累计设备比例计算。服务端检查项目BOM、正数、不重复、累计数量不超过BOM及实际领料。最后一批必须覆盖剩余BOM。Delivery.material_requirements保存本批快照；退料保留已交付所需数量。旧批次无快照沿用历史比例，不补造历史事实。
- `bom-change-preview/` 经理POST与revise-bom相同数据，返回变更前后、差异、需处理数量、can_apply/blockers及原采购入口；调用原服务在事务内校验后回滚，不能持久化审计、编号或ActionReceipt。最终保存仍独立重新校验。
- `cost-sources/` 金额可见角色GET category=materials/labor/expenses/purchase_return_variance，分页读取原记录，按成本贡献降序。负数保留退回和冲销含义，不创建成本台账。
- 工作台接受各组名_page正整数参数，组内分页仍保留原权限与待办条件。直达详情提供当前角色可执行动作，普通列表保存保持页码，改变筛选或每页数回第一页。移动端主菜单使用抽屉，桌面保留侧栏。
- 采购处理历史追加不含价格的数量及后续处理说明；合同协议以中文前后差异、附件名称与鉴权下载呈现。报表风险数字可筛选，项目金额可进入原业务页追溯。
- 运维检查入口和企业脱敏订单验收清单见OPERATIONS_AND_PILOT.md；企业实际订单、告警接收渠道需由企业提供，不以模拟验收替代。
