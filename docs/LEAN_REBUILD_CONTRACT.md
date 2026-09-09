# 精简版接口契约

根路径 `/api/business/`；需要 Bearer JWT。列表采用 `count/next/previous/results`，默认 20、最大 200 条，使用 `page` 和 `page_size`。业务写入为 JSON 对象；除基础资料 PATCH 外均为 POST。所有业务写入提供 `Idempotency-Key`，相同键和相同数据回放一次结果；数据改变必须换键，每次回放重新授权。

日期 YYYY-MM-DD；金额两位小数、数量三位小数的十进制字符串。错误：400 输入校验、403 无权限、404 不存在或不在范围、409 状态/并发冲突。界面展示服务端原因，不自行算账作为事实。

## 平台

`/api/auth/login/` 接收 username/password，返回 access/refresh；`refresh/` 接收 refresh；`me/` 返回 id、username、display_name、role；`directory/` 返回启用人员 id/display_name 数组。`password/` 接收 old_password/new_password，修改后令牌撤销，重新登录。

`/api/auth/users/` 管理员 GET/POST，`users/{id}/` GET/PATCH：username、display_name、role、hourly_cost、is_active、password。新增必填密码，至少 12 位；不可移除最后管理员。

`/api/core/company/` GET、`company/1/` 管理员 PATCH name/address/phone；`codes/`、`audit/` 管理员只读。`/api/health/` 返回 schema 版本。

## 销售

- `sales/` GET/POST：name/customer/manager/requirements/due_date/equipment_quantity/warranty_months。经理或管理员创建；管理员、经理、财务可读，其他角色禁止。
- `sales/{id}/quote/` POST amount/reason；需求中或已报价可报价。
- `sales/{id}/edit/` POST reason、expected_updated_at 与待修改的销售基础字段；仅未签约单可改。expected_updated_at 必须等于打开表单时的版本，过时返回 409；无实际修改返回 400。修改后清除当前报价并回到需求状态，必须重新报价，原报价及修改前后内容保留在审计中。
- `sales/{id}/sign/` POST date、manager?、members?、milestones[{title,amount,due_date}]；节点合计必须等于最终报价。单事务创建执行项目和应收，返回 id（销售）与 project。重复请求只回放，其他键再次签约拒绝。历史迁移的未签约项目保留原人员及编号。
- `sales/{id}/cancel/` POST reason；仅未签约单可取消。已签约合同保持历史，执行中止由项目处理，收款纠错由收付款处理。
- 销售独立存储报价、合同金额和签约日期；项目的同名字段为只读投影。项目执行数据在交接后独立维护。

## 项目与基础资料

- `items/`、`partners/` GET/POST/PATCH。编号自动生成；物料 name/specification/unit/is_active，往来单位 name/kind(customer/supplier/both)/contact/phone/address/is_active。采购员、经理、管理员维护。
- `projects/` GET/POST：name/customer/manager/members/requirements/due_date/equipment_quantity/warranty_months。经理或管理员创建，普通成员只看所属项目。
- `edit/`：reason 和待修改项目字段；签约或已有交付后不能直接改客户、设备数量、质保约定，包括无销售合同的独立项目；移除成员不能遗留待办。
- `cancel/`、`reopen/`、`close/`：reason。取消需要处理采购、退料和应付，原合同历史保留；结项需要全部设备验收、任务及采购完成、余额为零。
- `cost/` GET：materials、labor、expenses、purchase_return_variance、total。仅管理员、经理、财务可看。

## BOM 与采购

- `projects/{id}/demand/` GET：revision、lines[{bom_line,item,item_code,item_name,quantity,issued,incoming,available,shortage}]。共享库存不预留。
- `revise-bom/`：必填 expected_revision、lines[{item,quantity,change_note}]。版本取自 demand 或导入预览，缺失/格式错误返回 400，过时返回 409；数量不小于已领与在途，已有行修改需说明；同一物料只有一条有效 BOM。
- `bom/{id}/remove/`：reason，只能移除未领未采购的行，保留软删除历史。
- `projects/bom-template/` CSV 模板；`projects/{id}/import-preview/` multipart 单个 file（CSV/XLSX，5MB、1000 行上限）。返回 expected_revision/lines/errors/can_import。确认时仅将 item/quantity/change_note 提交 revise-bom；禁止直接提交预览中的行号或展示字段。
- `purchases/` POST：project/supplier/due_date/note/lines[{item,bom_line?,quantity,unit_price}]/from_demand。按缺料采购必须关联 BOM 并在服务端重新检查缺口。
- `purchases/{id}/submit/`、`approve/`：空对象。采购员提交，经理批准，批准生成唯一应付。
- `receive/`：location/reason/lines[{line,quantity}]，line 是本单采购明细 id；仓管分批收货，累计金额保留分角差。
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
- `entries/{id}/pay/`、`refund/`：amount/date/reason，金额为正，由服务器检查余额和方向。
- `cancel-expense/`：reason；`payments/{id}/reverse/`：date/reason。通过冲减及冲销保留历史，不物理删除。
- `payments/` 与 `time/` 的 `reversed_by` 为关联冲销记录 id，未冲销为 null；与 `reversal_of` 一起供页面展示原记录、冲销记录及有效记录，后端仍独立校验重复操作。
- `documents/` multipart POST project/category/file（20MB 上限）。分类 drawing/contract/receipt/delivery/other；合同经理上传，凭据财务上传；敏感分类仅金额可见角色读取。
- `documents/{id}/download/`：鉴权下载，无公开 media 路由；返回附件流、private/no-store、nosniff。
- `workbench/` GET：tasks 与按角色可见 approvals/receipts/drafts/settlements，每组 count 和前 20 条 results；数量统计为全量，已取消项目的待退款仍保留。

过滤字段以各 View 的 filterset_fields 为准。列表与动作都由后端执行角色和项目范围校验。采购价格仓管不可见，普通成员不可访问采购、库存、收付款或成本接口。
