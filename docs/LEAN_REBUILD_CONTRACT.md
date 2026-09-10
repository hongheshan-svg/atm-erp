# 精简版接口契约

## 本轮经营管控补充（优先于旧描述）

- manager 的项目范围为负责或参与项目；admin/purchaser/warehouse/finance 兼岗按岗位保持全局作业范围。报表独立授权仍为只读，返回 `can_open` 标记可进入原项目的行。
- 项目和采购返回 `can_manage`；按具体动作的岗位集合判断范围，兼任财务或仓库不会将全局读取权扩展为经理的全局审批权。
- 普通采购批准允许 `reason`，创建人或最后提交人不能自批。管理员自批须原因并记 `self_approval`；预付款确认使用相同人员隔离约束。
- `POST /api/core/company/1/period-lock/`：`locked_through`（日期或null）、`expected_revision`、`reason`；仅管理员，幂等及版本校验，读接口返回截止日/版本。资金、工时、收货补录及旧款项变动执行期间检查，修改截止与进行中的写入互斥。
- `purchases/{id}/contract-preview/?version=current|N`：当前资料或历史归档，默认最新归档；返回 `snapshot_hash/archived_version/signed_document/versions`。`archive-contract/` POST `expected_snapshot/document/delivery_address/reason/confirmed=true`，仅采购权限、批准后可归档，附件须属于本采购合同，主体资料须完整，版本不可覆盖。
- `reconciliations/supplier-monthly/` GET `supplier/month` 返回期初、收退货、净付款、期末及快照哈希；POST 同参数加 `expected_snapshot/counterparty_balance/reason`，财务确认零差异并按原应付生成授权，返回 `reconciliations/requires_advance_review`。有预付负余额时记录核对但不自动抵扣或核准新增付款。Reconciliation 的 `settlement_month` 非空时余额口径为该月收退货净额减已付，核准额度同时受当前可结算额约束。
- `items/similar/?name=` 提供相似物料；同名/规格/品牌/单位/类别的独立编码须 `duplicate_reason`，记录审计；自定义编码保持原唯一约束。
- `purchases/{id}/warranty/` GET 原收货批次与事项历史；POST 新增 `receipt/date/quantity/description`，处理 `case/expected_updated_at/status/response/replacement?/returned?/expense?`。更换须真实同物料同供应商收货，退货关联原批次，费用须同项目费用且金额可读岗位才可关联。
- `reports/?view=cash30|aging|late_purchase|stale_stock&page=&page_size=` 为全公司固定只读关注明细，独立于项目筛选；沿用报表授权。冲突响应可带 `actions[{label,path}]` 指向原单。

功能与验收边界见 [OPERATIONAL_HARDENING.md](OPERATIONAL_HARDENING.md)。

根路径 `/api/business/`；需要 Bearer JWT。列表采用 `count/next/previous/results`，默认 20、最大 200 条，使用 `page` 和 `page_size`。业务写入为 JSON 对象；除基础资料 PATCH 外均为 POST。所有业务写入提供 `Idempotency-Key`，相同键和相同数据回放一次结果；数据改变必须换键，每次回放重新授权。

日期 YYYY-MM-DD；金额两位小数、数量三位小数的十进制字符串。错误：400 输入校验、403 无权限、404 不存在或不在范围、409 状态/并发冲突。界面展示服务端原因，不自行算账作为事实。

## 表格导入导出

- `{resource}/import-schema/` GET 与模板共用有序字段定义，返回 `columns[{key,label,table_keys,hint}]` 和业务说明，沿用对应导入权限。模板及预览统一中文列名、列序；引用列明确填写编码、账号或ID，并映射页面显示名称。状态、派生余额、自动编号不作为新增输入。
- 新模板保留旧版列头兼容，按匹配模板的字段映射读取，不按新位置解释旧文件。标准件/非标件、往来类型、任务阶段、采购账期和结算方式可填写页面中文值，兼容原英文值。预览 `rows` 始终按文件行展开，`row_count` 为文件明细数，`count` 为待创建记录数；采购按分组创建草稿而不折叠预览行。
- BOM 新模板列为物料编码、单元、需求数量、变更说明，支持CSV/XLSX下载，兼容原三列/四列模板；物料名称、规格及品牌在预览中只读关联，已领、在途、库存和缺料仍由业务计算。

- 业务列表 `{resource}/export/?file_format=csv|xlsx` 使用原列表全部筛选结果，忽略分页，最多20000行；沿用 queryset 项目范围及序列化金额过滤。采购按明细展开。附件列表仅导出元数据，附件内容仍走独立鉴权下载。设置不属于业务表格导入范围。
- `reports/?file_format=csv|xlsx` 导出全部筛选项目明细与合计，沿用管理员/总经理报表授权。金额为 CNY 含税经营口径；XLSX数值使用文本单元格保存，CSV保存原始十进制字符串，避免服务端转换损失精度。Excel读取CSV时应按文本导入编码/大金额列，以免软件自动转换前导零或长数字。危险公式前缀转义为文本。
- items/partners/sales/projects/purchases/tasks/stocks/moves/entries/payments/time/deliveries 提供 `import-template/` GET（file_format同上）、`import-file/` POST multipart单个file、`import-confirm/` POST JSON `{token}`。CSV为UTF-8，XLSX仅一个工作表，禁止公式，文件5MB/1000行上限，严格使用模板列。关联使用编码或账号，标注ID的列从列表导出获取。
- 预览返回 count/rows/errors/can_import/token/note，在事务内调用现有服务校验后回滚；错误按文件行号展示。确认凭据绑定用户/模块、30分钟有效，确认重新授权和校验，任一行失败则全部回滚。同一token的重试或并发确认使用同一ActionReceipt，返回同一结果；新文件应重新预览。
- 物料/往来单位与采购由采购权限新增；销售/项目/任务/交付由经理权限新增；期初仅管理员；领料由仓库权限；费用和收付款由财务权限；工时保留本人任务和项目范围。采购同一分组号合为一张草稿，组内单据信息必须一致。销售/采购不自动审批签约；应收应付由原合同采购产生；退款、冲销、盘点、更正仍从原记录操作。预览不产生持久业务记录、审计或编号计数变更。

## 平台接口

`GET /api/core/setup/` 仅管理员读取首次配置状态、现有公司和编号规则；`me` 返回管理员的 `setup_required`。仅首次 `init_system` 新建公司时标记待配置，旧安装迁移默认不要求重做。

`POST /api/core/setup/` 提供 Idempotency-Key，提交 display_name、old_password、new_password、company{name,address,phone}、team（可空，最多50位，复用用户字段）、codes（仅变更规则，id及原configure完整字段）、confirmed=true。公司、管理员密码、人员、规则在同一事务提交；同公司锁阻止重复初始化，完成后其他新请求409。密码只做校验及哈希存储，不进入审计/回执；旧JWT撤销，重新登录。向导不创建业务台账、示例库存或订单。

账号支持兼任多个固定角色：用户管理接受非空、无重复的 `roles` 数组，仅允许现有七种角色；`me`、人员目录和用户列表返回 `roles`。旧 `role` 字段兼容单角色请求，提交该字段且未提交 roles 时替换为单角色。已有账号保留原角色，新增兼岗字段默认为空，不变更历史审计或业务负责人。

授权按业务角色集合合并，不通过主角色推断。销售读权限可合并财务读权限，但没有 admin/manager 时只能修改本人销售单；销售兼成员沿用项目成员范围。菜单、金额过滤、附件下载及幂等重放均检查有效角色。总经理报表仍需具备 manager 并显式授权，admin 默认允许；最后启用管理员保护也检查兼岗角色。用户修改审计保留角色集合前后值。兼岗不改变原有按操作人身份执行的审批限制。

`/api/auth/login/` 接收 username/password，返回 access/refresh；`refresh/` 接收 refresh；`me/` 返回 id、username、display_name、role、roles、management_reports；`directory/` 返回启用人员 id/display_name/role/roles 数组。`password/` 接收 old_password/new_password，修改后令牌撤销，重新登录。

`/api/auth/users/` 管理员 GET/POST，`users/{id}/` GET/PATCH：username、display_name、roles（兼容旧 role）、hourly_cost、is_active、password、management_reports。新增必填密码，至少 12 位；不可移除最后管理员。management_reports 默认为 false，包含 manager 角色时允许设为 true；管理员自动可看经营报表。授权更正留审计，me 返回本人此开关，不接受用户自行更改。

登录及令牌刷新沿用 LoginThrottle：APP_ENVIRONMENT=production（默认）为10次/分钟，development关闭限流，其他值拒绝启动。Compose/安装器通过 LEAN_ENVIRONMENT 设置该值，默认 production；发布时不得沿用 development 配置。DEBUG 独立且默认关闭。

## 经营报表

`/api/business/reports/` GET，管理员或 management_reports=true 的 manager 可读，其余角色 403，每次请求核对当前授权。参数 search（项目名称/编号，最多150字符）、status（项目状态，留空全部）、risk（over_budget/overdue/unbudgeted，留空全部）、page（正整数）、page_size（1–200，接口默认20）。响应 summary/count/page/page_size/results/generated_at/filters；summary 汇总全部筛选结果，不仅当前页。前端统一默认每页10条，可选10/20/50/100并跨页面保存，调整大小回第一页。

全部为当前筛选项目的累计经营口径，包含已结项和已取消项目（可用状态筛选排除）；已签约合同额不作为会计收入。实际成本与项目页共用批量投影，在途承诺、累计采购预算校验复用预算服务。未设预算与零预算区分；交付逾期仅统计计划日期早于今天且执行中/交付中的项目，质保阶段不再算交付逾期。待收待付按原单金额减抵减、减净收付款求余额，逾期为期限早于今天；正向余额和负向退款分别汇总，取消项目退款仍显示。费用属于待付款，付款不重复计成本，冲销按原负向流水抵消。报表无写接口、无独立台账、无期间收入/完工利润推算。

## 公司与编号

`/api/core/company/` GET、`company/1/` 管理员 PATCH name/address/phone；`codes/`、`audit/` 管理员可读。`/api/health/` 返回 schema 版本。

`/api/core/codes/{id}/configure/` 管理员 POST，提供 Idempotency-Key，完整提交 prefix/date_format/padding/reset_cycle/reason/expected_revision。前缀为 1–10 位字母、数字、短横线或下划线；日期可为空或 YYYY/YYYYMM/YYYYMMDD；流水补零位数 1–10，超出位数自然增长；周期 never/year/month/day，日期必须覆盖重置周期。生成格式为前缀＋服务器本地日期＋流水；修改配置不回退现有序号，仅周期切换时从 1 起，已存在编码（含软删除）自动跳过。规则版本过期拒绝，修改原因及前后配置留审计；不允许编辑计数器、用途或历史业务编号。

## 销售

- 仅 sales_manager 角色时，只能查询、导出及操作 manager=当前用户的销售单。新增或导入只能分配给自己，转交由管理员/项目经理执行；动作及幂等回放重新检查当前角色集合和订单负责人。签约指定具备 admin/manager 角色的项目负责人，兼任该岗位时可以承担项目经理职责。兼岗权限按平台接口所述规则合并。
- `sales/{id}/progress/` GET 复用关联项目状态、交付批次和 receivable 应收的原金额/抵减/净回款/余额（负数表示待退款）。只读且沿用销售范围，不返回项目成本、应付、银行账号或附件内容。补充协议仍由管理员/项目经理处理。
- 仅具备销售维护权限时，可读取共享客户及双用途往来单位，只能新增/编辑/导入纯 customer；兼任采购维护岗位可维护供应商。人员目录返回 roles 供销售负责人和项目负责人分别筛选，不返回工时成本。

- `sales/` GET/POST：name/customer/manager/requirements/due_date/equipment_quantity/warranty_months。项目经理、管理员或销售经理创建；管理员、项目经理、财务及按本人范围的销售经理可读，其他角色禁止。
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

### 列表界面筛选补充（2026-09-10）

- 用户列表支持 `search`（账号、姓名）、`is_active` 和 `role`；角色匹配主岗位及兼任岗位，管理员选项包含超级管理员。仍仅管理员可读取和维护用户。
- 库存列表支持 `search`（物料编码、名称、规格、品牌），以及 `location`、`item__brand`、`item__part_type`。响应中的 `specification/brand/part_type/unit` 只读派生自物料，不重复维护，库存金额仍按岗位过滤。
- 款项列表支持 `search`（款项标题、项目名称和编号）和 `unsettled=true`。未结判断为原金额不等于冲减加净已结算；负余额待退款同样保留，不以大于零过滤退款。沿用原项目范围与金额权限。
- 列表查询、分页、导出复用已应用的同一组筛选参数；状态页签不改变单据状态。

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

## 销售与采购单据附件

- `POST /documents/` 继续使用 multipart、`category`、`file` 和幂等键；`project`、`sale`、`purchase` 三选一，不能同时关联多个目标。历史项目附件保留原关联；新销售/采购附件只维护单据归属。
- 未签约销售可上传。销售经理仅读写本人销售单附件，管理员/项目经理可维护，财务只读；采购附件由管理员/项目经理/采购员维护，财务只读。仓库、普通成员无销售/采购附件权限，分类为“其他”的文件同样受单据权限控制。
- 单据附件支持合同、其他（报价及技术资料），不混入项目结算凭证。取消单据及关闭项目不能新增附件；原文件保留，可继续按权限下载。每次上传追加记录，单文件上限 20 MB，文件路径不公开。
- `GET /documents/?sale=ID`、`?purchase=ID` 读取单据附件；`?project=ID` 按原关联汇总项目及其销售、采购附件，签约后自动可见，不复制文件。序列化的 `project` 为实际所属项目，`sale/purchase/source` 标明来源。列表、元数据导出和下载共用权限过滤。
- 补充协议可关联当前销售单上传的合同或原项目合同，不接受采购合同。财务凭证继续沿用原项目附件流程。

## 业务对账与银行核对

- `reconciliations/` 财务/管理员 POST `entry/kind/counterparty_balance/approved_amount/basis?/document?/reason`，kind 为 settlement/prepayment/refund；金额按两位小数字符串，退款对方余额为负数。生成 DZ 编号及原业务快照；GET 列表和详情仅金额可读角色，支持 `entry/entry__project/status/kind` 筛选及原导出入口。
- `reconciliations/{id}/confirm/` POST reason。普通对账/退款由财务或管理员确认，预付款由项目经理或管理员核准；原数据变化、差异非零、额度超过可结算金额时拒绝。采购普通结算额度=min(未结余额, 收货净值-原净付款)，不含隔离品；未收货部分必须填写合同依据并申请 prepayment。`void/` 财务 POST reason 作废剩余额度，历史不删除。
- `entries/{id}/pay/`、`refund/` 增加可选 reconciliation。采购付款和所有退款必须提供同款项的有效确认单；普通客户收款、费用支付不强制。核准额度可分次使用，原单、收退货或其他资金流水改变后重新对账；原操作同键回放仍重新授权，冲销不能恢复旧授权额度。历史付款保留，无需倒补虚构对账。收付款导入追加“对账单ID”第9列，兼容旧4/8列；采购付款缺有效对账仍拒绝导入，不能绕过服务。
- `bank-records/` 财务/管理员 POST `project?/amount/date/account/reference/counterparty/reason`；收入正、支出负，账户+银行流水号在有效记录中唯一。记录实际银行事实，不修改 Entry/Payment 或项目成本，可暂不指定项目。GET 支持 project、search，返回 remaining_amount、匹配及退回历史。`void/` POST reason 仅作废无有效关联的误录记录，保留历史后可重新录入正确事实。
- `bank-records/{id}/allocate/` POST `entry/amount/reason/reconciliation?`：仅实际收入，客户收款或供应商退款经原 finance.pay 生成 Payment 后建立银行匹配，事务失败全部回滚；供应商退款仍需有效退款对账。允许分次认领或跨项目拆分，已明确项目的记录不能认领到其他项目。
- `bank-records/{id}/match/` POST payment/reason：匹配已有未冲销、未匹配的银行方式付款，核对账户、方向、流水号（原记录有填写时）和可用金额。允许一条银行记录匹配多笔付款，不新增资金流水。`unmatch/` POST match/reason 追加撤销匹配，不冲销付款；已匹配付款须先解除银行关联后才能冲销，已结项相关项目须先重开。
- `bank-records/{id}/return-unclaimed/` POST returned/amount/reason：未认领收入关联真实银行退款支出，核对账户、对方户名、项目及双方未匹配金额，追加不可变关联，不生成虚构项目款项。`reverse-return/` POST offset/reason 追加撤销关联，保留原始银行事实。
- 银行列表仅财务/管理员访问，对账单沿用金额可读权限，附件仍走原鉴权下载；新表为快照、银行原始记录及其关联，既有应收、应付、费用、成本仍只有原业务事实。工作台按角色展示预付款核准、财务对账、银行待认领；已结项项目实际银行流水仍可登记，但相关核销纠错需重新打开。

## 采购账期与到期投影

采购单保存后通过 `GET /api/business/purchases/{id}/contract-preview/` 自动投影打印合同；仅 admin/manager/purchaser/finance 可读，warehouse/member/sales_manager 拒绝。合同沿用采购单编号，引用当前公司、供应商、物料、交期、账期和备注，金额由服务端按明细计算；草稿/未批准、已取消和取消余量明确标示，不伪造签署状态。前端采购操作“预览采购合同”打开 A4 页面，可打印或另存 PDF；签署文件上传原采购附件，预览不新增合同金额台账或公开下载地址。

合同正文采用单页 A4 紧凑排版，包含交付结算、质量验收、每批验收合格起一年质保、维修更换费用、违约赔偿、不可抗力、保密及争议处理条款。多项或长明细在正文汇总，完整附件独立预览和打印，保留全部物料及长备注，附件允许分页；双方按同编号确认正文和附件。打印件不带系统生成说明、更新时间或系统订单状态，保留草稿/取消提示及业务条款。模板条款不自动新增采购售后台账，也不改变付款或收货服务规则。

- Partner、PurchaseOrder 增加 payment_term（manual/cash/month30/month60/month90/month120/custom）及 payment_days；custom 为0～365自然日。供应商只提供新单默认值，采购创建时保存条款；草稿可改，提交后沿用原审批和退回流程，供应商改默认值不追改已有订单。
- 月结＝每批实际合格收货日期的当月月底＋天数，不按下单日期、不按整单最后收货日，也不自动顺延工作日。cash＝合格收货日；隔离品合格入库才起算。receive/quality-accept 接受 received_date（缺省今天，不得晚于今天），存入不可变 StockMove；历史缺省日期仅在投影中回退为流水本地创建日。
- 继续一单一应付，不新增可编辑应付分账。payment_schedule 从原收货金额、原批次退货 supplier_credit 和净 Payment 计算，退货冲原批次，净付款按先到期顺序抵扣。未收货部分没有自动到期日；API due_date 为最近未结到期日，due_amount 为今天及之前到期金额，报表逾期只计今天之前的未结分批金额。数据库原 Entry.due_date 仅作为旧手工期限事实保留。
- manual 沿用独立 payment_due_date（留空兼容原交期）；自动账期不能同时填写指定付款日期。采购账期和 bank/cash/other 支付方式独立；到期投影不跳过对账或预付款核准，也不把未来到期付款一律禁止。
- 采购模板12列（兼容8/9/10列），供应商模板7列（兼容5列），末尾追加采购账期和自定义月结天数；同一采购分组条款必须一致。列表、导出及对账快照保留条款，到期明细可在收付款页面查看。

## 模块页面布局

- 设置按用户管理、公司资料、编号规则、操作审计、我的账户分为独立页签；非管理员仅有我的账户。基础资料、库存、收付款中的原上下堆叠模块使用同一页签组件。
- 项目内任务/工时、BOM需求/明细、交付/售后、款项/流水分开显示；预算与预测、实际成本归入独立“成本与预算”入口，沿用原金额权限及业务投影。
- `query.section` 支持模块直达，合法选择按用户及页面保留在当前浏览器会话；无效或无权限的页签回到合法选择。工作台 `resource/focus` 仍可定位原单据，主动切换模块清除旧定位。
- 页签首次打开时加载，同组已打开模块保留列表状态；全局项目筛选仍作用于所属业务流水，共享库存不新增项目归属。

## ERP 版本检查与升级接口

- 左上角“版本与升级”仅管理员可见。`GET /api/core/upgrade/` 返回当前版本、执行器连接状态及最近升级任务；`?check=1` 检查固定官方仓库的最新正式版本，网络失败返回可重试的 check_error。
- `POST /api/core/upgrade/` 接受 target、confirmed=true 和幂等键；后端重新校验管理员、最新版本、执行器及对应平台安装包 SHA256，事务内拒绝重复活动任务和降级。
- `/api/core/upgrade/agent/` 仅接受独立宿主机令牌，用于领取和报告任务；令牌不能访问业务数据接口。执行器身份绑定任务，丢失响应或进程中断不得重复执行升级。
- 状态依次为 queued/downloading/backing_up/installing/verifying/succeeded，异常为 failed。先校验发布包，停机备份，再前向迁移及检查目标版本健康；保留任务、审计和宿主机日志。迁移后失败不自动降级数据库。
- Docker 和原生部署均由可选宿主机脚本执行，应用容器不挂 docker.sock；首次配置及恢复边界见 README 在线升级章节。
