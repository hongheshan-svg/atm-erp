# 现状域分析(11 限界上下文)

> 由架构工作流的并行域分析 agent 产出,作为 Go 重构的现状基线。

---

## 身份与访问(IAM/RBAC)边界上下文,横跨 backend/apps/accounts(用户/角色/部门 + 考勤,后者非 IAM 核心)与 backend/apps/core 的权限内核(permission_models_new.py / permission_service.py / permission_mixin.py / mixins.py / permissions.py + 两个 init 命令 + signals)

IAM/RBAC 上下文覆盖认证(JWT)、授权与数据范围,核心实体为 User/Role/Department/Permission(树)/RolePermission/DataScope。授权为"菜单级"RBAC:has_permission 带 Redis 缓存与父码通配,数据范围按角色×模块解析最宽 scope 并在 ViewSet 过滤;对象级支持 @owner/@assignee。主要痛点:新旧字段双轨(role FK/M2M、permissions JSON/M2M、data_scope JSON/DataScope 表)并存导致兼容代码遍布;operation/field 两层权限为预留死代码,字段脱敏实际不生效(过度设计);菜单码与 module:resource:action 三级码靠 MODULE_MENU_MAP 硬编码桥接,粒度退化为"有菜单即全 CRUD",易越权;数据范围依赖字段约定反射、特例补丁多;部门树递归查库、企业微信同步阻塞混入 ViewSet。复杂度 4/5,是 Go 重写应优先收敛为单一鉴权服务的边界。

**复杂度**: 4/5

**核心实体**: User(AbstractUser+SoftDelete,employee_id/department FK/role FK 旧 + roles M2M 新)、Role(data_scope 旧 JSON 字段 + permissions JSON 旧 + permissions_new M2M via RolePermission 新)、Department(自引用树,manager FK)、Permission(core_permission,树形,code/type menu|operation|field/resource/field_name)、RolePermission(角色×权限关联表,不继承 BaseModel)、DataScope(core_data_scope,role×module→scope_type + custom_departments M2M)、AttendanceConfig/AttendanceRecord/LeaveRequest/OvertimeRequest(考勤,边界内但非 IAM 核心)

**痛点**:
- 新旧双轨严重并存:User.role(FK)/roles(M2M)、Role.data_scope(JSON)+permissions(JSON 旧)+permissions_new(M2M)+DataScope 表,get_active_user_roles 每处都要 OR 兼容,数据一致性脆弱
- 三层权限模型(menu/operation/field)只有 menu 级真正生效;operation/field 为死代码脚手架(ops()/field_perm()/get_hidden_fields 恒空,审计 C2)——过度设计,字段脱敏全系统不生效但代码与注释大量保留
- 菜单码与 ViewSet 权限码语义错位:2 级菜单码 vs 3 级 module:resource:action,靠 MODULE_MENU_MAP 硬编码桥接 + _has_module_menu_access 兜底,授权粒度退化为'有菜单即可全 CRUD',与 init 出的细粒度码不符,易越权(审计 C1 注释即在防此)
- 数据范围语义高度耦合模型字段约定(created_by/department/user),apply_scope_filter 用 hasattr 反射判断,字段缺失静默 queryset.none();多处 skip_data_scope / data_scope_user_field 特例补丁(审计 H13/H14)
- get_department_tree_ids 递归逐层查库(无 CTE),部门深时 N 次查询,性能隐患
- 权限缓存仅 5min TTL + 信号失效,跨进程一致性依赖 Redis delete_pattern(仅 django_redis 支持),无显式版本号;登录响应重计算整棵菜单树
- 企业微信同步逻辑(requests 同步 + 多次 HTTP 循环)直接塞在 UserViewSet @action 里,阻塞请求、无重试,职责混入 IAM
- 授权判定分散在 permission_service + permission_mixin + permissions.py(IsSystemAdmin) + 各 ViewSet @action 内散落 has_permission 硬编码,无单一鉴权入口

---

## 平台内核 apps/core 是全部 15 个业务 App 依赖的共享基础层,聚合七大横切能力,并越界承载大量非内核功能(共16771行)

平台内核 apps/core 是全 15 个业务 App 的共享底座,提供七大横切能力:BaseModel(时间戳/软删除/审计字段+双管理器)、审计日志中间件、通用附件(字符串软外键)、站内信+钉钉/企微通知、编码规则引擎(行锁序列号+周期重置)、审批工作流引擎(定义/步骤/实例/任务四模型)、统一权限 PermissionMixin。依赖 PG 行锁、Redis、Celery、Channels、ES、requests。主要痛点:模块边界严重膨胀(16771 行,夹带仪表盘/移动端/打印/备份/升级等非内核功能);工作流引擎用巨型 if/elif 反向 import 并直改 30+ 业务模型状态,内核反依赖全部业务、违反开闭;审计靠 URL 猜模型、object_id 恒空、直存请求体;附件无 DB 外键;权限字段脱敏惰性失效、菜单兜底语义晦涩;CodeRule 运行时猴补丁。复杂度 4/5。</section_md>
</invoke>


**复杂度**: 4/5

**核心实体**: BaseModel、SoftDeleteManager、AuditLog、Attachment、SystemNotification、SystemConfig、CodeRule、CodeHistory、WorkflowDefinition、WorkflowStep、WorkflowInstance、WorkflowTask、UpgradeJob

**痛点**:
- 模块边界严重膨胀:core 塞入仪表盘/移动端/打印/导入导出/备份/升级等 40+ 文件 16771 行,远超内核职责
- 工作流引擎硬编码业务耦合:_on_workflow_complete 与 _get_project_manager 用巨型 if/elif 散弹 import 30+ 业务模型并直改 status,内核反向依赖所有业务 App,新增类型须改内核(循环依赖/违反开闭)
- 审计中间件过粗:URL 切片猜 model_name、object_id 恒空、changes 直存请求体(敏感/超大)、bare except 吞异常
- 附件字符串软外键无 DB 约束/级联,易产生孤儿数据无法 JOIN
- 权限字段脱敏惰性失效(从不种子化 field 权限);MODULE_MENU_MAP 菜单前缀兜底绕过操作级粒度,语义晦涩易越权
- CodeRule.generate_code 运行时猴补丁覆盖类方法,隐晦反模式
- 工作流回调跨模块副作用(改状态/生成应收/执行库存调整)与通知混在一个 try,bare except 静默失败
- 软删除散落:部分 admin_delete 直接 update(is_deleted=True) 不走 soft_delete(),时间戳/审计不一致
- SystemConfig 强制 pk=1 单例 hack;通知用 hasattr 探测字段弱契约

---

## 主数据(masterdata)边界上下文,Django ERP 系统核心基础数据层

主数据上下文管理物料/客户/供应商/仓库/库位五大基础实体,并扩展客户信用与 CRM 跟进。它是全系统被引用最广的上游边界(60+ 文件依赖),边界地位清晰。但实现耦合度高:视图层极度臃肿(views.py 1494 行,单 Item Excel 导入/导出占 700+ 行无 service 层)、models/serializers/views 在信用与跟进模块混写同文件、Item 模型 60+ 字段加双 JSONField 过度设计。存在边界倒置(信用模块反依赖 finance.AccountReceivable)、树形递归与 Python 内过滤的 N+1/性能隐患、信用调整非原子、中英文枚举映射重复硬编码。Go 重写时应抽出 service 层、按聚合根拆分文件、瘦身 Item 字段、用领域事件或查询接口解耦财务依赖。整体复杂度中等(3/5):领域逻辑不深,主要是 CRUD+导入导出+树+信用规则,重写工程量集中在 Excel 智能导入与跨上下文解耦。

**复杂度**: 3/5

**核心实体**: Item、ItemCategory、Customer、Supplier、Warehouse、WarehouseLocation、CreditLevel、CustomerCredit、CreditAdjustment、CustomerFollowUp、CustomerReminder、CustomerContact

**痛点**:
- 视图层臃肿:views.py 1494 行,Item 的 import_excel/export_excel/export_template 三个方法占 700+ 行,Excel 解析/列名模糊匹配/中文枚举映射/编码生成/查重全塞在视图内,无 service 层,严重违反单一职责且无法测试
- 模型与序列化器/视图混放:credit_management.py、customer_follow.py 把 models+serializers+viewsets 写在同一文件(各 500 行),与 models.py 的拆分不一致,边界混乱
- Item 模型字段爆炸(60+ 字段),混杂基础/技术/价格/库存/非标行业专用字段,且有 technical_params/extra_fields 两个 JSONField 做开放扩展——过度设计,多数字段实际使用率存疑
- 跨上下文反向耦合:CustomerCredit.update_used_amount 直接 import apps.finance.AccountReceivable 聚合计算,主数据反依赖财务,边界倒置
- N+1 与性能隐患:ItemCategory.tree、WarehouseLocationTreeSerializer 递归查询子节点;warning_list 在 Python 内遍历全部信用记录用属性过滤 usage_rate;get_descendants 递归无深度限制
- 信用额度调整无事务包裹(adjust_credit 先 save 后 create 调整记录,非原子);Customer/Supplier 导入用 all_objects 复活软删记录的复杂处理散落在视图
- 枚举/映射硬编码重复:单位/状态/物料类型的中英文映射在导入视图内重复定义,与模型 choices 不同步,DRY 缺失
- 信用/跟进/联系人功能注释自承认'可选、非标行业需求较少',疑似为通用模板堆砌的低价值模块

---

## Django ERP「销售与CRM」边界上下文,位于 backend/apps/sales,约 11000 行 Python,分散在 12 个功能文件 + models.py 聚合

销售与CRM上下文位于 backend/apps/sales,约 1.1 万行散落 12 个文件,覆盖报价→订单→发货→合同→线索→商机六大主流程,并堆叠了报价估算/预测/模板、售后服务+客户门户、客户培训、业绩提成、RFM、漏斗与赢丢单分析等 11+ 子域,边界严重膨胀。ViewSet 用 PermissionMixin+WorkflowEnforcementMixin+SoftDelete+UserTracking 四件套统一权限与动态审批;状态机以字符串 choices 在 @action 里手写迁移(发货单 11 态最脆),订单 Excel 导入导出单块约 600 行内联。跨 app 靠函数内延迟 import 强耦合 finance(应收/开票)、inventory(出库)、masterdata(信用)、core.workflow(审批),无契约层。外部依赖 PG/Redis/Celery/审批引擎。复杂度 5。Go 重写建议先拆 Quote-to-Cash、CRM、After-Sales 三上下文,抽离状态机与领域事件,明确审批与财务/库存的服务边界。

**复杂度**: 5/5

**核心实体**: SalesQuotation、SalesQuotationLine、SalesOrder、SalesOrderLine、DeliveryOrder、DeliveryOrderLine、SalesContract、Lead、LeadSource、Opportunity、OpportunityActivity、SalesForecast、QuoteVersion、QuoteCostItem、QuoteEstimation、SalesTarget、SalesCommission、CustomerRFMAnalysis、WinLossReason、OpportunityCloseRecord、ServiceContract、ServiceRequest、CustomerPortalAccount、TrainingPlan

**痛点**:
- 范围严重膨胀:一个 sales app 塞进报价/订单/发货/合同/CRM/售后/培训/RFM/估算/预测/漏斗 11+ 子域,11000 行/12 文件,边界上下文不清,DDD 角度应至少拆为 Quote-to-Cash、CRM、After-Sales 三个上下文
- 单 ViewSet 巨型化:views.py 1838 行,SalesOrderViewSet 的 Excel import/export 单块逻辑约 600 行内联在 @action 里(手写 customer_cache/project_cache/item_cache),应抽 service/任务
- 状态机散落:DRAFT/PENDING/CONFIRMED... 字符串硬编码 + ViewSet @action 手写迁移,无集中状态机定义,DeliveryOrder 11 态尤其脆弱,易非法跃迁
- 跨 app 强耦合但无契约:十余处函数内延迟 import finance/inventory/projects/masterdata,确认订单直接写应收/付款计划、发货直接建 StockMove,业务编排渗透进 ViewSet,Go 重写需提取清晰的领域服务/事件边界
- 审批与业务双路径:直接 confirm 与 WorkflowService 回写靠共用函数勉强对齐,workflow_business_type 隐式契约,迁移时审批引擎是关键依赖需先定义
- 金额/税额冗余存储(total_amount/tax_amount/total_with_tax 三列且 save 里重算 line_amount/weighted_amount),计算逻辑藏在 Model.save,易与序列化层口径漂移
- 疑似过度设计与重复:quote_prediction/quote_estimation/quote_templates 三套报价相关子系统、win_loss 与 funnel 分析、customer_training 等可能利用率低;migrations 下存在重复嵌套 migrations/migrations 目录(技术债)

---

## 采购边界上下文位于 backend/apps/purchase（约 12.8k 行 Python）

采购上下文是全仓最重模块之一(约12.8k行、约63模型、约50个DRF路由)，覆盖PR→RFQ→PO→收货→合同→委外核心链路，并外扩供应商评价/资质/预算/合同执行跟踪/供应商门户/供应链协同等重型子系统。技术上统一用Mixin(权限+审批+软删除+用户追踪)、CodeRule编号、Celery到货提醒、NotificationService推送。主要痛点：范围严重膨胀且多为低成熟功能；RFQ/委外/供应商门户各存在两套并行模型概念分裂；与projects.ProjectBOM经signals+views双处隐式强耦合做状态机，逻辑分散难测；领域逻辑散落在model.save/services/各service文件无统一服务层；还有重复嵌套migrations目录等工程问题。Go重写建议先收敛到PR/RFQ/PO/GR/委外核心子域，把协同/门户拆为独立上下文，并将BOM联动改为显式领域事件。复杂度5/5。

**复杂度**: 5/5

**核心实体**: PurchaseRequest / PurchaseRequestLine、PurchaseOrder / PurchaseOrderLine、GoodsReceipt / GoodsReceiptLine、PurchaseContract、RFQ / RFQLine / RFQSupplier / SupplierQuotation / SupplierQuotationLine、QuotationComparison / QuotationScore / ItemPriceHistory、OutsourceOrder / OutsourceMaterialIssue / OutsourceReceipt / OutsourceInspection / OutsourceClaim、SupplierEvaluation / SupplierGradeHistory / SupplierBlacklist / SupplierQualification、PurchaseBudget / BudgetLine、ContractExecution / DeliveryRecord / PaymentRecord、SupplierPortalUser / RFQCollaboration / DeliveryCollaboration / SupplierAccount

**痛点**:
- 范围过度膨胀: ~63 模型/~50 ViewSet 塞进单一 app，含供应商门户+供应链协同平台+协同询价等重型子系统，远超 PR/RFQ/PO/GR/委外核心边界，多为低成熟度功能
- 实体重复/概念分裂: RFQ 体系存在两套(rfq_models 的 RFQ/RFQLine/SupplierQuotation 与 supply_chain_collaboration 的 RFQCollaboration/RFQItem/RFQItemQuote/RFQSupplierResponse), 供应商门户两套(supplier_portal 与 supply_chain_collaboration), 委外两套(outsource_models 与 outsource_tracking)
- BOM 状态机通过 signals 隐式跨上下文写 projects.ProjectBOM, 同时 ViewSet.perform_create/destroy 又手写 BOM 回退逻辑, 状态推进逻辑分散在 signals+views 两处易不一致、难测试
- 业务逻辑散落: 金额/税额在 model.save 计算, 预算校验在 services, 比价在 comparison_service, RFQ 在 rfq_service, 缺统一领域服务层
- 目录结构问题: 存在重复嵌套的 migrations/migrations/ 目录(疑似误提交)
- views.py 单文件 1685 行, rfq_views 911 行, 偏胖; 预算 used 取 max(PR估算, 实际移库) 的近似口径埋下核算准确性隐患

---

## 库存与MRP边界上下文位于 backend/apps/inventory（约7000行/23个py文件）

库存与MRP上下文约7000行，是账实一致性的核心域。职责广：Stock(加权平均成本)+StockMove(唯一真相源)+调整盘点+批次FIFO+领退料+MRP缺料+预警+备件全周期+成本核算+数据对账，含27+模型。ViewSet统一用PermissionMixin三件套，外依赖Celery、barcode/qrcode、邮件与钉钉/企微通知，无ES/Redis直接耦合，预测纯启发式无ML。主要痛点：关键一致性逻辑塞在StockMove.save()多层嵌套事务里，历史账实Bug靠注释补丁修复，业务规则与ORM强耦合；文件组织混乱(各子域models/serializers/views混写)，migrations有异常嵌套目录；备件子域与数据校验模块明显过度设计、全表Python循环有性能隐患。Go重写应显式建模"库存移动指令+领域事件"，拆分备件/校验子域。复杂度4/5。

**复杂度**: 4/5

**核心实体**: Stock、StockMove、StockAdjustment、StockAdjustmentLine、Batch、InventoryLot、LotConsumption、BatchMove、MaterialRequisition、MaterialRequisitionLine、MaterialReturn、MaterialReturnLine、MRPPlan、MRPLine、StockAlertRule、StockAlert、SparePart、SparePartCategory、SparePartConsumption、SparePartForecast、SparePartLifecyclePrediction、PurchaseSuggestion、InventoryCostConfig、ItemCostRecord、PeriodCostSummary、DataValidationRule、ReconciliationSession

**痛点**:
- 核心一致性逻辑藏在 StockMove.save() 重写中，多层嵌套 transaction.atomic + select_for_update，业务规则与ORM持久化强耦合，单测困难且Go重写须显式建模为领域服务/事件
- ADJUSTMENT 方向判定、出库不足残留假COMPLETED记录等历史账实Bug均靠 save() 内注释补丁修复，反映状态机隐式、缺乏统一移动指令抽象
- Stock 既是聚合视图又可被超管软删除，账实敏感对象边界不清
- 文件组织混乱：material_/batch_/spare_parts 各自把 models+serializers+views 塞进同一文件，与顶层 models.py/serializers.py/views.py 风格不一致；migrations 存在异常嵌套 migrations/migrations/ 目录
- URL 路由大量别名（moves/stock-moves、adjustments/stock-adjustments）及手写路径需排在router前避坑，契约冗余
- 备件子域过度膨胀：8+模型、寿命预测、采购建议、成本分析，预测仅为启发式比例计算却独立成完整模块，对非标行业价值与维护成本不匹配（代码注释自承多类预警意义不大）
- 数据准确性/对账模块989行，校验器逐行Python循环遍历全表（check_stock_cost_mismatch 等）存在性能隐患
- MRP 与成本核算服务直接 import 跨表查询，缺料计算依赖 projects BOM 强耦合

---

## backend/apps/projects 是整个 ERP 的「项目与工程」核心域,但实际已严重膨胀为巨型聚合:55 个 Python 文件、约 31.7k 行代码、60+ 模型类、121 个路由注册、229 个 ViewSet/View 导入

backend/apps/projects 名为「项目/BOM/图纸/任务/设备」核心域,实已膨胀为 55 文件、约 31.7k 行、60+ 模型、121 路由的巨型 app,吞并现场服务、设备 OEE/IoT 远程监控、CAD/Creo 集成、ECN、知识库、Bug、安调验收、双套成本追踪等 8+ 子域。Project 为业务中枢,但内嵌 8 个直查 finance/inventory 的聚合方法,边界泄漏;ProjectBOM 达 68 字段、views.py 3706 行,属 God Model/胖 ViewSet。跨域强耦合(导入 7 个兄弟 app 40+ 处),且存在字节级重复文件(requirement.py≡requirements.py)与 cost/advanced_cost 两套并存。外部依赖 Celery、Elasticsearch、pandas/openpyxl、CAD/Creo。复杂度 5/5:Go 重写须先按子域拆分限界上下文,抽独立 service 层,用事件/接口解耦财务库存聚合,并裁剪超前的 IoT/CAD 重资产功能。

**复杂度**: 5/5

**核心实体**: Project、ProjectMember、ProjectTask、ProjectBOM、TimeLog、Drawing、DrawingChangeNotice、DrawingVersion、ECN/ECNItem/ECNApproval、Equipment/EquipmentShipment/EquipmentInstallation/EquipmentAcceptance、MaintenanceSchedule、Fixture/FixtureCalibration/FixtureMaintenance、AfterSalesOrder/ServiceRecord/SparePartUsage、Bug/BugComment/BugHistory、KnowledgeArticle/ProjectArchive/StandardComponent/TechnicalIssue、Milestone/ProjectAlert、Equipment OEE/Inspection/DataPoint/Alarm(远程监控)

**痛点**:
- 单 app 体积失控:55 文件/31.7k 行/60+ 模型/121 路由,边界含 8+ 实际子域(现场服务、IoT 监控、CAD 集成、知识库、Bug),违背单一职责,应拆为多个 Go 限界上下文
- God Model:ProjectBOM 达 68 字段、views.py 3706 行;Project 模型内嵌 get_actual_material_cost/labor/expense、get_total_receivables/payables、invoice/bank_summary 等 8 个方法,直接 import finance/inventory 模型 → 领域边界泄漏与循环依赖风险
- 跨域强耦合:从 purchase/finance/production/inventory/masterdata/sales/accounts 共 40+ 处导入;成本/AR/AP 聚合逻辑下沉到 projects,而非通过服务接口/事件解耦
- 明显重复:requirement.py 与 requirements.py 为字节级完全相同的副本(MD5 一致);成本追踪有 cost_tracking + advanced_cost_tracking 两套并存
- 过度设计/超前功能:remote_monitoring(IoT 数据点/预测维护)、creo_integration(52KB 单文件)、cad_integration、equipment_oee 等高级特性,相对核心 ERP 闭环属重资产、低复用,迁移时应评估是否保留或独立服务
- 贫血+胖 ViewSet 混合:逻辑散落于 56+ @action 与各 *.py 的 ViewSet,缺乏独立 service 层,业务规则与 HTTP 层耦合,Go 重写需先抽出领域服务

---

## production app (backend/apps/production) 是 ERP 的「生产/MES/APS」边界上下文，覆盖工序/计划/日志/调试/质检等基础生产流程，外加一整套 MES 性质的子系统：APS 高级排程、安灯(Andon)、电子看板、工艺路线、序列号追溯、3D装配指导、产能资源规划、设备能力矩阵/OEE、看板WIP限制、数据采集

production 应用承载「生产基础流程 + MES/APS」整个边界上下文：工序/计划/日志/调试/质检，加排程、安灯、看板、工艺路线、序列号追溯、产能规划、装配指导、数据采集等约 40 模型、28 ViewSet、110+ 端点。统一走 BaseModel 软删除与 PermissionMixin 三件套，库存通过延迟 import 调 inventory.StockMove 联动。主要问题：排程子系统三套并存(aps/scheduling/finite_capacity)语义重叠、WorkCenter 概念分裂；装配/追溯/数据采集等多为 CRUD 骨架，无 MQTT/Modbus/channels/redis 等实时采集与推送，名为 MES 实为同步轮询；看板与产能计算在 Python 循环里逐工作中心逐天 aggregate，N×M 次查询且无缓存；样板代码与内联序列化器重复；migrations 出现嵌套重复目录。重写时应优先收敛排程模型、引入真正的实时采集/推送通道、并重设计跨上下文库存联动契约。复杂度 4/5：领域广、子系统多、迭代叠加耦合重。

**复杂度**: 4/5

**核心实体**: ProductionProcess、ProductionPlan、ProductionPlanProcess、ProductionLog、DebugRecord、DebugCheckItem、QualityInspection、InspectionItem、ScheduleOrder(aps)、APSScheduleTask、WorkCenter、ProductionSchedule、ScheduleTask(scheduling)、FiniteCapacityPlan、ScheduledTask(finite_capacity)、WorkStation、RoutingTemplate、RoutingOperation、ProjectRouting、AndonType、AndonStation、AndonCall、AndonEscalation、AndonAction、SerialNumber、SNTraceRecord、ComponentBinding、SNRule、ResourceType、Resource、ResourceAllocation、CapacityResourceConflict、EquipmentCapability、KanbanWIPRule、KanbanWIPAlert、AssemblyGuide、AssemblyStep、AssemblySession、DataSource、DataPoint、DataRecord、DataAlarm

**痛点**:
- 排程子系统三套并存且语义重叠：aps.py(ScheduleOrder+自带WorkCenter)、scheduling.py(WorkCenter+ProductionSchedule+ScheduleTask)、finite_capacity.py(FiniteCapacityPlan+ScheduledTask)，WorkCenter 概念分裂、ScheduleTask/ScheduledTask 命名近似，职责边界模糊，疑似多次迭代叠加未收敛
- 过度设计/铺摊过广：3D装配指导、序列号追溯、设备能力矩阵、数据采集等模块停留在 CRUD 骨架，data_acquisition 无任何实际采集逻辑(无 MQTT/Modbus/OPC-UA)，andon 升级与看板告警无实时推送(纯同步 ORM 轮询)，属典型规划先行、实现单薄
- 看板/产能计算性能差：kanban.py、aps.get_capacity_view 在 Python 循环内对每个工作中心×每天逐次 aggregate 查询(N×M 次 DB 往返)，大屏高频拉取下放大；无缓存、无预聚合
- 样板代码重复：每个 ViewSet 重复 PermissionMixin+SoftDeleteMixin+UserTrackingMixin 三件套与 get_queryset 中 include_deleted 过滤逻辑(SoftDeleteMixin 已可覆盖)，多处重复
- 序列化器组织不一致：仅 8 个基础序列化器集中在 serializers.py，其余散落各子模块文件内联，模型/视图/序列化器同文件耦合，难以按契约统一管理
- APS 自动排程算法粗糙：前向贪心、默认每单位1工时、未真正按 best 可用工作中心选择(循环内 best_wc 逻辑有冗余赋值)，无有限产能/约束求解，与 finite_capacity 模块意图重复但实现割裂
- 迁移目录异常：migrations/ 下存在嵌套 migrations/migrations/ 重复迁移文件(0001/0002 各两份)，存在历史遗留风险
- 跨上下文事务耦合：post_completion_stock_moves 借用 inventory 的 ADJUSTMENT move_type + reference 字段 hack 实现生产入库(因无 IN_PRODUCTION 类型)，语义不清晰，重写时需先厘清库存移动契约

---

## finance bounded context backend apps finance about 11660 lines python largest most complex covers AR AP expenses payment collection schedules invoices shared expense allocation three reconciliation types bank statement import general ledger tax fixed assets budget DRF ModelViewSet plus Mixins logic inlined in viewset actions no service layer

财务是 ERP 最重限界上下文 约1.17万行 约40模型 30+ViewSet 80+自定义动作 覆盖应收应付费用收付款计划发票对账银行流水总账税务固定资产预算 技术为DRF胖ViewSet加Mixin 逻辑几乎全内联在action 缺service层与领域模型 views2292行 bank_statement_views1102行 reconciliation_views989行 痛点三套对账与收付款计划及应收应付镜像代码重复 accounting asset tax三层混写一文件 金融计算借贷平衡折旧并发核销多币种分散无集中校验精度与竞态风险高 与projects sales purchase强耦合 依赖Celery定时任务reportlab与Excel导入 Go重写建议抽账务领域服务统一对账抽象引入凭证余额聚合根接口隔离跨上下文调用 复杂度5

**复杂度**: 5/5

**核心实体**: AccountReceivable、AccountPayable、Payment、Expense、PaymentSchedule、PurchasePaymentSchedule、PaymentRequest、Invoice、SharedExpense、CollectionPlan、PurchaseReconciliation、SalesReconciliation、InvoiceReconciliation、BankStatement、ChartOfAccount、JournalVoucher、VoucherLine、AccountBalance、FiscalPeriod、TaxDeclaration、TaxInvoice、FixedAsset、AssetDepreciation

**痛点**:
- no service layer logic inlined in fat viewsets views py 2292 lines
- models py 1398 lines paymentschedule duplicated
- model serializer view mixed in single files
- three reconciliations and AR AP heavily duplicated
- nested migrations dir
- financial calc scattered decimal precision and concurrency risk
- tight cross app coupling to projects sales purchase

---

## backend/apps/oa 是「OA与协同」边界上下文,实为多个弱关联子域的聚合:车辆管理(vehicle.py)、固定资产/低值易耗品(asset.py)、档案管理(archive.py)、电子签章(electronic_signature.py)、考勤硬件集成(attendance_device.py + attendance_sync_service.py:ZKTECO 考勤机 TCP/云/推送三种模式)、企业微信考勤同步(wechat_work.py)

OA 上下文实为车辆、资产、档案、电子签章、考勤机集成、企业微信同步六个弱关联子域的拼盘,IM 已删除仅留别名残留,日程/公告/考勤记录靠 urls 反向引入 core/accounts。每个文件自带 model+双 serializer+ViewSet,asset/archive 的借用/调拨/维护高度同构但未抽象。审批双轨:仅车辆接动态工作流且有"异常即自动批准"兜底,余者硬编码状态翻转。考勤同步最复杂最脆(三连接模式+iclock 解析+映射表+mock 回退,云API verify=False),签章为模拟未接第三方。依赖 Celery 定时任务与 Redis 缓存 token,无 ES。复杂度中等(3),Go 重写宜按子域拆分,统一流转与审批抽象。

**复杂度**: 3/5

**核心实体**: Vehicle / VehicleRequest / VehicleMaintenance、Asset / OAAssetCategory / AssetBorrow / OAAssetTransfer / AssetMaintenance、Archive / ArchiveCategory / ArchiveBorrow / ArchiveTransfer / ArchiveDestruction、SignatureSeal / SignatureDocument / SignatureParticipant / SignatureLog、AttendanceDevice / DeviceUserMapping / DeviceAttendanceLog / DeviceSyncLog、WechatWorkConfig / WechatUserMapping / WechatCheckinRecord / WechatSyncLog

**痛点**:
- 边界不内聚:6 个弱关联子域 + IM 已删残留 + 反向 register core/accounts 资源,实为多上下文拼盘,不是单一限界上下文
- 结构重复:每个 .py 内 model+List/Detail 双 serializer+ViewSet 堆叠,borrow/transfer/maintenance 在 asset/archive 间高度同构,可抽公共流转抽象但未抽
- 审批逻辑双轨:仅 vehicle 接 WorkflowEnforcementMixin,其余 @action 硬编码状态翻转;vehicle.submit 还有'工作流异常即自动批准'的兜底,审批可被静默绕过
- 考勤集成最重最脆:三种连接模式 + iclock 文本协议解析 + 多套 punch/verify 映射表 + mock 回退混在同步路径;requests verify=False 有安全隐患
- 电子签章为半成品:sign 为模拟实现,第三方签章 TODO 未接入,file_hash 之外无真实加签/验签
- models.py 名存实亡(仅别名),模型散落各业务文件,migrations 下还有嵌套 migrations/migrations 冗余目录

---

## 「报表与BI」边界上下文 = backend/apps/reports + backend/apps/analytics

报表与BI上下文由 reports + analytics 两个 App 组成,是只读聚合/BFF 层,自身几乎不持业务数据,而横向聚合销售、采购、项目、库存、财务、生产等几乎所有域。职责覆盖项目利润核算、高管 KPI 仪表盘、现金流预测、库存周转/呆滞、AR/AP 账龄、工时报表、行业专用报表、可配置报表引擎、导出与预测告警。核心实体含 ReportTemplate/Execution、Prediction/RiskAlert、ExportTemplate 及多个 Service 类。外部依赖 PG、Redis 缓存、Celery、pandas/xlsxwriter,未用 ES。主要痛点:跨域重度耦合、口径(含税/状态/账龄)多处重复且漂移、成本计算三套并存、management_dashboard 巨型 action 与 N+1 聚合无缓存、动态 importlib 报表引擎缺字段白名单与数据范围权限(越权风险)、analytics 代码风格陈旧且端点重复。复杂度 4。

**复杂度**: 4/5

**核心实体**: ReportTemplate、ReportExecution、ReportFavorite、PredictionModel、PredictionResult、RiskAlert、ExportTemplate(及 ExportHistory/ScheduledExport)、CostCalculationService、DashboardKPIService、CashFlowForecastService、InventoryAnalyticsService、ReportQueryService、PredictionService

**痛点**:
- 重度跨域耦合:几乎每个 view/service 内 import 全部业务 App 模型并手写聚合,口径(状态集合/含税字段/账龄分桶)在 views、analytics、cost_service、industry_reports、management_dashboard 多处重复且不一致,极易漂移
- management_dashboard 单个 action 350+ 行、堆砌十余个独立聚合查询,无分层、无缓存,N 次全表聚合,性能与可维护性差
- 成本/利润计算逻辑三套并存:cost_service(pandas+缓存)、analytics.project_costs(行内逐项目循环聚合)、industry_reports,结果口径不统一(含税 vs 不含税)
- ProjectProfitabilityExportView / analytics.project_costs 对每个项目循环调用计算→N+1 查询,5000 行硬上限兜底
- report_builder 用 importlib 动态加载模型 + qs.values() 无字段白名单/权限脱敏,存在越权读取与注入面风险(过度设计的'通用报表引擎'但能力薄弱)
- 权限不一致:报表 ViewSet 用 PermissionMixin,但大量 function-based view 与 APIView 仅 IsAuthenticated,无数据范围(DataScope)过滤,任何登录用户可看全量财务数据
- analytics app 无 models/urls 规范(viewset 注册路径 analytics/analytics 重复)、风格陈旧(无类型、缩进/单双引号不统一)、slow_moving 与 slow_moving_items 重复别名端点
- 缓存策略薄弱:仅项目利润缓存,失效靠手动 refresh;仪表盘/账龄实时全表聚合无缓存
- 迁移目录异常:reports/migrations 下嵌套重复 migrations/ 子目录
